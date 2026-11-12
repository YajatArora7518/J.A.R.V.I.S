"""Explicit inspect/save/forget commands over the existing personal memory store."""
import re


def handle_memory_command(text):
    from memory.memory_manager import load_memory, remember, forget, query_memory
    clean = text.strip()
    if clean.lower() in {'memory dikhao', 'meri memory dikhao', 'what do you remember', 'saved memory dikhao'}:
        message = query_memory('') or 'Abhi koi personal memory saved nahi hai.'
    else:
        save = re.fullmatch(r'(?:yaad rakh|remember)\s*:\s*([\w -]{1,64})\s*:\s*(.{1,700})', clean, re.I)
        remove = re.fullmatch(r'(?:bhool ja|bhool jao|forget memory)\s*:\s*([\w -]{1,64})', clean, re.I)
        search = re.fullmatch(r'memory mein\s+(.{1,100})', clean, re.I)
        if save:
            key, value = save.groups()
            key = key.strip().replace(' ', '_')
            remember(key, value.strip())
            stored = load_memory().get('notes', {}).get(key, {})
            if stored.get('value') != value.strip():
                return {'success': False, 'verified': False, 'message': 'Memory save verify nahi hua.'}
            message = f'Yaad rakh liya: {key.replace("_", " ")} — {value.strip()}'
        elif remove:
            key = remove.group(1).strip().replace(' ', '_')
            memory = load_memory()
            exact = [(category, name) for category, values in memory.items() if isinstance(values, dict)
                     for name in values if name.lower() == key.lower()]
            if len(exact) != 1:
                return {'success': False, 'verified': False, 'message': 'Memory ka exact unique naam do; pehle "memory dikhao" bol sakte ho.'}
            category, name = exact[0]
            forget(name, category=category)
            if name in load_memory().get(category, {}):
                return {'success': False, 'verified': False, 'message': 'Memory delete verify nahi hua.'}
            message = f'Theek hai, {name.replace("_", " ")} memory se hata diya.'
        elif search:
            message = query_memory(search.group(1))
        else:
            return None
    return {'success': True, 'verified': True, 'action': 'personal_memory', 'message': message}
