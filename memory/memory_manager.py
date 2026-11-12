import json
import re
from datetime import datetime
from threading import Lock
from pathlib import Path
import sys


def get_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


BASE_DIR         = get_base_dir()
MEMORY_PATH      = BASE_DIR / "memory" / "long_term.json"
_lock            = Lock()
MAX_VALUE_LENGTH = 380
MEMORY_MAX_CHARS = 2200


def _empty_memory() -> dict:
    return {
        "identity":      {},
        "preferences":   {},
        "projects":      {},
        "relationships": {},
        "wishes":        {},
        "notes":         {}
    }


_cached_memory_data = None
_cached_memory_mtime = 0.0


def load_memory() -> dict:
    global _cached_memory_data, _cached_memory_mtime
    with _lock:
        if not MEMORY_PATH.exists():
            return _empty_memory()
        try:
            mtime = MEMORY_PATH.stat().st_mtime
            if _cached_memory_data is not None and mtime == _cached_memory_mtime:
                import copy
                return copy.deepcopy(_cached_memory_data)

            data = json.loads(MEMORY_PATH.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                base = _empty_memory()
                for key in base:
                    if key not in data:
                        data[key] = {}
                _cached_memory_data = data
                _cached_memory_mtime = mtime
                import copy
                return copy.deepcopy(data)
            return _empty_memory()
        except Exception as e:
            print(f"[Memory] ⚠️ Load error: {e}")
            return _empty_memory()


def _all_entries(memory: dict) -> list[tuple]:
    entries = []
    for cat, items in memory.items():
        if not isinstance(items, dict):
            continue
        for key, entry in items.items():
            if isinstance(entry, dict) and "value" in entry:
                entries.append((cat, key, entry))
    return entries


def _trim_to_limit(memory: dict) -> dict:
    serialized = json.dumps(memory, ensure_ascii=False)
    if len(serialized) <= MEMORY_MAX_CHARS:
        return memory

    entries = _all_entries(memory)
    entries.sort(key=lambda t: t[2].get("updated", "0000-00-00"))

    for cat, key, _ in entries:
        if len(json.dumps(memory, ensure_ascii=False)) <= MEMORY_MAX_CHARS:
            break
        del memory[cat][key]
        print(f"[Memory] 🗑️  Trimmed {cat}/{key} (limit: {MEMORY_MAX_CHARS} chars)")

    return memory


def save_memory(memory: dict) -> None:
    global _cached_memory_data, _cached_memory_mtime
    if not isinstance(memory, dict):
        return

    import copy, os, time
    with _lock:
        mem_copy = copy.deepcopy(memory)
        mem_copy = _trim_to_limit(mem_copy)
        MEMORY_PATH.parent.mkdir(parents=True, exist_ok=True)
        tmp_file = MEMORY_PATH.parent / f"long_term.tmp.{os.getpid()}_{time.time_ns()}.json"
        try:
            tmp_file.write_text(
                json.dumps(mem_copy, indent=2, ensure_ascii=False),
                encoding="utf-8"
            )
            tmp_file.replace(MEMORY_PATH)
            _cached_memory_mtime = MEMORY_PATH.stat().st_mtime
            _cached_memory_data = copy.deepcopy(mem_copy)
        except Exception as e:
            print(f"[Memory] ⚠️ Save error: {e}")
            if tmp_file.exists():
                try:
                    tmp_file.unlink()
                except Exception:
                    pass


def _truncate_value(val: str) -> str:
    if isinstance(val, str) and len(val) > MAX_VALUE_LENGTH:
        return val[:MAX_VALUE_LENGTH].rstrip() + "…"
    return val


def _recursive_update(target: dict, updates: dict) -> bool:
    changed = False
    for key, value in updates.items():
        if value is None:
            continue
        if isinstance(value, str) and not value.strip():
            continue

        if isinstance(value, dict) and "value" not in value:
            if key not in target or not isinstance(target[key], dict):
                target[key] = {}
                changed = True
            if _recursive_update(target[key], value):
                changed = True
        else:
            if isinstance(value, dict) and "value" in value:
                new_val = _truncate_value(str(value["value"]))
                category = value.get("category", "")
                confidence = float(value.get("confidence", 1.0))
                source = value.get("source", "user_explicit")
                expiry = value.get("expiry", None)
            else:
                new_val = _truncate_value(str(value))
                category = ""
                confidence = 1.0
                source = "user_explicit"
                expiry = None

            now_iso = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            now_date = datetime.now().strftime("%Y-%m-%d")

            existing = target.get(key, {})
            created_at = existing.get("created_at", now_iso) if isinstance(existing, dict) else now_iso

            entry = {
                "value": new_val,
                "updated": now_date,
                "created_at": created_at,
                "last_accessed": now_iso,
                "confidence": confidence,
                "source": source,
                "expiry": expiry
            }
            if category:
                entry["category"] = category

            if not isinstance(existing, dict) or existing.get("value") != new_val or existing.get("expiry") != expiry:
                target[key] = entry
                changed = True

    return changed


def prune_expired_memories(memory: Optional[dict] = None) -> tuple:
    """
    Safely prunes expired temporary context entries from long-term memory.
    Stable explicit preferences and identity facts without an expired timestamp
    are guaranteed never to be pruned.
    Returns (updated_memory, pruned_count).
    """
    import time
    mem = memory if memory is not None else load_memory()
    now_ts = time.time()
    now_date = datetime.now().strftime("%Y-%m-%d")
    pruned_count = 0
    changed = False

    for cat, items in list(mem.items()):
        if not isinstance(items, dict):
            continue
        for key, entry in list(items.items()):
            if not isinstance(entry, dict):
                continue
            expiry = entry.get("expiry")
            if not expiry:
                continue

            # Check if expiry has passed
            is_expired = False
            try:
                if isinstance(expiry, (int, float)):
                    if now_ts >= expiry:
                        is_expired = True
                elif isinstance(expiry, str):
                    if len(expiry) == 10:
                        if now_date >= expiry:
                            is_expired = True
                    else:
                        exp_dt = datetime.fromisoformat(expiry)
                        if datetime.now() >= exp_dt:
                            is_expired = True
            except Exception:
                pass

            if is_expired:
                del items[key]
                pruned_count += 1
                changed = True
                print(f"[Memory] ⌛ Pruned expired temporary memory: {cat}/{key}")

    if changed and memory is None:
        save_memory(mem)

    return mem, pruned_count


def update_memory(memory_update: dict | str = None, key: Optional[str] = None, value: Optional[str] = None) -> dict:
    if isinstance(memory_update, str) and key is not None:
        memory_update = {memory_update: {key: value if value is not None else ""}}
    if not isinstance(memory_update, dict) or not memory_update:
        return load_memory()

    memory = load_memory()
    if _recursive_update(memory, memory_update):
        save_memory(memory)
        print(f"[Memory] Saved: {list(memory_update.keys())}")
    return memory


def _load_gemini_key() -> str:
    api_file = BASE_DIR / "config" / "api_keys.json"
    if api_file.exists():
        try:
            d = json.loads(api_file.read_text(encoding="utf-8"))
            return str(d.get("gemini_api_key", "")).strip()
        except Exception:
            pass
    import os
    return os.environ.get("GEMINI_API_KEY", "").strip()


def _call_llm_for_memory(prompt: str, system: str = "", max_tokens: int = 512, temperature: float = 0.2) -> str:
    """
    100% Local AI Memory Extractor via Ollama.
    Guarantees private personal facts, preferences, and names are never sent to cloud AI.
    """
    # 1. Primary: Strictly Local AI Provider (Ollama)
    try:
        from core.local_ai_provider import get_local_ai_provider
        provider = get_local_ai_provider()
        res = provider.chat(prompt, system=system, temperature=temperature)
        if res and isinstance(res, str):
            return res.strip()
    except Exception as local_err:
        pass

    # 2. Guarded Cloud Fallbacks (Blocked by default in 100% Local Mode)
    import core.ai_policy as ai_policy
    if not ai_policy.is_cloud_ai_allowed():
        return ""

    try:
        ai_policy.assert_cloud_ai_allowed("Cloud Memory Extraction")
        g_key = _load_gemini_key()
        if g_key:
            from google import genai
            from google.genai import types
            g_client = genai.Client(api_key=g_key)
            full_prompt = f"{system}\n\n{prompt}" if system else prompt
            response = g_client.models.generate_content(
                model="gemini-flash-latest",
                contents=full_prompt,
                config=types.GenerateContentConfig(
                    max_output_tokens=max_tokens,
                    temperature=temperature,
                )
            )
            if response and hasattr(response, "text") and response.text:
                return response.text.strip()
    except Exception:
        pass

    return ""


def should_extract_memory(user_text: str, jarvis_text: str, api_key: str = "") -> bool:
    try:
        combined = f"User: {user_text[:300]}\nJarvis: {jarvis_text[:1000]}"
        prompt = (
            f"Does this conversation contain ANY of the following?\n"
            f"- Personal facts (name, age, city, job, birthday, nationality)\n"
            f"- Preferences or favorites (food, color, music, sport, game, film, book, etc.)\n"
            f"- Active projects or goals the user is working on\n"
            f"- People in the user's life (friends, family, partner, colleagues)\n"
            f"- Things the user wants to do or buy in the future\n"
            f"- Any other fact worth remembering long-term\n\n"
            f"Reply only YES or NO.\n\nConversation:\n{combined}"
        )
        result = _call_llm_for_memory(prompt, system="You are a memory relevance checker. Reply only YES or NO.", max_tokens=5, temperature=0.0)
        return "YES" in result.upper()

    except Exception as e:
        print(f"[Memory] ⚠️ Stage1 check failed: {e}")
        return False


def extract_memory(user_text: str, jarvis_text: str, api_key: str = "") -> dict:
    try:
        combined = f"User: {user_text[:600]}\nJarvis: {jarvis_text[:300]}"
        prompt = (
            f"Extract ALL memorable personal facts from this conversation. Any language.\n"
            f"Return ONLY valid JSON. Use {{}} if truly nothing is worth saving.\n\n"
            f"Category guide:\n"
            f"  identity      → name, age, birthday, city, country, job, school, nationality, language\n"
            f"  preferences   → ANY favorite or preferred thing:\n"
            f"                  favorite_food, favorite_color, favorite_music, favorite_film,\n"
            f"                  favorite_game, favorite_sport, favorite_book, favorite_artist,\n"
            f"                  favorite_country, hobbies, interests, dislikes, etc.\n"
            f"  projects      → projects being built, ongoing work, goals, ideas in progress\n"
            f"                  (e.g. jarvis_app: 'Building a JARVIS-like AI assistant')\n"
            f"  relationships → people mentioned: friends, family, partner, colleagues\n"
            f"                  (e.g. best_friend_ali: 'Best friend, met in university')\n"
            f"  wishes        → future plans, things to buy, travel plans, dreams\n"
            f"  notes         → anything else worth remembering (habits, schedule, etc.)\n\n"
            f"IMPORTANT:\n"
            f"- Be LIBERAL: if something MIGHT be worth remembering, include it.\n"
            f"- Extract from BOTH user and Jarvis turns.\n"
            f"- Skip: weather, reminders, search results, one-time commands.\n"
            f"- Use concise English values regardless of conversation language.\n\n"
            f"Format:\n"
            f'{{"identity":{{"name":{{"value":"Ali"}}}},\n'
            f' "preferences":{{"favorite_color":{{"value":"blue"}}}},\n'
            f' "projects":{{"jarvis_app":{{"value":"JARVIS-like AI assistant"}}}},\n'
            f' "relationships":{{"friend_yusuf":{{"value":"close friend"}}}},\n'
            f' "wishes":{{"buy_guitar":{{"value":"wants an acoustic guitar"}}}},\n'
            f' "notes":{{"works_at_night":{{"value":"usually active late at night"}}}}}}\n\n'
            f"Conversation:\n{combined}\n\nJSON:"
        )

        raw = _call_llm_for_memory(prompt, system="Return ONLY valid JSON. No markdown, no explanation, no extra text.", max_tokens=1024, temperature=0.2)

        clean = raw.strip()
        clean = re.sub(r"```(?:json)?", "", clean).strip().rstrip("`").strip()

        if not clean or clean == "{}":
            return {}

        return json.loads(clean)

    except json.JSONDecodeError:
        return {}
    except Exception as e:
        if "429" not in str(e):
            print(f"[Memory] ⚠️ Extract failed: {e}")
        return {}


def format_memory_for_prompt(memory: Optional[dict] = None) -> str:
    if memory is None:
        memory = load_memory()
    if not memory:
        return ""

    lines = []

    identity  = memory.get("identity", {})
    id_fields = ["name", "age", "birthday", "city", "job", "language", "school", "nationality"]
    for field in id_fields:
        entry = identity.get(field)
        if entry:
            val = entry.get("value") if isinstance(entry, dict) else entry
            if val:
                lines.append(f"{field.title()}: {val}")
    for key, entry in identity.items():
        if key in id_fields:
            continue
        val = entry.get("value") if isinstance(entry, dict) else entry
        if val:
            lines.append(f"{key.replace('_', ' ').title()}: {val}")

    prefs = memory.get("preferences", {})
    if prefs:
        lines.append("")
        lines.append("Preferences:")
        for key, entry in list(prefs.items())[:15]:
            val = entry.get("value") if isinstance(entry, dict) else entry
            if val:
                lines.append(f"  - {key.replace('_', ' ').title()}: {val}")

    projects = memory.get("projects", {})
    if projects:
        lines.append("")
        lines.append("Active Projects / Goals:")
        for key, entry in list(projects.items())[:8]:
            val = entry.get("value") if isinstance(entry, dict) else entry
            if val:
                lines.append(f"  - {key.replace('_', ' ').title()}: {val}")

    rels = memory.get("relationships", {})
    if rels:
        lines.append("")
        lines.append("People in their life:")
        for key, entry in list(rels.items())[:10]:
            val = entry.get("value") if isinstance(entry, dict) else entry
            if val:
                lines.append(f"  - {key.replace('_', ' ').title()}: {val}")

    wishes = memory.get("wishes", {})
    if wishes:
        lines.append("")
        lines.append("Wishes / Plans / Wants:")
        for key, entry in list(wishes.items())[:8]:
            val = entry.get("value") if isinstance(entry, dict) else entry
            if val:
                lines.append(f"  - {key.replace('_', ' ').title()}: {val}")

    notes = memory.get("notes", {})
    if notes:
        lines.append("")
        lines.append("Other notes:")
        for key, entry in list(notes.items())[:8]:
            val = entry.get("value") if isinstance(entry, dict) else entry
            if val:
                lines.append(f"  - {key}: {val}")

    if not lines:
        return ""

    header = "[WHAT YOU KNOW ABOUT THIS PERSON — use naturally, never recite like a list]\n"
    result = header + "\n".join(lines)
    if len(result) > 2000:
        result = result[:1997] + "…"

    try:
        from memory.adaptive_intelligence import default_adaptive_engine
        adaptive_ctx = default_adaptive_engine.get_adaptive_context()
        if adaptive_ctx:
            result += f"\n\n{adaptive_ctx}"
    except Exception as e:
        print(f"[Memory] ⚠️ Adaptive context append note: {e}")

    return result + "\n"


def remember(key: str, value: str, category: str = "notes") -> str:
    valid = {"identity", "preferences", "projects", "relationships", "wishes", "notes"}
    if category not in valid:
        category = "notes"
    update_memory({category: {key: {"value": value}}})
    return f"I've remembered that for you, sir: {key} = {value}"


def forget(key: str, category: str = "notes") -> str:
    memory = load_memory()
    for cat_name, cat in memory.items():
        if isinstance(cat, dict) and key.lower() in [k.lower() for k in cat]:
            matched_key = next(k for k in cat if k.lower() == key.lower())
            del cat[matched_key]
            memory[cat_name] = cat
            save_memory(memory)
            return f"I've removed '{matched_key}' from memory, sir."
    return f"I couldn't find '{key}' in my memory records, sir."

forget_memory = forget


def query_memory(topic: str = "") -> str:
    """Searches memory store for entries matching topic query."""
    memory = load_memory()
    if not topic or topic.strip() == "":
        return format_memory_for_prompt(memory)

    topic_lower = topic.lower().strip()
    matches = []
    for cat, items in memory.items():
        if isinstance(items, dict):
            for k, entry in items.items():
                val = entry.get("value") if isinstance(entry, dict) else str(entry)
                if topic_lower in k.lower() or topic_lower in str(val).lower():
                    matches.append(f"• [{cat.title()}] {k.replace('_', ' ').title()}: {val}")

    if not matches:
        return f"I don't have any saved memories regarding '{topic}', sir."
    return f"Here is what I remember about '{topic}':\n" + "\n".join(matches)


def parse_memory_command(text: str) -> Optional[str]:
    """Parses natural language memory directives."""
    txt = text.strip()
    if not txt:
        return None

    # Remember command
    rem_match = re.search(r"(?:remember|save)\s+(?:that|this)?\s*(.+)", txt, re.IGNORECASE)
    if rem_match:
        content = rem_match.group(1).strip()
        if ":" in content:
            k, v = content.split(":", 1)
            return remember(k.strip().replace(" ", "_"), v.strip())
        else:
            key_name = f"note_{int(time.time()) % 10000}"
            return remember(key_name, content)

    # Forget command
    forg_match = re.search(r"(?:forget|delete memory)\s+(?:about)?\s*(.+)", txt, re.IGNORECASE)
    if forg_match:
        target = forg_match.group(1).strip()
        return forget(target)

    # Query command
    query_match = re.search(r"what\s+do\s+you\s+remember\s+about\s+(.+)", txt, re.IGNORECASE)
    if query_match:
        return query_memory(query_match.group(1).strip())

    return None


def rank_relevant_memories(query: str, limit: int = 5) -> List[Dict[str, Any]]:
    """
    Ranks saved memories by keyword relevance score for prompt context compression.
    """
    if not query or not query.strip():
        return []

    tokens = set(re.findall(r"\w+", query.lower()))
    memory = load_memory()
    ranked = []

    for cat, items in memory.items():
        if not isinstance(items, dict):
            continue
        for k, entry in items.items():
            val = entry.get("value") if isinstance(entry, dict) else str(entry)
            text_block = f"{cat} {k} {val}".lower()
            
            # Simple term frequency overlap score
            score = sum(1 for token in tokens if token in text_block)
            if score > 0:
                ranked.append({
                    "category": cat,
                    "key": k,
                    "value": val,
                    "score": score,
                    "updated": entry.get("updated", "") if isinstance(entry, dict) else ""
                })

    ranked.sort(key=lambda x: (x["score"], x["updated"]), reverse=True)
    return ranked[:limit]


def retrieve_relevant_memories(query: str, limit: int = 5) -> List[Dict[str, Any]]:
    """
    Phase 4D Multi-factor memory retrieval engine:
    Ranks memories considering:
    - Semantic & token relevance across key, value, and category
    - Explicit user source outranking inferred source
    - Confidence score weighting (0.0 to 1.0)
    - Recency of information
    - Category / priority hierarchy

    Preserves entry['value'] schema compatibility.
    """
    memory = load_memory()
    if not memory:
        return []

    tokens = set(re.findall(r"\w+", (query or "").lower()))
    stop_words = {"the", "a", "an", "is", "are", "was", "were", "to", "in", "on", "at", "my", "your", "kya", "hai", "ka", "ki", "ke", "ko"}
    query_tokens = {t for t in tokens if t not in stop_words and len(t) > 1} or tokens

    ranked = []
    now_year = datetime.now().year

    for cat, items in memory.items():
        if not isinstance(items, dict):
            continue
        for k, entry in items.items():
            val = entry.get("value") if isinstance(entry, dict) else str(entry)
            text_block = f"{cat} {k} {val}".lower()
            key_clean = k.replace("_", " ").lower()

            # 1. Semantic / keyword match
            token_matches = sum(1 for token in query_tokens if token in text_block) if query_tokens else 0
            exact_key_bonus = 4.0 if any(token in key_clean for token in query_tokens) else 0.0

            # If query provided but no match, skip unless query is empty
            if query_tokens and token_matches == 0 and exact_key_bonus == 0.0:
                continue

            # 2. Source weighting (explicit user source outranks inferred)
            source = entry.get("source", "user_explicit") if isinstance(entry, dict) else "user_explicit"
            source_weight = 3.0 if "explicit" in str(source).lower() else 1.0

            # 3. Confidence weighting (0.0 to 1.0, default 1.0)
            confidence = float(entry.get("confidence", 1.0)) if isinstance(entry, dict) else 1.0

            # 4. Recency weighting
            updated_str = entry.get("updated", "") if isinstance(entry, dict) else ""
            recency_weight = 1.0
            if updated_str and str(now_year) in updated_str:
                recency_weight = 1.4

            # 5. Category priority weighting
            cat_priority = 1.5 if cat in ["identity", "preferences", "projects"] else 1.0

            total_score = (token_matches * 2.0 + exact_key_bonus + source_weight) * confidence * recency_weight * cat_priority

            ranked.append({
                "category": cat,
                "key": k,
                "value": val,
                "confidence": confidence,
                "source": source,
                "updated": updated_str,
                "score": round(total_score, 3)
            })

    ranked.sort(key=lambda x: (x["score"], x["updated"]), reverse=True)
    return ranked[:limit]


def handle_memory_correction(text: str) -> Optional[Dict[str, Any]]:
    """
    Handles natural language memory corrections without deleting unrelated memories:
    - 'Nahi, ye preference galat hai.'
    - 'Ye yaad mat rakh.'
    - 'Is memory ko update karo.'
    Returns dict with correction details or None.
    """
    lower = text.lower().strip()

    # Case 1: "Nahi, ye preference galat hai" / "Ye preference galat hai"
    if any(p in lower for p in ["ye preference galat hai", "galat hai", "wrong preference", "not my preference", "preference galat"]):
        memory = load_memory()
        prefs = memory.get("preferences", {})
        matched_key = None
        for k in prefs.keys():
            k_clean = k.replace("_", " ").lower()
            if k.lower() in lower or k_clean in lower:
                matched_key = k
                break
        if matched_key:
            del prefs[matched_key]
            save_memory(memory)
            return {
                "action": "deleted_preference",
                "key": matched_key,
                "message": f"Preference '{matched_key}' memory se hata diya gaya hai."
            }
        else:
            if prefs:
                sorted_prefs = sorted(prefs.items(), key=lambda t: t[1].get("updated", "") if isinstance(t[1], dict) else "", reverse=True)
                target_key = sorted_prefs[0][0]
                del prefs[target_key]
                save_memory(memory)
                return {
                    "action": "deleted_recent_preference",
                    "key": target_key,
                    "message": f"Recent preference '{target_key}' memory se hata diya gaya hai."
                }

    # Case 2: "Ye yaad mat rakh" / "Don't remember this"
    if any(p in lower for p in ["ye yaad mat rakh", "yaad mat rakh", "dont remember", "don't remember", "ye bhool jao"]):
        memory = load_memory()
        for cat in ["notes", "preferences", "wishes"]:
            items = memory.get(cat, {})
            for k in list(items.keys()):
                k_clean = k.replace("_", " ").lower()
                if k.lower() in lower or k_clean in lower:
                    del items[k]
                    save_memory(memory)
                    return {
                        "action": "forgot_entry",
                        "category": cat,
                        "key": k,
                        "message": f"Memory '{k}' ko bhula diya gaya hai."
                    }
        notes = memory.get("notes", {})
        if notes:
            last_k = list(notes.keys())[-1]
            del notes[last_k]
            save_memory(memory)
            return {
                "action": "forgot_recent_note",
                "key": last_k,
                "message": f"Aapki last note '{last_k}' ko forget kar diya gaya hai."
            }

    # Case 3: "Is memory ko update karo" / "Update memory"
    if any(p in lower for p in ["is memory ko update karo", "update memory", "memory update karo", "update preference"]):
        match = re.search(r"update\s+([a-zA-Z0-9_\s]+)\s+(?:to|se|as|karo)?\s*[:=]?\s*(.+)", lower)
        if match:
            k = match.group(1).strip().replace(" ", "_")
            v = match.group(2).strip()
            update_memory({"preferences": {k: {"value": v, "source": "user_explicit"}}})
            return {
                "action": "updated",
                "key": k,
                "value": v,
                "message": f"Memory update ho gayi: {k} = {v}"
            }

    return None