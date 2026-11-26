from collections import defaultdict
from dataclasses import dataclass, replace
from math import ceil

from .reshoot import (
    FRAME_LIMIT,
    certify_feature_reshoot,
    certify_minimum_reshoot,
    certify_reshoot,
    clear_frame_count,
    evaluate_reshoot_sequence,
    minimum_reshoot_count,
    verification_requirement,
)


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


def certificate_view(lot):
    certificate = lot.get('reshoot_certificate', lot.get('reshoot'))
    if certificate is None:
        flat_minimum_keys = (
            'minimum_reshoot', 'certified_minimum', 'reshoot_count',
            'approved_reshoot', 'minimum_supplemental_frames',
            '最少补拍量', '核定补拍量',
        )
        if any(key in lot for key in flat_minimum_keys) or any(
            key in lot for key in ('manual_review', 'reshoot_manual_review', '补拍转人工')
        ):
            certificate = {
                'minimum': next((lot[key] for key in flat_minimum_keys if lot.get(key) is not None), None),
                'manual': lot.get('reshoot_manual_review', lot.get('manual_review', lot.get('补拍转人工', False))),
                'basis': lot.get('补拍依据', lot.get('reshoot_basis', '')),
                'upper': lot.get('upper', lot.get('补拍后上沿')),
                'required': lot.get('required', lot.get('补拍后核验量')),
                'clean': lot.get('clean_frames', lot.get('补拍后清晰帧')),
                'total': lot.get('total_frames', lot.get('补拍后总帧')),
                'status': lot.get('status'),
            }
    if certificate is None:
        return None
    if hasattr(certificate, 'to_dict'):
        certificate = certificate.to_dict()
    if not isinstance(certificate, dict):
        return None

    def first(*names):
        for name in names:
            if name in certificate and certificate[name] is not None:
                return certificate[name]
        return None

    minimum = first('minimum', '最少补拍量', '核定补拍量', '最少补拍张数', '额外取像张数')
    manual = first('manual_review', '转人工')
    if manual is None:
        manual = certificate.get('status') == 'MANUAL_REVIEW'
    return {
        'minimum': None if minimum is None else int(minimum),
        'manual': bool(manual),
        'basis': first('basis', '补拍依据') or '',
        'upper': first('upper', '补拍后上沿'),
        'required': first('required', '补拍后核验量', '核验需求量'),
        'clean': first('clean_frames', '补拍后清晰帧', '预计清晰帧'),
        'total': first('total_frames', '补拍后总帧'),
    }


def operating_ledger(rows):
    lanes = defaultdict(lambda:[0,0,0,0,0])
    camera_queue = []
    for lot in sorted(rows,key=lambda ticket:(ticket['zone'],ticket['key'])):
        if lot['unmeasured']:
            camera_queue.append({'业务安排':'补扫相机参数联','关联单据':lot['key'],'可计入返扫':False})
            continue
        sequence = scan_frame_budget(lot)
        certificate = certificate_view(lot)
        accumulator = lanes[(lot['zone'],sequence.channel)]
        accumulator[0] += sequence.strip_size
        accumulator[1] += sequence.discarded
        basis_fields = {}
        if certificate and certificate['basis']:
            trial_fields = {
                '补拍后总帧': certificate['total'],
                '补拍后上沿': certificate['upper'],
                '补拍后核验量': certificate['required'],
                '补拍后清晰帧': certificate['clean'],
            }
            if sequence.stop_reason:
                basis_fields = {
                    '补拍依据': f'{sequence.stop_reason}，暂停期间不签发补拍量；复位后试算：{certificate["basis"]}',
                    '复位后最少补拍量': certificate['minimum'] if not certificate['manual'] else None,
                    **trial_fields,
                }
            else:
                basis_fields = {'补拍依据': certificate['basis'], **trial_fields}
        if sequence.stop_reason:
            accumulator[2] += sequence.clean_frames
            action = sequence.stop_reason
        elif certificate is not None and certificate['manual']:
            sequence = replace(sequence, requisition=0)
            accumulator[4] += 1
            action = '补拍依据不足，转人工'
        elif certificate is not None and certificate['minimum'] is not None:
            sequence = replace(sequence, requisition=max(0, certificate['minimum']))
            if sequence.requisition:
                accumulator[3] += sequence.requisition
                action = '补采清晰帧'
            else:
                # A signed zero count needs no camera task; the lane summary and
                # ticket detail still retain its certification basis.
                continue
        elif sequence.requisition:
            accumulator[3] += sequence.requisition
            action = '补采清晰帧'
        else:
            continue
        if sequence.stop_reason or (certificate is not None and certificate['manual']):
            signed_minimum = None
        else:
            signed_minimum = sequence.requisition
        camera_queue.append({'业务安排':action, '关联单据':lot['key'], '取像位':sequence.channel,
                             '原帧组':f'1–{sequence.strip_size}', '遮光弃用张数':sequence.discarded,
                             '估计有效帧':sequence.clean_frames, '额外取像张数':sequence.requisition,
                             '补拍量':sequence.requisition, '最少补拍量':signed_minimum,
                             '核定补拍量':signed_minimum,
                             **basis_fields})
    for (printer,channel), (source,lost,hold,to_scan,manual_count) in sorted(lanes.items()):
        use = source-lost-hold
        if use < 0:
            raise ArithmeticError('相机返扫批帧数不平')
        handoff = {'业务安排':'返扫帧窗交接','喷码线':printer,'取像位':channel,
                             '来源帧':source,'弃用帧':lost,'暂停见证帧':hold,'可核帧':use,'待补拍张数':to_scan}
        if manual_count:
            handoff['补拍转人工单数'] = manual_count
        camera_queue.append(handoff)
    return camera_queue


build_operating_ledger = operating_ledger
reshoot_ledger = operating_ledger


def __getattr__(name):
    from . import reshoot as _reshoot_compat
    if hasattr(_reshoot_compat, name):
        return getattr(_reshoot_compat, name)
    raise AttributeError(f'module {__name__!r} has no attribute {name!r}')
