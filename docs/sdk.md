# 🐍 JARVIS Python SDK Reference (`JarvisAPI`)

The `JarvisAPI` class provides programmatic Python control over JARVIS.

```python
from jarvis_api import JarvisAPI
```

---

## 🛠️ Constructor

```python
jarvis = JarvisAPI(config=None)
```
- `config` *(Optional[JarvisConfig])*: Custom configuration instance. If omitted, loads default hierarchical config.

---

## 📚 Public Methods

### `get_status() -> HealthStatusModel`
Runs startup diagnostics and returns current system health.

### `execute(command_text: str) -> ToolResultModel`
Executes a natural language voice or text command.

### `call_tool(tool_name: str, args: dict = None) -> ToolResultModel`
Executes a specific tool through schema validation, security authorization, and post-action verification.

### `run_task(goal_description: str, priority: str = "normal") -> TaskResultModel`
Submits a goal to the autonomous planner and background task queue.

### `remember(key: str, value: Any, category: str = "notes") -> MemoryResultModel`
Saves a persistent key-value fact into long-term storage.

### `get_memory(category: str = None, key: str = None) -> Any`
Retrieves facts from persistent memory storage.

### `delete_memory(category: str, key: str) -> bool`
Deletes a persistent fact from long-term memory.

### `analyze_screen(question: str = "What is visible?") -> ToolResultModel`
Captures screen screenshot and runs visual vision processing.

### `list_tools() -> List[dict]`
Returns definitions, descriptions, parameters, and risk levels for all registered tools.
