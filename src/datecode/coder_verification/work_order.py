def collect_camera_frame(measures, missing, estimate):
    specular = measures['specular']
    frames = measures['frames']
    if not (frames<=31):
        return None
    value=frames*(1-specular/100)
    return {'现场复核':'同批返扫','可复查值':round(value,3),'单位':'张','归档要求':'留存未通过图和同批正常图',
            '需补测':not set(missing).isdisjoint(('specular', 'frames'))}


def collect_film_glare(measures, missing, estimate):
    specular = measures['specular']
    if not (specular>=35):
        return None
    value=specular
    return {'现场复核':'补光核查','可复查值':round(value,3),'单位':'%','归档要求':'调整灯路角度后锁螺母',
            '需补测':not set(missing).isdisjoint(('specular',))}


def collect_nozzle_height(measures, missing, estimate):
    head_gap = measures['head_gap']
    if not (head_gap>=8):
        return None
    value=head_gap
    return {'现场复核':'喷距测量','可复查值':round(value,3),'单位':'mm','归档要求':'用量规核对实际喷距',
            '需补测':not set(missing).isdisjoint(('head_gap',))}


def collect_tension_shift(measures, missing, estimate):
    speed = measures['speed']
    film_tension = measures['film_tension']
    if not (film_tension>=150 or speed>=150):
        return None
    value=film_tension
    return {'现场复核':'检查膜带','可复查值':round(value,3),'单位':'N','归档要求':'记录改速前后牵引读数',
            '需补测':not set(missing).isdisjoint(('speed', 'film_tension'))}


def check_coder_verification(records):
    guide = []
    for ticket in records:
        if ticket['state'] not in ('已分派','暂停','人工判读'):
            continue
        measures=ticket['measurements']
        absent=ticket['unmeasured']
        estimate=ticket['estimate']
        checks = (
            collect_camera_frame(measures,absent,estimate),
            collect_film_glare(measures,absent,estimate),
            collect_nozzle_height(measures,absent,estimate),
            collect_tension_shift(measures,absent,estimate),
        )
        required=tuple(check for check in checks if check is not None)
        if not required:
            continue
        review=ticket['key']
        for check in required:
            guide.append({'签收单':review,'作业区':ticket['zone'],'处置':ticket['state'],**check})
    return guide
