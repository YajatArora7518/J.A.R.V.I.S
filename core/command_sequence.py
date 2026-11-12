"""Bounded explicit sequences through the existing verified command pipeline."""
import re
from core.intent_router import classify_intent


def split_sequence(text):
    if text.startswith('[FILE_UPLOADED] '):
        return None
    quoted = list(re.finditer(r'"(?:\\.|[^"\\])*"|\x27[^\x27]*\x27', text))
    cuts = [m for m in re.finditer(r'\s*(?:;|\b(?:and then|then|phir|fir|aur|and|फिर|उसके बाद)\b)\s*', text, re.I)
            if not any(q.start() <= m.start() < q.end() for q in quoted)]
    parts, start = [], 0
    for cut in cuts:
        parts.append(text[start:cut.start()].strip(' ,'))
        start = cut.end()
    parts.append(text[start:].strip(' ,'))
    if len(parts) < 2 or not all(parts):
        return None
    # Do not split ordinary prose or a list of app names.
    for part in parts:
        intent = classify_intent(part).get('intent')
        if intent in {'DRAFT_TEXT', 'COMPLEX_PLANNER'}:
            return None
        if intent == 'OTHER':
            from core.command_pipeline import _parse_power_request
            if not _parse_power_request(part):
                return None
    return parts


def execute_sequence(text, source, execute, progress=None):
    parts = split_sequence(text)
    if not parts:
        return None
    if len(parts) > 8:
        return {'success': False, 'verified': False, 'status': 'SEQUENCE_DETAILS_REQUIRED',
                'message': 'Ek request mein 8 tak clear steps do, bhai.'}
    from actions.social_chat import parse_social_command
    for part in parts:
        social = parse_social_command(part, include_whatsapp=True)
        literal_quotes = [q.group(0)[1:-1] for q in re.finditer(r'"[^"\n]+"|\x27[^\x27\n]+\x27', part)]
        send = (social and social.get('action') == 'send') or classify_intent(part).get('intent') == 'WHATSAPP_MESSAGE'
        quoted_payload = bool(literal_quotes) and (not social or social.get('message_text', '').strip('"\x27') in literal_quotes)
        if send and not quoted_payload:
            return {'success': False, 'verified': False, 'status': 'SEQUENCE_DETAILS_REQUIRED',
                    'message': 'Multiple steps mein message ka exact text quotes mein do, taaki agla command message mein na jaye.'}
    return run_sequence_steps(parts, source, execute, progress)


def run_sequence_steps(parts, source, execute, progress=None, previous=None):
    """Resume only remaining commands; previously verified steps are never replayed."""
    results = list(previous or [])
    offset = len(results)
    total = offset + len(parts)
    for local_index, part in enumerate(parts, 1):
        index = offset + local_index
        if progress:
            progress(f'Step {index}/{total}: {part}')
        result = execute(part, source=source)
        results.append({'step': index, 'command': part, 'result': result})
        if not result.get('success') or not result.get('verified') or result.get('requires_confirmation'):
            return {**result, 'success': False, 'verified': False, 'action': 'command_sequence',
                    'message': f'Step {index}/{total} par ruka: ' + str(result.get('message', 'Result verify nahi hua.'))
                               + ('\nBaaki steps abhi nahi chale: ' + '; '.join(parts[local_index:]) if parts[local_index:] else ''),
                    'steps': results, 'remaining_commands': parts[local_index:], 'status': result.get('status', 'SEQUENCE_STOPPED')}
    from core.voice_conversation import natural_action_reply
    return {'success': True, 'verified': True, 'action': 'command_sequence', 'status': 'COMPLETED',
            'message': '\n'.join(f"{r['step']}. {natural_action_reply(r['result'])}" for r in results), 'steps': results}
