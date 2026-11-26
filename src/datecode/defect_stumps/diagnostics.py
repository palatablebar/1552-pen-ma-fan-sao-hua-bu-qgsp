from math import exp, log, fsum, sqrt
from statistics import median, mean, quantiles

from .boost_model import score_kernel



def explain_defect_stumps(fit, calibration, replay, live):
    origin, pieces = fit.parameters
    columns = ('喷扩','墨路','反光','膜带','余帧')
    influence = [[] for _ in columns]
    for coordinate, split, left, right in pieces:
        influence[coordinate].append((split,abs(right-left)))
    checks = []
    for position, votes in enumerate(influence):
        if votes:
            dominant = max(votes,key=lambda item:item[1])
            checks.append({'返扫描量':columns[position],'分割数量':len(votes),
                           '最大阶跃':round(dominant[1],4),'标准切点':round(dominant[0],4)})
    sample = [row for row in replay if row.outcome is not None]
    if sample:
        baseline = mean(abs(row.outcome-origin) for row in sample)
        corrected = mean(abs(row.outcome-score_kernel((origin,pieces),row)[0]) for row in sample)
        checks.append({'核验帧批':len(sample),'树桩改善':round(baseline-corrected,3),'基础误差':round(baseline,3)})
    return checks
