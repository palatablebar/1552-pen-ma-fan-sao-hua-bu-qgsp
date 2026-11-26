from collections import defaultdict
from hashlib import blake2b
from math import fsum, isfinite

from .contracts import MODEL_NAME, Fit, Prediction
from .baseline import baseline_review
from .diagnostics import explain_defect_stumps
from .boost_model import fit_kernel, score_kernel


def fit_model(history, feature_stamp):
    ordered = tuple(sorted(history,key=lambda sheet:(sheet.day,sheet.key)))
    if not feature_stamp or len(ordered)<8:
        raise ValueError('计数模型缺少八条有效班次或对应特征版本')
    seen = set()
    unit_load = defaultdict(list)
    reg = blake2b(digest_size=8)
    reg.update(repr((feature_stamp,MODEL_NAME)).encode())
    for window in ordered:
        if window.key in seen:
            raise ValueError('计数实绩重复登记')
        if window.outcome is None or not isfinite(window.outcome) or not all(map(isfinite,window.values)):
            raise ValueError('计数目标和输入必须有限')
        if window.outcome < 0:
            raise ValueError('实际件数不可为负')
        seen.add(window.key)
        unit_load[window.cohort].append(window.outcome)
        reg.update(repr((window.key,window.day,window.cohort,window.values,window.outcome)).encode())
    function, readings = fit_kernel(ordered)
    by_period = tuple((f'{station}历史均值',fsum(group)/len(group)) for station,group in sorted(unit_load.items()))
    return Fit(MODEL_NAME,feature_stamp,reg.hexdigest(),function,(*readings,*by_period))


def predict_one(fit, shift):
    expected, balance = score_kernel(fit.parameters,shift)
    if expected<0 or not isfinite(expected):
        raise ArithmeticError('班次件数预测无法使用')
    explanations = tuple(balance)
    if not all(map(isfinite,explanations)):
        raise ValueError('计数模型权重未收敛')
    return Prediction(shift.key,shift.cohort,shift.day,expected,explanations,shift.missing,
                      shift.excursions,shift.outcome,shift.observed,shift.input_values)


def predict(fit, observations, feature_stamp):
    if fit.feature != feature_stamp:
        raise ValueError('实时件数预测依赖锁定的特征版本')
    return tuple(map(lambda shift:predict_one(fit,shift),observations))


def compare_batches(fit, groups, feature_stamp):
    separate = tuple(prediction for group in groups for prediction in predict(fit, group, feature_stamp))
    return separate == predict(fit, (row for group in groups for row in group), feature_stamp)


def inspection_rows(fit, sections):
    """Return model-specific evidence for the current run without retraining."""
    return (explain_defect_stumps(fit, sections.calibration, sections.replay, sections.live)
            + baseline_review(fit, sections.train, sections.replay))
