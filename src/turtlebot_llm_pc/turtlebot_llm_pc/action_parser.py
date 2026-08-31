
"""
command_parser_node에서 사용하는 액션 문자열 파서

입력 ex: "search(dog) > move(dir=left, speed=fast) > stop(time=3)"
출력: dict 리스트. 각 dict는 Action.msg 필드와 1:1 대응
"""

import re

def parse_action_string(text: str):
    text = text.strip()
    if not text:
        return []

    parts = [p.strip() for p in text.split('>')]
    actions = []

    for part in parts:
        if not part:
            continue

        m = re.match(r'^(\w+)\((.*)\)$', part)
        if m:
            type_name, args_str = m.group(1), m.group(2)
        elif part == 'resume':
            type_name, args_str = 'resume', ''
        else:
            raise ValueError(f'파싱 불가능한 액션: "{part}" (원문 전체: "{text}")')

        action = {
            'type': type_name,
            'target': '',
            'dir': '',
            'speed': '',
            'action': '',
            'time': -1,
            'repeat': -1,
        }

        if type_name == 'search':
            # search만 key= 없이 값 하나 (ex: search(dog))
            action['target'] = args_str.strip()
        elif args_str:
            for kv in args_str.split(','):
                kv = kv.strip()
                if not kv or '=' not in kv:
                    continue
                k, v = kv.split('=', 1)
                k, v = k.strip(), v.strip()
                if k in ('time', 'repeat'):
                    action[k] = int(v)
                elif k in ('dir', 'speed', 'action'):
                    action[k] = v

        actions.append(action)

    return actions
