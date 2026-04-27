import os

os.environ["QT_QPA_PLATFORM"] = "xcb"

PI_IP = "192.168.50.1"
PORT = 8000
EXPECTED_FPS = 60

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.abspath(os.path.join(BASE_DIR, ".."))

CONFIG_FILE = os.path.join(PARENT_DIR, "cam.json")
DATA_FILE = os.path.join(PARENT_DIR, "data.json")

CHECK_INTERVAL = 0.5

URL = f"tcp://{PI_IP}:{PORT}"

CATEGORIES = ["white", "chalky", "broken", "brown", "black", "others"]