"""Pure, deterministic rules over normalized events from a single batch."""

from dataclasses import dataclass
from datetime import datetime, timedelta

RULESET_VERSION = "1.0.0"


@dataclass(frozen=True)
class Event:
    id: int
    occurred_at: datetime
    severity: str
    message: str


@dataclass(frozen=True)
class Rule:
    code: str
    severity: str
    threshold: int
    window: timedelta
    event_severities: tuple[str, ...]
    phrases: tuple[str, ...]
    summary: str
    explanation: str
    suggested_action: str


RULES = (
    Rule(
        "REPEATED_TIMEOUTS",
        "HIGH",
        3,
        timedelta(minutes=5),
        ("ERROR", "CRITICAL"),
        ("connection timed out", "request timed out", "connection timeout", "upstream timeout"),
        "Repeated connection or request timeouts",
        "At least three timeout-related ERROR or CRITICAL events occurred within an inclusive "
        "five-minute window. Evidence includes every matching event in a qualifying window; "
        "this suggests an investigation direction, not confirmed upstream downtime.",
        "Check network reachability, upstream service health, application timeout settings, "
        "and connection pool configuration.",
    ),
    Rule(
        "REPEATED_AUTH_FAILURES",
        "MEDIUM",
        5,
        timedelta(minutes=10),
        ("WARNING", "ERROR", "CRITICAL"),
        ("authentication failed", "login failed", "invalid credentials", "unauthorized request"),
        "Repeated authentication failures",
        "At least five authentication-related WARNING, ERROR or CRITICAL events occurred "
        "within an inclusive ten-minute window. Repeated failures alone do not establish "
        "an attack or compromise.",
        "Investigate authentication configuration, recent credential changes, account lockouts, "
        "and identity-provider availability.",
    ),
    Rule(
        "DATABASE_CONNECTION_ERRORS",
        "HIGH",
        2,
        timedelta(minutes=5),
        ("ERROR", "CRITICAL"),
        (
            "database connection failed",
            "database connection timed out",
            "connection pool exhausted",
            "could not connect to database",
        ),
        "Recurring database connection errors",
        "At least two database connection-related ERROR or CRITICAL events occurred within "
        "an inclusive five-minute window. The observed errors do not prove database downtime.",
        "Check database availability, connection limits, application configuration, "
        "and network connectivity.",
    ),
)


@dataclass(frozen=True)
class Detection:
    rule: Rule
    events: tuple[Event, ...]


def supporting_events(events: list[Event], rule: Rule) -> tuple[Event, ...]:
    matches = [
        event
        for event in events
        if event.severity in rule.event_severities
        and any(phrase in event.message.casefold() for phrase in rule.phrases)
    ]
    # Every maximal window ending at right is [left, right]. Mark the union of
    # threshold-satisfying intervals using a difference array, without O(n²) copies.
    changes = [0] * (len(matches) + 1)
    left = 0
    for right, event in enumerate(matches):
        while event.occurred_at - matches[left].occurred_at > rule.window:
            left += 1
        if right - left + 1 >= rule.threshold:
            changes[left] += 1
            changes[right + 1] -= 1
    active = 0
    evidence = []
    for index, event in enumerate(matches):
        active += changes[index]
        if active:
            evidence.append(event)
    return tuple(evidence)


def analyze(events: list[Event]) -> list[Detection]:
    # IDs identify evidence; repeated input references cannot inflate thresholds.
    ordered = sorted(
        {event.id: event for event in events}.values(),
        key=lambda event: (event.occurred_at, event.id),
    )
    detections = []
    for rule in RULES:
        evidence = supporting_events(ordered, rule)
        if evidence:
            detections.append(Detection(rule, evidence))
    return detections
