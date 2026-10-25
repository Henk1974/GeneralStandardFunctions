import pytest

from general_standard_functions.i18n import gettext, set_translator
from general_standard_functions.validation.email import InvalidEmailError, normalize_email
from general_standard_functions.validation.password import InvalidPasswordError, PasswordPolicy, validate_password

ENGLISH = {
    "Wachtwoord moet minimaal %(n)s tekens lang zijn.": "Password must be at least %(n)s characters long.",
    "E-mailadressen van domein %(domain)r worden niet ondersteund.": "Addresses from %(domain)r are not supported.",
}


@pytest.fixture
def english():
    set_translator(ENGLISH.get)
    yield
    set_translator(None)


def test_without_translator_the_dutch_source_is_returned():
    assert gettext("Hallo %(naam)s", naam="Henk") == "Hallo Henk"


def test_variables_are_filled_in_after_translating(english):
    with pytest.raises(InvalidPasswordError, match="at least 12 characters"):
        validate_password("kort", PasswordPolicy(min_length=12))


def test_package_messages_go_through_the_translator(english):
    with pytest.raises(InvalidEmailError, match="Addresses from 'x.nl' are not supported."):
        normalize_email("a@x.nl", {"gmail.com"})


def test_unknown_message_falls_back_to_the_source(english):
    assert gettext("Onbekend") == "Onbekend"


def test_percent_sign_without_variables_is_left_alone():
    assert gettext("100% zeker") == "100% zeker"


def test_ngettext_uses_the_plural_translator():
    from general_standard_functions.i18n import ngettext

    set_translator(None, lambda s, p, n: "%(n)s minute" if n == 1 else "%(n)s minutes")
    try:
        assert ngettext("%(n)s minuut", "%(n)s minuten", 3) == "3 minutes"
    finally:
        set_translator(None)
