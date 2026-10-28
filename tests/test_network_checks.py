import socket
import ssl
import threading
from unittest.mock import Mock

import httpcore
import httpx
import pytest

from app import network_checks as checks
from app.network_security import UnsafeDestination, public_address
from app.network_transport import DeadlineStream, PinnedBackend

PUBLIC = "93.184.216.34"


@pytest.fixture(autouse=True)
def no_external_network(monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", Mock(side_effect=AssertionError("Unmocked DNS")))
    monkeypatch.setattr(socket, "socket", Mock(side_effect=AssertionError("Unmocked socket")))


@pytest.fixture
def resolved(monkeypatch):
    resolver = Mock(return_value=[PUBLIC])
    monkeypatch.setattr(checks, "resolve", resolver)
    return resolver


def test_dns_success(resolved):
    result = checks.check(checks.Target("DNS", "example.com"), 1)
    assert result.outcome == "success"
    assert result.details["resolved_addresses"] == [PUBLIC]
    assert result.duration_ms >= 0


@pytest.mark.parametrize(
    "error,code",
    [
        (socket.gaierror("synthetic secret"), "DNS_ERROR"),
        (TimeoutError(), "TIMEOUT"),
        (checks.ResolverBusy(), "DNS_BUSY"),
        (OSError("synthetic secret"), "CONNECTION_ERROR"),
    ],
)
def test_dns_failures(resolved, error, code):
    resolved.side_effect = error
    result = checks.check(checks.Target("DNS", "example.com"), 1)
    assert result.error_code == code and result.outcome == "failure"
    assert "secret" not in str(result)


@pytest.mark.parametrize(
    "error,code",
    [
        (None, None),
        (ConnectionRefusedError(), "CONNECTION_REFUSED"),
        (TimeoutError(), "TIMEOUT"),
        (OSError(), "CONNECTION_ERROR"),
    ],
)
def test_tcp_outcomes(monkeypatch, resolved, error, code):
    connect = Mock(side_effect=error)
    monkeypatch.setattr(checks, "connect_tcp", connect)
    result = checks.check(checks.Target("TCP", "example.com", 443), 1)
    assert result.error_code == code
    assert result.outcome == ("failure" if code else "success")
    assert connect.call_args.args[:2] == (PUBLIC, 443)
    assert 0 < connect.call_args.args[2] <= 1


def test_socket_closes_and_connects_numeric_address(monkeypatch):
    connection = Mock()
    connection.__enter__ = Mock(return_value=connection)
    connection.__exit__ = Mock(return_value=False)
    factory = Mock(return_value=connection)
    monkeypatch.setattr(socket, "socket", factory)
    checks.connect_tcp(PUBLIC, 443, 1)
    connection.connect.assert_called_once_with((PUBLIC, 443))
    connection.settimeout.assert_called_once_with(1)
    connection.__exit__.assert_called_once()
    connection.connect.side_effect = ConnectionRefusedError()
    with pytest.raises(ConnectionRefusedError):
        checks.connect_tcp(PUBLIC, 443, 1)
    assert connection.__exit__.call_count == 2


@pytest.mark.parametrize(
    "address",
    [
        "127.0.0.1",
        "0.0.0.0",
        "10.0.0.1",
        "172.16.0.1",
        "192.168.1.1",
        "169.254.169.254",
        "100.100.100.200",
        "224.0.0.1",
        "240.0.0.1",
        "198.18.0.1",
        "192.0.0.9",
        "168.63.129.16",
        "::",
        "::1",
        "fc00::1",
        "fe80::1",
        "ff02::1",
        "2001:db8::1",
        "::ffff:8.8.8.8",
        "64:ff9b::a00:1",
        "2002:0808:0808::1",
        "fe80::1%eth0",
    ],
)
def test_special_addresses_blocked(address):
    with pytest.raises(UnsafeDestination):
        public_address(address)


@pytest.mark.parametrize("addresses", [["127.0.0.1"], [PUBLIC, "10.0.0.1"], ["::1"]])
def test_resolved_unsafe_answers_never_connect(monkeypatch, resolved, addresses):
    resolved.return_value = addresses
    connect = Mock(side_effect=AssertionError("Unsafe connection attempted"))
    monkeypatch.setattr(checks, "connect_tcp", connect)
    monkeypatch.setattr(checks, "http_probe", connect)
    for kind in ("DNS", "TCP", "HTTP"):
        result = checks.check(checks.Target(kind, "example.com", 443, "https", "/"), 1)
        assert result.error_code == "UNSAFE_DESTINATION"
    connect.assert_not_called()


@pytest.mark.parametrize(
    "status,expected",
    [(200, None), (204, None), (302, None), (404, "HTTP_STATUS"), (500, "HTTP_STATUS")],
)
def test_http_status(monkeypatch, resolved, status, expected):
    probe = Mock(return_value=(status, None, {"body_read": False}))
    monkeypatch.setattr(checks, "http_probe", probe)
    result = checks.check(checks.Target("HTTP", "example.com", 443, "https", "/health"), 1)
    assert result.status_code == status and result.error_code == expected
    assert probe.call_args.args[1] == PUBLIC


@pytest.mark.parametrize(
    "error,code",
    [
        (httpx.ReadTimeout("timeout"), "TIMEOUT"),
        (httpx.ConnectError("connection"), "CONNECTION_ERROR"),
        (httpx.RemoteProtocolError("bad response"), "HTTP_PROTOCOL_ERROR"),
        (ssl.SSLCertVerificationError("certificate"), "TLS_ERROR"),
    ],
)
def test_http_failures(monkeypatch, resolved, error, code):
    monkeypatch.setattr(checks, "http_probe", Mock(side_effect=error))
    assert (
        checks.check(checks.Target("HTTP", "example.com", 443, "https", "/"), 1).error_code == code
    )


def test_wrapped_tls_verification_failure(monkeypatch, resolved):
    error = httpx.ConnectError("untrusted response text")
    error.__cause__ = ssl.SSLCertVerificationError("untrusted certificate text")
    monkeypatch.setattr(checks, "http_probe", Mock(side_effect=error))
    assert (
        checks.check(checks.Target("HTTP", "example.com", 443, "https", "/"), 1).error_code
        == "TLS_ERROR"
    )


def test_http_transport_pins_peer_preserves_tls_and_never_reads_body(monkeypatch):
    monkeypatch.setenv("HTTPS_PROXY", "http://user:secret@127.0.0.1:8080")
    monkeypatch.setenv("HTTP_PROXY", "http://user:secret@127.0.0.1:8080")
    stream = Mock()
    stream.get_extra_info.side_effect = lambda key: (PUBLIC, 443) if key == "server_addr" else None
    stream.start_tls.return_value = stream
    stream.read.return_value = (
        b"HTTP/1.1 302 Found\r\nLocation: http://127.0.0.1/secret\r\nContent-Length: 500\r\n\r\n"
    )
    backend = Mock(return_value=stream)
    monkeypatch.setattr(httpcore.SyncBackend, "connect_tcp", backend)
    status, error, info = checks.http_probe(
        checks.Target("HTTP", "example.com", 443, "https", "/health"), PUBLIC, 1
    )
    assert status == 302 and error is None and info["redirect_not_followed"]
    assert info["body_read"] is False
    assert backend.call_args.args[:2] == (PUBLIC, 443)
    assert backend.call_count == 1
    assert stream.read.call_count == 1  # Header read only; no follow-up body read.
    tls_context, server_name, _ = stream.start_tls.call_args.args
    assert tls_context.verify_mode == ssl.CERT_REQUIRED and tls_context.check_hostname
    assert server_name == "example.com"
    written = b"".join(call.args[0] for call in stream.write.call_args_list)
    assert b"GET /health HTTP/1.1" in written and b"Host: example.com" in written
    assert checks.USER_AGENT.encode() in written
    assert b"Authorization:" not in written and b"Cookie:" not in written
    stream.close.assert_called()


@pytest.mark.parametrize("peer", ["10.0.0.1", "8.8.8.8"])
def test_actual_peer_mismatch_closes_connection(monkeypatch, peer):
    stream = Mock()
    stream.get_extra_info.return_value = (peer, 443)
    monkeypatch.setattr(httpcore.SyncBackend, "connect_tcp", Mock(return_value=stream))
    with pytest.raises((UnsafeDestination, httpcore.ConnectError)):
        PinnedBackend("example.com", 443, PUBLIC, 1).connect_tcp("example.com", 443)
    stream.close.assert_called_once()
    stream.write.assert_not_called()


def test_backend_rejects_new_destinations():
    with pytest.raises(httpcore.ConnectError):
        PinnedBackend("example.com", 443, PUBLIC, 1).connect_tcp("attacker.com", 443)


def test_http_response_size_limit(monkeypatch):
    stream = Mock()
    stream.get_extra_info.side_effect = lambda key: (PUBLIC, 80) if key == "server_addr" else None
    stream.read.return_value = b"HTTP/1.1 200 OK\r\nContent-Length: 9999999\r\n\r\n"
    monkeypatch.setattr(httpcore.SyncBackend, "connect_tcp", Mock(return_value=stream))
    status, error, info = checks.http_probe(
        checks.Target("HTTP", "example.com", 80, "http", "/"), PUBLIC, 1
    )
    assert status == 200 and error == "RESPONSE_TOO_LARGE" and info["body_read"] is False
    stream.close.assert_called()


def test_total_deadline_and_wire_limit(monkeypatch):
    stream = Mock()
    wrapped = DeadlineStream(stream, 0)
    with pytest.raises(httpcore.ReadTimeout):
        wrapped.read(10)
    stream.close.assert_called()
    wrapped = DeadlineStream(stream, float("inf"))
    wrapped.received = 65536
    with pytest.raises(httpcore.ReadError):
        wrapped.read(10)


def test_dns_timeout_and_bounded_workers(monkeypatch):
    from app import network_checks

    release = threading.Event()
    started = threading.Event()

    def slow(*args, **kwargs):
        started.set()
        release.wait(1)
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (PUBLIC, 443))]

    monkeypatch.setattr(network_checks, "DNS_SLOTS", threading.BoundedSemaphore(1))
    monkeypatch.setattr(socket, "getaddrinfo", slow)
    try:
        with pytest.raises(TimeoutError):
            checks.resolve("example.com", 443, 0.01)
        assert started.is_set()
        with pytest.raises(checks.ResolverBusy):
            checks.resolve("example.com", 443, 0.01)
    finally:
        release.set()


def test_actual_resolver_and_public_ipv6(monkeypatch):
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        Mock(
            return_value=[
                (socket.AF_INET6, socket.SOCK_STREAM, 6, "", ("2606:4700:4700::1111", 443, 0, 0))
            ]
        ),
    )
    assert checks.resolve("example.com", 443, 1) == ["2606:4700:4700::1111"]
    assert public_address("2606:4700:4700::1111") == "2606:4700:4700::1111"
