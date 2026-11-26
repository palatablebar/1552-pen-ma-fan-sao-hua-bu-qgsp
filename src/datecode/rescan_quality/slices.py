from collections import defaultdict
from math import fsum, log


def groups_for_rescan_quality(raw):
    speed, head_gap, ink_age, film_tension, specular, frames = raw
    if frames<=20:
        yield '返扫帧少'
    if speed>=150:
        yield '高速班'
    if specular>=48:
        yield '多反光膜'
    if head_gap>=9:
        yield '负载临界喷头'
    if ink_age>=55:
        yield '墨路运行过半'

def poisson_loss(actual, forecast):
    forecast = max(.001,forecast)
    if actual<=0:
        return 2*forecast
    return max(0.,2*(actual*log(actual/forecast)-actual+forecast))


def count_summary(cases, cutoff):
    matched = len(cases)
    expected = fsum(row.estimate for row in cases)
    confirmed = fsum(row.raw.outcome for row in cases)
    open_below = [row for row in cases if row.raw.outcome>=cutoff and row.estimate<cutoff]
    deviance = fsum(poisson_loss(row.raw.outcome,row.estimate) for row in cases)
    shortfall = fsum(row.raw.outcome-row.estimate for row in open_below)
    return {'实绩数':matched,'实绩累计':round(confirmed,2),'预测累计':round(expected,2),
            '均泊松偏差':round(deviance/matched,4) if matched else None,
            '实际越线但未预警':len(open_below),'未预警差额':round(shortfall,2),
            '预测与实绩之比':round(expected/confirmed,4) if confirmed else None}


def replay_slices(points, threshold, *, risk_model=False):
    shifts = {label: [] for label in ('返扫帧少', '高速班', '多反光膜', '负载临界喷头', '墨路运行过半')}
    for row in points:
        if row.raw.observed and row.raw.outcome is not None:
            for phase in groups_for_rescan_quality(row.raw.input_values):
                shifts[phase].append(row)
    return [{'难点':phase,**count_summary(records,threshold)} for phase,records in shifts.items()]
