from bisect import bisect_right
from collections import Counter, defaultdict
from dataclasses import replace

from .contracts import Chronology, FoldSummary, Span, WindowRule
from .readiness import formation_tail


def assign_fold(record, rule):
    phases=(*rule.folds(),('live',rule.live))
    begins=tuple(period.begin for _,period in phases)
    selected=bisect_right(begins,record.day)-1
    if selected<0:
        return None,'EMBARGO_OR_UNSCHEDULED'
    name, span=phases[selected]
    if record.day not in span:
        return None,'EMBARGO_OR_UNSCHEDULED'
    if name=='live':
        return (name,'OPEN_RUN') if record.received<=rule.as_of else (None,'AFTER_SHIFT_REPORT')
    if record.result_day is None or record.received not in span or record.result_day>=span.end:
        return None,'RESULT_NOT_MATURE'
    ready = record.result_day>=record.day and record.outcome is not None
    if not ready:
        return None,'MISSING_OUTCOME'
    return (name,'LOCKED_HISTORY') if record.observed or rule.allow_censor else (None,'CENSORED_OUTCOME')


def build_windows(records, rule=None):
    local = rule or WindowRule.standard(allow_censor=False)
    divisions = {key:[] for key,_ in (*local.folds(),('live',local.live))}
    quarantined={}
    orders=tuple(records)
    for ticket in orders:
        stage, consequence=assign_fold(ticket,local)
        if stage is None:
            quarantined[ticket.key] = consequence
        else:
            divisions[stage].append(ticket)
    for source in divisions.values():
        source.sort(key=lambda receipt:(receipt.day,receipt.key))
    schedule=Chronology(*(tuple(divisions[name]) for name in ('train','calibration','replay','live')),excluded=tuple(sorted(quarantined.items())))
    schedule.check_conservation(len(orders))
    return schedule


def partition_summary(windows):
    statistics=[]
    for label, tickets in windows.partitions():
        count=len(tickets)
        locations={entry.cohort for entry in tickets}
        unresolved=sum(entry.observed is False for entry in tickets)
        dates=tuple(entry.day for entry in tickets)
        statistics.append(FoldSummary(label,count,len(locations),unresolved,min(dates,default=None),max(dates,default=None)))
    return tuple(statistics)


def window_evidence(windows):
    short={'train':'拟合','calibration':'校准','replay':'回放','live':'当班'}
    view=[{'时段':short[row.name], '单量':row.count, '作业组':row.cohort_count, '右截尾':row.censored, '有效起点':row.first_day,'有效末日':row.last_day}
          for row in partition_summary(windows)]
    view.extend({'样本隔离':code,'单量':amount} for code,amount in Counter(reason for _,reason in windows.excluded).items())
    return view


def model_inputs(windows):
    history=windows.train
    if len(history)<16:
        raise ValueError('包装取像至少需要 16 张成熟历史单据')
    minimum={'calibration':3,'replay':1,'live':1}
    for field,value in windows.partitions():
        if field in minimum and len(value)<minimum[field]:
            raise ValueError(f'包装取像的 {field} 窗内单据不足 {minimum[field]} 条')
    return tuple(item.key for item in history)


def readiness_evidence(windows, as_of=96):
    report=formation_tail(windows, replace(WindowRule.standard(), as_of=as_of))
    return sorted(report,key=lambda entry:(entry['交班段'],-entry['有效单'],entry['来源']))
