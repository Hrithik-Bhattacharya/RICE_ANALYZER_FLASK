#!/usr/bin/env python
# coding: utf-8

# In[1]:


import cv2
import os

video_path = "original_video.mp4"
output_folder = "original_frames"
target_fps = 60

os.makedirs(output_folder, exist_ok=True)

cap = cv2.VideoCapture(video_path)
video_fps = cap.get(cv2.CAP_PROP_FPS)
frame_duration = 1 / video_fps
target_duration = 1 / target_fps

current_time = 0
next_capture_time = 0

frame_id = 0
saved_id = 0

while True:
    ret, frame = cap.read()
    if not ret:
        break

    if current_time >= next_capture_time:
        filename = f"{output_folder}/frame_{saved_id:05d}.jpg"
        cv2.imwrite(filename, frame)
        saved_id += 1
        next_capture_time += target_duration

    current_time += frame_duration
    frame_id += 1

cap.release()

print(f"Saved {saved_id} frames")


# In[ ]:




