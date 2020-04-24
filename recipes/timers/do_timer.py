#!/usr/bin/env python3
import sys
import json
import time

for line in sys.stdin:
    intent = json.loads(line)

    # Extract time integers
    hours = int(intent["slots"].get("hours", 0))
    minutes = int(intent["slots"].get("minutes", 0))
    seconds = int(intent["slots"].get("seconds", 0))

    # Compute total number of seconds to wait
    total_seconds = (hours * 60 * 60) + (minutes * 60) + seconds

    # Wait
    print(f"Waiting for {total_seconds} second(s)")
    time.sleep(total_seconds)
