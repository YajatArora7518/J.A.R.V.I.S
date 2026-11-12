import os
import re
import json
from pathlib import Path

root = Path(".")
patterns = [
    r"google\.genai", r"google\.generativeai", r"genai\.Client", r"generate_content",
    r"send_realtime", r"gemini-2", r"gemini-1", r"gemini", r"cloud_model",
    r"cloud fallback", r"AI_MULTITIER", r"live\.connect"
]
regex = re.compile("|".join(patterns), re.IGNORECASE)

inventory = []
skip_dirs = {".git", "__pycache__", "node_modules", ".freebuff", "BACKUPS", "graphify-out"}

for p in root.rglob("*.py"):
    if any(part in skip_dirs for part in p.parts):
        continue
    try:
        lines = p.read_text(encoding="utf-8", errors="ignore").splitlines()
    except Exception:
        continue
    
    for idx, line in enumerate(lines, 1):
        if regex.search(line):
            stripped = line.strip()
            is_comment = stripped.startswith("#") or stripped.startswith('"""') or stripped.startswith("'''")
            is_test = "test" in str(p).lower()
            
            if is_test:
                classification = "TEST"
            elif is_comment:
                classification = "COMMENT/DOCUMENTATION"
            else:
                classification = "ACTIVE RUNTIME"
                
            inventory.append({
                "file": str(p).replace("\\", "/"),
                "line_num": idx,
                "snippet": stripped[:120],
                "classification": classification
            })

print(f"Total occurrences found: {len(inventory)}")
by_class = {}
for item in inventory:
    by_class[item["classification"]] = by_class.get(item["classification"], 0) + 1
print("Summary by classification:", by_class)

out_file = Path("cloud_ai_inventory.json")
out_file.write_text(json.dumps(inventory, indent=2), encoding="utf-8")
print(f"Inventory written to {out_file.resolve()}")
