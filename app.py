from flask import Flask, render_template, jsonify, Response
import cv2
import numpy as np
import time
import threading
import socket
import json
import portalocker as fcntl
import os
from collections import deque
from pathlib import Path
from extracting_frames import extract_rice_grains
from rice_counter_frames import count_rice_grains, update_shared_counts

import torch
import torch.nn as nn
from PIL import Image
from torchvision import models, transforms
from torchvision.models import EfficientNet_B0_Weights

app = Flask(__name__)

# ============================================
# CONFIGURATION
# ============================================
PI_IP = "192.168.50.1"
PI_HEALTH_PORT = 8001
PI_STREAM_PORT = 8000
HEALTH_CHECK_INTERVAL = 5  # seconds

SHARED_FILE = "shared_counts.json"

# Classifier config
MODEL_PATH = Path(__file__).parent / "rice_model.pth"
CLASSES = ["brown", "chalky", "white", "yellow"]   # must match training order
BROKEN_AREA_THRESHOLD = 300  # px² — synced with count_grains_updated.py

system_state = {
    'is_running': False,
    'start_time': None,
    'fps': 0,
    'frame_count': 0,
    'last_fps_time': time.time(),
    'health_status': {
        'online': False,
        'camera_started': False,
        'camera_configured': False,
        'last_check': 0,
        'latency_ms': None,
        'error': None
    }
}
state_lock = threading.Lock()
counter_lock = threading.Lock()


# Thread-safe queue storing (grain_image, area) tuples
grain_queue = deque()
queue_lock = threading.Lock()


# ============================================
# MODEL DEFINITION + TRANSFORMS
# ============================================

def build_model(num_classes: int) -> nn.Module:
    model = models.efficientnet_b0(weights=EfficientNet_B0_Weights.IMAGENET1K_V1)
    for p in model.parameters():
        p.requires_grad = False
    in_features = model.classifier[1].in_features
    model.classifier = nn.Sequential(
        nn.Dropout(0.3),
        nn.Linear(in_features, 512),
        nn.BatchNorm1d(512),
        nn.Dropout(0.3),
        nn.Linear(512, 256),
        nn.BatchNorm1d(256),
        nn.Dropout(0.3),
        nn.Linear(256, num_classes),
    )
    return model

val_transform = transforms.Compose([
    transforms.Resize((224, 224)),
    transforms.ToTensor(),
    transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
])


# AI Classification Worker
class AIClassifier:
    """Async worker that pulls (grain_image, area) from queue and classifies them."""

    def __init__(self):
        self._device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self._model = self._load_model()
        self._softmax = nn.Softmax(dim=1)
        self._running = True
        self._thread = threading.Thread(target=self._classify_loop, daemon=True)
        self._thread.start()
        print(f"[AI] Classifier ready on {self._device}  |  model: {MODEL_PATH}")

    def _load_model(self) -> nn.Module:
        model = build_model(len(CLASSES)).to(self._device)
        if MODEL_PATH.exists():
            model.load_state_dict(torch.load(str(MODEL_PATH), map_location=self._device))
            print(f"[AI] Loaded weights from {MODEL_PATH}")
        else:
            print(f"[AI] WARNING: {MODEL_PATH} not found — using random weights")
        model.eval()
        return model

    def _classify_loop(self):
        """Background loop: classify grains from queue."""
        while self._running:
            item = None
            with queue_lock:
                if grain_queue:
                    item = grain_queue.popleft()

            if item is not None:
                # Support both (image, area) tuples and plain images
                if isinstance(item, tuple):
                    grain_image, area = item
                else:
                    grain_image, area = item, -1
                rice_type = self._classify_grain(grain_image, area)
                self._update_type_count(rice_type)
            else:
                time.sleep(0.01)

    def _classify_grain(self, grain_image: np.ndarray, area: float = -1) -> str:
        """Classify a single grain crop using EfficientNet-B0.

        Area-based broken detection runs first (requires area from extraction stage).
        Falls back to model inference for whole-grain type classification.
        """
        if 0 < area < BROKEN_AREA_THRESHOLD:
            return 'broken'
        try:
            rgb = cv2.cvtColor(grain_image, cv2.COLOR_BGR2RGB)
            tensor = val_transform(Image.fromarray(rgb)).unsqueeze(0).to(self._device)
            with torch.no_grad():
                probs = self._softmax(self._model(tensor)).cpu().numpy()[0]
            return CLASSES[int(probs.argmax())]
        except Exception as e:
            print(f"[AI] Inference error: {e}")
            return 'other'

    def _update_type_count(self, rice_type):
        """Update specific type count in shared file."""
        with counter_lock:
            try:
                # Read current data
                with open(SHARED_FILE, 'r') as f:
                    fcntl.flock(f.fileno(), fcntl.LOCK_SH)
                    try:
                        data = json.load(f)
                    finally:
                        fcntl.flock(f.fileno(), fcntl.LOCK_UN)

                # Update type count
                if rice_type in data:
                    data[rice_type] += 1
                    data['last_update'] = time.time()

                # Write back
                with open(SHARED_FILE, 'w') as f:
                    fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                    try:
                        json.dump(data, f)
                    finally:
                        fcntl.flock(f.fileno(), fcntl.LOCK_UN)

            except (FileNotFoundError, json.JSONDecodeError):
                pass  # Ignore if file issues

    def stop(self):
        self._running = False

# Initialize AI classifier
ai_classifier = AIClassifier()

# ============================================
# SHARED FILE READER (with file locking)
# ============================================
class SharedCountsReader:
    """Reads grain counts from shared JSON file with proper locking.
    Other programs write to this file; we read it safely."""

    def __init__(self, filepath):
        self.filepath = filepath
        self._last_mtime = 0
        self._cache = {}

    def read(self):
        """Read shared counts file with advisory locking.
        Waits if another process is writing."""
        try:
            with open(self.filepath, 'r') as f:
                # Acquire shared (read) lock - waits if writer has exclusive lock
                fcntl.flock(f.fileno(), fcntl.LOCK_SH)
                try:
                    data = json.load(f)
                    self._cache = data
                    self._last_mtime = os.path.getmtime(self.filepath)
                    return data
                finally:
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)
        except (FileNotFoundError, json.JSONDecodeError, PermissionError) as e:
            # Return cached data or zeros if file not accessible
            return self._cache if self._cache else {
                "total": 0, "chalky": 0, "white": 0, "brown": 0,
                "yellow": 0, "broken": 0, "other": 0, "last_update": 0
            }

    def get_counts(self):
        """Get just the count values."""
        data = self.read()
        return {
            'total':  data.get('total',  0),
            'chalky': data.get('chalky', 0),
            'white':  data.get('white',  0),
            'brown':  data.get('brown',  0),
            'yellow': data.get('yellow', 0),
            'broken': data.get('broken', 0),
            'other':  data.get('other',  0),
        }

# Initialize shared reader
shared_reader = SharedCountsReader(SHARED_FILE)

# ============================================
# ASYNC HEALTH CHECKER (Background Thread)
# ============================================
class HealthChecker:
    """Checks Pi health every 5 seconds via TCP socket on port 8001."""

    def __init__(self, ip, port, interval=5):
        self.ip = ip
        self.port = port
        self.interval = interval
        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def _check_health(self):
        """Send STATUS command to Pi health server and parse response."""
        s = None
        start_time = time.time()

        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(3.0)
            s.connect((self.ip, self.port))
            s.sendall(b'STATUS\n')

            response = b''
            while b'\n' not in response:
                chunk = s.recv(1024)
                if not chunk:
                    break
                response += chunk

            latency = round((time.time() - start_time) * 1000, 1)
            data = json.loads(response.decode().strip())

            camera_status = data.get('camera', {})

            return {
                'online': True,
                'camera_started': camera_status.get('started', False),
                'camera_configured': camera_status.get('configured', False),
                'last_check': time.time(),
                'latency_ms': latency,
                'error': None
            }

        except socket.timeout:
            return {
                'online': False,
                'camera_started': False,
                'camera_configured': False,
                'last_check': time.time(),
                'latency_ms': None,
                'error': 'Connection timeout'
            }
        except (ConnectionRefusedError, OSError) as e:
            return {
                'online': False,
                'camera_started': False,
                'camera_configured': False,
                'last_check': time.time(),
                'latency_ms': None,
                'error': str(e)
            }
        except json.JSONDecodeError as e:
            return {
                'online': True,
                'camera_started': False,
                'camera_configured': False,
                'last_check': time.time(),
                'latency_ms': round((time.time() - start_time) * 1000, 1),
                'error': f'Invalid JSON: {e}'
            }
        finally:
            if s:
                try:
                    s.close()
                except:
                    pass

    def _run_loop(self):
        """Background loop: check health every interval seconds."""
        while self._running:
            result = self._check_health()
            with state_lock:
                system_state['health_status'] = result
            time.sleep(self.interval)

    def get_status(self):
        """Get current health status."""
        with state_lock:
            return dict(system_state['health_status'])

    def is_healthy(self):
        """Check if Pi is online AND camera is ready."""
        status = self.get_status()
        return status['online'] and status['camera_started'] and status['camera_configured']

    def stop(self):
        self._running = False

# Initialize health checker
health_checker = HealthChecker(PI_IP, PI_HEALTH_PORT, HEALTH_CHECK_INTERVAL)

# ============================================
# VIDEO STREAM FROM PI (via TCP)
# ============================================
class PiVideoStream:
    """Handles connection to Pi video stream on port 8000."""

    def __init__(self, ip, port):
        self.ip = ip
        self.port = port
        self.cap = None
        self._connected = False
        self._lock = threading.Lock()

    def connect(self):
        """Connect to Pi video stream."""
        with self._lock:
            if self._connected and self.cap and self.cap.isOpened():
                return True

            # Close existing if any
            if self.cap:
                self.cap.release()

            url = f"tcp://{self.ip}:{self.port}"
            self.cap = cv2.VideoCapture(url, cv2.CAP_FFMPEG)

            if self.cap.isOpened():
                self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                self._connected = True
                print(f"[VIDEO] Connected to {url}")
                return True
            else:
                self._connected = False
                print(f"[VIDEO] Failed to connect to {url}")
                return False

    def disconnect(self):
        """Disconnect from stream."""
        with self._lock:
            if self.cap:
                self.cap.release()
                self.cap = None
            self._connected = False
            print("[VIDEO] Disconnected")

    def read_frame(self):
        """Read a single frame."""
        with self._lock:
            if not self._connected or not self.cap:
                return None
            ret, frame = self.cap.read()
            if not ret:
                self._connected = False
                return None
            return frame

    def is_connected(self):
        with self._lock:
            return self._connected and self.cap and self.cap.isOpened()
video_stream = PiVideoStream(PI_IP, PI_STREAM_PORT)

def process_frame_for_rice(frame):
    """Process frame: extract grains, count, queue for AI classification."""
    grain_images = extract_rice_grains(frame)
    grain_count = len(grain_images)
    if grain_count > 0:
        update_shared_counts(grain_count)

    # Queue as (image, area) tuples; support plain images if extract_rice_grains
    # doesn't return areas (area=-1 disables broken detection)
    with queue_lock:
        for item in grain_images:
            grain_queue.append(item if isinstance(item, tuple) else (item, -1))

def generate_video_frames():
    """Generator that yields MJPEG frames from Pi stream."""
    frame_time = time.time()

    while True:
        # Auto-reconnect if disconnected but system is running
        if system_state['is_running'] and not video_stream.is_connected():
            if health_checker.is_healthy():
                video_stream.connect()
            else:
                # Return placeholder frame when Pi is not healthy
                placeholder = generate_placeholder_frame("Waiting for Pi...", 
                    subtext="Health check failed or camera not ready")
                ret, buffer = cv2.imencode('.jpg', placeholder, [cv2.IMWRITE_JPEG_QUALITY, 85])
                if ret:
                    yield (b'--frame\r\n'
                           b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')
                time.sleep(0.5)
                continue

        frame = video_stream.read_frame()

        if frame is not None:
            # Update FPS
            system_state['frame_count'] += 1
            current_time = time.time()
            if current_time - system_state['last_fps_time'] >= 1.0:
                system_state['fps'] = system_state['frame_count']
                system_state['frame_count'] = 0
                system_state['last_fps_time'] = current_time

            # Process frame for rice analysis if system is running
            if system_state['is_running']:
                process_frame_for_rice(frame)

            # Add overlay
            frame = add_overlay(frame)

            ret, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
            if ret:
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')
        else:
            # Connection lost - show placeholder
            placeholder = generate_placeholder_frame("Connection Lost",
                subtext="Attempting to reconnect...")
            ret, buffer = cv2.imencode('.jpg', placeholder, [cv2.IMWRITE_JPEG_QUALITY, 85])
            if ret:
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')
            time.sleep(0.5)

        # Target ~30 FPS for stream
        elapsed = time.time() - frame_time
        if elapsed < 1/30:
            time.sleep(1/30 - elapsed)
        frame_time = time.time()

def generate_placeholder_frame(main_text, subtext=""):
    """Generate a placeholder frame when stream is unavailable."""
    frame = np.zeros((480, 640, 3), dtype=np.uint8)

    # Gradient background
    for i in range(480):
        frame[i, :] = [40 + i//8, 45 + i//9, 55 + i//10]

    # Main text
    cv2.putText(frame, main_text, (60, 220),
                cv2.FONT_HERSHEY_SIMPLEX, 1.2, (255, 255, 255), 2)

    if subtext:
        cv2.putText(frame, subtext, (80, 270),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (180, 180, 200), 1)

    # Health status
    health = health_checker.get_status()
    status_text = f"Pi: {'Online' if health['online'] else 'Offline'}"
    cv2.putText(frame, status_text, (60, 320),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 200, 0) if health['online'] else (0, 0, 200), 2)

    if health['latency_ms']:
        cv2.putText(frame, f"Latency: {health['latency_ms']}ms", (60, 360),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (180, 180, 200), 1)

    return frame

def add_overlay(frame):
    """Add info overlay to frame."""
    h, w = frame.shape[:2]

    # Semi-transparent header bar
    overlay = frame.copy()
    cv2.rectangle(overlay, (0, 0), (w, 50), (0, 0, 0), -1)
    cv2.addWeighted(overlay, 0.5, frame, 0.5, 0, frame)

    # Title
    cv2.putText(frame, "Rice Grain Analyzer", (15, 35),
                cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 255), 2)

    # FPS
    cv2.putText(frame, f"FPS: {system_state['fps']}", (w - 120, 35),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

    # Status
    status = "LIVE" if system_state['is_running'] else "STANDBY"
    color = (0, 255, 0) if system_state['is_running'] else (0, 165, 255)
    cv2.putText(frame, status, (w//2 - 40, 35),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)

    # Grain count from shared file
    counts = shared_reader.get_counts()
    cv2.putText(frame, f"Total Grains: {counts['total']}", (15, h - 20),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

    return frame

# ============================================
# FLASK ROUTES
# ============================================

@app.route('/')
def index():
    """Render the main dashboard page."""
    return render_template('index.html')

@app.route('/api/start', methods=['POST'])
def start_system():
    """Start the rice flow and analysis."""
    if not system_state['is_running']:
        # Only start if Pi is healthy
        if not health_checker.is_healthy():
            return jsonify({
                'success': False,
                'status': 'error',
                'message': 'Pi is not healthy. Camera not ready or unreachable.'
            }), 503

        system_state['is_running'] = True
        system_state['start_time'] = time.time()
        system_state['frame_count'] = 0
        system_state['last_fps_time'] = time.time()

        # Connect to video stream
        video_stream.connect()

    return jsonify({'success': True, 'status': 'started'})

@app.route('/api/stop', methods=['POST'])
def stop_system():
    """Stop the rice flow and analysis."""
    system_state['is_running'] = False
    system_state['start_time'] = None
    video_stream.disconnect()
    ai_classifier.stop()
    return jsonify({'success': True, 'status': 'stopped'})

@app.route('/api/shutdown', methods=['POST'])
def shutdown_system():
    """Shutdown the Raspberry Pi."""
    system_state['is_running'] = False
    video_stream.disconnect()
    ai_classifier.stop()
    return jsonify({'success': True, 'status': 'shutdown_initiated'})

@app.route('/api/counters')
def get_counters():
    """Get current counter values from shared file + system state."""
    counts = shared_reader.get_counts()

    with state_lock:
        data = {
            'counters': counts,
            'is_running': system_state['is_running'],
            'fps': system_state['fps'],
            'uptime': get_uptime(),
            'health': health_checker.get_status()
        }
    return jsonify(data)

@app.route('/api/health')
def get_health():
    """Get real-time health status of Pi."""
    return jsonify({
        'health': health_checker.get_status(),
        'is_healthy': health_checker.is_healthy(),
        'timestamp': time.time()
    })

@app.route('/api/connection')
def get_connection_status():
    """Get connection status of video stream."""
    return jsonify({
        'video_connected': video_stream.is_connected(),
        'pi_healthy': health_checker.is_healthy(),
        'health': health_checker.get_status(),
        'timestamp': time.time()
    })

@app.route('/api/reset', methods=['POST'])
def reset_counters():
    """Reset shared counts file to zero."""
    try:
        data = {
            "total": 0, "chalky": 0, "white": 0, "brown": 0,
            "yellow": 0, "broken": 0, "other": 0, "last_update": time.time()
        }
        with open(SHARED_FILE, 'w') as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            try:
                json.dump(data, f)
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
        return jsonify({'success': True, 'status': 'reset'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/video_feed')
def video_feed():
    """Video streaming route from Pi."""
    return Response(generate_video_frames(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

def get_uptime():
    """Calculate session uptime in HH:MM:SS format."""
    if system_state['start_time'] is None:
        return "00:00:00"
    elapsed = int(time.time() - system_state['start_time'])
    hours = elapsed // 3600
    minutes = (elapsed % 3600) // 60
    seconds = elapsed % 60
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

@app.template_filter('format_number')
def format_number(value):
    return f"{value:,}"

if __name__ == '__main__':
    print(f"[INIT] Flask server starting...")
    print(f"[INIT] Pi IP: {PI_IP}")
    print(f"[INIT] Health check port: {PI_HEALTH_PORT}")
    print(f"[INIT] Stream port: {PI_STREAM_PORT}")
    print(f"[INIT] Shared file: {SHARED_FILE}")
    app.run(host='0.0.0.0', port=5000, debug=True, threaded=True)