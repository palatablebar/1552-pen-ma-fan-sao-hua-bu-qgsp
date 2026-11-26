from .operating_ledger import operating_ledger
from collections import Counter, defaultdict
from math import exp, isfinite

from .contracts import RuleNotice, Job, Plan, Policy, RISK_CUTOFF
from .constraints import WorkOrder, apply_camera_backlog
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


def measures(raw):
    return tuple(raw)


def signals(data, estimate, missing=()):
    absent=frozenset(missing)
    speed, head_gap, ink_age, film_tension, specular, frames = data
    hits = []
    if not absent.intersection(('specular', 'frames')) and (specular >= 56 and frames <= 17):
        hits.append(RuleNotice('CAMERA_SPOT', '更换取像角度后二次返扫', hard=True))
    if not absent.intersection(('speed', 'head_gap')) and (head_gap >= 11 and speed >= 155):
        hits.append(RuleNotice('HEAD_DISTANCE', '喷头间距过大需先复位', hard=False))
    if not absent.intersection(('ink_age', 'frames')) and (ink_age >= 66 and frames < 25):
        hits.append(RuleNotice('INK_SETTLE', '复扫墨路运行末班', hard=False))
    return tuple(hits)


def expected_load(measurements):
    speed, head_gap, ink_age, film_tension, specular, frames = measurements
    return 1 + int(speed >= 145) + int(frames < 18)


def dispatch_pressure(values, estimate):
    speed, head_gap, ink_age, film_tension, specular, frames = values
    return (speed/110)*(1+specular/100)+max(0,22-frames)/15


def confidence_weight(estimate, cutoff):
    shifted = (estimate - cutoff) / max(.5, abs(cutoff) * .35)
    if shifted >= 0:
        return 1 / (1 + exp(-shifted))
    bounded = exp(shifted)
    return bounded / (1 + bounded)


def recommend(assessment, attention, policy, reshoot_review=frozenset()):
    raw = assessment.raw
    data = measures(raw.input_values)
    estimate = assessment.estimate
    domain_codes = signals(data, estimate, raw.missing)
    level = confidence_weight(estimate, policy.trigger)
    cost = expected_load(data)
    if not isfinite(estimate) or not 1 <= cost <= 12:
        raise ValueError('处置量不在有效范围')
    if domain_codes and domain_codes[0].hard:
        state = '暂停'
        reason = domain_codes[0].rule_id
        summary = domain_codes[0].meaning
    elif raw.key in attention or assessment.uncertain:
        state = '人工判读'
        reason = 'OUT_OF_REFERENCE' if raw.key in attention else 'INSUFFICIENT_CALIBRATION'
        summary = '分布偏移或校准量不足，需核对原始单据'
    elif raw.key in reshoot_review and (domain_codes or estimate >= policy.trigger):
        state = '人工判读'
        reason = 'FRAME_BUDGET_REVIEW'
        summary = '补拍试算在量测上限内无法满足上沿核验量，需人工安排'
    elif domain_codes or estimate >= policy.trigger:
        state = '候选'
        reason = domain_codes[0].rule_id if domain_codes else 'ABOVE_TRIGGER'
        summary = domain_codes[0].meaning if domain_codes else '达到本班复核阈值'
    else:
        state = '观察'
        reason = 'BELOW_TRIGGER'
        summary = '保留记录并等待下一次巡查'
    return Job(raw.key, raw.cohort, round(estimate, 4), assessment.lower, assessment.upper, cost,
               state, reason, summary, round(level, 5), tuple(item.rule_id for item in domain_codes))


class ShiftAllocation:
    def __init__(self, policy):
        self.policy = policy
        self.remainder = policy.capacity
        self.load = Counter()
        self.entries = {}

    def wait(self, order, code, detail):
        self.entries[order.job.key]=order.job.change('候补',code,detail)
        return False

    def approve(self, candidate):
        task=candidate.job
        operation=frame_segment(candidate.assessment.raw.input_values)
        before=self.load[task.cohort]
        if self.remainder < task.cost:
            return self.wait(candidate,'CAPACITY_REACHED','当前班次额度不足')
        if before+task.cost>self.policy.group_quota:
            return self.wait(candidate,'GROUP_CAP_REACHED','该作业区先清理已有工位')
        if operation<0:
            return self.wait(candidate,'BAND_UNSUPPORTED','预留可见帧位')
        self.entries[task.key]=task.change('已分派',task.reason,task.summary)
        self.load[task.cohort] += task.cost
        self.remainder -= task.cost
        return True


def allocate(assessments, attention, policy, reshoot_review=frozenset()):
    desk=ShiftAllocation(policy)
    triaged={}
    route=[]
    for observation in assessments:
        ticket=recommend(observation,attention,policy,reshoot_review)
        if ticket.key in triaged:
            raise ValueError('出现重复作业单据')
        triaged[ticket.key]=ticket
        if ticket.state=='候选':
            route.append(WorkOrder(ticket,observation))
    def priority(order):
        risk=dispatch_pressure(order.assessment.raw.input_values,order.job.estimate)
        band=frame_segment(order.assessment.raw.input_values)
        return not order.job.rule_hits,-risk,band,order.job.cost,order.job.key
    apply_camera_backlog(sorted(route,key=priority),desk.approve,desk.wait)
    if len(desk.entries)!=len(route):
        raise ArithmeticError('仍有未处理的候选')
    triaged.update(desk.entries)
    rowlist=sorted(triaged.values(),key=lambda job: (job.state!='已分派',job.state=='观察',-job.priority,job.key))
    return Plan(tuple(rowlist),policy.capacity,desk.remainder,tuple(sorted(desk.load.items())))


def collect_reshoot_review(*sources):
    keys = set()
    for source in sources:
        if source is None:
            continue
        if isinstance(source, str):
            keys.add(source)
            continue
        if isinstance(source, dict):
            for key, value in source.items():
                if isinstance(key, str) and _certificate_requests_review(value, default=True):
                    keys.add(key)
            continue
        for item in source:
            if isinstance(item, str):
                keys.add(item)
            elif isinstance(item, dict):
                key = item.get('key') or item.get('关联单据') or item.get('单号')
                if key and _certificate_requests_review(item, default=False):
                    keys.add(key)
            else:
                key = getattr(item, 'key', None)
                if key and getattr(item, 'manual_review', False):
                    keys.add(key)
    return frozenset(keys)


def _certificate_requests_review(value, *, default):
    if value is None:
        return False
    if isinstance(value, bool):
        return value
    if isinstance(value, dict):
        manual = value.get('manual_review', value.get('转人工'))
        if manual is None:
            status = value.get('status') or value.get('核定状态')
            manual = status in {'MANUAL_REVIEW', '转人工'}
        return bool(manual)
    manual = getattr(value, 'manual_review', None)
    return bool(manual) if manual is not None else default


def plan_jobs(assessments, attention, capacity, mode='balanced', reshoot_review=frozenset(),
              *, certificates=None, reshoot_plans=None, frame_certificates=None):
    review = collect_reshoot_review(
        reshoot_review, certificates, reshoot_plans, frame_certificates
    )
    return allocate(assessments, frozenset(attention), Policy.select(capacity, mode), review)


def action_evidence(plan):
    counts = Counter(job.state for job in plan.jobs)
    status = [{'处置': state, '单量': count} for state, count in sorted(counts.items())]
    status.extend({'处置': '分区 ' + group, '额度': cost} for group, cost in plan.used_by_group)
    status += [{'处置': '剩余额度', '额度': plan.balance}]
    return status


def frame_segment(raw):
    frames = raw[5]
    return int(frames//12)


def operating_group(assessments, progression):
    source={line.raw.key:line.raw.input_values for line in assessments}
    cells=Counter()
    for work in progression.jobs:
        if work.state != '已分派':
            continue
        band=frame_segment(source[work.key])
        cells[work.cohort,band] += work.cost
    return [{ '作业区': zone, '返扫窗': band, '班组用量': total } for (zone,band),total in sorted(cells.items())]


def __getattr__(name):
    from . import reshoot as _reshoot_compat
    if hasattr(_reshoot_compat, name):
        return getattr(_reshoot_compat, name)
    raise AttributeError(f'module {__name__!r} has no attribute {name!r}')
