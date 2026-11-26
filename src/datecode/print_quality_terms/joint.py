from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class JointAction:
    case: str
    work_units: int
    notes: str
    changes: dict[str, tuple[float, float]]

    def evidence(self, old_value, new_value, extrapolates):
        return {'联动推演':self.case, '用量':self.work_units, '先决条件':self.notes,
                '原预测':round(old_value,4), '替换预测':round(new_value,4),
                '变化':round(new_value-old_value,4), '超训练域':bool(extrapolates),
                '联动量测':{item:{'原值':before,'替换值':after} for item,(before,after) in self.changes.items()}}


def simulate_slow_rescan(readings, invalid):
    speed, frames = readings[0], readings[5]
    if invalid.intersection(('speed', 'frames')):
        return None
    if not (speed>=65 and frames<=54):
        return None
    speed_adjusted = speed-20
    frames_adjusted = frames+10
    inspected = {
        'speed': (speed, speed_adjusted),
        'frames': (frames, frames_adjusted),
    }
    if any(new != old for old,new in inspected.values()):
        return JointAction('低速补拍', 2, '降低膜带速度后定量补拍', inspected)
    return None


def simulate_reset_reflection(readings, invalid):
    film_tension, specular = readings[3], readings[4]
    if invalid.intersection(('film_tension', 'specular')):
        return None
    if not (specular>=15 and film_tension>=67):
        return None
    specular_adjusted = specular-10
    film_tension_adjusted = film_tension-21
    inspected = {
        'specular': (specular, specular_adjusted),
        'film_tension': (film_tension, film_tension_adjusted),
    }
    if any(new != old for old,new in inspected.values()):
        return JointAction('控光张力重置', 3, '重新固定光角和压膜张力', inspected)
    return None


def simulate_clean_ink_circuit(readings, invalid):
    head_gap, ink_age = readings[1], readings[2]
    if invalid.intersection(('head_gap', 'ink_age')):
        return None
    if not (ink_age>=22 and head_gap>=5):
        return None
    ink_age_adjusted = 1
    head_gap_adjusted = head_gap-2
    inspected = {
        'ink_age': (ink_age, ink_age_adjusted),
        'head_gap': (head_gap, head_gap_adjusted),
    }
    if any(new != old for old,new in inspected.values()):
        return JointAction('换墨缩距', 2, '清洗墨路后检查间隙量规', inspected)
    return None


def simulate_trial_matte_film(readings, invalid):
    specular, frames = readings[4], readings[5]
    if invalid.intersection(('specular', 'frames')):
        return None
    if not (specular>=22 and frames<=60):
        return None
    specular_adjusted = specular-15
    frames_adjusted = frames+5
    inspected = {
        'specular': (specular, specular_adjusted),
        'frames': (frames, frames_adjusted),
    }
    if any(new != old for old,new in inspected.values()):
        return JointAction('低反光胶片试印', 2, '用哑面片确认图像支撑', inspected)
    return None


def simulate_steady_print(readings, invalid):
    speed, head_gap = readings[0], readings[1]
    if invalid.intersection(('speed', 'head_gap')):
        return None
    if not (speed>=75 and head_gap>=7):
        return None
    speed_adjusted = speed-29
    head_gap_adjusted = head_gap-3
    inspected = {
        'speed': (speed, speed_adjusted),
        'head_gap': (head_gap, head_gap_adjusted),
    }
    if any(new != old for old,new in inspected.values()):
        return JointAction('退喷距放慢节拍', 2, '定速后重打标准批', inspected)
    return None


def options(values, missing):
    measurements=tuple(values)
    unobserved=frozenset(missing)
    cases=(
        simulate_slow_rescan(measurements, unobserved),
        simulate_reset_reflection(measurements, unobserved),
        simulate_clean_ink_circuit(measurements, unobserved),
        simulate_trial_matte_film(measurements, unobserved),
        simulate_steady_print(measurements, unobserved),
    )
    return tuple(action for action in cases if action is not None)
