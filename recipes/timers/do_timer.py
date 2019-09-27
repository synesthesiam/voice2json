#!/usr/bin/env python3
import sys
import json
import time

def parse_time_string(time_str):
    """Parse a string like '30 2' and return the integer 32."""
    return sum(int(n) for n in time_str.split(" "))

for line in sys.stdin:
    intent = json.loads(line)

    # Extract time strings
    hours_str = intent["slots"].get("hours", "0")
    minutes_str = intent["slots"].get("minutes", "0")
    seconds_str = intent["slots"].get("seconds", "0")

    # Parse into integers
    hours = parse_time_string(hours_str)
    minutes = parse_time_string(minutes_str)
    seconds = parse_time_string(seconds_str)

    # Compute total number of seconds to wait
    total_seconds = (hours * 60 * 60) + (minutes * 60) + seconds

    # Wait
    print(f"Waiting for {total_seconds} second(s)")
    time.sleep(total_seconds)
