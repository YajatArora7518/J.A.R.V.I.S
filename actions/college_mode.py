# actions/college_mode.py
# JARVIS — Modular College Mode Engine (Timetable, Assignments, Lecture Notes, Study Planner)

import json
import os
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional

def get_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent

BASE_DIR             = get_base_dir()
COLLEGE_CONFIG_PATH  = BASE_DIR / "config" / "college_schedule.json"


def load_college_config() -> Dict[str, Any]:
    """Loads college timetable and assignments config from JSON."""
    if not COLLEGE_CONFIG_PATH.exists():
        return {
            "college_mode_enabled": True,
            "timetable": {},
            "assignments": [],
            "courses": [],
            "exams": []
        }
    try:
        with open(COLLEGE_CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"[CollegeMode] ⚠️ Error loading college config: {e}")
        return {"college_mode_enabled": True, "timetable": {}, "assignments": [], "courses": [], "exams": []}


def save_college_config(config: Dict[str, Any]) -> bool:
    """Saves updated college configuration to disk."""
    try:
        with open(COLLEGE_CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=4, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"[CollegeMode] ⚠️ Error saving college config: {e}")
        return False


def college_mode(
    parameters: Optional[Dict[str, Any]] = None,
    player: Any = None,
    speak: Any = None,
    **kwargs
) -> Dict[str, Any]:
    """
    Main tool handler for College Mode capabilities.
    Actions:
      - 'enable' / 'status': Enables or returns College Mode status.
      - 'schedule' / 'timetable': Returns today's or weekly timetable.
      - 'assignments': Returns list of pending assignments & deadlines.
      - 'add_assignment': Adds a new assignment to tracker.
      - 'summarize_notes': Summarizes lecture notes / text / PDF.
      - 'generate_flashcards': Creates study flashcards for a topic/subject.
    """
    params = parameters or kwargs or {}
    action = (params.get("action") or "schedule").lower().strip()
    query  = params.get("query", "")

    cfg = load_college_config()

    if action in ["enable", "status", "toggle"]:
        cfg["college_mode_enabled"] = True
        save_college_config(cfg)
        msg = "College Mode is active, sir. Timetable, assignments, and study planner are ready."
        return {"success": True, "action": action, "message": msg, "verified": True}

    elif action in ["schedule", "timetable"]:
        from actions.college_schedule import schedule_query_engine
        res = schedule_query_engine.query_schedule_natural(query or params.get("day", ""))
        return res

    elif action in ["assignments", "deadlines"]:
        asgs = cfg.get("assignments", [])
        pending = [a for a in asgs if a.get("status", "").lower() != "completed"]
        if not pending:
            msg = "You have no pending assignments right now, sir."
        else:
            items = [f"• [{a.get('course')}] {a.get('title')} (Due: {a.get('due_date')})" for a in pending]
            msg = f"You have {len(pending)} pending assignment(s):\n" + "\n".join(items)

        return {"success": True, "action": action, "assignments": pending, "message": msg, "verified": True}

    elif action == "add_assignment":
        title = params.get("title", "New Assignment")
        course = params.get("course", "General")
        due_date = params.get("due_date", datetime.now().strftime("%Y-%m-%d"))

        new_asg = {
            "id": f"ASG-{len(cfg.get('assignments', [])) + 1}",
            "course": course,
            "title": title,
            "due_date": due_date,
            "status": "Pending"
        }
        cfg.setdefault("assignments", []).append(new_asg)
        save_college_config(cfg)
        msg = f"Added assignment '{title}' for {course}, due {due_date}."
        return {"success": True, "action": action, "assignment": new_asg, "message": msg, "verified": True}

    elif action in ["complete_assignment", "mark_completed", "finish_assignment"]:
        target_id_or_title = (params.get("id") or params.get("title") or query or "").lower().strip()
        asgs = cfg.get("assignments", [])
        found = False
        for a in asgs:
            if target_id_or_title and (target_id_or_title in a.get("id", "").lower() or target_id_or_title in a.get("title", "").lower() or target_id_or_title in a.get("course", "").lower()):
                a["status"] = "Completed"
                found = True
                save_college_config(cfg)
                msg = f"Marked assignment '{a.get('title')}' as Completed, Boss."
                return {"success": True, "action": action, "assignment": a, "message": msg, "verified": True}
        
        # If no specific match was mentioned, mark the earliest pending assignment
        for a in asgs:
            if a.get("status", "").lower() != "completed":
                a["status"] = "Completed"
                found = True
                save_college_config(cfg)
                msg = f"Marked assignment '{a.get('title')}' ({a.get('course')}) as Completed, Boss."
                return {"success": True, "action": action, "assignment": a, "message": msg, "verified": True}

        return {"success": False, "action": action, "message": "No pending assignments found to mark complete.", "verified": False}

    elif action == "summarize_notes":
        text_content = params.get("text", "") or query
        if not text_content:
            return {"success": False, "action": action, "message": "No note content provided to summarize.", "verified": False}

        try:
            from core.ai_multitier_engine import get_ai_engine
            ai_brain = get_ai_engine()
            res = ai_brain.generate_response(
                prompt=f"Summarize these lecture notes concisely into key concepts and bullet points:\n\n{text_content[:4000]}",
                system_override="You are an expert study assistant. Summarize notes concisely with clear bullet points."
            )
            summary_text = res.get("text", "").strip()
            return {"success": True, "action": action, "summary": summary_text, "message": summary_text, "verified": True}
        except Exception as e:
            return {"success": False, "action": action, "message": f"Summarization failed: {e}", "verified": False}

    elif action == "generate_flashcards":
        topic = params.get("topic") or query or "General Study"
        try:
            from core.ai_multitier_engine import get_ai_engine
            ai_brain = get_ai_engine()
            res = ai_brain.generate_response(
                prompt=f"Generate 5 key Q&A study flashcards for topic: {topic}. Output format:\nQ: ...\nA: ...",
                system_override="You are a study assistant. Generate clear, memorable flashcards."
            )
            flashcards = res.get("text", "").strip()
            return {"success": True, "action": action, "flashcards": flashcards, "message": flashcards, "verified": True}
        except Exception as e:
            return {"success": False, "action": action, "message": f"Flashcard generation failed: {e}", "verified": False}

    return {"success": False, "action": action, "message": f"Unknown College Mode action '{action}'.", "verified": False}
