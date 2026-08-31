# jarvis_api/models.py
# Data Response Models for SDK & REST API

from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field


@dataclass
class ToolResultModel:
    success: bool
    tool: str
    message: str
    data: Dict[str, Any] = field(default_factory=dict)
    verification: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    execution_time_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "tool": self.tool,
            "message": self.message,
            "data": self.data,
            "verification": self.verification,
            "error": self.error,
            "execution_time_ms": round(self.execution_time_ms, 2),
        }


@dataclass
class TaskResultModel:
    task_id: str
    status: str
    goal: str
    created_at: float
    result: Optional[str] = None
    error: Optional[str] = None
    steps: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "status": self.status,
            "goal": self.goal,
            "created_at": self.created_at,
            "result": self.result,
            "error": self.error,
            "steps": self.steps,
        }


@dataclass
class HealthStatusModel:
    status: str
    version: str
    all_systems_operational: bool
    diagnostics: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "version": self.version,
            "all_systems_operational": self.all_systems_operational,
            "diagnostics": self.diagnostics,
        }


@dataclass
class MemoryResultModel:
    success: bool
    category: str
    key: str
    value: Any

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "category": self.category,
            "key": self.key,
            "value": self.value,
        }


@dataclass
class ErrorResultModel:
    error_code: str
    message: str
    details: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "error_code": self.error_code,
            "message": self.message,
            "details": self.details or {},
        }
