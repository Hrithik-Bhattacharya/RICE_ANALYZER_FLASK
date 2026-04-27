import os
import json
import random
from constants import DATA_FILE, CATEGORIES

def process(frame):
    try:
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, "r") as f:
                data = json.load(f)
        else:
            data = {"count": 0}
            for c in CATEGORIES:
                data[c] = 0

        data["count"] += 1
        chosen = random.choice(CATEGORIES)
        data[chosen] += 1

        with open(DATA_FILE, "w") as f:
            json.dump(data, f, indent=4)

    except Exception as e:
        print(f"[ERROR] Processing failed: {e}")