import random
from datetime import datetime, timedelta, timezone

import pytest
from itsdangerous import URLSafeSerializer

from general_standard_functions.security.captcha import (
    DEFAULT_SALT,
    MAX_SECONDS,
    MIN_SECONDS,
    CaptchaError,
    HoneypotTriggered,
    create_challenge,
    verify_challenge,
)
from general_standard_functions.security.lockout import (
    LockoutAction,
    LockoutPolicy,
    decide_after_failure,
    is_locked,
    minutes_left,
)
from general_standard_functions.security.redirects import is_same_host_url, safe_next_path
from general_standard_functions.security.secret_key import (
    DEV_SECRET_KEY_PLACEHOLDER,
    InsecureSecretKeyError,
    ensure_production_secret_key,
)
from general_standard_functions.security.tokens import hash_token, new_token

NOW = datetime(2026, 10, 25, 12, 0, tzinfo=timezone.utc)

# --- tokens --------------------------------------------------------------


def test_tokens_are_unique_and_hash_is_stable_hex():
    a, b = new_token(), new_token()
    assert a != b and len(a) >= 43
    assert hash_token(a) == hash_token(a) != hash_token(b)
    assert len(hash_token(a)) == 64 and int(hash_token(a), 16) >= 0


# --- inlogblokkade -------------------------------------------------------


def test_lockout_full_sequence():
    assert decide_after_failure(1, False, NOW).attempts_left == 2
    assert decide_after_failure(2, False, NOW).attempts_left == 1
    lock = decide_after_failure(3, False, NOW)
    assert lock.action is LockoutAction.LOCK and lock.locked_until == NOW + timedelta(minutes=15)
    fourth = decide_after_failure(4, True, NOW)
    assert fourth.action is LockoutAction.WARN and fourth.attempts_left == 2 and fourth.reset_follows
    assert decide_after_failure(5, True, NOW).attempts_left == 1
    assert decide_after_failure(6, True, NOW).action is LockoutAction.REQUIRE_RESET


def test_lock_is_never_set_twice():
    # Gelijktijdige pogingen: de teller staat al op 4 terwijl de blokkade al gezet is.
    assert decide_after_failure(4, True, NOW).action is LockoutAction.WARN


def test_custom_lockout_policy():
    policy = LockoutPolicy(max_attempts=5, lockout_minutes=60)
    assert decide_after_failure(4, False, NOW, policy).action is LockoutAction.WARN
    assert decide_after_failure(5, False, NOW, policy).locked_until == NOW + timedelta(hours=1)
    assert decide_after_failure(10, True, NOW, policy).action is LockoutAction.REQUIRE_RESET


def test_is_locked_and_minutes_left():
    assert not is_locked(None, NOW)
    assert not is_locked(NOW - timedelta(seconds=1), NOW)
    assert is_locked(NOW + timedelta(minutes=1), NOW)
    assert minutes_left(NOW + timedelta(minutes=14, seconds=1), NOW) == 15
    assert minutes_left(NOW + timedelta(seconds=1), NOW) == 1


# --- redirects -----------------------------------------------------------


@pytest.mark.parametrize("target", ["/kelder", "/a?b=c#d"])
def test_safe_paths_pass(target):
    assert safe_next_path(target, "/") == target


@pytest.mark.parametrize("target", [None, "", "https://evil.example/", "//evil.example", "/\\evil.example", "kelder"])
def test_unsafe_targets_fall_back(target):
    assert safe_next_path(target, "/home") == "/home"


def test_same_host_url():
    assert is_same_host_url("https://app.example:8000/x", "app.example:8000")
    assert not is_same_host_url("https://app.example/x", "app.example:8000")
    assert not is_same_host_url(None, "app.example")


# --- geheime sleutel -----------------------------------------------------


def test_secret_key_only_enforced_in_production():
    ensure_production_secret_key("", is_production=False)
    ensure_production_secret_key("x" * 32, is_production=True)
    for bad in ("", DEV_SECRET_KEY_PLACEHOLDER, "kort"):
        with pytest.raises(InsecureSecretKeyError):
            ensure_production_secret_key(bad, is_production=True)


# --- captcha -------------------------------------------------------------

SECRET = "test-secret"
T0 = 1_700_000_000


def _challenge(salt=DEFAULT_SALT):
    challenge = create_challenge(SECRET, now=T0, rng=random.Random(1), salt=salt)
    a, b = [int(x) for x in challenge.question.removeprefix("Hoeveel is ").rstrip("?").split(" + ")]
    return challenge, str(a + b)


def test_correct_answer_passes_also_with_whitespace():
    challenge, answer = _challenge()
    verify_challenge(SECRET, challenge.token, f"  {answer} ", "", now=T0 + 10)


@pytest.mark.parametrize("offset", [MIN_SECONDS - 1, MAX_SECONDS + 1])
def test_too_fast_or_expired_fails(offset):
    challenge, answer = _challenge()
    with pytest.raises(CaptchaError):
        verify_challenge(SECRET, challenge.token, answer, "", now=T0 + offset)


def test_wrong_or_non_numeric_answer_fails():
    challenge, answer = _challenge()
    for given in (str(int(answer) + 1), "elf"):
        with pytest.raises(CaptchaError):
            verify_challenge(SECRET, challenge.token, given, "", now=T0 + 10)


def test_honeypot_is_checked_first():
    challenge, answer = _challenge()
    with pytest.raises(HoneypotTriggered):
        verify_challenge(SECRET, challenge.token, answer, "http://spam.example", now=T0 + 10)


def test_tampered_forged_or_other_form_token_fails():
    challenge, answer = _challenge()
    forged = URLSafeSerializer("guess", salt=DEFAULT_SALT).dumps({"s": 5, "t": T0})
    other_form, other_answer = _challenge(salt="ander-formulier")
    for token, given in [(challenge.token + "x", answer), ("", answer), (forged, "5"), (other_form.token, other_answer)]:
        with pytest.raises(CaptchaError):
            verify_challenge(SECRET, token, given, "", now=T0 + 10)
