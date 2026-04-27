# Pi Analyzer

A two-part rice analysis system:

- **Worker (Python + OpenCV):** Monitors Raspberry Pi reachability, opens a TCP video stream, optionally runs frame processing, and updates counters in `data.json`.
- **Frontend (Next.js):** Dashboard to start/stop camera flow, reset/save counters, and view live category totals.

## Repository Layout

```text
pi_analyzer/
├── cam.json                    # Runtime flags (camera/process control)
├── data.json                   # Live counter output
├── logs/                       # Saved counter snapshots
├── worker/                     # Python worker service
│   ├── main.py                 # Worker loop entrypoint
│   ├── processor.py            # Processing logic (edit this for processing changes)
│   ├── network.py              # Pi ping utility
│   ├── stream.py               # Stream connect/cleanup helpers
│   ├── utils.py                # Config file reader helpers
│   ├── constants.py            # Paths/network/constants
│   └── pyproject.toml          # Python dependencies for uv
└── rice_interface/             # Next.js frontend + API routes
    └── src/app/api/
        ├── ping/route.ts
        ├── camera/route.ts
        └── data/route.ts
```

## Prerequisites

- Linux environment (current project behavior and ping flags are Linux-oriented)
- Python 3.11+
- [uv](https://docs.astral.sh/uv/) installed
- Node.js 20+ and npm
- Raspberry Pi reachable at `192.168.50.1` (default in `worker/constants.py`)

## Quick Start

Run worker and frontend in separate terminals.

### 1) Worker

From project root:

```bash
cd worker
uv venv
uv sync
uv run main.py
```

Notes:

- `uv venv` creates a virtual environment in `worker/.venv`.
- `uv sync` installs dependencies from `worker/pyproject.toml`.
- `uv run main.py` starts the worker loop.
- Processing customization should be done in `worker/processor.py` (the `process(frame)` function).

### 2) Frontend

From project root:

```bash
cd rice_interface
npm i
npm run dev
```

Then open `http://localhost:3000`.

## Runtime Files and Flags

### `cam.json`

```json
{
  "CAMERA_RUN": false,
  "PROCESS": true
}
```

- `CAMERA_RUN`
  - `true`: worker tries to connect/read stream.
  - `false`: worker stays idle and disconnects stream if open.
- `PROCESS`
  - `true`: call `process(frame)` for every frame.
  - `false`: stream displays only; no counter updates.

### `data.json`

Stores running totals:

```json
{
  "count": 0,
  "white": 0,
  "chalky": 0,
  "broken": 0,
  "brown": 0,
  "black": 0,
  "others": 0
}
```

## Worker Documentation

### `worker/main.py`

Main loop responsibilities:

1. Read `CAMERA_RUN` and `PROCESS` from `cam.json` every `CHECK_INTERVAL`.
2. If camera is disabled, ensure stream/window are closed and wait.
3. Ping Pi (`network.ping_pi`) before trying stream connection.
4. Connect stream via `stream.connect_stream()` when Pi is reachable.
5. Read frames from OpenCV capture.
6. If `PROCESS` is true, run `processor.process(frame)`.
7. Display stream window and handle ESC/window-close shutdown.
8. Always cleanup stream and windows on exit.

It also computes instantaneous and average FPS internally.

### `worker/processor.py`

Holds the processing implementation used by `main.py`.

- Entry function: `process(frame)`
- Current behavior:
  - Loads `data.json`.
  - Increments `count`.
  - Randomly selects one category from constants.
  - Increments that category.
  - Saves updated `data.json`.

If you want to change analysis logic, **edit this file**. This is the file referenced for processing updates.

### `worker/constants.py`

Defines:

- Network: `PI_IP`, `PORT`, `URL`
- Timing: `EXPECTED_FPS`, `CHECK_INTERVAL`
- Paths: `CONFIG_FILE` (`../cam.json`), `DATA_FILE` (`../data.json`)
- Category labels for counters

### `worker/network.py`

- Function `ping_pi(ip, timeout_sec=1)`
- Uses system `ping -c 1 -W <timeout>`
- Returns boolean reachability

### `worker/stream.py`

- `connect_stream()`
  - Opens `cv2.VideoCapture(URL, cv2.CAP_FFMPEG)`
  - Sets `CAP_PROP_BUFFERSIZE` to 1
- `cleanup_stream(cap, window_created)`
  - Releases capture
  - Destroys OpenCV windows

### `worker/utils.py`

- `read_config_flag(path, key)`
  - Loads JSON and returns boolean value for key
  - Fails safely (`False`) for missing/invalid files

## Frontend and API Documentation

The dashboard (`rice_interface/src/app/page.tsx`) uses three API routes.

### `GET /api/ping`

Checks Raspberry Pi connectivity using shell ping.

- Implementation: `rice_interface/src/app/api/ping/route.ts`
- Behavior:
  - Executes `ping -c 1 -W 1 192.168.50.1`
  - Returns HTTP 200 for both pass/fail, with boolean payload

Success response:

```json
{ "connected": true }
```

Failure response:

```json
{ "connected": false }
```

### `GET /api/camera`

Reads camera run state from `cam.json`.

- Implementation: `rice_interface/src/app/api/camera/route.ts`
- Response:

```json
{ "cameraRun": true }
```

Error:

```json
{ "error": "Failed to read camera state" }
```

### `POST /api/camera`

Updates `CAMERA_RUN` in `cam.json`.

Request body:

```json
{ "cameraRun": true }
```

Success response:

```json
{ "ok": true, "cameraRun": true }
```

Validation error (`cameraRun` missing/not boolean):

```json
{ "error": "cameraRun must be a boolean" }
```

Server error:

```json
{ "error": "Failed to update camera state" }
```

### `GET /api/data`

Returns current counters from `data.json`.

- Implementation: `rice_interface/src/app/api/data/route.ts`

Response example:

```json
{
  "count": 12,
  "white": 3,
  "chalky": 1,
  "broken": 2,
  "brown": 2,
  "black": 1,
  "others": 3
}
```

Error:

```json
{ "error": "Failed to read data" }
```

### `POST /api/data`

Supports two actions:

#### Action: reset

Request:

```json
{ "action": "reset" }
```

Behavior:

- Resets `data.json` to all zeros.
- Returns reset object.

#### Action: save

Request:

```json
{ "action": "save" }
```

Behavior:

- Reads current `data.json`.
- Ensures `logs/` exists.
- Writes snapshot as `logs/log(YYYY-MM-DD_HH-MM-SS).json`.

Success response:

```json
{ "ok": true, "fileName": "logs/log(2026-04-27_10-33-22).json" }
```

Invalid action response:

```json
{ "error": "Invalid action" }
```

Server error:

```json
{ "error": "Failed to process data action" }
```

## Frontend Control Behavior

Buttons map to API calls:

- **Start**
  - Calls `POST /api/camera` with `{ cameraRun: true }`
  - Only enabled when Pi is connected and camera is stopped
- **Stop**
  - Calls `POST /api/camera` with `{ cameraRun: false }`
  - Only enabled when Pi is connected and camera is running
- **Reset**
  - Calls `POST /api/data` with `{ action: "reset" }`
  - Disabled while camera is running
- **Save**
  - Calls `POST /api/data` with `{ action: "save" }`
  - Always available unless another update/save is in progress

Polling behavior:

- Pi connection check every 1 second (`/api/ping`)
- Counter polling every 1 second while camera is running (`/api/data`)

## Troubleshooting

### Pi always shows disconnected

- Verify Pi IP in `worker/constants.py` and `rice_interface/src/app/api/ping/route.ts`.
- Confirm network route/firewall allows ICMP ping.

### Worker starts but no stream window

- Ensure stream source is available at `tcp://<PI_IP>:8000`.
- Validate OpenCV + FFmpeg support in environment.

### UI controls work but counters never increase

- Ensure `cam.json` has `PROCESS: true`.
- Confirm worker is running (`uv run main.py`).
- Check worker terminal for `[ERROR] Processing failed` logs.

### Need custom processing logic

- Update `worker/processor.py` in `process(frame)`.
- Keep output schema compatible with `data.json` keys expected by frontend.

## Optional Developer Commands

From `rice_interface/`:

```bash
npm run lint
npm run build
npm run start
```
