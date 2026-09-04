from decimal import Decimal

from .constants import SCORE_QUANTUM


def clamp(value: Decimal, lower: Decimal = Decimal(0), upper: Decimal = Decimal(100)) -> Decimal:
    return min(upper, max(lower, value))


def count_score(count: Decimal | int, scale: Decimal | int) -> Decimal:
    count_value = max(Decimal(0), Decimal(count))
    return Decimal(100) * (Decimal(1) - (-count_value / Decimal(scale)).exp())


def round_score(value: Decimal) -> Decimal:
    return clamp(value).quantize(SCORE_QUANTUM)


def weighted_average(parts: list[tuple[Decimal, Decimal]]) -> Decimal:
    return sum((value * weight for value, weight in parts), Decimal(0))


def interpolate(value: Decimal, points: tuple[tuple[Decimal, Decimal], ...]) -> Decimal:
    value = clamp(value)
    for (left_x, left_y), (right_x, right_y) in zip(points, points[1:], strict=False):
        if value <= right_x:
            position = (value - left_x) / (right_x - left_x)
            return left_y + position * (right_y - left_y)
    return points[-1][1]
