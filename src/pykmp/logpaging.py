# SPDX-FileCopyrightText: 2026 Jan Kundrát <jkt@jankundrat.com>
#
# SPDX-License-Identifier: Apache-2.0

"""
Adaptive paging for reading a range of log entries via GetLogIDPastAbs (CID=B8h).

GetLogIDPastAbs has no documented byte-budget parameter (unlike the GetLogTimePresent
family in KMP spec section 4.2, which has an explicit MaxL and a size formula) - the
meter's own response buffer limit is undocumented and only observable as a response
shorter than what was requested.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import attrs

if TYPE_CHECKING:
    from collections.abc import Callable, MutableMapping, Sequence


def fill_window(
    window_bottom: int,
    window_top: int,
    page_size: int,
    fetch: Callable[[int, int], tuple[int, bool]],
) -> int:
    """
    Read the inclusive log-ID range [window_bottom, window_top], oldest-page-first.

    Calls `fetch(log_id, num_entries)` once per underlying request; `fetch` must return
    `(actual, truncated)`, where `actual` is understood - like GetLogIDPastAbs itself -
    to cover [log_id - actual + 1, log_id], i.e. the *newer* end of what was requested.
    `truncated` means the meter's own buffer is why `actual` fell short of what was
    asked for, as opposed to some unrelated reason (e.g. skipping one bad record after a
    checksum error) - only a truncated response shrinks page_size. actual == 0 gives up
    on the remainder of this window.

    `page_size` shrinks (permanently, for the rest of this call) the first time a
    response is reported truncated, and is never grown back. Returns the (possibly
    shrunk) page_size so callers can carry it into their next call - e.g. the next
    register, or the next window - instead of rediscovering the limit from scratch.
    """
    lid = window_top
    while lid >= window_bottom:
        requested = min(lid - window_bottom + 1, page_size)
        actual, truncated = fetch(lid, requested)
        if actual < 1:
            break
        if truncated:
            page_size = actual
        lid -= actual
    return page_size


@attrs.frozen(kw_only=True)
class ReadRange:
    """What to read and how to chunk it for read_checkpointed()."""

    lo: int
    hi: int
    checkpoint_window_size: int
    reg_ids: Sequence[int]
    default_page_size: int


def read_checkpointed(
    spec: ReadRange,
    page_sizes: MutableMapping[int, int],
    fetch: Callable[[int, int, int], tuple[int, bool]],
    checkpoint: Callable[[int, int], None],
) -> None:
    """
    Read spec.lo..spec.hi oldest-window-first, checkpointing once per window.

    Windows are up to `spec.checkpoint_window_size` log IDs, independent of any
    register's own transfer size, since different registers pack a different number of
    bytes per record and so have a different real limit (see fill_window). Each register
    keeps its own entry in `page_sizes` (mutated in place; missing keys default to
    `spec.default_page_size`), carried across windows and across calls, so a limit
    learned for one register never affects another's.

    `fetch(rid, log_id, num_entries)` is as for fill_window's `fetch`, plus which
    register the call is for. `checkpoint(window_bottom, window_top)` is called once a
    window has been fully read for every register in `spec.reg_ids`, and should persist
    whatever the caller's own `fetch` accumulated as a side effect - a window is never
    partially checkpointed, so an exception raised from `fetch` (e.g. on a communication
    failure) leaves only whole, already-checkpointed windows behind; the in-progress
    window's work is simply repeated on the next call with the same `spec.lo`.
    """
    window_bottom = spec.lo
    while window_bottom <= spec.hi:
        window_top = min(window_bottom + spec.checkpoint_window_size - 1, spec.hi)
        for rid in spec.reg_ids:

            def fetch_for_rid(
                log_id: int, num_entries: int, rid: int = rid
            ) -> tuple[int, bool]:
                return fetch(rid, log_id, num_entries)

            page_sizes[rid] = fill_window(
                window_bottom,
                window_top,
                page_sizes.get(rid, spec.default_page_size),
                fetch_for_rid,
            )
        checkpoint(window_bottom, window_top)
        window_bottom = window_top + 1
