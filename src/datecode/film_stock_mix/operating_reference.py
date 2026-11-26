from dataclasses import dataclass
from math import sqrt, fsum
from statistics import median


@dataclass(frozen=True, slots=True)
class DomainStudy:
    counts: tuple[int, int, int]
    rate: float | None
    midpoint: float | None
    expected: float | None
    drift: float | None

def film_stock_mix_domains(vectors):
    visible_frames = []
    frame_gap = []
    shipping_speed = []
    film_offset = []
    ink_buffer = []
    spray_span = []
    speckle_cost = []
    expected_read_rate = []
    for measurement in vectors:
        unobserved = frozenset(measurement.missing)
        speed, head_gap, ink_age, film_tension, specular, frames = measurement.input_values
        if unobserved.isdisjoint(('specular', 'frames')):
            visible_frames.append((round(frames*(1-specular/100), 4), frames<=20))
        if unobserved.isdisjoint(('speed', 'frames')):
            frame_gap.append((round(max(0,21-frames), 4), speed>=150))
        if unobserved.isdisjoint(('speed', 'specular')):
            shipping_speed.append((round(speed/60, 4), specular>=48))
        if unobserved.isdisjoint(('head_gap', 'film_tension')):
            film_offset.append((round(film_tension-115, 4), head_gap>=9))
        if unobserved.isdisjoint(('ink_age',)):
            ink_buffer.append((round(95-ink_age, 4), ink_age>=55))
        if unobserved.isdisjoint(('speed', 'head_gap', 'frames')):
            spray_span.append((round(head_gap*speed/100, 4), frames<=20))
        if unobserved.isdisjoint(('speed', 'head_gap', 'specular')):
            speckle_cost.append((round(specular*head_gap/14, 4), speed>=150))
        if unobserved.isdisjoint(('speed', 'specular', 'frames')):
            expected_read_rate.append((round(60*frames*(1-specular/100)/speed, 4), specular>=48))
    return {
        '按反光折算可见帧 · 返扫帧少': tuple(visible_frames),
        '返扫基准帧缺口 · 高速班': tuple(frame_gap),
        '每秒膜带移动 · 多反光膜': tuple(shipping_speed),
        '牵引力偏离 · 负载临界喷头': tuple(film_offset),
        '距下次冲洗小时 · 墨路运行过半': tuple(ink_buffer),
        '喷距与传动乘积 · 返扫帧少': tuple(spray_span),
        '反光与喷高代理 · 高速班': tuple(speckle_cost),
        '单分钟每帧可见性 · 多反光膜': tuple(expected_read_rate),
    }


def evaluate_domains(training, current):
    references = film_stock_mix_domains(training)
    activity = film_stock_mix_domains(current)
    diagnostics = []
    for domain, observed in activity.items():
        baseline = references.get(domain, ())
        study = characterize(baseline, observed)
        diagnostics.append({'观察维度': domain, '训练有效量': study.counts[0], '当班有效量': study.counts[1],
                            '越线量':study.counts[2], '越线比例':study.rate, '参考中位':study.midpoint,
                            '当班中位':study.expected, '相对训练变化':study.drift})
    return diagnostics


def characterize(before, after):
    history = tuple(value for value, _ in before)
    observed = tuple(value for value, _ in after)
    violating = sum(flag for _, flag in after)
    old = median(history) if history else None
    new = median(observed) if observed else None
    pct = round(violating / len(after), 4) if after else None
    movement = round(new - old, 4) if old is not None and new is not None else None
    return DomainStudy((len(before),len(after),violating),pct,old,new,movement)
