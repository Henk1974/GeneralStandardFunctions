import pytest

from general_standard_functions.validation.barcode import InvalidBarcodeError, normalize_barcode
from general_standard_functions.validation.email import (
    InvalidEmailError,
    normalize_email,
    normalize_email_format,
)
from general_standard_functions.validation.password import (
    InvalidPasswordError,
    PasswordPolicy,
    validate_password,
)

# --- barcode -------------------------------------------------------------


def test_barcode_whitespace_is_stripped_and_leading_zeros_kept():
    assert normalize_barcode("  0012345  ") == "0012345"


@pytest.mark.parametrize("bad", ["", "   ", None, "541-0228-123", "12a4"])
def test_invalid_barcodes_raise(bad):
    with pytest.raises(InvalidBarcodeError):
        normalize_barcode(bad)


# --- e-mail --------------------------------------------------------------

DOMAINS = {"gmail.com", "Outlook.com"}


def test_format_only_accepts_any_domain_and_lowercases():
    assert normalize_email_format("  Jan@Ziggo.NL ") == "jan@ziggo.nl"


@pytest.mark.parametrize("bad", ["", "   ", "geen-email", "a@b", "twee@@x.nl", "met spatie@x.nl"])
def test_format_rejects_malformed(bad):
    with pytest.raises(InvalidEmailError):
        normalize_email_format(bad)


def test_format_rejects_too_long():
    with pytest.raises(InvalidEmailError):
        normalize_email_format("a" * 251 + "@x.nl")  # 256 tekens


def test_allowed_domain_passes_case_insensitively():
    assert normalize_email("Henk@GMAIL.com", DOMAINS) == "henk@gmail.com"
    assert normalize_email("henk@outlook.com", DOMAINS) == "henk@outlook.com"


def test_disallowed_domain_raises_with_hint():
    with pytest.raises(InvalidEmailError, match="Gebruik een Gmail-adres."):
        normalize_email("iemand@wegwerp.xyz", DOMAINS, rejection_hint="Gebruik een Gmail-adres.")


# --- wachtwoord ----------------------------------------------------------


def test_valid_password_passes():
    validate_password("Correct1-Horse")


@pytest.mark.parametrize(
    "bad, reason",
    [
        ("Short1!", "minimaal 10"),
        (None, "minimaal 10"),
        ("WACHTWOORD1", "makkelijk"),
        ("correct1-horse", "hoofdletter"),
        ("Correct-Horse", "cijfer"),
        ("Correct1Horse", "speciaal"),
    ],
)
def test_policy_violations_name_the_reason(bad, reason):
    with pytest.raises(InvalidPasswordError, match=reason):
        validate_password(bad)


def test_custom_policy_is_respected():
    relaxed = PasswordPolicy(min_length=6, require_special=False)
    validate_password("Abcde1", relaxed)
    with pytest.raises(InvalidPasswordError, match="minimaal 12"):
        validate_password("Correct1-Horse"[:11], PasswordPolicy(min_length=12))


def test_accented_capital_counts_as_uppercase():
    validate_password("élève1-École")
