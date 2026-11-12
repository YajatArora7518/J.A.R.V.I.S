from core.intent_router import classify_intent

tests = [
    'open Notepad',
    'open "Notepad"',
    'open Chrome',
    'open Calculator',
    'open File Explorer',
    'Jarvis, open Notepad',
    'Jarvis open Notepad',
    'please open Notepad',
    'Notepad kholo',
    'Chrome kholo',
]

for t in tests:
    res = classify_intent(t)
    print(f"{t!r:30} --> intent={res.get('intent')}, tool={res.get('tool')}, target={res.get('target')!r}")
