from collections import Counter
from math import isfinite


def accountable_plan(rows, actual_balance, starting_capacity):
    seen = set()
    counts = Counter()
    total = 0
    for row in rows:
        if row['key'] in seen:
            raise ArithmeticError('复核凭证的关联单号不唯一')
        key = row['key']
        seen.add(key)
        state = row['state']
        counts[state] += 1
        if state == '已分派':
            total += row['cost']
        if not isfinite(row['estimate']):
            raise ArithmeticError('非有限估计不能签发')
    if total + actual_balance != starting_capacity:
        raise ArithmeticError('处置清册与工位余额不符')
    return counts, total


def register_coder_verification(measurements, estimate):
    speed = measurements['speed']
    head_gap = measurements['head_gap']
    ink_age = measurements['ink_age']
    film_tension = measurements['film_tension']
    specular = measurements['specular']
    frames = measurements['frames']
    return {
        '按反光折算可见帧': round(frames*(1-specular/100), 3),
        '每秒膜带移动': round(speed/60, 3),
        '反光与喷高代理': round(specular*head_gap/14, 3),
        '单分钟每帧可见性': round(60*frames*(1-specular/100)/speed, 3),
        '复核代价指标': round((speed/110)*(1+specular/100)+max(0,22-frames)/15, 4),
    }


def document_control(rows):
    register = []
    for row in rows:
        if row['state'] not in {'已分派', '暂停', '人工判读'}:
            continue
        note = register_coder_verification(row['measurements'], row['estimate'])
        register.append({'单号': row['key'], '区段': row['zone'], '处置': row['state'], **note})
    return register
