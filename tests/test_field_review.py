from datecode.pipeline import preview
from datecode.camera_backlog.service import operating_ledger


def note(key, measures, *, zone='甲区', state='已分派', estimate=0, hits=(), missing=()):
    return {'key':key,'zone':zone,'state':state,'estimate':estimate,'hits':hits,
            'unmeasured':missing,'measurements':dict(zip(('speed', 'head_gap', 'ink_age', 'film_tension', 'specular', 'frames'),measures,strict=True))}


def test_field_plan_is_visible_and_references_real_tickets():
    desk = preview()
    plan = desk['sections'][6]
    assert plan['operating_title'] == '返扫帧窗交接'
    assert plan['operating_rows']
    scoped = {item['关联单据'] for item in plan['operating_rows'] if '关联单据' in item}
    assert scoped and scoped <= {row['key'] for row in desk['rows']}
    assert all(item['业务安排'] for item in plan['operating_rows'])


def test_paused_camera_frames_are_recorded_but_not_credited():
    proof = note('DC-1',(190,9,71,129,60,16),state='暂停',estimate=16,hits=('CAMERA_SPOT',))
    action, counts = operating_ledger([proof])
    assert action['业务安排']=='取像角复位前暂停'
    assert counts['可核帧']==0 and counts['弃用帧']+counts['暂停见证帧']==16
