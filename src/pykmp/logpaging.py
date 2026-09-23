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

if TYPE_CHECKING:
    from collections.abc import Callable


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
