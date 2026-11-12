"""Local daily goals, check-in history and user-confirmed timetable prompts.

Uses the existing task and college stores. No screen/camera capture or external sends.
"""
from datetime import datetime, timedelta
import json
import logging
from pathlib import Path
import random
import re
import threading
import time

from agent.task_manager import default_task_manager
from core.intent_router import normalize_command_prefix

ROOT = Path(__file__).resolve().parent.parent
logger = logging.getLogger('JARVIS.DailyPlanner')


def desktop_idle_seconds():
    """Read activity age only; no keys, screen content or app input."""
    try:
        import ctypes
        from ctypes import wintypes
        class LastInput(ctypes.Structure):
            _fields_ = [('size', wintypes.UINT), ('tick', wintypes.DWORD)]
        value = LastInput()
        value.size = ctypes.sizeof(value)
        if not ctypes.windll.user32.GetLastInputInfo(ctypes.byref(value)):
            return None
        return ((ctypes.windll.kernel32.GetTickCount() - value.tick) & 0xffffffff) / 1000
    except Exception:
        return None


def parse_timetable(text):
    """Explicit complete rows, e.g. Monday 09:00-10:00 C programming."""
    days = {day.lower(): day for day in ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']}
    clock = r'\d{1,2}:\d{2}(?:\s*[ap]m)?|\d{1,2}\s*[ap]m'
    rows = []
    for line in re.split(r'[;\n]+', text.strip()):
        if not line.strip():
            continue
        match = re.fullmatch(rf'\s*(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)\s*:?\s*({clock})\s*(?:-|–|to)\s*({clock})\s*:?\s+(.+?)\s*', line, re.I)
        if not match:
            raise ValueError('Har row aise likho: Monday 09:00-10:00 C programming. Rows alag line ya ; se do.')
        values = []
        for raw in match.group(2, 3):
            raw = raw.replace(' ', '').upper()
            fmt = '%I:%M%p' if ':' in raw and raw.endswith(('AM', 'PM')) else '%I%p' if raw.endswith(('AM', 'PM')) else '%H:%M'
            values.append(datetime.strptime(raw, fmt).strftime('%H:%M'))
        start, end = values
        if start >= end:
            raise ValueError('Class ka end time start ke baad hona chahiye.')
        day = days[match[1].lower()]
        if any(row['day'] == day and start < row['end'] and row['start'] < end for row in rows):
            raise ValueError(f'{day} mein class timings overlap kar rahi hain; pehle sahi timings batao.')
        rows.append({'day': day, 'start': start, 'end': end, 'subject': match[4][:160]})
    if not rows:
        raise ValueError('Timetable ki actual rows bhejo; sample timetable ko tumhara nahi maanunga.')
    return rows


class DailyPlanner:
    def __init__(self, path=None, tasks=None):
        self.path = Path(path or ROOT / 'config' / 'daily_planner.json')
        self.tasks = tasks or default_task_manager
        self.lock = threading.RLock()
        self.started_at = 0
        self.return_gap = 0
        self.last_user_at = 0
        self.last_save_at = 0
        self.load_error = None
        self.state = {'settings': {'enabled': True, 'casual_per_day': 1, 'review_time': '21:00'},
                      'days': {}, 'last_seen': 0, 'paused_until': 0, 'pending': None}
        if self.path.exists():
            try:
                data = json.loads(self.path.read_text(encoding='utf-8'))
                self.state.update(data)
                if not isinstance(self.state['days'], dict) or not isinstance(self.state['settings'], dict):
                    raise ValueError('Invalid daily planner structure')
                self.state['settings'] = {'enabled': True, 'casual_per_day': 1, 'review_time': '21:00', **self.state['settings']}
            except (OSError, ValueError, TypeError) as error:
                self.load_error = str(error)
                logger.warning('Daily planner store could not be loaded; preserving file: %s', error)

    def _save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.state['days'] = dict(sorted(self.state['days'].items())[-30:])
        temporary = self.path.with_suffix('.tmp')
        temporary.write_text(json.dumps(self.state, ensure_ascii=False, indent=2), encoding='utf-8')
        temporary.replace(self.path)

    def _day(self, now):
        return self.state['days'].setdefault(now.date().isoformat(), {'goals': [], 'notes': [], 'delivered': {}})

    def start_session(self, timestamp=None):
        if self.load_error:
            return
        with self.lock:
            now = timestamp if timestamp is not None else time.time()
            previous = self.state.get('last_user_at') or self.state.get('last_seen', 0)
            self.return_gap = max(0, now - previous) if previous else 0
            self.started_at = now
            self.state['last_seen'] = now
            self.state['pending'] = None  # A stale question is not a current reply slot.
            self._save()

    def heartbeat(self, timestamp=None):
        with self.lock:
            if not self.started_at:
                return
            now = timestamp if timestamp is not None else time.time()
            if now - self.last_save_at >= 60:
                self.state['last_seen'] = now
                self.last_save_at = now
                self._save()

    def note_interaction(self, text, timestamp=None):
        with self.lock:
            self.last_user_at = timestamp if timestamp is not None else time.time()
            previous = self.state.get('last_user_at', 0)
            if previous and self.last_user_at - previous >= 4 * 3600:
                self.return_gap = self.last_user_at - previous
            self.state['last_user_at'] = self.last_user_at
            if not self.load_error:
                self._save()
        from agent.emotional_context import get_emotional_context
        get_emotional_context().detect_state(normalize_command_prefix(text))

    def _note(self, kind, text, now):
        day = self._day(now)
        day['notes'].append({'kind': kind, 'text': text[:1500], 'at': now.isoformat(timespec='seconds')})
        pending = self.state.get('pending')
        if pending and pending['kind'] == kind and pending.get('question'):
            day['notes'][-1]['question'] = pending['question']
        day['notes'] = day['notes'][-40:]

    def _goals(self, now):
        ids = set(self._day(now)['goals'])
        return [task for task in self.tasks._load_tasks() if task.id in ids]

    def _plan_text(self, now):
        goals = self._goals(now)
        if not goals:
            return 'Aaj ke 2–3 main kaam kya hain? Alag line ya comma se batao; phir manageable plan banate hain.'
        lines = ['Aaj ka plan:']
        for task in goals:
            flag = '✓' if task.status == 'COMPLETED' else '○'
            lines.append(f'{flag} {task.title}')
        lines.append(f'{sum(t.status == "COMPLETED" for t in goals)}/{len(goals)} complete. Agla chhota step kya rakhna hai?')
        return '\n'.join(lines)

    def _save_goals(self, content, now):
        entries = [re.sub(r'^\s*(?:[-•]|\d+[.)])\s*', '', item).strip() for item in re.split(r'[\n;,]+', content)]
        entries = [item for item in entries if item]
        if not entries or len(entries) > 7:
            return 'Ek din ke liye 1–7 clear kaam batao; pehle 2–3 priorities rakhna practical rahega.'
        for title in entries:
            task, _ = self.tasks.add_task(title=title[:160], description=content[:1500], category='daily', due_at=now.date().isoformat())
            day = self._day(now)
            if task.id not in day['goals']:
                day['goals'].append(task.id)
        self.state['pending'] = None
        self._save()
        return self._plan_text(now)

    def handle_command(self, text, intent='OTHER', now=None):
        raw = normalize_command_prefix(text).strip()
        lower = raw.casefold().strip(' .!?')
        now = now or datetime.now()
        stamp = now.timestamp()
        with self.lock:
            if self.load_error:
                if re.search(r'plan|check.in|timetable|progress', lower):
                    return {'success': False, 'verified': False, 'message': 'Daily planner ki saved file read nahi ho rahi. Usse repair karna padega; purani file preserve hai.', 'status': 'PLANNER_STORE_UNAVAILABLE'}
                return None
            result = None
            if lower in ('aaj mat pooch', 'aaj check-in mat kar', 'check-ins band karo', 'stop check-ins', 'check in band karo'):
                self.state['paused_until'] = (now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)).timestamp()
                self.state['pending'] = None
                result = 'Theek hai, aaj ke check-ins pause kar diye. Zaroorat ho to khud bula lena.'
            elif lower in ('check-ins chalu karo', 'resume check-ins', 'check in chalu karo'):
                self.state['paused_until'] = 0
                result = 'Check-ins wapas chalu. Busy ho to baad mein bol dena.'
            elif lower in ('baad mein', 'abhi nahi', 'busy hun', 'busy hoon', 'later', 'not now', 'rehne do', 'stop asking'):
                self.state['paused_until'] = stamp + 3600
                self.state['pending'] = None
                result = 'Theek hai, ek ghante tak nahi tokunga.'
            else:
                timing = re.fullmatch(r'(?:daily review|evening check|progress check)\s+(\d{1,2}:\d{2})\s*(?:pe|par|at)?\s*(?:rakho|set karo)?', raw, re.I)
                plan = re.fullmatch(r'(?:aaj ka plan|today\x27s plan|today plan|daily plan|aaj ke goals|mera plan)\s*[:=-]\s*(.+)', raw, re.I | re.S)
                timetable = re.fullmatch(r'(?:remember|save|yaad rakho)\s+(?:my\s+|mera\s+)?timetable\s*[:=-]\s*(.+)', raw, re.I | re.S)
                progress = re.fullmatch(r'(?:aaj ka progress|progress update|aaj kya kiya)\s*[:=-]\s*(.+)', raw, re.I | re.S)
                completed = re.fullmatch(r'(?:done|complete|completed)\s*:\s*(.+)', raw, re.I | re.S)
                if timing:
                    try:
                        self.state['settings']['review_time'] = datetime.strptime(timing[1], '%H:%M').strftime('%H:%M')
                        result = f"Evening progress check {self.state['settings']['review_time']} par rakh diya, jab app khula aur tum free ho."
                    except ValueError:
                        result = 'Time 24-hour format mein do, jaise 21:00.'
                elif plan:
                    result = self._save_goals(plan[1], now)
                elif timetable:
                    message, saved = self._save_timetable(timetable[1])
                    return {'success': saved, 'verified': saved, 'message': message, 'action': 'daily_planner',
                            'status': 'TIMETABLE_SAVED' if saved else 'TIMETABLE_DETAILS_REQUIRED'}
                elif progress:
                    self._note('progress', progress[1], now)
                    self.state['pending'] = None
                    result = 'Progress note save kar li. Kaunsa planned task poora hua? `done: exact title` likho ya bolo.'
                elif completed:
                    matches = [task for task in self._goals(now) if task.title.casefold() == completed[1].strip().casefold() or task.id == completed[1].strip()]
                    if len(matches) == 1:
                        self.tasks.mark_completed(matches[0].id)
                        result = self._plan_text(now)
                    else:
                        result = 'Aaj ke plan mein woh exact task nahi mila. Title batao; andaze se complete nahi karunga.'
                elif lower in ('aaj ka plan', 'aaj ka plan banao', 'daily planner', 'daily plan', 'today plan', "today's plan", 'aaj kya karna hai', 'aaj ka progress', 'progress batao'):
                    result = self._plan_text(now)
                    if not self._goals(now):
                        self.state['pending'] = {'kind': 'plan', 'expires_at': stamp + 900}
                else:
                    pending = self.state.get('pending')
                    eligible = intent == 'OTHER' and raw and not re.search(r'[?？]|\b(?:kya|kaise|what|why|how|open|send|call|delete|shutdown|restart|stop|cancel)\b|क्या|कैसे|क्यों', lower)
                    if pending and stamp <= pending['expires_at'] and eligible:
                        kind = pending['kind']
                        if re.search(r'\b(?:tired|thak|neend|sad|udaas|stressed|tension)\b|mood off', lower):
                            self._note('feeling', raw, now)
                            self.state['pending'] = None
                            self.state['paused_until'] = stamp + 1800
                            result = 'Samjha, plan ko abhi side mein rakhte hain. Batana chahe to bata, kya hua?'
                        elif kind == 'plan' and lower not in ('haan', 'yes', 'ok', 'okay', 'nahi', 'no'):
                            result = self._save_goals(raw, now)
                        elif kind in ('return', 'casual', 'review', 'class'):
                            self._note(kind, raw, now)
                            self.state['pending'] = None
                            if kind == 'return':
                                self.state['pending'] = {'kind': 'plan', 'expires_at': stamp + 900}
                                result = 'Samjha. Aaj ke 2–3 main kaam kya rakhne hain?'
                            elif kind == 'review':
                                result = 'Update save kar li. Jo reh gaya usmein blocker kya tha—time, confusion ya kuch aur?'
                            elif kind == 'class':
                                result = 'Theek hai, class wala update yaad rakh liya.'
                            else:
                                result = 'Samjha. Bata, usmein sabse achha ya sabse irritating kya raha?'
            if result is None:
                return None
            self._save()
            return {'success': True, 'verified': True, 'action': 'daily_planner', 'message': result, 'status': 'PLANNER_RESPONSE'}

    def _save_timetable(self, text):
        try:
            rows = parse_timetable(text)
        except ValueError as error:
            return str(error), False
        from actions.college_mode import load_college_config, save_college_config
        config = load_college_config()
        table = {}
        for row in sorted(rows, key=lambda row: (row['day'], row['start'])):
            table.setdefault(row['day'], []).append({'time': f"{row['start']} - {row['end']}", 'course': row['subject']})
        config['timetable'] = table
        config['timetable_confirmed_by_user'] = True
        config['timetable_saved_at'] = datetime.now().isoformat(timespec='seconds')
        if not save_college_config(config):
            return 'Timetable save nahi hua; retry se pehle file access check karna padega.', False
        from actions.college_schedule import schedule_query_engine
        schedule_query_engine.store.reload()
        return f'Tumhari {len(rows)} class timings save kar li. Usi timetable se class-time check-ins poochhunga.', True

    def next_check_in(self, now=None, idle_seconds=None):
        now = now or datetime.now()
        stamp = now.timestamp()
        with self.lock:
            if self.load_error or not self.started_at or not self.state['settings']['enabled'] or stamp < self.state.get('paused_until', 0):
                return None
            if not 7 <= now.hour < 23 or stamp - self.started_at < 60 or stamp - self.last_user_at < 120:
                return None
            if idle_seconds is None or not 15 <= idle_seconds <= 300:
                return None
            pending = self.state.get('pending')
            if pending and stamp <= pending['expires_at']:
                return None
            day = self._day(now)
            sent = day['delivered']
            if sent and stamp - max(sent.values()) < 1800:
                return None
            if self.return_gap >= 4 * 3600 and 'return' not in sent:
                return {'key': 'return', 'kind': 'return', 'message': 'Kaafi der se baat nahi hui. Busy tha ya break liya? Kya chal raha tha?'}
            if now.strftime('%H:%M') >= self.state['settings']['review_time'] and 'review' not in sent:
                return {'key': 'review', 'kind': 'review', 'message': 'Aaj ka din kaisa gaya? Jo plan kiya tha, usmein kitna hua aur kya atka?'}
            if 'plan' not in sent and not self._goals(now) and now.hour < 18:
                return {'key': 'plan', 'kind': 'plan', 'message': 'Chal, aaj ke 2–3 main kaam bata. Padhai ke saath break ka bhi time rakhenge.'}
            class_event = self._class_event(now, sent)
            if class_event:
                return class_event
            if 'casual' not in sent and self.state['settings'].get('casual_per_day', 1) and 10 <= now.hour < 21 and stamp - self.started_at >= 2700:
                return {'key': 'casual', 'kind': 'casual', 'message': random.choice([
                    'Sab theek hai, bhai? Mann ho to bata, kya chal raha hai?',
                    'Oye, kya chal raha hai? Aaj kuch interesting hua ya wahi routine?',
                    'Do minute free hai? Bata, din kaisa ja raha hai?',
                    'Bhai, padhai ke alawa kya scene hai aaj?'
                ])}
            return None

    def _class_event(self, now, sent):
        from actions.college_mode import load_college_config
        config = load_college_config()
        if not config.get('timetable_confirmed_by_user'):
            return None
        for cls in config.get('timetable', {}).get(now.strftime('%A'), []):
            try:
                start, end = [datetime.strptime(value.strip(), '%H:%M').time() for value in cls['time'].split('-')]
            except (ValueError, KeyError):
                continue
            start_dt, end_dt = datetime.combine(now.date(), start), datetime.combine(now.date(), end)
            key = f"class:{cls['course']}:{start}"
            if start_dt - timedelta(minutes=5) <= now < end_dt and key not in sent:
                return {'key': key, 'kind': 'class', 'message': f"Timetable mein {cls['course']} {cls['time']} par hai. Class mein ho, online hai, ya aaj nahi gaye?"}
        return None

    def mark_delivered(self, event, now=None):
        now = now or datetime.now()
        with self.lock:
            self._day(now)['delivered'][event['key']] = now.timestamp()
            self.state['pending'] = {'kind': event['kind'], 'question': event.get('message', ''), 'expires_at': now.timestamp() + 900}
            self._save()

    def prompt_context(self, now=None):
        if self.load_error:
            return 'Daily planner memory unavailable; never invent a saved plan.'
        now = now or datetime.now()
        with self.lock:
            goals = self._goals(now)
            notes = self._day(now)['notes'][-3:]
            lines = [f"Today's saved goals: {[(t.title, t.status) for t in goals]}"]
            if notes:
                lines.append(f'Recent user-reported check-ins: {notes}')
            pending = self.state.get('pending')
            if pending and now.timestamp() <= pending['expires_at']:
                lines.append(f"Awaiting user reply to a {pending['kind']} check-in; use assistant_command to record their exact reply.")
            return '\n'.join(lines)


_planner = None
_planner_lock = threading.Lock()
def get_daily_planner():
    global _planner
    if _planner is None:
        with _planner_lock:
            if _planner is None:
                _planner = DailyPlanner()
    return _planner
