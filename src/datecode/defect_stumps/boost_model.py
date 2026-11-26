from math import fsum
from statistics import mean


def candidate_splits(records, residual):
    dimensions = len(records[0].values)
    for feature in range(dimensions):
        alignment = sorted(zip(records, residual, strict=True), key=lambda pair: pair[0].values[feature])
        for index in range(8, len(alignment) - 7, max(2, len(alignment)//18)):
            upper = alignment[index][0].values[feature]
            lower = alignment[index - 1][0].values[feature]
            if upper == lower:
                continue
            left, right = ([target for _, target in rows] for rows in (alignment[:index], alignment[index:]))
            avg_left, avg_right = mean(left), mean(right)
            cost = fsum((y-avg_left)**2 for y in left) + fsum((y-avg_right)**2 for y in right)
            yield cost, feature, .5 * (upper + lower), avg_left, avg_right


def fit_kernel(rows):
    centre = mean(row.outcome for row in rows)
    predictions = [centre] * len(rows)
    pieces = []
    gain = 0.
    for _ in range(18):
        residual = [record.outcome - estimate for record, estimate in zip(rows, predictions, strict=True)]
        selected = min(candidate_splits(rows, residual), default=None)
        if selected is None:
            break
        cost, slot, cut, low, high = selected
        diff = fsum(value*value for value in residual) - cost
        if diff < .025:
            break
        gain += diff
        up, down = .18 * high, .18 * low
        pieces.append((slot, cut, down, up))
        predictions = [old + (down if item.values[slot] <= cut else up) for old, item in zip(predictions, rows, strict=True)]
    return (centre, tuple(pieces)), (('投票树桩', len(pieces)), ('残差拟合增益', gain), ('初始缺陷均值', centre))


def score_kernel(ensemble, sample):
    intercept, trees = ensemble
    importance = [0.] * len(sample.values)
    for feature, boundary, left, right in trees:
        importance[feature] += left if sample.values[feature] <= boundary else right
    return max(0.0, intercept + fsum(importance)), tuple(importance)
