from dataclasses import replace
from statistics import median

from .contracts import PrintQualityTerms, Proposal


def measure_print_quality_terms(values) -> PrintQualityTerms:
    speed, head_gap, ink_age, film_tension, specular, frames = values
    return PrintQualityTerms(
        visible_frames=frames*(1-specular/100),
        frame_gap=max(0,21-frames),
        shipping_speed=speed/60,
        film_offset=film_tension-115,
        ink_buffer=95-ink_age,
        spray_span=head_gap*speed/100,
        speckle_cost=specular*head_gap/14,
        expected_read_rate=60*frames*(1-specular/100)/speed,
    )


def propose_camera_backlog(values, missing=()):
    speed, head_gap, ink_age, film_tension, specular, frames = values
    if 'frames' not in missing and (frames<=53):
        yield Proposal('加拍十二帧', 'frames', frames, min(65,frames+12), 2)
    if 'specular' not in missing and (specular>=15):
        yield Proposal('调整相机避反光', 'specular', specular, max(3,specular-12), 1)
    if 'speed' not in missing and (speed>=55):
        yield Proposal('下一批降速十五档', 'speed', speed, max(40,speed-15), 1)
    if 'head_gap' not in missing and (head_gap>=5):
        yield Proposal('清洗后缩小喷距', 'head_gap', head_gap, max(2,head_gap-2), 2)
