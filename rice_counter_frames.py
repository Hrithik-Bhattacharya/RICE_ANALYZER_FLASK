import cv2
import numpy as np
import json
import fcntl
import threading
import time

SHARED_FILE = "shared_counts.json"
counter_lock = threading.Lock()

def count_rice_grains(image):
    """
    Count rice grains in image.
    Returns count.
    """
    # Convert to HSV
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)

    # Expanded white range (captures dim rice too)
    lower_white = np.array([0, 0, 140])   # ↓ reduced from 180 → 140
    upper_white = np.array([180, 80, 255]) # ↑ saturation tolerance

    mask1 = cv2.inRange(hsv, lower_white, upper_white)

    #  Extra: detect slightly gray rice (very useful)
    lower_gray = np.array([0, 0, 100])
    upper_gray = np.array([180, 60, 200])

    mask2 = cv2.inRange(hsv, lower_gray, upper_gray)

    # Combine both
    mask = cv2.bitwise_or(mask1, mask2)

    # Morphology
    kernel = np.ones((3,3), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=2)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)

    contours, _ = cv2.findContours(
        mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
    )

    rice_count = 0

    for cnt in contours:
        area = cv2.contourArea(cnt)

        if 40 < area < 5500:
            rice_count += 1

    return rice_count

def update_shared_counts(new_count):
    """
    Update shared counts file with new total grains.
    Thread-safe with file locking.
    """
    with counter_lock:
        try:
            # Read current data
            with open(SHARED_FILE, 'r') as f:
                fcntl.flock(f.fileno(), fcntl.LOCK_SH)
                try:
                    data = json.load(f)
                finally:
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)

            # Update total
            data['total'] += new_count
            data['last_update'] = time.time()

            # Write back
            with open(SHARED_FILE, 'w') as f:
                fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                try:
                    json.dump(data, f)
                finally:
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)

        except (FileNotFoundError, json.JSONDecodeError):
            # Initialize if file doesn't exist
            data = {
                "total": new_count, "chalky": 0, "white": 0, "brown": 0,
                "black": 0, "broken": 0, "other": 0, "last_update": time.time()
            }
            with open(SHARED_FILE, 'w') as f:
                fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                try:
                    json.dump(data, f)
                finally:
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)

