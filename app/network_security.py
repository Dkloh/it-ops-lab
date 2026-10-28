"""Destination validation shared by registration and immediate pre-connect checks."""

import ipaddress
import re


class UnsafeDestination(ValueError):
    pass


# Block special routing/translation endpoints even where is_global may be true.
SPECIAL = tuple(
    ipaddress.ip_network(value)
    for value in (
        "168.63.129.16/32",
        "192.0.0.0/24",
        "192.88.99.0/24",
        "64:ff9b::/96",
        "64:ff9b:1::/48",
        "2002::/16",
        "2001::/32",
    )
)


def public_address(value: str) -> str:
    try:
        address = ipaddress.ip_address(value)
    except ValueError as exc:
        raise UnsafeDestination("Destination must resolve to public IP addresses") from exc
    if (
        "%" in value
        or not address.is_global
        or address.is_multicast
        or address.is_reserved
        or any(address in network for network in SPECIAL if network.version == address.version)
        or (isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped is not None)
    ):
        raise UnsafeDestination("Destination must resolve to public IP addresses")
    return str(address)


def hostname(value: str) -> str:
    if not value or value != value.strip() or len(value) > 253:
        raise ValueError("Use a public IP or ASCII DNS hostname")
    try:
        ipaddress.ip_address(value)
    except ValueError:
        # Disallow legacy numeric IP forms, credentials, URLs, ports, scope IDs and IDN ambiguity.
        labels = value.lower().split(".")
        if (
            len(labels) < 2
            or all(label.isdigit() for label in labels)
            or not re.fullmatch(r"[a-z]{2,63}", labels[-1])
            or any(
                not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label) for label in labels
            )
            or labels[-1] in {"localhost", "local", "internal", "test", "invalid"}
        ):
            raise ValueError("Use a public IP or ASCII DNS hostname without a URL or port")
        return value.lower()
    return public_address(value)
