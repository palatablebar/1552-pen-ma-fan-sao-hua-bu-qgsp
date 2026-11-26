from bisect import bisect_right
from math import sqrt, fsum
from collections import Counter

from .contracts import ShiftReport, ReferenceProfile, DriftBand
from .operating_reference import evaluate_domains


def quantile_breaks(source):
    finite = sorted(set(source))
    interior = finite[1:-1]
    if len(interior) < 4:
        return tuple(interior)
    n = len(interior)
    return tuple(interior[n*k//5] for k in range(1,5))


def counts(series, boundaries):
    distribution = Counter(bisect_right(boundaries, observation) for observation in series)
    return tuple(distribution[position] for position in range(len(boundaries)+1))


def hellinger(before, after):
    if len(before)!=len(after):
        raise ValueError('分布桶位未对齐')
    base = fsum(before)+len(before)*.5
    live = fsum(after)+len(after)*.5
    return sqrt(fsum((sqrt((n+.5)/base)-sqrt((m+.5)/live))**2 for n,m in zip(before,after,strict=True)) / 2)


def fit_baseline(features, signature):
    if not features:
        raise ValueError('训练数据缺少分布量测')
    references = []
    for name, data in zip(('blur_load', 'ink_dwell', 'reflection', 'transport_stretch', 'unread_buffer'),zip(*(field.values for field in features),strict=True),strict=True):
        boundaries = quantile_breaks(data)
        references.append(DriftBand(name,boundaries,counts(data,boundaries)))
    zones = Counter(sample.cohort for sample in features)
    return ReferenceProfile(signature,tuple(references),tuple(zones.items()),len(features))


def scan_current(reference, observed, signature):
    if reference.signature != signature:
        raise ValueError('分布来源变更，须重建参考分布')
    if not observed:
        return ShiftReport(0,(),(),(),'NO_CURRENT_RECORDS')
    recent = tuple(zip(*(note.values for note in observed),strict=True))
    delta = [(guide.name,hellinger(guide.counts,counts(column,guide.edges))) for guide,column in zip(reference.bands,recent,strict=True)]
    unfamiliar = set(note.cohort for note in observed).difference(dict(reference.cohorts))
    review = tuple(sorted(note.key for note in observed if note.cohort in unfamiliar or len(note.excursions)>=2 or len(note.missing)>=2))
    return ShiftReport(len(observed),tuple(sorted(delta,key=lambda p:-p[1])),tuple(sorted(unfamiliar)),review,
                       'SHIFT_REVIEW' if unfamiliar or any(item[1]>=.35 for item in delta) else 'STABLE')



def coverage_by_group(calibration, validation):
    past = Counter(item.cohort for item in calibration)
    current = Counter(item.cohort for item in validation)
    return tuple((key,past[key],current[key]) for key in sorted(past.keys()|current.keys()))


def shift_evidence(current, coverage):
    names = dict(zip(('blur_load', 'ink_dwell', 'reflection', 'transport_stretch', 'unread_buffer'),('高速喷头扩散', '墨路驻留', '反光与可见帧', '膜带张力偏离', '读码余量'),strict=True))
    new = set(current.novel)
    table = [{'检测项':names.get(field,field), 'Hellinger 距离':round(evidence,4)} for field,evidence in current.signals]
    table.extend({'检测项':unit, '校准单数':old,'本班单数':seen,'现场': '未登记' if unit in new else '已登记'}
                 for unit,old,seen in coverage)
    return table


def shop_floor_shift(reference, current):
    measures = evaluate_domains(reference,current)
    return sorted(measures,key=lambda line:(-line['越线量'],line['观察维度']))
