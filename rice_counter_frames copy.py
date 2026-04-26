#!/usr/bin/env python
# coding: utf-8

# In[1]:


import cv2
import numpy as np
import os


# In[2]:


def count_rice_grains(image):
    output = image.copy()

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
            x, y, w, h = cv2.boundingRect(cnt)
            cv2.rectangle(output, (x,y), (x+w, y+h), (0,255,0), 2)

    return rice_count, output, mask


# In[3]:


def process_and_save(folder_path, output_folder):
    total_count = 0

    # Create output folders
    detected_folder = os.path.join(output_folder, "detected")
    mask_folder = os.path.join(output_folder, "mask")

    os.makedirs(detected_folder, exist_ok=True)
    os.makedirs(mask_folder, exist_ok=True)

    image_files = sorted([
        f for f in os.listdir(folder_path)
        if f.endswith(('.png', '.jpg', '.jpeg'))
    ])

    for img_name in image_files:
        img_path = os.path.join(folder_path, img_name)

        image = cv2.imread(img_path)
        if image is None:
            continue

        count, output, mask = count_rice_grains(image)
        total_count += count

        print(f"{img_name}: {count} grains")

        # Save detected image
        detected_path = os.path.join(detected_folder, img_name)
        cv2.imwrite(detected_path, output)

        # Save mask image
        mask_path = os.path.join(mask_folder, img_name)
        cv2.imwrite(mask_path, mask)

    print("\nTotal rice grains from all images:", total_count)

    return total_count


# In[4]:


input_folder = "original_frames"
output_folder = "original_output_frames"

total = process_and_save(input_folder, output_folder)


# In[ ]:




