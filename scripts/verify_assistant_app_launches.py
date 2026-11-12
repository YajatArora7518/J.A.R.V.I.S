"""Launch only the three services requested for this assistant; never send/call/read."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from actions.open_app import open_app_structured

results = []
for name in ("WhatsApp", "Discord", "Instagram"):
    try:
        response = open_app_structured(name)
        results.append({key: response.get(key) for key in ("app", "success", "mode", "verified", "message")})
    except Exception as exc:
        results.append({"app": name, "success": False, "message": str(exc)[:180]})
print(json.dumps(results, ensure_ascii=False, indent=2))
(Path(__file__).resolve().parent.parent / "scratch" / "assistant_app_launches.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
