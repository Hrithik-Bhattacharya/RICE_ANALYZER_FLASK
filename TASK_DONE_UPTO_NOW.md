---

# Rice Processing Pipeline: In-Memory Implementation

## Project Overview
This project implements a real-time rice classification and counting pipeline using Python Flask. The system processes incoming video, performs grain counting, and runs AI classification asynchronously using a thread-safe queue.

## Architectural Constraints
* **Dimensions:** All frames must be resized to exactly $128 \times 128$ pixels.
* **Memory Management:** **Zero Disk I/O** for intermediate frames. All frame transfers between `extracting_frames.py`, `image_each_grain.py`, and `rice_counter_frames.py` must happen via dynamic memory (NumPy arrays/BytesIO) and Thread-Safe Queues.
* **UI/Logging:** No modifications to the frontend or additional logging beyond standard error handling.

## Core Components & Logic Flow

### 1. In-Memory Ingestion (`extracting_frames.py`)
* **Action:** Captures video feed and resizes frames to $128 \times 128$.
* **Modification:** Removed all `os.mkdir`, `cv2.imwrite`, or directory-based storage logic.
* **Output:** Passes the raw frame data directly to the counter modules and the AI queue.

### 2. Counting Module (`image_each_grain.py` & `rice_counter_frames.py`)
* **Action:** Processes the $128 \times 128$ frame to detect and count individual grains.
* **Modification:** Core detection logic remains identical, but input/output paths are redirected to handle in-memory objects instead of reading from a local `/frames` folder.
* **Result:** Updates the "Total Count" attribute in `shared_output.json`.

### 3. AI Classification Queue
* **Worker:** A background thread monitors a `queue.Queue` object.
* **Inference:** Pulls the $128 \times 128$ frame from the queue.
* **Placeholder:** Includes a standardized placeholder for model inference: 
    `print(f"AI Model: Classifying frame from memory...")`
* **Result:** Updates the "Type" attributes in `shared_output.json`.

### 4. State Synchronization (`shared_output.json`)
* **Atomic Writes:** To prevent collisions between the AI thread, the counter logic, and the Flask frontend, all writes to `shared_output.json` use atomic replacement.
* **Process:** Write to a temporary string/file and use `os.replace()` to ensure the frontend always reads a valid JSON object.

---

## Technical Stack
| Component | Technology |
| :--- | :--- |
| **Backend** | Python Flask |
| **Data Format** | JSON (`shared_output.json`) |
| **Concurrency** | `threading.Thread`, `queue.Queue` |
| **Image Processing** | OpenCV / NumPy (In-memory) |

---

## Execution Instructions
1.  Run `app.py` to initialize the Flask server and the background AI worker thread.
2.  The system will begin listening for the video stream.
3.  Monitor the console for the AI placeholder signals.
4.  The frontend will poll `shared_output.json` every 1000ms for real-time updates.
