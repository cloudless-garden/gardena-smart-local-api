"""WebSocket communication helper with async queue and request tracking."""

import asyncio
import json
import logging
import ssl
import uuid
from datetime import datetime

import aiohttp
from pydantic import BaseModel, Field

from smart_system_local.devices.messages import Event, Request, Response

logger = logging.getLogger(__name__)


class WebSocketMessage(BaseModel):
    """Represents a WebSocket message with metadata."""

    model_config = {"arbitrary_types_allowed": True}

    data: list[Event | Response]
    timestamp: datetime = Field(default_factory=datetime.now)
    raw: str = ""


class PendingRequest(BaseModel):
    """Tracks a pending request waiting for a response."""

    model_config = {"arbitrary_types_allowed": True}

    request_id: str
    future: asyncio.Future
    timeout_handle: asyncio.TimerHandle | None = None


class WebSocketHelper:
    """
    Async WebSocket helper for managing connections and message queues.

    Features:
    - Connect from connection details or use existing websocket
    - Async queue for received events
    - Send commands with optional wait-for-reply
    - Request/response tracking using request-id
    - Configurable timeouts

    Usage:
    - WebSocketHelper(ws) for existing connections
    - WebSocketHelper.from_config(host, port, ...) for new connections
    """

    def __init__(self, websocket: aiohttp.ClientWebSocketResponse):
        """
        Initialize WebSocket helper with an existing WebSocket connection.

        Args:
            websocket: Existing WebSocket connection
        """
        self._ws: aiohttp.ClientWebSocketResponse = websocket
        self._message_queue: asyncio.Queue[WebSocketMessage] = asyncio.Queue()
        self._pending_requests: dict[str, PendingRequest] = {}
        self._listener_task: asyncio.Task | None = None
        self._session: aiohttp.ClientSession | None = None
        self._owns_session = False
        self._owns_websocket = False
        self._connected = False
        self._closed = False

    @classmethod
    async def from_config(
        cls,
        host: str,
        port: int,
        path: str = "/",
        use_ssl: bool = False,
        verify_ssl: bool = False,
        username: str | None = None,
        password: str | None = None,
    ) -> "WebSocketHelper":
        """
        Create and connect a WebSocketHelper from connection configuration.

        Args:
            host: Hostname to connect to
            port: Port number
            path: WebSocket path
            use_ssl: Whether to use SSL/TLS
            verify_ssl: Whether to verify SSL certificates
            username: Optional username for basic auth
            password: Optional password for basic auth

        Returns:
            Connected WebSocketHelper instance
        """
        # Create SSL context if needed
        ssl_context: ssl.SSLContext | bool = False
        if use_ssl:
            ssl_context = ssl.create_default_context()
            if not verify_ssl:
                ssl_context.check_hostname = False
                ssl_context.verify_mode = ssl.CERT_NONE

        # Build URL
        scheme = "wss" if use_ssl else "ws"
        url = f"{scheme}://{host}:{port}{path}"

        # Create session and connect
        session = aiohttp.ClientSession()
        auth = aiohttp.BasicAuth(username, password) if username and password else None

        ws = await session.ws_connect(url, ssl=ssl_context, auth=auth)

        # Create helper instance
        helper = cls(ws)
        helper._session = session
        helper._owns_session = True
        helper._owns_websocket = True

        return helper

    async def connect(self) -> None:
        """Start listening for WebSocket messages."""
        if self._connected:
            return

        if not self._ws:
            raise RuntimeError("No WebSocket connection available")

        self._connected = True
        self._listener_task = asyncio.create_task(self._listen())

    async def _listen(self) -> None:
        """Listen for incoming WebSocket messages and queue them."""
        if not self._ws:
            return

        try:
            async for msg in self._ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    try:
                        data = json.loads(msg.data)
                        ws_msg = WebSocketMessage(data=data, raw=msg.data)

                        # Check if this is a response to a pending request (only Response objects)
                        responses = [
                            item for item in ws_msg.data if isinstance(item, Response)
                        ]
                        if responses and await self._handle_response(responses):
                            # Response was handled, don't queue it
                            continue

                        # Queue the message for consumer
                        await self._message_queue.put(ws_msg)

                    except json.JSONDecodeError:
                        logger.warning(f"Non-JSON message, discarding: {msg.data}")
                    except Exception as e:
                        logger.warning(
                            f"Invalid message structure, discarding: {msg.data} - {e}"
                        )

                elif msg.type == aiohttp.WSMsgType.ERROR:
                    break
                elif msg.type == aiohttp.WSMsgType.CLOSED:
                    break

        except asyncio.CancelledError:
            pass
        finally:
            self._connected = False

    async def _handle_response(self, data: list[Response]) -> bool:
        """
        Check if data is a response to a pending request.

        Returns:
            True if this was a response that was handled, False otherwise
        """
        for item in data:
            if (request_id := item.request_id) in self._pending_requests:
                pending = self._pending_requests.pop(request_id)

                # Cancel timeout
                if pending.timeout_handle:
                    pending.timeout_handle.cancel()

                # Set result
                if not pending.future.done():
                    pending.future.set_result(item)

                return True

        return False

    async def send(
        self,
        request: Request | list[Request],
        wait_for_reply: bool = False,
        timeout: float = 30.0,
    ) -> Response | None:
        """
        Send a request through the WebSocket.

        Args:
            request: Request model or list of requests to send
            wait_for_reply: If True, wait for a response matching the request-id
            timeout: Timeout in seconds when waiting for reply

        Returns:
            Response dict if wait_for_reply=True, None otherwise

        Raises:
            asyncio.TimeoutError: If waiting for reply times out
            RuntimeError: If not connected
        """
        if not self._connected or not self._ws:
            raise RuntimeError("WebSocket not connected")

        # Convert to list if single request
        requests = request if isinstance(request, list) else [request]

        # Handle request ID for wait_for_reply
        request_id = None
        if wait_for_reply:
            # Use existing request_id or generate new one
            request_id = requests[0].request_id or str(uuid.uuid4())
            requests[0].request_id = request_id

            # Create pending request
            future = asyncio.get_event_loop().create_future()
            pending = PendingRequest(request_id=request_id, future=future)
            self._pending_requests[request_id] = pending

            # Setup timeout
            def on_timeout():
                if request_id in self._pending_requests:
                    pending_req = self._pending_requests.pop(request_id)
                    if not pending_req.future.done():
                        pending_req.future.set_exception(
                            asyncio.TimeoutError(
                                f"Request {request_id} timed out after {timeout}s"
                            )
                        )

            timeout_handle = asyncio.get_event_loop().call_later(timeout, on_timeout)
            pending.timeout_handle = timeout_handle

        # Send the message
        data = [req.model_dump(exclude_none=True) for req in requests]
        message = json.dumps(data)
        await self._ws.send_str(message)

        # Wait for reply if requested
        if wait_for_reply and request_id in self._pending_requests:
            try:
                result = await self._pending_requests[request_id].future
                return result
            except asyncio.TimeoutError:
                raise

        return None

    async def receive(self, timeout: float | None = None) -> WebSocketMessage:
        """
        Receive a message from the queue.

        Args:
            timeout: Optional timeout in seconds

        Returns:
            WebSocketMessage from the queue

        Raises:
            asyncio.TimeoutError: If timeout expires
        """
        if timeout:
            return await asyncio.wait_for(self._message_queue.get(), timeout=timeout)
        return await self._message_queue.get()

    def has_messages(self) -> bool:
        """Check if there are messages in the queue."""
        return not self._message_queue.empty()

    async def close(self) -> None:
        """Close the WebSocket connection and cleanup."""
        self._closed = True

        # Cancel listener task
        if self._listener_task and not self._listener_task.done():
            self._listener_task.cancel()
            try:
                await self._listener_task
            except asyncio.CancelledError:
                pass

        # Cancel all pending requests
        for pending in self._pending_requests.values():
            if pending.timeout_handle:
                pending.timeout_handle.cancel()
            if not pending.future.done():
                pending.future.set_exception(
                    RuntimeError("WebSocket connection closed")
                )
        self._pending_requests.clear()

        # Close WebSocket if we own it
        if self._ws and self._owns_websocket:
            await self._ws.close()

        # Close session if we own it
        if self._session and self._owns_session:
            await self._session.close()

        self._connected = False

    @property
    def is_connected(self) -> bool:
        """Check if WebSocket is connected."""
        return self._connected and self._ws is not None and not self._ws.closed

    @property
    def queue_size(self) -> int:
        """Get the current size of the message queue."""
        return self._message_queue.qsize()

    async def __aenter__(self):
        """Async context manager entry."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()
