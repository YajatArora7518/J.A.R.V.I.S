# examples/sdk_example.py
# Autonomous Task & Screen Vision SDK Example

import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from jarvis_api import JarvisAPI

def main():
    jarvis = JarvisAPI()

    # 1. Autonomous Task Submission
    print("[*] Submitting autonomous task...")
    task = jarvis.run_task("Organize files on my desktop by type")
    print(f"Task Submitted: ID={task.task_id}, Status={task.status}")

    # 2. Screen Vision Analysis
    print("[*] Analyzing current screen display...")
    shot = jarvis.analyze_screen("What is currently on screen?")
    print(f"Screen Analysis: {shot.message}")

if __name__ == "__main__":
    main()
