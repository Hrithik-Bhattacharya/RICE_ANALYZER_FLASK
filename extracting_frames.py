import cv2
import numpy as np

def extract_rice_grains(image):
    """
    Extract individual rice grains from image as 128x128 resized crops.
    Returns list of grain images (no file storage).
    """
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)

    lower_white = np.array([0, 0, 140])
    upper_white = np.array([180, 80, 255])

    mask = cv2.inRange(hsv, lower_white, upper_white)

    kernel = np.ones((3,3), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=1)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=1)

    contours, _ = cv2.findContours(
        mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
    )

    grain_images = []

    for cnt in contours:
        area = cv2.contourArea(cnt)

        if 15 < area < 2500:
            x, y, w, h = cv2.boundingRect(cnt)

            # Add padding
            pad = 5
            x1 = max(x - pad, 0)
            y1 = max(y - pad, 0)
            x2 = min(x + w + pad, image.shape[1])
            y2 = min(y + h + pad, image.shape[0])

            crop = image[y1:y2, x1:x2]

            # Resize to 128x128
            resized = cv2.resize(crop, (128, 128))

            grain_images.append((resized, area))

    return grain_images