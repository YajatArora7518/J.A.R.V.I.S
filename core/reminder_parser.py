"""Parse common English and Hinglish reminder times without an AI request."""
import re
from datetime import datetime, timedelta


def parse_reminder_query(query: str, now: datetime | None = None) -> dict:
    now = now or datetime.now()
    text = (query or "").strip()
    lower = text.lower()
    if not text:
        raise ValueError("Reminder kis time ke liye aur kis cheez ka chahiye?")
    relative = re.search(r"\b(\d+(?:\.\d+)?)\s*(seconds?|secs?|minutes?|mins?|hours?|hrs?|days?|ghante?|din)\b", lower)
    if relative:
        amount, unit = float(relative[1]), relative[2]
        scale = 86400 if unit.startswith(("day", "din")) else 3600 if unit.startswith(("hour", "hr", "ghant")) else 60 if unit.startswith("min") else 1
        if not 0 < amount * scale <= 366 * 86400:
            raise ValueError("Reminder duration 0 se zyada aur ek saal se kam rakho.")
        target = now + timedelta(seconds=amount * scale)
        timing_span = relative.span()
    else:
        clock = re.search(r"\b(\d{1,2})(?::(\d{2}))?\s*(am|pm|baje)\b|\b(\d{1,2}):(\d{2})\b", lower)
        if not clock:
            raise ValueError("Time batao, jaise '10 minute baad paani peena yaad dilana' ya 'kal 9 am reminder laga'.")
        hour, minute = int(clock[1] or clock[4]), int(clock[2] or clock[5] or 0)
        period = clock[3]
        if period in ("am", "pm"):
            if not 1 <= hour <= 12:
                raise ValueError("AM/PM time mein hour 1 se 12 hona chahiye.")
            hour = hour % 12 + (12 if period == "pm" else 0)
        elif period == "baje":
            if any(w in lower for w in ("shaam", "raat", "evening", "night")) and hour < 12:
                hour += 12
            elif not any(w in lower for w in ("subah", "morning", "shaam", "raat", "evening", "night")):
                raise ValueError("Subah ya shaam? Time AM/PM ke saath batao.")
        if hour > 23 or minute > 59:
            raise ValueError("Yeh time valid nahi hai.")
        target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if re.search(r"\b(kal|tomorrow)\b", lower):
            target += timedelta(days=1)
        elif target <= now:
            if re.search(r"\b(aaj|today)\b", lower):
                raise ValueError("Aaj ka yeh time nikal chuka hai. Naya time batao.")
            target += timedelta(days=1)
        timing_span = clock.span()
    message = text[:timing_span[0]] + " " + text[timing_span[1]:]
    message = re.sub(r"\b(?:hey\s+)?jarvis\b|\b(?:remind me|set (?:a )?(?:reminder|timer|alarm)|reminder (?:set|laga)|mujhe yaad dilana|yaad dilana|timer laga|alarm laga|aaj|today|kal|tomorrow)\b", " ", message, flags=re.I)
    message = re.sub(r"\s+", " ", message).strip(" .,;:-")
    message = re.sub(r"^(?:(?:to|for|ki|ke liye|baad|mein|in|after|at)\b\s*)+", "", message, flags=re.I)
    return {"date": target.strftime("%Y-%m-%d"), "time": target.strftime("%H:%M:%S"), "message": message or "Timer complete"}
