from collections import defaultdict
from dataclasses import dataclass
from math import ceil


@dataclass(frozen=True, slots=True)
class FrameRun:
    stop_reason: str | None
    strip_size: int
    discarded: int
    clean_frames: int
    requisition: int
    channel: str


def scan_frame_budget(lot):
    readings = lot['measurements']
    pitch = readings['speed'] / 180
    blur = readings['head_gap'] >= 11 and readings['speed'] >= 155
    reflection = readings['specular'] >= 56
    lost_fraction = min(.8, (readings['specular']/160) + (.22 if pitch > 1 else 0))
    eligible = int(readings['frames'])
    good = max(0,eligible-ceil(eligible*lost_fraction))
    if 'CAMERA_SPOT' in lot['hits']:
        return FrameRun('取像角复位前暂停',eligible,eligible-good,good,0,'斜光替位')
    if blur:
        return FrameRun('间距复位前暂停',eligible,eligible-good,good,0,'前段码窗')
    potential_defects = max(0,ceil(lot['estimate']))
    needed = min(32,max(12,2 * potential_defects))
    channel = '膜边压线' if readings['film_tension'] < 70 else '斜光替位' if reflection else '常规码窗'
    if readings['ink_age'] >= 66 and channel=='常规码窗':
        channel = '墨路末段定位'
    return FrameRun(None,eligible,eligible-good,good,max(0,needed-good),channel)


def operating_ledger(rows):
    lanes = defaultdict(lambda:[0,0,0,0])
    camera_queue = []
    for lot in sorted(rows,key=lambda ticket:(ticket['zone'],ticket['key'])):
        if lot['unmeasured']:
            camera_queue.append({'业务安排':'补扫相机参数联','关联单据':lot['key'],'可计入返扫':False})
            continue
        sequence = scan_frame_budget(lot)
        accumulator = lanes[(lot['zone'],sequence.channel)]
        accumulator[0] += sequence.strip_size
        accumulator[1] += sequence.discarded
        if sequence.stop_reason:
            accumulator[2] += sequence.clean_frames
            action = sequence.stop_reason
        elif sequence.requisition:
            accumulator[3] += sequence.requisition
            action = '补采清晰帧'
        else:
            continue
        camera_queue.append({'业务安排':action, '关联单据':lot['key'], '取像位':sequence.channel,
                             '原帧组':f'1–{sequence.strip_size}', '遮光弃用张数':sequence.discarded,
                             '估计有效帧':sequence.clean_frames, '额外取像张数':sequence.requisition})
    for (printer,channel), (source,lost,hold,to_scan) in sorted(lanes.items()):
        use = source-lost-hold
        if use < 0:
            raise ArithmeticError('相机返扫批帧数不平')
        camera_queue.append({'业务安排':'返扫帧窗交接','喷码线':printer,'取像位':channel,
                             '来源帧':source,'弃用帧':lost,'暂停见证帧':hold,'可核帧':use,'待补拍张数':to_scan})
    return camera_queue
