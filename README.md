# 🌾 Rice Grain Analyzer - Flask Application

Real-Time Rice Grain Detection, Counting & Classification System with Claymorphism UI.

## 📁 Project Structure

```
rice_analyzer_flask/
├── app.py                  # Flask backend + video streaming + grain detection
├── requirements.txt        # Python dependencies
├── README.md              # This file
│
├── templates/
│   └── index.html         # Main dashboard (Jinja2 template)
│
└── static/
    ├── css/
    │   └── style.css      # Claymorphism UI styles
    ├── js/
    │   └── main.js        # Frontend logic + real-time polling
    └── images/
        └── (placeholder for any images)
```

## 🚀 Setup & Installation

### 1. Install Dependencies

```bash
cd rice_analyzer_flask
pip install -r requirements.txt
```

### 2. Run the Flask App

```bash
python app.py
```

The app will start on `http://0.0.0.0:5000` (accessible from any device on your network).

### 3. Access the Dashboard

Open your browser and go to:
- **Local:** `http://localhost:5000`
- **Network:** `http://<your-pi-ip>:5000` (e.g., `http://192.168.1.50:5000`)

## 🎮 How to Use

| Button | Action |
|--------|--------|
| **🟢 Start Rice Flow** | Begins video streaming and grain detection/classification |
| **🔴 Stop Rice Flow** | Pauses the analysis and counter updates |
| **⚫ Shutdown Pi** | Sends shutdown command to Raspberry Pi |

## ⚡ Real-Time Counter Updates

The frontend polls the backend **every 100ms** via `/api/counters` endpoint to get instant updates:
- Total grain count
- Individual classification counts (Chalky, White, Brown, Black, Broken, Others)
- Live FPS from video stream
- Session uptime

## 🔌 API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Main dashboard page |
| `/video_feed` | GET | MJPEG video stream (use as `<img src="/video_feed">`) |
| `/api/start` | POST | Start rice flow & analysis |
| `/api/stop` | POST | Stop rice flow & analysis |
| `/api/shutdown` | POST | Shutdown Raspberry Pi |
| `/api/counters` | GET | Get current counter values + FPS + uptime |
| `/api/reset` | POST | Reset all counters to zero |

## 🛠️ Connecting Real Pi Camera

Replace the `generate_dummy_frame()` function in `app.py` with actual Pi Camera code:

```python
from picamera2 import Picamera2

picam2 = Picamera2()
picam2.configure(picam2.create_preview_configuration(main={"format": 'RGB888', "size": (640, 480)}))
picam2.start()

def generate_frame():
    frame = picam2.capture_array()
    # Run your ML model here
    # Update counters based on detections
    ret, buffer = cv2.imencode('.jpg', frame)
    return buffer.tobytes()
```

## ⌨️ Keyboard Shortcuts

- **SPACE** — Toggle Start/Stop
- **ESC** — Stop system

## 📝 Notes

- The app uses **threaded=True** for handling concurrent video streaming and API requests
- Background grain detection runs in a separate thread
- Video stream uses MJPEG format for browser compatibility
- All static files are served via Flask's `url_for('static', filename=...)`
