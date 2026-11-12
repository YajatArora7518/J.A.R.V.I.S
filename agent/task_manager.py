# agent/task_manager.py
# Unified Task & Assignment Management Engine for J.A.R.V.I.S
# Builds on existing task/reminder infrastructure without competing systems.

import os
import sys
import re
import json
import time
from datetime import datetime, timedelta
from pathlib import Path
from dataclasses import dataclass, field, asdict
from threading import Lock
from uuid import uuid4
from typing import Dict, Any, List, Optional, Tuple

BASE_DIR = Path(__file__).resolve().parent.parent
TASKS_STORE_PATH = BASE_DIR / "config" / "tasks.json"
_task_lock = Lock()


def parse_assignment(text: str) -> Optional[Tuple[str, str]]:
    """Return an explicitly named local task and assignee, without contacting them."""
    patterns = [
        r'assign\s+(?:task\s+)?(.+?)\s+to\s+(.+?)(?:\s+please)?',
        r'(.+?)\s+ko\s+(.+?)\s+assign\s+(?:kar\s*(?:do|de)|karo|kardo|karde)',
    ]
    raw = text.strip().rstrip('.!? ')
    match = re.fullmatch(patterns[0], raw, re.I)
    if match:
        title, assignee = match.groups()
    else:
        match = re.fullmatch(patterns[1], raw, re.I)
        if not match:
            return None
        assignee, title = match.groups()
    title, assignee = title.strip(' \"\''), assignee.strip(' \"\'')
    if not title or not assignee or len(title) > 500 or len(assignee) > 100:
        return None
    return title, assignee


@dataclass
class TaskItem:
    id: str
    title: str
    description: str = ""
    category: str = "general"          # "assignment", "project", "personal", "study", "general"
    priority: str = "MEDIUM"           # "LOW", "MEDIUM", "HIGH", "CRITICAL"
    due_at: Optional[str] = None       # "YYYY-MM-DD" or "YYYY-MM-DD HH:MM"
    status: str = "PENDING"            # "PENDING", "IN_PROGRESS", "COMPLETED", "CANCELLED"
    project_or_subject: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    reminder_set: bool = False
    assignee: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TaskItem":
        return cls(
            id=data.get("id", f"task_{int(time.time() * 1000)}"),
            title=data.get("title", "Untitled Task"),
            description=data.get("description", ""),
            category=data.get("category", "general"),
            priority=data.get("priority", "MEDIUM"),
            due_at=data.get("due_at"),
            status=data.get("status", "PENDING"),
            project_or_subject=data.get("project_or_subject"),
            created_at=data.get("created_at", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
            reminder_set=bool(data.get("reminder_set", False)),
            assignee=data.get("assignee")
        )


class UnifiedTaskManager:
    """
    Unified manager for user tasks, college assignments, project deadlines,
    and reminder schedules.
    """

    def __init__(self, store_path: Path = TASKS_STORE_PATH):
        self.store_path = store_path
        self._ensure_store()

    def _ensure_store(self) -> None:
        if not self.store_path.exists():
            self.store_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.store_path, "w", encoding="utf-8") as f:
                json.dump({"tasks": []}, f, indent=2)

    def _load_tasks(self) -> List[TaskItem]:
        with _task_lock:
            if not self.store_path.exists():
                return []
            try:
                with open(self.store_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return [TaskItem.from_dict(t) for t in data.get("tasks", [])]
            except Exception:
                return []

    def _save_tasks(self, tasks: List[TaskItem]) -> None:
        with _task_lock:
            self.store_path.parent.mkdir(parents=True, exist_ok=True)
            data = {"tasks": [t.to_dict() for t in tasks]}
            with open(self.store_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

    def add_task(
        self,
        title: str,
        description: str = "",
        category: str = "general",
        priority: str = "MEDIUM",
        due_at: Optional[str] = None,
        project_or_subject: Optional[str] = None,
        set_system_reminder: bool = False,
        assignee: Optional[str] = None
    ) -> Tuple[TaskItem, bool]:
        """
        Adds a new task while preventing duplicate entries.
        Returns (task, is_new).
        """
        tasks = self._load_tasks()
        norm_title = re.sub(r"[^\w\s]", "", title.lower()).strip()

        # Deduplication check across pending tasks
        for existing in tasks:
            if existing.status in ["PENDING", "IN_PROGRESS"]:
                ex_norm = re.sub(r"[^\w\s]", "", existing.title.lower()).strip()
                if norm_title == ex_norm or (category != 'daily' and not assignee and len(norm_title) > 6 and (norm_title in ex_norm or ex_norm in norm_title)):
                    # Update priority or due date if more urgent
                    if priority in ["HIGH", "CRITICAL"] and existing.priority != "CRITICAL":
                        existing.priority = priority
                    if due_at:
                        existing.due_at = due_at
                    if assignee:
                        existing.assignee = assignee
                    self._save_tasks(tasks)
                    return existing, False

        task_id = f"task_{uuid4().hex[:12]}"
        new_task = TaskItem(
            id=task_id,
            title=title.strip(),
            description=description.strip(),
            category=category,
            priority=priority.upper(),
            due_at=due_at,
            status="PENDING",
            project_or_subject=project_or_subject,
            reminder_set=False,
            assignee=assignee
        )

        # Trigger existing Windows Task Scheduler reminder if requested and due_at has time
        if set_system_reminder and due_at:
            try:
                from actions.reminder import reminder
                parts = due_at.split(" ")
                date_part = parts[0]
                time_part = parts[1] if len(parts) > 1 else "09:00"
                res = reminder({"date": date_part, "time": time_part, "message": f"Task Due: {title}"})
                if "Reminder set" in res:
                    new_task.reminder_set = True
            except Exception:
                pass

        tasks.append(new_task)
        self._save_tasks(tasks)
        return new_task, True

    def get_pending_tasks(self) -> List[TaskItem]:
        """Returns pending tasks sorted by priority (CRITICAL > HIGH > MEDIUM > LOW) and due date."""
        tasks = self._load_tasks()

        # Also pull academic assignments from college config to prevent duplicate systems
        try:
            from actions.college_mode import load_college_config
            cfg = load_college_config()
            for asg in cfg.get("assignments", []):
                asg_title = asg.get("title", "")
                if not any(t.title.lower() == asg_title.lower() for t in tasks):
                    tasks.append(TaskItem(
                        id=f"asg_{asg.get('id', '1')}",
                        title=asg_title,
                        description=f"Course: {asg.get('course_code', '')}",
                        category="assignment",
                        priority="HIGH",
                        due_at=asg.get("due_date"),
                        status="PENDING",
                        project_or_subject=asg.get("course_code")
                    ))
        except Exception:
            pass

        pending = [t for t in tasks if t.status in ["PENDING", "IN_PROGRESS"]]
        priority_weights = {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1}
        pending.sort(key=lambda t: (
            -priority_weights.get(t.priority, 1),
            t.due_at or "9999-99-99"
        ))
        return pending

    def get_most_important_task(self) -> Optional[TaskItem]:
        """Returns the single highest-priority, most imminent task."""
        pending = self.get_pending_tasks()
        return pending[0] if pending else None

    def mark_completed(self, query_or_id: str) -> Optional[TaskItem]:
        """Marks a task matching the query or ID as completed."""
        tasks = self._load_tasks()
        q_clean = query_or_id.lower().strip()

        for t in tasks:
            if t.id.lower() == q_clean or q_clean in t.title.lower() or t.title.lower() in q_clean:
                t.status = "COMPLETED"
                self._save_tasks(tasks)
                return t

        return None

    def handle_natural_command(self, text: str) -> Optional[str]:
        """
        Natural Language interface for Hinglish and English task directives:
        - 'Ye yaad rakhna: ...'
        - 'Kal assignment submit karna hai'
        - 'Friday tak project complete karna hai'
        - 'Pending tasks batao'
        - 'Sabse important kya hai?'
        - 'Is task ko complete mark karo'
        """
        raw = text.strip()
        lower = raw.lower()

        assignment = parse_assignment(raw)
        if assignment:
            title, assignee = assignment
            task, _ = self.add_task(title=title, assignee=assignee)
            return f"Task board mein '{task.title}' {task.assignee} ke naam save kar diya. Unhe notification abhi nahi bheja hai."

        # 1. "Sabse important kya hai?" / "What is most important?"
        if any(w in lower for w in ["sabse important", "most important", "top priority", "kya important hai"]):
            top = self.get_most_important_task()
            if top:
                due_info = f" (Due: {top.due_at})" if top.due_at else ""
                subj = f" [{top.project_or_subject}]" if top.project_or_subject else ""
                return f"Boss, sabse important task hai: '{top.title}'{subj}{due_info}, priority: {top.priority}."
            return "Boss, koi pending task nahi hai. Everything is up to date!"

        # 2. "Pending tasks batao" / "Show pending tasks" / "What tasks do I have"
        if any(w in lower for w in ["pending tasks", "tasks batao", "kya kaam hai", "what do i need to do", "pending kaam"]):
            pending = self.get_pending_tasks()
            if not pending:
                return "Boss, filhaal koi pending tasks nahi hain."
            lines = [f"Aapke {len(pending)} pending tasks hain:"]
            for idx, t in enumerate(pending[:7], 1):
                due_str = f" [Due: {t.due_at}]" if t.due_at else ""
                owner = f" — {t.assignee}" if t.assignee else ""
                lines.append(f"{idx}. [{t.priority}] {t.title}{owner}{due_str}")
            return "\n".join(lines)

        # 3. "Is task ko complete mark karo" / "Mark complete"
        if any(w in lower for w in ["complete mark", "mark complete", "complete ho gaya", "finish ho gaya", "done mark"]):
            target = re.sub(r"^(is\s+)?(task\s+)?(ko\s+)?(complete\s+mark\s+karo|mark\s+complete|done)\s*", "", raw, flags=re.IGNORECASE).strip()
            target = target or raw
            matched = self.mark_completed(target)
            if matched:
                return f"Task '{matched.title}' completed mark kar diya gaya hai, boss."
            return "Kaunsa task complete hua? Uska exact title ya task ID batao."

        # 4. "Kal assignment submit karna hai"
        if any(w in lower for w in ["kal assignment", "assignment submit", "submit assignment"]):
            tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
            task, is_new = self.add_task(
                title="Submit assignment",
                description=raw,
                category="assignment",
                priority="HIGH",
                due_at=tomorrow,
                project_or_subject="College"
            )
            return f"Assignment task record kar liya hai (Due tomorrow: {tomorrow}). Priority: HIGH."

        # 5. "Friday tak project complete karna hai"
        if "friday" in lower and any(w in lower for w in ["project", "complete", "submit"]):
            # Calculate next Friday
            today = datetime.now()
            days_ahead = (4 - today.weekday() + 7) % 7 or 7
            next_friday = (today + timedelta(days=days_ahead)).strftime("%Y-%m-%d")
            task, is_new = self.add_task(
                title="Complete project",
                description=raw,
                category="project",
                priority="HIGH",
                due_at=next_friday,
                project_or_subject="JARVIS"
            )
            return f"Project deadline set kar di hai (Due Friday: {next_friday}). Priority: HIGH."

        # 6. "Ye yaad rakhna" / "Remember this task"
        if any(lower.startswith(w) for w in ["ye yaad rakhna", "remember this", "yaad rakhna", "save task"]):
            content = re.sub(r"^(ye\s+)?(yaad\s+rakhna|remember\s+this)[\s:]*", "", raw, flags=re.IGNORECASE).strip()
            content = content or raw
            task, is_new = self.add_task(
                title=content[:60],
                description=content,
                category="personal",
                priority="MEDIUM"
            )
            return f"Maine task save kar liya hai, boss: '{task.title}'."

        return None


# Default singleton instance
default_task_manager = UnifiedTaskManager()
