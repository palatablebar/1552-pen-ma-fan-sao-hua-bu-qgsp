from dataclasses import replace
from hashlib import sha256
from math import fsum, sqrt, isfinite
from statistics import median, quantiles

from .measurement_bands import evaluate_shift
from .contracts import PreparedRuns, FeatureState, FeatureVector, FEATURE_KEYS, RAW_KEYS


def spread(samples):
    refs = sorted(samples)
    if len(refs) < 5:
        center=fsum(refs)/len(refs)
        width=sqrt(fsum((value-center)**2 for value in refs)/len(refs)) or 1.
        return center,width
    q1,_,q3=quantiles(refs,n=4,method='inclusive')
    return median(refs),max(1e-8,(q3-q1)/1.349) if q3>q1 else 1.


def derive(values):
    speed, head_gap, ink_age, film_tension, specular, frames = values
    blur_load = speed*head_gap/100
    ink_dwell = ink_age*(1+head_gap/20)
    reflection = specular/(frames+2)
    transport_stretch = abs(film_tension-115)/60
    unread_buffer = speed/(frames+3)
    return blur_load, ink_dwell, reflection, transport_stretch, unread_buffer


def fill_contract(items):
    defaults = {}
    for name in RAW_KEYS:
        reads = [getattr(row,name) for row in items]
        measured = [reading for reading in reads if reading is not None]
        if not measured:
            raise ValueError(f'{name} 没有可用检测值')
        defaults[name] = median(measured)
    return defaults


def layer_digits(row, reference):
    lookup=tuple(getattr(row,name) for name in RAW_KEYS)
    unknown=tuple(RAW_KEYS[index] for index,value in enumerate(lookup) if value is None)
    values=tuple(reference[index] if current is None else current for index,current in enumerate(lookup))
    return values,unknown


def fit_features(training):
    snapshots=sorted(training,key=lambda sample:(sample.day,sample.received,sample.key))
    default_map=fill_contract(snapshots)
    keys=tuple(default_map[name] for name in RAW_KEYS)
    computed=tuple(derive(layer_digits(note,keys)[0]) for note in snapshots)
    bounds=tuple((min(column),max(column),spread(column)) for column in zip(*computed,strict=True))
    descriptions=(keys,FEATURE_KEYS,bounds,tuple(rec.signature() for rec in snapshots))
    stamp=sha256(repr(descriptions).encode()).hexdigest()[-16:]
    return FeatureState(keys,tuple(band[2][0] for band in bounds),tuple(band[2][1] for band in bounds),
                        tuple(band[0] for band in bounds),tuple(band[1] for band in bounds),stamp)


def numeric_fields(values, reference):
    actual=derive(values)
    data=[]
    warnings=[]
    for position,name in enumerate(FEATURE_KEYS):
        reading=actual[position]
        center=reference.offsets[position]
        ratio=reference.scales[position]
        scale=(reading-center)/ratio
        if not isfinite(scale):
            raise ValueError('分位规范值无效')
        data.append(scale)
        if reading < reference.floor[position]-.7*ratio or reading > reference.ceil[position]+.7*ratio:
            warnings.append(name)
    return tuple(data),actual,tuple(warnings)


def transform(measurement, reference):
    actual, lost=layer_digits(measurement,reference.fill)
    vector, physical, warnings=numeric_fields(actual,reference)
    return FeatureVector(measurement.key,measurement.cohort,measurement.day,vector,physical,lost,warnings,
                         measurement.outcome,measurement.observed,actual)


def transform_all(observations, reference):
    current=[transform(sample,reference) for sample in observations]
    return tuple(current)


def transform_windows(windows, reference):
    return PreparedRuns(*(transform_all(records, reference) for _, records in windows.partitions()))


def feature_evidence(reference):
    return [{'特征': name,'中心':round(center,3),'尺度':round(scale,3),'训练最小':round(low,3),'训练最大':round(high,3)}
            for name,center,scale,low,high in zip(FEATURE_KEYS,reference.offsets,reference.scales,reference.floor,reference.ceil,strict=True)]


def render_interventions(vector, reference, score):
    from .interventions import propose_camera_backlog

    records = []
    estimate = score(vector)
    for adjustment in propose_camera_backlog(vector.input_values, vector.missing):
        position=RAW_KEYS.index(adjustment.field)
        modified=tuple(adjustment.after if position==slot else part for slot,part in enumerate(vector.input_values))
        values, factors, flags = numeric_fields(modified,reference)
        alternative=replace(vector,values=values,factors=factors,input_values=modified,excursions=flags)
        revised=score(alternative)
        records.append({**adjustment.evidence(),'原预测':round(estimate,4),'替换预测':round(revised,4),
                        '预测变化':round(revised-estimate,4),'超训练域':bool(flags)})
    return records


def business_factors(vector):
    from .interventions import measure_print_quality_terms

    return measure_print_quality_terms(vector.input_values).explain()


def measure_review(features):
    return evaluate_shift(features.train, features.live)


def render_joint_experiments(vector, reference, score):
    from .joint import options

    raw = vector.input_values
    base = score(vector)
    replies=[]
    for action in options(raw,vector.missing):
        adjusted = tuple(action.changes[key][1] if key in action.changes else value for key,value in zip(RAW_KEYS,raw,strict=True))
        normalized, measured, signals=numeric_fields(adjusted,reference)
        scenario=replace(vector,values=normalized,input_values=adjusted,factors=measured,excursions=signals)
        replies.append(action.evidence(base,score(scenario),signals))
    return replies
