"""Atlas coordinator: the tool schemas the model sees, the argument checks, and the system-prompt slot. Pure Python, no HA import.

tool_specs() returns the tools in the format HA's Ollama integration sends to the model:
  {"type": "function", "function": {"name", "description", "parameters": <JSON schema>}}
The integration builds its voluptuous schemas from the same SPECS, and its test checks that HA's own conversion gives these exact JSON schemas.
Handles in the enums come from the allowed-target map; only enabled ones are offered. AC is not a v1 tool (gated by the owner).
"""
from __future__ import annotations

import re

API_ID = 'atlas_household'
API_NAME = 'Atlas household'


def _enum(handles: dict, kinds: tuple[str, ...]) -> list[str]:
    """Only usable handles are offered: enabled, and for scenes only those whose lights were reviewed (members and expected states frozen)."""
    return sorted(h for h, t in handles.items() if t['kind'] in kinds and t.get('enabled', True) and (t['kind'] != 'scene' or t.get('expect')))


def specs(handles: dict, timer_blinds: bool = False) -> list[dict]:
    """(name, description, properties, required) per tool. One source for the JSON schemas and the voluptuous ones."""
    lights, scenes, blinds = _enum(handles, ('light',)), _enum(handles, ('scene',)), _enum(handles, ('blind',))
    timed = _enum(handles, ('light', 'scene', 'blind') if timer_blinds else ('light', 'scene'))   # reviewed scenes only (see _enum); blinds only if the map enables them
    media = _enum(handles, ('media',))
    out = [
        ('atlas_lights', 'Turn lights on or off, set their brightness, or dim / brighten them one 20% step. Use one handle: a single light, a room ("<room>_lights"), a floor or outside.',
         {'target_handle': {'type': 'string', 'enum': lights, 'description': 'Which lights.'},
          'operation': {'type': 'string', 'enum': ['on', 'off', 'brightness', 'dim', 'brighten']},
          'brightness_percent': {'type': 'integer', 'minimum': 1, 'maximum': 100, 'description': 'Only with on or brightness.'}},
         ['target_handle', 'operation']),
        ('atlas_scene', 'Run a household lighting scene.',
         {'recipe_handle': {'type': 'string', 'enum': scenes}}, ['recipe_handle']),
        ('atlas_blind', 'Open, close or position a blind. Always returns a question to ask first; nothing moves until the person says yes.',
         {'target_handle': {'type': 'string', 'enum': blinds}, 'operation': {'type': 'string', 'enum': ['open', 'close', 'position']},
          'position_percent': {'type': 'integer', 'minimum': 0, 'maximum': 100, 'description': 'Percent open; only with position.'}},
         ['target_handle', 'operation']),
        ('atlas_confirm', "Use right after the person answers yes to the coordinator's question. Pass the confirmation code you were given.",
         {'confirmation': {'type': 'string'}}, ['confirmation']),
        ('atlas_schedule', f"Do something later (up to 24 hours ahead): switch lights on or off{', run a scene' if scenes else ''}{', or open or close a blind (asks for a yes now)' if timer_blinds else ''}. Give in_minutes OR at_time.",
         {'target_handle': {'type': 'string', 'enum': timed}, 'operation': {'type': 'string', 'enum': ['on', 'off', 'open', 'close'] if timer_blinds else ['on', 'off'], 'description': 'A scene uses on.'},
          'in_minutes': {'type': 'integer', 'minimum': 1, 'maximum': 1440}, 'at_time': {'type': 'string', 'description': '24-hour HH:MM, Sydney time; the next one within 24 hours.'}},
         ['target_handle', 'operation']),
        ('atlas_scheduled', "List the timers that are waiting (\"what's scheduled?\").", {}, []),
        ('atlas_cancel', 'Cancel a waiting timer ("cancel that"). Leave task out to cancel the latest one set in this conversation.',
         {'task': {'type': 'string', 'description': 'A task code from atlas_scheduled or atlas_schedule.'}}, []),
        ('atlas_undo', 'Undo the last action ("undo that"), within 10 minutes.',
         {'receipt': {'type': 'string', 'description': 'Optional receipt code; leave out for the latest action.'}}, []),
    ]
    if not scenes:     # no reviewed scene yet: don't offer a scene tool with an empty list
        out = [x for x in out if x[0] != 'atlas_scene']
    if not blinds:     # no enabled blind (phase 1, lights only): don't offer a blind tool with an empty list either
        out = [x for x in out if x[0] != 'atlas_blind']
    if media:      # later v1 group: offered only once a media handle is enabled
        out.insert(3, ('atlas_media', 'Pause, resume, mute, unmute or set the volume (up to 40%) on a media player.',
                       {'target_handle': {'type': 'string', 'enum': media}, 'operation': {'type': 'string', 'enum': ['resume', 'pause', 'mute', 'unmute', 'volume']},
                        'volume_percent': {'type': 'integer', 'minimum': 0, 'maximum': 40}}, ['target_handle', 'operation']))
    return out


def tool_specs(handles: dict, timer_blinds: bool = False) -> list[dict]:
    return [{'type': 'function', 'function': {'name': n, 'description': d,
             'parameters': {'type': 'object', 'properties': p, 'required': r}}} for n, d, p, r in specs(handles, timer_blinds)]   # HA always emits required, even []


_HHMM = re.compile(r'^([01]\d|2[0-3]):[0-5]\d$')


def validate_args(name: str, args: dict, handles: dict, timer_blinds: bool = False) -> str | None:
    """None when args fit the schema exactly; otherwise the first problem. Unknown fields are rejected (no entity ids, services or flags)."""
    spec = next((s for s in specs(handles, timer_blinds) if s[0] == name), None)
    if spec is None:
        return f'unknown tool {name}'
    if not isinstance(args, dict):
        return 'arguments must be an object'
    _, _, props, req = spec
    for k in args:
        if k not in props:
            return f'unknown field {k}'
    for k in req:
        if k not in args:
            return f'missing {k}'
    for k, v in args.items():
        p = props[k]
        if p['type'] == 'string':
            if not isinstance(v, str):
                return f'{k} must be text'
            if 'enum' in p and v not in p['enum']:
                return f'{k}: {v!r} is not allowed'
        elif p['type'] == 'integer':
            if isinstance(v, bool) or not isinstance(v, int):
                return f'{k} must be a whole number'
            if not p.get('minimum', v) <= v <= p.get('maximum', v):
                return f'{k} must be {p["minimum"]}-{p["maximum"]}'
    if name == 'atlas_schedule':
        if ('in_minutes' in args) == ('at_time' in args):
            return 'give exactly one of in_minutes or at_time'
        if 'at_time' in args and not _HHMM.match(args['at_time']):
            return 'at_time must be HH:MM'
    if name == 'atlas_lights' and args.get('operation') in ('off', 'dim', 'brighten') and 'brightness_percent' in args:
        return 'brightness_percent only with on or brightness'
    if name == 'atlas_blind' and args.get('operation') != 'position' and 'position_percent' in args:
        return 'position_percent only with position'
    return None


# The coordinator's part of the system prompt (HA appends an LLM API's prompt after the agent's own prompt).
API_PROMPT = """You can control some things in the house, only through the atlas_ tools.
- Use a tool only for a clear request. If the place or device is unclear (for example "turn the lights off" with no room), ask which one first.
- After a tool call, tell the person what the tool's summary says, in your own short words. Never say something is done unless the tool's status is "done" or "undone".
- "skipped_already": say it was already that way. "not_verified" or "failed": say you couldn't confirm it. "denied": say you can't do that, kindly, with the reason in plain words.
- "needs_confirmation": ask the tool's question exactly, then stop. Only if the person's next reply is a yes, call atlas_confirm with the code.
- "needs_choice": ask which one.
- Timers: "in 10 minutes" or "at 9:30" goes to atlas_schedule (up to 24 hours ahead). "Now" is not a timer: do it straight away. A vague time such as "tomorrow morning" needs a clock time: ask. "This time tomorrow" is in_minutes 1440. "What's scheduled?" is atlas_scheduled. "Cancel that" is atlas_cancel. "Undo that" is atlas_undo.
- Never mention handles, codes or tool names to the person.
Handles you can use:
{handles}"""


def handle_lines(handles: dict) -> str:
    rows, by = [], {}
    for h, t in sorted(handles.items()):
        if t.get('enabled', True) and (t['kind'] != 'scene' or t.get('expect')):
            by.setdefault((t['kind'], t.get('area') or t.get('floor') or ''), []).append(f"{h} ({t['label']})")
    for (kind, place), hs in sorted(by.items()):
        rows.append(f"- {kind}{' / ' + place if place else ''}: " + ', '.join(hs))
    return '\n'.join(rows)


def api_prompt(handles: dict) -> str:
    return API_PROMPT.format(handles=handle_lines(handles))


def system_prompt(atlas_prompt: str, handles: dict) -> str:
    """The slot: the Atlas-side project's Atlas prompt (the agent's own prompt, owned by the Atlas-side project) followed by the coordinator's API prompt, as HA joins them."""
    return atlas_prompt.rstrip('\n') + '\n' + api_prompt(handles)
