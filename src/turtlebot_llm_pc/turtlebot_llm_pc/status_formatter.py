"""RobotStatus.msg -> 문자열(프롬프트용) 변환"""


def status_to_string(status) -> str:
    t = status.type
    r = status.result

    if t == 'search':
        return f'search({status.target}, result={r})'
    elif t == 'move':
        return f'move(dir={status.dir}, result={r})'
    elif t == 'perform':
        return f'perform(action={status.action}, result={r})'
    elif t == 'stop':
        return f'stop(result={r})'
    elif t == 'resume':
        return f'resume(result={r})'
    else:
        raise ValueError(f'알 수 없는 액션 타입: {t}')
