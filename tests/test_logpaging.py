# SPDX-FileCopyrightText: 2026 Jan Kundrát <jkt@jankundrat.com>
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import itertools

import pytest

from pykmp.logpaging import ReadRange, fill_window, read_checkpointed


class FakeMeter:
    """
    Simulates a GetLogIDPastAbs-speaking device with a fixed internal buffer limit.

    `fetch()` matches the real protocol: a request for `log_id`/`num_entries` is
    answered with entries covering [log_id - actual + 1, log_id] (the *newer* end of
    what was asked for), where `actual = min(num_entries, buffer_limit)`. Every call is
    recorded so tests can assert on the exact request sequence, not just the outcome.
    """

    def __init__(self, buffer_limit: int) -> None:
        self.buffer_limit = buffer_limit
        self.calls: list[tuple[int, int]] = []

    def fetch(self, log_id: int, num_entries: int) -> tuple[int, bool]:
        self.calls.append((log_id, num_entries))
        actual = min(num_entries, self.buffer_limit)
        return actual, actual < num_entries


def covered_lids(meter: FakeMeter) -> set[int]:
    """Reconstruct which LIDs were actually delivered, from the recorded calls."""
    lids: set[int] = set()
    for log_id, num_entries in meter.calls:
        actual = min(num_entries, meter.buffer_limit)
        lids.update(range(log_id - actual + 1, log_id + 1))
    return lids


def test_fits_in_one_request_no_truncation() -> None:
    unlimited = 1000
    meter = FakeMeter(buffer_limit=unlimited)

    final_page_size = fill_window(
        window_bottom=100, window_top=110, page_size=unlimited, fetch=meter.fetch
    )

    assert meter.calls == [(110, 11)]  # one shot, anchored at the top of the window
    assert final_page_size == unlimited  # never truncated, nothing learned
    assert covered_lids(meter) == set(range(100, 111))


def test_truncation_is_learned_once_and_not_repeated() -> None:
    # The window is far bigger than the device can actually deliver in one response.
    small_buffer = 7
    meter = FakeMeter(buffer_limit=small_buffer)

    final_page_size = fill_window(
        window_bottom=1, window_top=1000, page_size=1000, fetch=meter.fetch
    )

    assert final_page_size == small_buffer
    # First call optimistically asks for the whole window and gets truncated down.
    assert meter.calls[0] == (1000, 1000)
    # Every later call already asks for (at most) the learned size - it never asks
    # for 1000 again.
    retries = meter.calls[1:]
    assert all(requested <= small_buffer for _log_id, requested in retries)
    # ... and in fact every one of them is a full-sized request except the last, which
    # is whatever's left to reach window_bottom.
    full_retries = meter.calls[1:-1]
    assert [requested for _log_id, requested in full_retries] == [small_buffer] * len(
        full_retries
    )
    # No gaps, no overlaps, no data lost to the retries.
    assert covered_lids(meter) == set(range(1, 1001))


def test_page_size_carries_over_into_the_next_call() -> None:
    # Mimics dump-logs.py threading page_size from one register's fill_window() call
    # into the next register's, so the limit is discovered once per run, not once per
    # register.
    small_buffer = 5
    meter = FakeMeter(buffer_limit=small_buffer)

    page_size = fill_window(
        window_bottom=1, window_top=20, page_size=1000, fetch=meter.fetch
    )
    assert page_size == small_buffer
    calls_in_first_register = len(meter.calls)

    page_size = fill_window(
        window_bottom=1, window_top=20, page_size=page_size, fetch=meter.fetch
    )
    assert page_size == small_buffer
    # Second register never re-tries the oversized 1000 request; every one of its calls
    # is already sized to the previously-learned limit.
    later_calls = meter.calls[calls_in_first_register:]
    assert all(requested <= small_buffer for _log_id, requested in later_calls)


def test_non_truncated_short_response_does_not_shrink_page_size() -> None:
    # A single skipped/errored LID (e.g. a checksum failure) looks like a short response
    # too, but it isn't evidence of a buffer limit - fetch() reports it via
    # truncated=False, and page_size must be left alone.
    starting_page_size = 1000
    bad_lid = 50
    calls: list[tuple[int, int]] = []

    def flaky_fetch(log_id: int, num_entries: int) -> tuple[int, bool]:
        calls.append((log_id, num_entries))
        if log_id == bad_lid:
            return 1, False  # one bad LID recorded as an error, not a buffer limit
        return num_entries, False

    final_page_size = fill_window(
        window_bottom=1, window_top=100, page_size=starting_page_size, fetch=flaky_fetch
    )

    assert final_page_size == starting_page_size  # unchanged - never "truncated"
    assert calls[0] == (100, 100)  # first request still covers the whole window at once


def test_gives_up_on_a_dead_response_without_looping_forever() -> None:
    starting_page_size = 50

    def dead_fetch(_log_id: int, _num_entries: int) -> tuple[int, bool]:
        return 0, False

    final_page_size = fill_window(
        window_bottom=1, window_top=100, page_size=starting_page_size, fetch=dead_fetch
    )

    assert final_page_size == starting_page_size  # nothing learned, nothing to shrink


class FakeMeterPerRid:
    """Like FakeMeter, but with an independent buffer limit per register (RID)."""

    def __init__(self, buffer_limits: dict[int, int]) -> None:
        self.buffer_limits = buffer_limits
        self.calls: list[tuple[int, int, int]] = []

    def fetch(self, rid: int, log_id: int, num_entries: int) -> tuple[int, bool]:
        self.calls.append((rid, log_id, num_entries))
        actual = min(num_entries, self.buffer_limits[rid])
        return actual, actual < num_entries


def covered_pairs(
    calls: list[tuple[int, int, int]], buffer_limits: dict[int, int]
) -> set[tuple[int, int]]:
    """Reconstruct which (rid, lid) pairs were delivered, from the recorded calls."""
    pairs: set[tuple[int, int]] = set()
    for rid, log_id, num_entries in calls:
        actual = min(num_entries, buffer_limits[rid])
        pairs.update((rid, lid) for lid in range(log_id - actual + 1, log_id + 1))
    return pairs


def test_read_checkpointed_learns_page_size_independently_per_register() -> None:
    # RID 1's values are narrow enough to never hit the buffer limit; RID 2's are wide
    # enough that they do. One must not affect the other's learned page size.
    buffer_limits = {1: 1000, 2: 5}
    meter = FakeMeterPerRid(buffer_limits)
    page_sizes: dict[int, int] = {}
    checkpoints: list[tuple[int, int]] = []

    read_checkpointed(
        ReadRange(
            lo=1,
            hi=20,
            checkpoint_window_size=1000,
            reg_ids=[1, 2],
            default_page_size=1000,
        ),
        page_sizes,
        meter.fetch,
        lambda wb, wt: checkpoints.append((wb, wt)),
    )

    assert page_sizes == {1: 1000, 2: 5}
    assert checkpoints == [(1, 20)]  # whole range fits in a single checkpoint window
    assert covered_pairs(meter.calls, buffer_limits) == {
        (rid, lid) for rid in (1, 2) for lid in range(1, 21)
    }


class AbortedReadError(Exception):
    """Simulates fetch() raising for any reason partway through a read."""


class AbortingMeterPerRid(FakeMeterPerRid):
    """A FakeMeterPerRid that raises AbortedReadError once a call budget is used up."""

    def __init__(self, buffer_limits: dict[int, int], calls_allowed: int) -> None:
        super().__init__(buffer_limits)
        self.calls_allowed = calls_allowed

    def fetch(self, rid: int, log_id: int, num_entries: int) -> tuple[int, bool]:
        if len(self.calls) >= self.calls_allowed:
            raise AbortedReadError
        return super().fetch(rid, log_id, num_entries)


def test_exception_mid_window_leaves_only_whole_windows_and_resumes_without_gaps() -> (
    None
):
    # Not specific to any particular failure mode (network, USB, Ctrl-C, ...) - the
    # guarantee is about *any* exception out of fetch(), which is why AbortedReadError
    # here is a plain, made-up exception rather than something protocol-specific.
    buffer_limits = {1: 3, 2: 4}
    reg_ids = [1, 2]
    lo, hi = 1, 30
    checkpoint_window_size = 8
    page_sizes: dict[int, int] = {}
    checkpoints: list[tuple[int, int]] = []

    def record_checkpoint(window_bottom: int, window_top: int) -> None:
        checkpoints.append((window_bottom, window_top))

    # Comfortably fewer calls than a full, uninterrupted read of this range would take,
    # so the abort lands mid-run rather than after everything already completed.
    aborting_meter = AbortingMeterPerRid(buffer_limits, calls_allowed=10)
    with pytest.raises(AbortedReadError):
        read_checkpointed(
            ReadRange(
                lo=lo,
                hi=hi,
                checkpoint_window_size=checkpoint_window_size,
                reg_ids=reg_ids,
                default_page_size=1000,
            ),
            page_sizes,
            aborting_meter.fetch,
            record_checkpoint,
        )

    # Whatever got checkpointed before the abort is a gap-free prefix from `lo` - never
    # a window skipped ahead of an unfinished one.
    assert checkpoints  # the abort happened after at least one window completed
    assert checkpoints[0][0] == lo
    for (_bottom1, top1), (bottom2, _top2) in itertools.pairwise(checkpoints):
        assert top1 + 1 == bottom2
    # ... and it really did interrupt things - it didn't just finish quietly.
    last_checkpointed = checkpoints[-1][1]
    assert last_checkpointed < hi

    # Resume: pick up right after the last checkpointed window, reusing the page_sizes
    # already learned (a fresh dict would just re-learn the same numbers, but a real run
    # reads this back from wherever it persisted page_sizes - the point is that nothing
    # *forces* relearning).
    resumed_meter = FakeMeterPerRid(buffer_limits)
    read_checkpointed(
        ReadRange(
            lo=last_checkpointed + 1,
            hi=hi,
            checkpoint_window_size=checkpoint_window_size,
            reg_ids=reg_ids,
            default_page_size=1000,
        ),
        page_sizes,
        resumed_meter.fetch,
        record_checkpoint,
    )

    assert checkpoints[0][0] == lo
    assert checkpoints[-1][1] == hi
    for (_bottom1, top1), (bottom2, _top2) in itertools.pairwise(checkpoints):
        assert top1 + 1 == bottom2  # still no gap or overlap across the resume boundary
    assert page_sizes == buffer_limits  # both registers' real limits, not the default
    # The resumed meter never re-tries the oversized default - every one of its calls is
    # already sized to what was learned before the abort.
    assert all(
        num_entries <= buffer_limits[rid]
        for rid, _log_id, num_entries in resumed_meter.calls
    )
