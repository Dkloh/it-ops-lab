"""Bounded public-only DNS/TCP/HTTP observations, without persistence or HTTP routes."""

import ipaddress
import queue
import socket
import ssl
import threading
from dataclasses import dataclass
from time import monotonic

import httpx

from app.network_security import UnsafeDestination, hostname, public_address
from app.network_transport import PinnedTransport

DNS_SLOTS = threading.BoundedSemaphore(2)
MAX_HEADER_BYTES = 16 * 1024
MAX_DECLARED_BODY_BYTES = 1024 * 1024
USER_AGENT = "IT-Ops-Lab-Network-Diagnostics/1.0"


@dataclass(frozen=True)
class Target:
    check_type: str
    host: str
    port: int | None = None
    scheme: str | None = None
    path: str | None = None


@dataclass(frozen=True)
class Observation:
    outcome: str
    duration_ms: float
    error_code: str | None
    status_code: int | None
    details: dict


class ResolverBusy(Exception):
    pass


def resolve(host: str, port: int, timeout: float) -> list[str]:
    try:
        return [str(ipaddress.ip_address(host))]
    except ValueError:
        pass
    slots = DNS_SLOTS
    if not slots.acquire(blocking=False):
        raise ResolverBusy
    result = queue.Queue(maxsize=1)

    def lookup():
        try:
            addresses = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
            result.put(([row[4][0] for row in addresses], None))
        except OSError as exc:
            result.put((None, exc))
        finally:
            slots.release()

    threading.Thread(target=lookup, daemon=True).start()
    try:
        addresses, error = result.get(timeout=timeout)
    except queue.Empty as exc:
        raise TimeoutError from exc
    if error is not None:
        raise error
    return addresses


def connect_tcp(address: str, port: int, timeout: float):
    # Numeric socket.connect avoids a second DNS lookup, including legacy numeric parsing.
    address = public_address(address)
    family = socket.AF_INET6 if ":" in address else socket.AF_INET
    with socket.socket(family, socket.SOCK_STREAM) as connection:
        connection.settimeout(timeout)
        connection.connect((address, port))


def http_probe(target: Target, address: str, timeout: float) -> tuple[int, str | None, dict]:
    address = public_address(address)
    original_host = f"[{target.host}]" if ":" in target.host else target.host
    url = f"{target.scheme}://{original_host}:{target.port}{target.path}"
    with httpx.Client(
        transport=PinnedTransport(target.host, target.port, address, timeout),
        trust_env=False,
        follow_redirects=False,
        timeout=httpx.Timeout(timeout),
        headers={"User-Agent": USER_AGENT},
    ) as client:
        with client.stream("GET", url) as response:
            info = {"redirect_not_followed": 300 <= response.status_code < 400, "body_read": False}
            if sum(len(key) + len(value) for key, value in response.headers.raw) > MAX_HEADER_BYTES:
                return response.status_code, "RESPONSE_TOO_LARGE", info
            length = response.headers.get("content-length")
            if length is not None:
                try:
                    if int(length) > MAX_DECLARED_BODY_BYTES or int(length) < 0:
                        return response.status_code, "RESPONSE_TOO_LARGE", info
                except ValueError:
                    return response.status_code, "HTTP_PROTOCOL_ERROR", info
            # Never iterate/read the response stream; closing discards the body.
            return response.status_code, None, info


def certificate_failure(error: BaseException) -> bool:
    seen = set()
    while error is not None and id(error) not in seen:
        seen.add(id(error))
        if isinstance(error, ssl.SSLCertVerificationError):
            return True
        error = error.__cause__ or error.__context__
    return False


def check(target: Target, timeout: float) -> Observation:
    started = monotonic()
    details = {"host": target.host, "port": target.port, "check_type": target.check_type}
    status = None

    def finish(error=None):
        return Observation(
            "failure" if error else "success",
            round((monotonic() - started) * 1000, 2),
            error,
            status,
            details,
        )

    try:
        hostname(target.host)  # Revalidate persisted configuration before resolution.
        addresses = resolve(target.host, target.port or 443, timeout)
        if not addresses:
            return finish("DNS_ERROR")
        # Reject the entire answer if even one address is unsafe, rather than cherry-picking.
        addresses = sorted({public_address(address) for address in addresses})
        details["resolved_addresses"] = addresses
        if target.check_type == "DNS":
            return finish()
        remaining = timeout - (monotonic() - started)
        if remaining <= 0:
            return finish("TIMEOUT")
        selected = addresses[0]
        details["connected_address"] = selected
        if target.check_type == "TCP":
            connect_tcp(selected, target.port, remaining)
        else:
            status, error, info = http_probe(target, selected, remaining)
            details.update(info)
            if error:
                return finish(error)
            if not 200 <= status < 400:
                return finish("HTTP_STATUS")
        return finish()
    except UnsafeDestination:
        return finish("UNSAFE_DESTINATION")
    except ResolverBusy:
        return finish("DNS_BUSY")
    except socket.gaierror:
        return finish("DNS_ERROR")
    except (TimeoutError, httpx.TimeoutException):
        return finish("TIMEOUT")
    except ConnectionRefusedError:
        return finish("CONNECTION_REFUSED")
    except httpx.ConnectError as exc:
        return finish("TLS_ERROR" if certificate_failure(exc) else "CONNECTION_ERROR")
    except ssl.SSLCertVerificationError:
        return finish("TLS_ERROR")
    except httpx.ProtocolError:
        return finish("HTTP_PROTOCOL_ERROR")
    except (OSError, httpx.RequestError):
        return finish("CONNECTION_ERROR")
