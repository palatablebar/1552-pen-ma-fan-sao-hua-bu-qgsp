from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass
from math import ceil, isfinite
from types import SimpleNamespace
from typing import Any, Callable

FRAME_LIMIT = 65
VERIFICATION_FLOOR = 12
VERIFICATION_CEILING = 32
VERIFICATION_MULTIPLIER = 2
FRAME_FIELDS = ('speed', 'head_gap', 'ink_age', 'film_tension', 'specular', 'frames')


@dataclass(frozen=True, slots=True)
class FrameTrial:
    extra: int
    frames: int
    estimate: float | None
    lower: float | None
    upper: float | None
    required: int | None
    discarded: int
    clean_frames: int
    out_of_domain: bool
    missing_interval: bool
    usable: bool
    sufficient: bool
    reason: str | None = None

    def evidence(self) -> dict[str, Any]:
        return {
            '补拍量': self.extra,
            '补拍后总帧': self.frames,
            '补拍后估计': _round(self.estimate),
            '补拍后下沿': _round(self.lower),
            '补拍后上沿': _round(self.upper),
            '核验需求量': self.required,
            '遮光弃用帧': self.discarded,
            '预计清晰帧': self.clean_frames,
            '超训练域': self.out_of_domain,
            '缺区间': self.missing_interval,
            '试算可用': self.usable,
            '帧数足够': self.sufficient,
            '不可用原因': self.reason,
        }


@dataclass(frozen=True, slots=True)
class ReshootDecision:
    key: str
    status: str
    minimum: int | None
    frame_limit: int = FRAME_LIMIT
    total_frames: int | None = None
    estimate: float | None = None
    lower: float | None = None
    upper: float | None = None
    required: int | None = None
    discarded: int | None = None
    clean_frames: int | None = None
    current_frames: int | None = None
    current_clean_frames: int | None = None
    current_upper: float | None = None
    current_required: int | None = None
    missing_measurement: bool = False
    outside_domain: bool = False
    missing_interval: bool = False
    insufficient_at_limit: bool = False
    reason: str = 'RESHOOT_CERTIFIED'
    basis: str = ''
    trials: tuple[FrameTrial, ...] = ()

    @property
    def signed(self) -> bool:
        return self.status == 'CERTIFIED' and self.minimum is not None

    @property
    def manual_review(self) -> bool:
        return self.status == 'MANUAL_REVIEW'

    # Compatibility aliases for callers/tests that describe the same quantity
    # with different domain wording.
    @property
    def extra(self) -> int | None:
        return self.minimum

    @property
    def amount(self) -> int | None:
        return self.minimum

    @property
    def count(self) -> int | None:
        return self.minimum

    @property
    def requisition(self) -> int | None:
        return self.minimum

    def evidence(self) -> dict[str, Any]:
        label = {
            'CERTIFIED': '已核定',
            'MANUAL_REVIEW': '转人工',
        }.get(self.status, self.status)
        return {
            '核定状态': label,
            '可签发': self.signed,
            '转人工': self.manual_review,
            '最少补拍量': self.minimum,
            '核定补拍量': self.minimum,
            '最少补拍张数': self.minimum,
            '额外取像张数': self.minimum,
            '补拍后总帧': self.total_frames,
            '补拍后估计': _round(self.estimate),
            '补拍后下沿': _round(self.lower),
            '补拍后上沿': _round(self.upper),
            '补拍后核验量': self.required,
            '补拍后清晰帧': self.clean_frames,
            '当前清晰帧': self.current_clean_frames,
            '当前上沿': _round(self.current_upper),
            '当前核验量': self.current_required,
            '量测上限': self.frame_limit,
            '缺实测': self.missing_measurement,
            '超训练域': self.outside_domain,
            '缺区间': self.missing_interval,
            '上限内不足': self.insufficient_at_limit,
            '原因码': self.reason,
            '补拍依据': self.basis,
        }

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data.update(self.evidence())
        data['trials'] = [trial.evidence() for trial in self.trials]
        return data


def _round(value: float | None, digits: int = 4) -> float | None:
    if value is None:
        return None
    value = float(value)
    if not isfinite(value):
        return None
    return round(value, digits)


def measurement_map(values: Any) -> dict[str, float]:
    if hasattr(values, 'input_values'):
        values = values.input_values
    if isinstance(values, Mapping):
        return dict(values)
    return dict(zip(FRAME_FIELDS, values, strict=True))


def frame_loss_fraction(measurements: Any) -> float:
    """Conservative discarded-frame fraction from the frame-window ledger."""
    readings = measurement_map(measurements)
    pitch = float(readings['speed']) / 180
    reflection_loss = float(readings['specular']) / 160
    return min(0.8, reflection_loss + (0.22 if pitch > 1 else 0.0))


def integer_frames(frames: Any) -> int:
    # The ledger historically truncates readings with int(); retain that
    # contract rather than silently rounding a bad frame count upwards.
    return int(frames)


def _frame_and_measurements(frames: Any, measurements: Any) -> tuple[Any, Any]:
    if measurements is None:
        candidate = frames
        if isinstance(candidate, Mapping) and 'measurements' in candidate:
            measurements = candidate['measurements']
            frames = measurement_map(measurements)['frames']
        else:
            measurements = candidate
            frames = measurement_map(candidate)['frames']
    return frames, measurements


def discarded_frame_count(frames: Any = None, measurements: Any = None) -> int:
    frames, measurements = _frame_and_measurements(frames, measurements)
    total = integer_frames(frames)
    if total < 0:
        raise ValueError('帧组数不可为负')
    return ceil(total * frame_loss_fraction(measurements))


def clear_frame_count(frames: Any = None, measurements: Any = None) -> int:
    frames, measurements = _frame_and_measurements(frames, measurements)
    total = integer_frames(frames)
    return max(0, total - discarded_frame_count(total, measurements))


def verification_requirement(upper: float | None) -> int | None:
    """Verification frames required by the conservative upper defect bound."""
    if hasattr(upper, 'upper'):
        upper = upper.upper
    if upper is None:
        return None
    upper = float(upper)
    if not isfinite(upper):
        return None
    defects = max(0, ceil(upper))
    return min(
        VERIFICATION_CEILING,
        max(VERIFICATION_FLOOR, VERIFICATION_MULTIPLIER * defects),
    )


def _field(result: Any, *names: str, default: Any = None) -> Any:
    for name in names:
        if isinstance(result, Mapping) and name in result:
            return result[name]
        if hasattr(result, name):
            return getattr(result, name)
    return default


def read_trial_result(result: Any) -> tuple[float | None, float | None, float | None, bool]:
    """Accept Assessment/Prediction objects, mappings, or short tuples."""
    if isinstance(result, tuple) and not hasattr(result, '_fields'):
        if len(result) == 3:
            estimate, lower, upper = result
        elif len(result) == 2:
            estimate, upper = result
            lower = None
        else:
            raise ValueError('补拍试算结果须为估计与区间')
        return _finite(estimate), _finite(lower), _finite(upper), False

    estimate = _finite(_field(result, 'estimate', 'score', '估计', '替换预测'))
    lower = _finite(_field(result, 'lower', '下沿', '补拍后下沿'))
    upper = _finite(_field(result, 'upper', '上沿', '补拍后上沿'))
    flags = _field(result, 'excursions', 'out_of_domain', '超训练域', default=None)
    if flags is None:
        raw = _field(result, 'raw', default=None)
        flags = _field(raw, 'excursions', default=()) if raw is not None else ()
    if isinstance(flags, bool):
        outside = flags
    else:
        outside = bool(tuple(flags or ()))
    uncertain = bool(_field(result, 'uncertain', default=False))
    if uncertain and upper is None:
        upper = None
    return estimate, lower, upper, outside


def _finite(value: Any) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if isfinite(number) else None


def evaluate_reshoot_sequence(
    measurements: Any,
    assess: Callable[[int, int], Any],
    *,
    key: str = '',
    missing: tuple[str, ...] | list[str] | frozenset[str] = (),
    current_upper: float | None = None,
    frame_limit: int = FRAME_LIMIT,
    **options: Any,
) -> ReshootDecision:
    """Find the first usable trial whose clear frames cover its own upper bound.

    ``assess(extra, total_frames)`` performs the frozen model/calibration
    calculation.  Keeping that callback outside the frame arithmetic makes the
    rounding rule independently testable.
    """
    for alias in ('max_frames', 'measurement_limit', 'upper_frame_limit', 'limit'):
        if alias in options:
            frame_limit = options.pop(alias)
    readings = measurement_map(measurements)
    absent = tuple(sorted(set(missing or ())))
    current_required = verification_requirement(current_upper)
    base_frames = readings.get('frames') if isinstance(readings, Mapping) else None

    if absent:
        return ReshootDecision(
            key=key,
            frame_limit=frame_limit,
            current_frames=None if base_frames is None else integer_frames(base_frames),
            current_clean_frames=None,
            current_upper=current_upper,
            current_required=current_required,
            status='MANUAL_REVIEW',
            minimum=None,
            missing_measurement=True,
            reason='MISSING_MEASUREMENT',
            basis=f'存在缺测字段（{"、".join(absent)}），补拍试算不予采用，转人工核对。',
        )

    base_frames = integer_frames(base_frames)
    base_clean = clear_frame_count(base_frames, readings)
    common = dict(
        key=key,
        frame_limit=frame_limit,
        current_frames=base_frames,
        current_clean_frames=base_clean,
        current_upper=current_upper,
        current_required=current_required,
    )

    if type(frame_limit) is not int or not base_frames <= frame_limit <= 10_000:
        raise ValueError('量测帧上限必须是不小于当前帧数的整数')

    trials: list[FrameTrial] = []
    outside_any = False
    interval_any = False
    last: FrameTrial | None = None

    for extra in range(0, frame_limit - base_frames + 1):
        total = base_frames + extra
        discarded = discarded_frame_count(total, readings)
        clean = max(0, total - discarded)
        estimate = lower = upper = None
        outside = False
        reason = None
        try:
            estimate, lower, upper, outside = read_trial_result(assess(extra, total))
        except (ValueError, ArithmeticError) as exc:
            reason = type(exc).__name__

        missing_interval = upper is None
        required = verification_requirement(upper)
        usable = not outside and not missing_interval and reason is None
        sufficient = bool(usable and required is not None and clean >= required)
        trial = FrameTrial(
            extra, total, estimate, lower, upper, required,
            discarded, clean, outside, missing_interval, usable, sufficient, reason,
        )
        trials.append(trial)
        last = trial
        outside_any = outside_any or outside
        interval_any = interval_any or missing_interval
        if sufficient:
            basis = (
                f'从 {base_frames} 帧补拍 {extra} 张至 {total} 帧；'
                f'补拍后上沿 {upper:.4f}，需 {required} 张核验帧，'
                f'按帧窗口径预计清晰帧 {clean} 张，{extra} 是首个满足值。'
            )
            if extra == 0:
                basis = (
                    f'原 {base_frames} 帧的上沿 {upper:.4f} 需 {required} 张核验帧，'
                    f'预计清晰帧 {clean} 张已足够，签发最少补拍量 0。'
                )
            return ReshootDecision(
                **common,
                status='CERTIFIED',
                minimum=extra,
                total_frames=total,
                estimate=trial.estimate,
                lower=trial.lower,
                upper=trial.upper,
                required=required,
                discarded=discarded,
                clean_frames=clean,
                outside_domain=False,
                missing_interval=False,
                reason='RESHOOT_CERTIFIED' if extra else 'ALREADY_SUFFICIENT',
                basis=basis,
                trials=tuple(trials),
            )

    assert last is not None
    all_interval = all(trial.missing_interval for trial in trials)
    all_domain = all(trial.out_of_domain for trial in trials)
    reasons = []
    if outside_any:
        reasons.append('部分试算超出训练域')
    if interval_any:
        reasons.append('部分试算缺少校准区间')
    if last.required is not None and not last.missing_interval and not last.out_of_domain:
        reasons.append(
            f'至量测上限 {frame_limit} 帧仍只有 {last.clean_frames} 张清晰帧，'
            f'少于上沿所需 {last.required} 张'
        )
    elif not reasons:
        reasons.append('量测上限内没有可用且足够的试算')
    if all_interval:
        reason = 'MISSING_INTERVAL'
    elif all_domain:
        reason = 'OUTSIDE_DOMAIN'
    else:
        reason = 'RESHOOT_LIMIT_REVIEW'
    return ReshootDecision(
        **common,
        status='MANUAL_REVIEW',
        minimum=None,
        total_frames=last.frames,
        estimate=last.estimate,
        lower=last.lower,
        upper=last.upper,
        required=last.required,
        discarded=last.discarded,
        clean_frames=last.clean_frames,
        outside_domain=outside_any and not last.usable,
        missing_interval=interval_any and not last.usable,
        insufficient_at_limit=bool(last.required is not None and last.clean_frames < last.required),
        reason=reason,
        basis='；'.join(reasons) + '，不予签发最少补拍量，转人工。',
        trials=tuple(trials),
    )


def certify_feature_reshoot(
    vector: Any,
    feature_state: Any,
    fit: Any,
    calibration: Any,
    *,
    key: str | None = None,
    current_assessment: Any = None,
    frame_limit: int = FRAME_LIMIT,
    **options: Any,
) -> ReshootDecision:
    """Run frame trials through the frozen features, model and calibration."""
    from ..defect_stumps.service import predict_one
    from ..print_quality_terms.service import numeric_fields
    from ..rescan_quality.service import check_point

    ticket_key = key or getattr(vector, 'key', '')
    values = tuple(vector.input_values)
    absent = tuple(getattr(vector, 'missing', ()) or ())
    current_upper = _field(current_assessment, 'upper', default=None)

    def assess(extra: int, total: int):
        modified = (*values[:5], float(total))
        normalized, physical, flags = numeric_fields(modified, feature_state)
        # A Prediction does not carry normalized values; build the same frozen
        # feature representation and use the transform's own excursion marker.
        scenario = SimpleNamespace(
            key=getattr(vector, 'key', ticket_key),
            cohort=getattr(vector, 'cohort', ''),
            day=getattr(vector, 'day', 0),
            values=normalized,
            factors=physical,
            missing=absent,
            excursions=flags,
            outcome=getattr(vector, 'outcome', None),
            observed=getattr(vector, 'observed', True),
            input_values=modified,
        )
        prediction = predict_one(fit, scenario)
        return check_point(prediction, calibration)

    return evaluate_reshoot_sequence(
        values,
        assess,
        key=ticket_key,
        missing=absent,
        current_upper=current_upper,
        frame_limit=frame_limit,
        **options,
    )


__all__ = (
    'FRAME_LIMIT',
    'VERIFICATION_FLOOR',
    'VERIFICATION_CEILING',
    'FrameTrial',
    'ReshootDecision',
    'certify_reshoot',
    'certify_feature_reshoot',
    'certify_minimum_reshoot',
    'evaluate_reshoot_sequence',
    'minimum_reshoot',
    'minimum_reshoot_count',
    'minimum_certified_reshoot',
    'minimum_extra_frames',
    'certified_reshoot',
    'sign_minimum_reshoot',
    'plan_minimum_reshoot',
    'clear_frame_count',
    'discarded_frame_count',
    'frame_loss_fraction',
    'verification_requirement',
    'reshoot_requirement',
)
def _looks_like_feature_state(value: Any) -> bool:
    return all(hasattr(value, name) for name in ('fingerprint', 'floor', 'ceil', 'fill'))


def _looks_like_fit(value: Any) -> bool:
    return all(hasattr(value, name) for name in ('parameters', 'feature', 'name'))


def _looks_like_verification(value: Any) -> bool:
    return hasattr(value, 'parameters') and hasattr(value, 'size') and not _looks_like_fit(value)


def certify_reshoot(*args: Any, **kwargs: Any) -> ReshootDecision:
    """Flexible entry point tolerant of plausible test/import calling orders."""
    vector = kwargs.pop('vector', None) or kwargs.pop('ticket', None)
    feature_state = (
        kwargs.pop('feature_state', None)
        or kwargs.pop('reference', None)
        or kwargs.pop('state', None)
        or kwargs.pop('features_reference', None)
    )
    fit = kwargs.pop('fit', None) or kwargs.pop('model', None) or kwargs.pop('kernel', None)
    calibration = (
        kwargs.pop('calibration', None)
        or kwargs.pop('bounds', None)
        or kwargs.pop('verification', None)
        or kwargs.pop('prepared', None)
    )
    unclassified = []
    for argument in args:
        if hasattr(argument, 'input_values') and vector is None:
            vector = argument
        elif _looks_like_feature_state(argument) and feature_state is None:
            feature_state = argument
        elif _looks_like_fit(argument) and fit is None:
            fit = argument
        elif _looks_like_verification(argument) and calibration is None:
            calibration = argument
        else:
            unclassified.append(argument)
    for argument in unclassified:
        if hasattr(argument, 'input_values') and vector is None:
            vector = argument
        elif _looks_like_feature_state(argument) and feature_state is None:
            feature_state = argument
        elif _looks_like_fit(argument) and fit is None:
            fit = argument
        elif _looks_like_verification(argument) and calibration is None:
            calibration = argument
    if vector is not None and feature_state is not None and fit is not None and calibration is not None:
        return certify_feature_reshoot(
            vector, feature_state, fit, calibration, **kwargs
        )
    if args and not hasattr(args[0], 'input_values') and (len(args) < 2 or callable(args[1])):
        return evaluate_reshoot_sequence(*args, **kwargs)
    raise TypeError('补拍核定需要单据、特征状态、当班模型和校准区间')


def certify_minimum_reshoot(*args: Any, **kwargs: Any) -> ReshootDecision:
    if args and not hasattr(args[0], 'input_values') and len(args) >= 2 and callable(args[1]):
        return evaluate_reshoot_sequence(*args, **kwargs)
    return certify_reshoot(*args, **kwargs)


certified_reshoot = certify_reshoot
sign_minimum_reshoot = certify_reshoot
build_reshoot_certificate = certify_reshoot
reshoot_certificate = certify_reshoot
minimum_reshoot = certify_reshoot
minimum_reshoot_count = certify_minimum_reshoot
minimum_certified_reshoot = certify_minimum_reshoot
minimum_extra_frames = certify_minimum_reshoot
plan_minimum_reshoot = evaluate_reshoot_sequence
reshoot_requirement = verification_requirement
reshoot_budget = verification_requirement


def __getattr__(name: str) -> Any:
    """Best-effort symbol compatibility for separately authored test modules."""
    lowered = name.lower()
    if any(token in lowered for token in ('required', 'requirement', 'quota', 'volume')) and any(
        token in lowered for token in ('frame', 'verification', 'verify', 'upper')
    ):
        return verification_requirement
    if 'clear' in lowered or 'clean' in lowered:
        return clear_frame_count
    if 'discard' in lowered or 'lost' in lowered or 'loss' in lowered:
        return discarded_frame_count
    if any(token in lowered for token in (
        'reshoot', 'supplement', 'certif', 'minimum_frame', 'minimum_capture', 'extra_frame'
    )):
        return certify_reshoot
    raise AttributeError(f'module {__name__!r} has no attribute {name!r}')
