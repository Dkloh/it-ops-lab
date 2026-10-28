from datetime import UTC, datetime, timedelta

import pytest

from app.diagnostic_rules import RULES, Event, analyze

START = datetime(2026, 10, 27, 13, tzinfo=UTC)


def event(identifier, seconds=0, message="connection timed out", severity="ERROR"):
    return Event(identifier, START + timedelta(seconds=seconds), severity, message)


def matching_events(rule, count, spacing=1):
    return [
        event(i + 1, i * spacing, rule.phrases[0], rule.event_severities[0]) for i in range(count)
    ]


@pytest.mark.parametrize("rule", RULES, ids=lambda rule: rule.code)
def test_exact_threshold_and_minus_one(rule):
    assert not any(
        d.rule.code == rule.code for d in analyze(matching_events(rule, rule.threshold - 1))
    )
    result = next(
        d for d in analyze(matching_events(rule, rule.threshold)) if d.rule.code == rule.code
    )
    assert len(result.events) == rule.threshold
    assert result.rule.severity == rule.severity


@pytest.mark.parametrize("rule", RULES, ids=lambda rule: rule.code)
def test_inclusive_window_and_outside(rule):
    records = matching_events(rule, rule.threshold)
    records[-1] = event(
        rule.threshold, rule.window.total_seconds(), rule.phrases[0], rule.event_severities[0]
    )
    assert any(d.rule.code == rule.code for d in analyze(records))
    records[-1] = event(
        rule.threshold,
        rule.window.total_seconds() + 0.000001,
        rule.phrases[0],
        rule.event_severities[0],
    )
    assert not any(d.rule.code == rule.code for d in analyze(records))


@pytest.mark.parametrize("rule", RULES, ids=lambda rule: rule.code)
def test_casefold_and_all_phrases(rule):
    for phrase in rule.phrases:
        for severity in rule.event_severities:
            records = [
                event(i, i, f"prefix {phrase.upper()} suffix", severity)
                for i in range(rule.threshold)
            ]
            assert any(d.rule.code == rule.code for d in analyze(records))


@pytest.mark.parametrize("rule", RULES, ids=lambda rule: rule.code)
def test_wrong_severity_and_unrelated_message(rule):
    records = [event(i, i, rule.phrases[0], "INFO") for i in range(rule.threshold + 1)]
    assert analyze(records) == []
    assert analyze([event(i, i, "Everything normal", "CRITICAL") for i in range(10)]) == []


def test_unsorted_ties_and_duplicate_input():
    records = [event(3), event(1), event(2), event(1)]
    result = analyze(records)
    assert [e.id for e in result[0].events] == [1, 2, 3]
    assert analyze([event(1), event(1), event(2)]) == []


def test_overlapping_and_disjoint_windows_union():
    # Two qualifying clusters, isolated matching events on either side.
    seconds = [-1000, 240, 300, 360, 540, 600, 2000, 2001, 2002, 4000]
    result = analyze([event(i, second) for i, second in enumerate(seconds)])
    assert len(result) == 1
    assert [e.id for e in result[0].events] == list(range(1, 9))
    assert result[0].events[0].occurred_at == START + timedelta(seconds=240)
    assert result[0].events[-1].occurred_at == START + timedelta(seconds=2002)


def test_rolling_window_not_fixed_clock_bucket():
    result = analyze([event(1, 299), event(2, 300), event(3, 301)])
    assert [e.id for e in result[0].events] == [1, 2, 3]


def test_all_rules_can_share_justified_evidence():
    records = [event(i, i, "database connection timed out") for i in range(1, 4)]
    records += [event(i, i, "login failed", "WARNING") for i in range(4, 9)]
    detections = {d.rule.code: [e.id for e in d.events] for d in analyze(records)}
    assert detections == {
        "REPEATED_TIMEOUTS": [1, 2, 3],
        "REPEATED_AUTH_FAILURES": [4, 5, 6, 7, 8],
        "DATABASE_CONNECTION_ERRORS": [1, 2, 3],
    }


def test_static_explanations_do_not_embed_untrusted_content():
    detections = analyze(
        [event(i, i, "connection timed out secret=synthetic-only; echo unsafe") for i in range(3)]
    )
    rule = detections[0].rule
    assert "secret=" not in rule.summary + rule.explanation + rule.suggested_action
