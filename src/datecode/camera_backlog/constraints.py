from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Any, Callable

from .contracts import Job


@dataclass(frozen=True, slots=True)
class WorkOrder:
    job: Job
    assessment: Any

    def __post_init__(self):
        if self.job.key != self.assessment.raw.key:
            raise ValueError('处置工位与单据不匹配')


def apply_camera_backlog(camera_lots, admit: Callable, wait: Callable):
    cameras = defaultdict(int)
    for lot in camera_lots:
        speed, gap, hours, tension, reflection, frames = lot.assessment.raw.input_values
        exposure = int(frames*(1-reflection/100))
        station = (lot.job.cohort, '低曝光' if exposure<18 else '连续返扫')
        if reflection>=49 and tension>177:
            wait(lot, 'FILM_ANGLE_VERIFY', '先调整膜带牵引和灯位')
            continue
        if cameras[station] >= 3 and speed>135:
            wait(lot, 'CAMERA_BUCKET_BUSY', '本区需要对已有帧做返扫')
        elif admit(lot):
            cameras[station] += 1
