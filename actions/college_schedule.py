# actions/college_schedule.py
# Production College Schedule Intelligence Engine for JARVIS (ScheduleParser, ScheduleStore, ScheduleQueryEngine)

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List, Optional
from actions.college_mode import COLLEGE_CONFIG_PATH, load_college_config


class ScheduleParser:
    """Parses raw timetable structure into validated schedule records."""

    @staticmethod
    def parse_config(raw_data: Dict[str, Any]) -> Dict[str, Any]:
        timetable = raw_data.get("timetable", {})
        courses = {c.get("code", ""): c for c in raw_data.get("courses", [])}

        parsed_tt = {}
        for day, classes in timetable.items():
            parsed_classes = []
            for cls in classes:
                code = cls.get("course", "")
                c_info = courses.get(code, {})
                parsed_classes.append({
                    "time": cls.get("time", ""),
                    "course_code": code,
                    "course_name": c_info.get("name", code),
                    "faculty": c_info.get("instructor", "Faculty info unavailable"),
                    "room": cls.get("room", "Room info unavailable"),
                })
            parsed_tt[day.capitalize()] = parsed_classes

        return {
            "university": raw_data.get("university_name", "University"),
            "semester": raw_data.get("semester", "Current Semester"),
            "timetable": parsed_tt,
            "assignments": raw_data.get("assignments", []),
            "exams": raw_data.get("exams", [])
        }


class ScheduleStore:
    """In-memory data store with JSON persistence backing."""

    def __init__(self, config_path: Path = COLLEGE_CONFIG_PATH):
        self.config_path = config_path
        self._data = self.reload()

    def reload(self) -> Dict[str, Any]:
        raw = load_college_config()
        self._data = ScheduleParser.parse_config(raw)
        return self._data

    def get_day_classes(self, day_name: str) -> List[Dict[str, Any]]:
        return self._data.get("timetable", {}).get(day_name.capitalize(), [])


class ScheduleQueryEngine:
    """High-level query engine supporting natural language college schedule queries."""

    def __init__(self, store: Optional[ScheduleStore] = None):
        self.store = store or ScheduleStore()

    def get_today_schedule(self, dt: Optional[datetime] = None) -> Dict[str, Any]:
        now = dt or datetime.now()
        day_name = now.strftime("%A")
        classes = self.store.get_day_classes(day_name)
        return {
            "day": day_name,
            "date": now.strftime("%Y-%m-%d"),
            "classes": classes,
            "count": len(classes)
        }

    def get_tomorrow_schedule(self, dt: Optional[datetime] = None) -> Dict[str, Any]:
        now = dt or datetime.now()
        tomorrow = now + timedelta(days=1)
        day_name = tomorrow.strftime("%A")
        classes = self.store.get_day_classes(day_name)
        return {
            "day": day_name,
            "date": tomorrow.strftime("%Y-%m-%d"),
            "classes": classes,
            "count": len(classes)
        }

    def get_current_or_next_class(self, dt: Optional[datetime] = None) -> Dict[str, Any]:
        now = dt or datetime.now()
        day_name = now.strftime("%A")
        today_classes = self.store.get_day_classes(day_name)

        current_time_str = now.strftime("%H:%M")
        
        # Check current or upcoming class today
        for cls in today_classes:
            time_range = cls.get("time", "")
            if "-" in time_range:
                start_str, end_str = [t.strip() for t in time_range.split("-")]
                if start_str <= current_time_str <= end_str:
                    return {"status": "current", "class": cls, "day": day_name}
                elif current_time_str < start_str:
                    return {"status": "next", "class": cls, "day": day_name}

        # Fallback to tomorrow's first class
        tomorrow = now + timedelta(days=1)
        tomorrow_name = tomorrow.strftime("%A")
        tomorrow_classes = self.store.get_day_classes(tomorrow_name)
        if tomorrow_classes:
            return {"status": "next", "class": tomorrow_classes[0], "day": tomorrow_name}

        return {"status": "none", "message": "No upcoming classes found."}

    def query_schedule_natural(self, prompt: str, dt: Optional[datetime] = None) -> Dict[str, Any]:
        now = dt or datetime.now()
        p_lower = (prompt or "").lower()

        if any(k in p_lower for k in ["today", "aaj", "aaj meri class"]):
            today_res = self.get_today_schedule(now)
            classes = today_res["classes"]
            if not classes:
                msg = f"No classes scheduled for today ({today_res['day']}), sir."
            else:
                items = [f"• {c['time']}: {c['course_name']} ({c['course_code']}) in {c['room']} by {c['faculty']}" for c in classes]
                msg = f"Today's ({today_res['day']}) Schedule ({len(classes)} classes):\n" + "\n".join(items)
            return {"success": True, "type": "today_schedule", "message": msg, "data": today_res}

        elif any(k in p_lower for k in ["tomorrow", "kal", "kal kiski class"]):
            tom_res = self.get_tomorrow_schedule(now)
            classes = tom_res["classes"]
            if not classes:
                msg = f"No classes scheduled for tomorrow ({tom_res['day']}), sir."
            else:
                items = [f"• {c['time']}: {c['course_name']} ({c['course_code']}) in {c['room']} by {c['faculty']}" for c in classes]
                msg = f"Tomorrow's ({tom_res['day']}) Schedule:\n" + "\n".join(items)
            return {"success": True, "type": "tomorrow_schedule", "message": msg, "data": tom_res}

        elif any(k in p_lower for k in ["next class", "abhi meri class", "current class", "room"]):
            status_res = self.get_current_or_next_class(now)
            if status_res["status"] == "current":
                cls = status_res["class"]
                msg = f"Right now, you have {cls['course_name']} ({cls['course_code']}) in {cls['room']} with {cls['faculty']} ({cls['time']})."
            elif status_res["status"] == "next":
                cls = status_res["class"]
                msg = f"Your next class is {cls['course_name']} ({cls['course_code']}) in {cls['room']} with {cls['faculty']} at {cls['time']} ({status_res['day']})."
            else:
                msg = "You have no more classes remaining today, sir."
            return {"success": True, "type": "current_next_class", "message": msg, "data": status_res}

        # Day mapping for English and Hindi/Hinglish
        day_map = {
            "monday": "Monday", "somwar": "Monday",
            "tuesday": "Tuesday", "mangalwar": "Tuesday",
            "wednesday": "Wednesday", "budhwar": "Wednesday",
            "thursday": "Thursday", "guruwar": "Thursday", "veervar": "Thursday",
            "friday": "Friday", "shukrawar": "Friday",
            "saturday": "Saturday", "shanivar": "Saturday",
            "sunday": "Sunday", "ravivar": "Sunday"
        }
        for kw, d_name in day_map.items():
            if kw in p_lower:
                classes = self.store.get_day_classes(d_name)
                if not classes:
                    msg = f"No classes scheduled for {d_name}, Boss."
                else:
                    items = [f"• {c['time']}: {c['course_name']} ({c['course_code']}) in {c['room']} by {c['faculty']}" for c in classes]
                    msg = f"{d_name} Schedule ({len(classes)} classes):\n" + "\n".join(items)
                return {"success": True, "type": "day_schedule", "day": d_name, "message": msg}

        # Professor / Faculty inquiry
        if any(k in p_lower for k in ["professor", "instructor", "faculty", "kaun padhata hai", "teacher"]):
            courses = self.store._data.get("courses", []) if hasattr(self.store, "_data") else []
            raw = load_college_config()
            courses_list = raw.get("courses", [])
            items = [f"• {c.get('name')} ({c.get('code')}): {c.get('instructor', 'N/A')}" for c in courses_list]
            msg = "Faculty list for your enrolled courses, Boss:\n" + "\n".join(items)
            return {"success": True, "type": "faculty_info", "message": msg}

        # General schedule overview
        today_res = self.get_today_schedule(now)
        msg = f"College Schedule Overview — {today_res['day']}: {today_res['count']} classes scheduled."
        return {"success": True, "type": "general_schedule", "message": msg}


# Global singleton instance
schedule_query_engine = ScheduleQueryEngine()
