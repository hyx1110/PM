from datetime import datetime

import pytest


def overlaps(new_start: datetime, new_end: datetime, existing_start: datetime, existing_end: datetime) -> bool:
    return new_start < existing_end and new_end > existing_start


def dt(hour: int, minute: int = 0) -> datetime:
    return datetime(2026, 10, 1, hour, minute)


@pytest.mark.parametrize(
    ("new_start", "new_end", "expected"),
    [
        (dt(10), dt(11), True),       # 完全包含
        (dt(8), dt(10), True),        # 左侧相交
        (dt(11), dt(13), True),       # 右侧相交
        (dt(8), dt(13), True),        # 完全覆盖
        (dt(12), dt(14), False),      # 右边界相接
        (dt(7), dt(9), False),        # 左边界相接
        (dt(13), dt(14), False),      # 不相交
        (dt(9), dt(12), True),        # 完全相同
    ],
)
def test_overlap_formula(new_start: datetime, new_end: datetime, expected: bool) -> None:
    assert overlaps(new_start, new_end, dt(9), dt(12)) is expected

