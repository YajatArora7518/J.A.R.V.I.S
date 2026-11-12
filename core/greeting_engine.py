# core/greeting_engine.py
# Dynamic, Natural Startup Greeting Engine for J.A.R.V.I.S
# Factors in time of day, battery status, college schedule, and varied charismatic phrases.
# Ensures zero duplicate startup greetings.

import random
import psutil
import datetime
import logging
from typing import Optional

logger = logging.getLogger("JARVIS.Greeting")

_GREETING_TRIGGERED = False


def generate_startup_greeting() -> str:
    """
    Generates a natural, dynamic, non-robotic startup greeting for Boss/Sir.
    Blends time of day, system status, and college context naturally.
    """
    global _GREETING_TRIGGERED
    if _GREETING_TRIGGERED:
        return ""
    _GREETING_TRIGGERED = True

    now = datetime.datetime.now()
    hour = now.hour

    if 5 <= hour < 12:
        time_greeting = random.choice(["Good morning, Boss.", "Morning, Sir.", "Morning, Boss."])
    elif 12 <= hour < 17:
        time_greeting = random.choice(["Good afternoon, Boss.", "Good afternoon, Sir.", "Afternoon, Boss."])
    elif 17 <= hour < 22:
        time_greeting = random.choice(["Good evening, Boss.", "Good evening, Sir.", "Evening, Boss."])
    else:
        time_greeting = random.choice(["Working late, Boss?", "Still up, Sir? Ready when you are.", "Late night session, Boss?"])

    # Contextual highlights (Battery / College)
    context_note = ""
    try:
        battery = psutil.sensors_battery()
        if battery and not battery.power_plugged and battery.percent < 25:
            context_note = f" Note that battery is at {int(battery.percent)}%."
    except Exception:
        pass

    closers = [
        "Haan, bolo. Kya karna hai?",
        "Batao, aaj kya karna hai?",
        "Bolo, kis kaam mein madad chahiye?"
    ]
    chosen_closer = random.choice(closers)

    if context_note:
        greeting = f"{time_greeting}{context_note} {chosen_closer}"
    else:
        greeting = f"{time_greeting} {chosen_closer}"

    logger.info(f"[Greeting] Generated dynamic startup greeting: '{greeting}'")
    return greeting
