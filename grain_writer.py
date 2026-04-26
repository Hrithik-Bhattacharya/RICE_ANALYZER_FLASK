#!/usr/bin/env python3
"""
EXAMPLE: External Grain Detection Program
This simulates your ML model writing grain counts to the shared file.
In production, this would be your OpenCV + EfficientNet pipeline.
"""

import json
import fcntl
import time
import random
import os

SHARED_FILE = "shared_counts.json"

GRAIN_TYPES = ['chalky', 'white', 'brown', 'black', 'broken', 'other']
WEIGHTS = [0.15, 0.30, 0.20, 0.05, 0.15, 0.15]

def write_counts(counts):
    """Write counts to shared file with exclusive lock."""
    data = {
        **counts,
        "last_update": time.time()
    }

    # Use a temp file for atomic write
    temp_file = SHARED_FILE + ".tmp"

    with open(temp_file, 'w') as f:
        # Exclusive lock - blocks readers until write is complete
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        try:
            json.dump(data, f)
            f.flush()
            os.fsync(f.fileno())
        finally:
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)

    # Atomic rename
    os.rename(temp_file, SHARED_FILE)
    print(f"[WRITE] Updated counts: {counts}")

def main():
    print("[INIT] Grain detection writer started")
    print(f"[INIT] Writing to: {SHARED_FILE}")

    counts = {
        "total": 0,
        "chalky": 0,
        "white": 0,
        "brown": 0,
        "black": 0,
        "broken": 0,
        "other": 0
    }

    try:
        while True:
            # Simulate detecting 1-3 grains
            num_grains = random.choices([1, 2, 3], weights=[0.6, 0.3, 0.1], k=1)[0]

            for _ in range(num_grains):
                grain_type = random.choices(GRAIN_TYPES, weights=WEIGHTS, k=1)[0]
                counts[grain_type] += 1
                counts["total"] += 1

            write_counts(counts)

            # Wait before next detection batch
            time.sleep(random.uniform(0.2, 0.8))

    except KeyboardInterrupt:
        print("\n[EXIT] Writer stopped")

if __name__ == '__main__':
    main()
