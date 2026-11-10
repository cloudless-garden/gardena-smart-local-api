# SPDX-FileCopyrightText: 2026 GARDENA GmbH
#
# SPDX-License-Identifier: LGPL-3.0-or-later

import asyncio

from ..messages import ErrorMessage, Reply


class PendingReplies:
    """Futures for requests waiting on their reply, by request id.

    The read loop resolves them; a dropped connection fails them all.
    """

    def __init__(self) -> None:
        self._futures: dict[str, asyncio.Future[Reply | ErrorMessage]] = {}

    def expect(
        self, request_ids: list[str]
    ) -> dict[str, asyncio.Future[Reply | ErrorMessage]]:
        """Register the ids; the futures come back in the order of the ids."""
        if not self._futures.keys().isdisjoint(request_ids):
            raise ValueError("A request with the same request_id is already waiting")
        loop = asyncio.get_running_loop()
        futures = {rid: loop.create_future() for rid in request_ids}
        self._futures.update(futures)
        return futures

    def forget(self, request_ids: list[str]) -> None:
        for rid in request_ids:
            self._futures.pop(rid, None)

    def resolve(self, message: Reply | ErrorMessage) -> bool:
        """Hand the message to its request; return False if none is waiting."""
        if message.request_id is None:
            return False
        future = self._futures.pop(message.request_id, None)
        if future is None:
            return False
        if not future.done():
            future.set_result(message)
        return True

    def fail_all(self) -> None:
        """Fail every waiting request, because the connection is gone."""
        for future in self._futures.values():
            if not future.done():
                future.set_exception(
                    ConnectionError("WebSocket disconnected before a reply arrived")
                )
        self._futures.clear()
