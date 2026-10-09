import socket

import pytest
from fastapi import HTTPException

from backend.app.api.v1.endpoints.integrations import _checkout_failure_context, _make_flaws, _safe_url


@pytest.mark.parametrize(
    ("family", "sockaddr"),
    [
        (socket.AF_INET, ("8.8.8.8", 443)),
        (socket.AF_INET6, ("fec0::1", 443, 0, 0)),
    ],
)
def test_safe_url_classifies_resolved_addresses(monkeypatch, family, sockaddr):
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *_args, **_kwargs: [
            (family, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", sockaddr)
        ],
    )

    if family == socket.AF_INET:
        assert _safe_url("https://example.com") == "https://example.com"
    else:
        with pytest.raises(HTTPException) as error:
            _safe_url("https://example.com")
        assert error.value.status_code == 400


def test_checkout_failure_requires_observed_evidence_before_confirmed():
    context = _checkout_failure_context({
        "request_count": 12,
        "error_rate": 0.1,
        "checkout_failure_probability": 0.25,
        "active_failure_modes": ["checkout_failures"],
    })

    assert context["state"] == "insufficient_evidence"
    assert context["configured_probability"] == 0.25


def test_checkout_failure_is_confirmed_once_threshold_is_breached():
    context = _checkout_failure_context({
        "request_count": 50,
        "error_rate": 0.25,
        "checkout_failure_probability": 0.25,
        "active_failure_modes": ["checkout_failures"],
    })

    assert context["state"] == "confirmed"
    assert context["observed_error_rate"] == 0.25


def test_configured_checkout_failure_mode_without_evidence_does_not_create_confirmed_finding():
    flaws = _make_flaws(
        "DemoShop",
        {"status": "healthy"},
        {
            "request_count": 12,
            "error_rate": 0.1,
            "checkout_failure_probability": 0.25,
            "active_failure_modes": ["checkout_failures"],
        },
    )

    titles = [flaw.title for flaw in flaws]
    assert "Checkout failure mode enabled with insufficient observed evidence" in titles
    assert "Elevated checkout failure rate" not in titles
