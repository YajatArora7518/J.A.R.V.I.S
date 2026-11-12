import sys, os
sys.path.insert(0, os.path.abspath("."))
from core.intent_router import classify_intent

cmds = [
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
    'open SomeApplicationThatDefinitelyDoesNotExist123'
]
for c in cmds:
    res = classify_intent(c)
    print(f"{c:50} | intent: {res.get('intent', ''):20} | target: {res.get('target', ''):25} | tool: {res.get('tool')}")
