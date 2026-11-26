from dataclasses import dataclass
from math import isfinite
from ..coder_lot_print.contracts import DatecodeRecord as RawObservation

RAW_KEYS = ('speed', 'head_gap', 'ink_age', 'film_tension', 'specular', 'frames')
FEATURE_KEYS = ('blur_load', 'ink_dwell', 'reflection', 'transport_stretch', 'unread_buffer')
FEATURE_NAMES = ('高速喷头扩散', '墨路驻留', '反光与可见帧', '膜带张力偏离', '读码余量')


@dataclass(frozen=True, slots=True)
class FeatureState:
    fill: tuple[float, ...]
    offsets: tuple[float, ...]
    scales: tuple[float, ...]
    floor: tuple[float, ...]
    ceil: tuple[float, ...]
    fingerprint: str

    def __post_init__(self):
        if len(self.fill) != len(RAW_KEYS):
            raise ValueError('补值向量维数与字段表不匹配')
        if any(len(column) != len(FEATURE_KEYS) for column in (self.offsets, self.scales, self.floor, self.ceil)):
            raise ValueError('特征状态维数不匹配')
        if min(self.scales) <= 0:
            raise ValueError('特征尺度必须为正')


@dataclass(frozen=True, slots=True)
class FeatureVector:
    key: str
    cohort: str
    day: int
    values: tuple[float, ...]
    factors: tuple[float, ...]
    missing: tuple[str, ...]
    excursions: tuple[str, ...]
    outcome: float | None
    observed: bool
    input_values: tuple[float, ...]


@dataclass(frozen=True, slots=True)
class PreparedRuns:
    train: tuple[FeatureVector, ...]
    calibration: tuple[FeatureVector, ...]
    replay: tuple[FeatureVector, ...]
    live: tuple[FeatureVector, ...]

    def segments(self):
        return tuple((name, getattr(self, name)) for name in ('train', 'calibration', 'replay', 'live'))


@dataclass(frozen=True, slots=True)
class Proposal:
    name: str
    field: str
    before: float
    after: float
    work: int

    def __post_init__(self):
        if self.before == self.after or not isfinite(self.after) or self.work < 0:
            raise ValueError('推演动作需要实质变动和有效额度')

    def evidence(self):
        return {'情形': self.name, '变更项': self.field, '原值': self.before,
                '置换值': self.after, '用量': self.work}

@dataclass(frozen=True, slots=True)
class PrintQualityTerms:
    visible_frames: float
    frame_gap: float
    shipping_speed: float
    film_offset: float
    ink_buffer: float
    spray_span: float
    speckle_cost: float
    expected_read_rate: float

    def __post_init__(self):
        if not all(isfinite(amount) for amount in (self.visible_frames, self.frame_gap, self.shipping_speed, self.film_offset, self.ink_buffer, self.spray_span, self.speckle_cost, self.expected_read_rate)):
            raise ValueError('包装工位批存在无效的作业量测')

    def explain(self, labels=None):
        return (
            ('按反光折算可见帧', round(self.visible_frames, 4)),
            ('返扫基准帧缺口', round(self.frame_gap, 4)),
            ('每秒膜带移动', round(self.shipping_speed, 4)),
            ('牵引力偏离', round(self.film_offset, 4)),
            ('距下次冲洗小时', round(self.ink_buffer, 4)),
            ('喷距与传动乘积', round(self.spray_span, 4)),
            ('反光与喷高代理', round(self.speckle_cost, 4)),
            ('单分钟每帧可见性', round(self.expected_read_rate, 4)),
        )
