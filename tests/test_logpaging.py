# SPDX-FileCopyrightText: 2026 Jan Kundrát <jkt@jankundrat.com>
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from pykmp.logpaging import fill_window


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
