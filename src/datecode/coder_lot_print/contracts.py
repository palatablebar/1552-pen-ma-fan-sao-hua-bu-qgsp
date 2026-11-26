from dataclasses import dataclass

FIELDS = {'speed': ('传送带频率', 'm/min', 40, 235),
 'head_gap': ('喷头间距', 'mm', 2, 14),
 'ink_age': ('墨路启用时长', 'h', 1, 95),
 'film_tension': ('膜带牵引', 'N', 42, 220),
 'specular': ('反光读数', '%', 3, 70),
 'frames': ('返扫可用帧', '张', 4, 65)}
LIMITS = {'result_max': 10000}


class MeasureIssue(ValueError):
    def __init__(self, field: str, code: str):
        super().__init__(f'{field}:{code}')
        self.field = field
        self.code = code


@dataclass(frozen=True, slots=True)
class DatecodeRecord:
    key: str
    cohort: str
    day: int
    received: int
    revision: int
    result_day: int | None
    outcome: float | None
    observed: bool
    speed: float | None
    head_gap: float | None
    ink_age: float | None
    film_tension: float | None
    specular: float | None
    frames: float | None

    def signature(self):
        return (self.key, self.cohort, self.day, self.revision, self.result_day, self.outcome, self.observed,
                *(getattr(self, key) for key in FIELDS))


@dataclass(frozen=True, slots=True)
class Issue:
    source_row: int
    key: str
    field: str
    code: str

    def evidence(self):
        return {'行号': self.source_row, '单号': self.key, '字段': FIELDS.get(self.field, (self.field,))[0],
                '原因': self.code}


@dataclass(frozen=True, slots=True)
class DecodeResult:
    entries: tuple[DatecodeRecord, ...]
    issues: tuple[Issue, ...]
    source_rows: int
