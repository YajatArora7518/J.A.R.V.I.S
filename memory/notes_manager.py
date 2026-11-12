"""
memory/notes_manager.py
Searchable Notes System for J.A.R.V.I.S.

Provides:
- Create, read, update, delete notes
- Categories: general, project, study, personal
- Timestamps, searchable by keyword
- Stored in memory/notes.json
- Commands: "Note this down", "Open my hackathon notes", "What did I note yesterday?"
"""

import json
import time
import uuid
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

logger = logging.getLogger("JARVIS.NotesManager")

BASE_DIR = Path(__file__).resolve().parent.parent
NOTES_FILE = BASE_DIR / "memory" / "notes.json"


class Note:
    """A single note entry."""
    def __init__(self, note_id: str = "", title: str = "", content: str = "", category: str = "general",
                 tags: List[str] = None, created_at: float = 0.0, updated_at: float = 0.0):
        self.note_id = note_id or str(uuid.uuid4())[:8]
        self.title = title
        self.content = content
        self.category = category  # general | project | study | personal
        self.tags = tags or []
        self.created_at = created_at or time.time()
        self.updated_at = updated_at or time.time()

    def to_dict(self) -> dict:
        return {
            "note_id": self.note_id,
            "title": self.title,
            "content": self.content,
            "category": self.category,
            "tags": self.tags,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @staticmethod
    def from_dict(data: dict) -> "Note":
        return Note(
            note_id=data.get("note_id", ""),
            title=data.get("title", ""),
            content=data.get("content", ""),
            category=data.get("category", "general"),
            tags=data.get("tags", []),
            created_at=data.get("created_at", 0.0),
            updated_at=data.get("updated_at", 0.0),
        )

    def matches(self, query: str) -> bool:
        """Check if this note matches a search query."""
        q = query.lower()
        return (
            q in self.title.lower()
            or q in self.content.lower()
            or q in self.category.lower()
            or any(q in t.lower() for t in self.tags)
        )


class NotesManager:
    """Manages persistent searchable notes."""

    def __init__(self):
        self._notes: Dict[str, Note] = {}
        self._load()

    def _load(self):
        try:
            if NOTES_FILE.exists():
                data = json.loads(NOTES_FILE.read_text(encoding="utf-8"))
                for note_data in data.get("notes", []):
                    note = Note.from_dict(note_data)
                    self._notes[note.note_id] = note
                logger.info(f"[NotesManager] Loaded {len(self._notes)} notes.")
        except Exception as e:
            logger.warning(f"[NotesManager] Could not load: {e}")

    def _save(self):
        try:
            NOTES_FILE.parent.mkdir(parents=True, exist_ok=True)
            data = {"notes": [n.to_dict() for n in self._notes.values()]}
            NOTES_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        except Exception as e:
            logger.error(f"[NotesManager] Save failed: {e}")

    def create_note(self, title: str, content: str, category: str = "general", tags: List[str] = None) -> Dict[str, Any]:
        """Create a new note."""
        note = Note(title=title, content=content, category=category, tags=tags or [])
        self._notes[note.note_id] = note
        self._save()
        logger.info(f"[NotesManager] Created note: '{title}' ({note.note_id})")
        return {"success": True, "message": f"Note saved: '{title}'", "note_id": note.note_id}

    def get_note(self, note_id: str) -> Optional[Note]:
        return self._notes.get(note_id)

    def search_notes(self, query: str) -> List[Note]:
        """Search notes by keyword across title, content, category, tags."""
        return [n for n in self._notes.values() if n.matches(query)]

    def get_recent_notes(self, count: int = 5) -> List[Note]:
        """Get the most recently created/updated notes."""
        sorted_notes = sorted(self._notes.values(), key=lambda n: n.updated_at, reverse=True)
        return sorted_notes[:count]

    def get_notes_by_category(self, category: str) -> List[Note]:
        return [n for n in self._notes.values() if n.category.lower() == category.lower()]

    def update_note(self, note_id: str, title: str = None, content: str = None, category: str = None, tags: List[str] = None) -> Dict[str, Any]:
        note = self._notes.get(note_id)
        if not note:
            return {"success": False, "message": f"Note '{note_id}' not found."}
        if title:
            note.title = title
        if content:
            note.content = content
        if category:
            note.category = category
        if tags is not None:
            note.tags = tags
        note.updated_at = time.time()
        self._save()
        return {"success": True, "message": f"Note '{note.title}' updated."}

    def delete_note(self, note_id: str) -> Dict[str, Any]:
        if note_id in self._notes:
            title = self._notes[note_id].title
            del self._notes[note_id]
            self._save()
            return {"success": True, "message": f"Deleted note: '{title}'"}
        return {"success": False, "message": f"Note '{note_id}' not found."}

    def get_summary(self) -> str:
        if not self._notes:
            return "No notes saved yet."
        lines = []
        for n in sorted(self._notes.values(), key=lambda x: x.updated_at, reverse=True)[:10]:
            dt = datetime.fromtimestamp(n.created_at).strftime("%d %b %H:%M")
            lines.append(f"- [{n.category}] {n.title} ({dt})")
        return f"Notes ({len(self._notes)} total):\n" + "\n".join(lines)


# Global singleton
_NOTES_MANAGER: Optional[NotesManager] = None

def get_notes_manager() -> NotesManager:
    global _NOTES_MANAGER
    if _NOTES_MANAGER is None:
        _NOTES_MANAGER = NotesManager()
    return _NOTES_MANAGER


def notes_manager_tool(
    parameters: Optional[Dict[str, Any]] = None,
    response: Any = None,
    player: Any = None,
    session_memory: Any = None,
    speak: Any = None,
    **kwargs: Any,
) -> Dict[str, Any]:
    """Standard tool entry point for Notes Manager."""
    params = dict(parameters) if isinstance(parameters, dict) else {}
    if kwargs:
        for k, v in kwargs.items():
            if k not in ("speak", "player", "response", "session_memory") and k not in params:
                params[k] = v

    action = params.get("action", "list").lower()
    mgr = get_notes_manager()

    if action == "create":
        title = params.get("title", "Untitled Note")
        content = params.get("content", params.get("text", ""))
        category = params.get("category", "general")
        tags = params.get("tags", [])
        return mgr.create_note(title, content, category, tags)

    elif action == "search":
        query = params.get("query", params.get("text", ""))
        results = mgr.search_notes(query)
        if not results:
            return {"success": True, "message": f"No notes found matching '{query}'."}
        msg = f"Found {len(results)} notes:\n" + "\n".join(f"- {n.title}: {n.content[:80]}" for n in results)
        return {"success": True, "message": msg}

    elif action == "list":
        return {"success": True, "message": mgr.get_summary()}

    elif action == "get":
        note_id = params.get("note_id", "")
        note = mgr.get_note(note_id)
        if note:
            return {"success": True, "message": f"{note.title}\n{note.content}", "data": note.to_dict()}
        return {"success": False, "message": f"Note '{note_id}' not found."}

    elif action == "update":
        note_id = params.get("note_id", "")
        return mgr.update_note(note_id, title=params.get("title"), content=params.get("content"), category=params.get("category"), tags=params.get("tags"))

    elif action == "delete":
        note_id = params.get("note_id", "")
        return mgr.delete_note(note_id)

    elif action == "recent":
        count = int(params.get("count", 5))
        notes = mgr.get_recent_notes(count)
        if not notes:
            return {"success": True, "message": "No notes yet."}
        msg = "Recent notes:\n" + "\n".join(f"- {n.title}: {n.content[:60]}" for n in notes)
        return {"success": True, "message": msg}

    return {"success": False, "message": f"Unknown notes action: {action}"}
