"""Explicit conversation controls; never infer pausing from ordinary sentences."""
import re
from core.intent_router import normalize_command_prefix


def conversation_control(text):
    clean = normalize_command_prefix(text or '').lower().strip(' ,.!?।')
    if clean in {'wait', 'wait kar', 'wait karo', 'ab wait kar', 'baad mein baat karte hain',
                 'baad me baat karte hain', 'pause conversation', 'stop listening',
                 'wake word ka wait kar', 'अभी रुको', 'बाद में बात करते हैं', 'सुनना बंद करो'}:
        return 'pause'
    if clean in {'baat karte hain', 'sun raha hai', 'keep listening', 'continue conversation',
                 'start listening', 'बात करते हैं', 'सुनते रहो'}:
        return 'resume'
    return None


def natural_action_reply(result):
    """Change only presentation of an exact verified app result, never payloads."""
    message = str(result.get('message', ''))
    if result.get('success') and result.get('verified'):
        match = re.fullmatch(r'Opened ([^\n]+)\.', message)
        if match:
            return f'{match.group(1)} khol diya, bhai.'
        match = re.fullmatch(r'The answer is ([+-]?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)\.', message)
        if match:
            return f'Iska jawab {match.group(1)} hai, bhai.'
    return message
