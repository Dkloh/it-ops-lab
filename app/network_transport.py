"""Small HTTPX/httpcore adapter: pinned numeric peer, verified original-host TLS, deadline."""

import ssl
from time import monotonic

import httpcore
import httpx

from app.network_security import public_address

MAX_WIRE_BYTES = 64 * 1024


class DeadlineStream(httpcore.NetworkStream):
    def __init__(self, stream, deadline):
        self.stream = stream
        self.deadline = deadline
        self.received = 0

    def remaining(self):
        remaining = self.deadline - monotonic()
        if remaining <= 0:
            self.close()
            raise httpcore.ReadTimeout("Network check deadline exceeded")
        return remaining

    def read(self, max_bytes, timeout=None):
        if self.received >= MAX_WIRE_BYTES:
            self.close()
            raise httpcore.ReadError("Network response limit exceeded")
        data = self.stream.read(min(max_bytes, MAX_WIRE_BYTES - self.received), self.remaining())
        self.received += len(data)
        return data

    def write(self, buffer, timeout=None):
        self.stream.write(buffer, self.remaining())

    def start_tls(self, ssl_context, server_hostname=None, timeout=None):
        return DeadlineStream(
            self.stream.start_tls(ssl_context, server_hostname, self.remaining()), self.deadline
        )

    def get_extra_info(self, info):
        return self.stream.get_extra_info(info)

    def close(self):
        self.stream.close()


class PinnedBackend(httpcore.NetworkBackend):
    def __init__(self, host, port, address, timeout):
        self.host, self.port = host, port
        self.address = public_address(address)
        self.deadline = monotonic() + timeout

    def connect_tcp(self, host, port, timeout=None, **kwargs):
        if host != self.host or port != self.port:
            raise httpcore.ConnectError("Unexpected destination")
        remaining = self.deadline - monotonic()
        if remaining <= 0:
            raise httpcore.ConnectTimeout("Network check deadline exceeded")
        stream = httpcore.SyncBackend().connect_tcp(self.address, port, timeout=remaining)
        # Verify the actual peer before TLS or sending HTTP bytes.
        peer = stream.get_extra_info("server_addr")
        try:
            if not peer or public_address(peer[0]) != self.address:
                raise httpcore.ConnectError("Unexpected connection peer")
        except Exception:
            stream.close()
            raise
        return DeadlineStream(stream, self.deadline)


class HeadersOnlyStream(httpx.SyncByteStream):
    def __init__(self, response):
        self.response = response

    def __iter__(self):
        return iter(())  # Availability checks never consume response bodies.

    def close(self):
        self.response.close()


class PinnedTransport(httpx.BaseTransport):
    def __init__(self, host, port, address, timeout):
        self.pool = httpcore.ConnectionPool(
            ssl_context=ssl.create_default_context(),
            retries=0,
            max_connections=1,
            max_keepalive_connections=0,
            network_backend=PinnedBackend(host, port, address, timeout),
        )

    def handle_request(self, request):
        try:
            response = self.pool.handle_request(
                httpcore.Request(
                    method=request.method,
                    url=httpcore.URL(
                        scheme=request.url.raw_scheme,
                        host=request.url.raw_host,
                        port=request.url.port,
                        target=request.url.raw_path,
                    ),
                    headers=request.headers.raw,
                    content=b"",
                    extensions=request.extensions,
                )
            )
        except httpcore.TimeoutException as exc:
            raise httpx.TimeoutException("Network check timed out", request=request) from exc
        except httpcore.NetworkError as exc:
            raise httpx.ConnectError("Network connection failed", request=request) from exc
        except httpcore.ProtocolError as exc:
            raise httpx.RemoteProtocolError("Invalid HTTP response", request=request) from exc
        return httpx.Response(
            response.status,
            headers=response.headers,
            stream=HeadersOnlyStream(response),
            extensions=response.extensions,
        )

    def close(self):
        self.pool.close()
