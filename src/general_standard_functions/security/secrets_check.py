"""Controle: staan er per ongeluk geheimen in bestanden die git bijhoudt?

Bewust geen "lijkt-op-een-sleutel"-scanner (te veel valse meldingen), maar
drie gerichte controles:

1. Worden de bestanden met echte geheimen (``.env`` e.d.) door git genegeerd?
2. Staat een echte geheime waarde uit die bestanden letterlijk in een
   bestand dat git bijhoudt?
3. Staat er een PostgreSQL-verbindingsstring met wachtwoord in een
   bijgehouden bestand? Die hoort altijd uit een omgevingsvariabele te komen.

Laat ``run_all_checks`` meedraaien in de tests van elk project, dan gebeurt
de controle vanzelf vóór elke commit of deploy::

    def test_no_secrets_committed():
        findings = run_all_checks(SecretsCheckConfig(project_root=ROOT))
        assert not findings, "\\n".join(findings)
"""

from __future__ import annotations

import re
import subprocess
from collections.abc import Collection, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from general_standard_functions.security.secret_key import DEV_SECRET_KEY_PLACEHOLDER

__all__ = [
    "SecretsCheckConfig",
    "read_env_file",
    "find_unignored_secret_files",
    "find_hardcoded_secret_values",
    "find_hardcoded_connection_strings",
    "run_all_checks",
]

_CONNECTION_STRING_WITH_PASSWORD = re.compile(r"postgres(?:ql)?://[^:\s@'\"]+:[^@\s'\"]+@")
_MIN_SECRET_LENGTH = 8


@dataclass(frozen=True)
class SecretsCheckConfig:
    """Wat er per project gecontroleerd wordt.

    Attributes:
        project_root: De root van de git-repo.
        secret_files: Bestanden met echte geheimen, relatief aan de root.
        secret_env_vars: Namen van variabelen waarvan de waarde geheim is.
        excluded_from_connection_string_check: Bestanden die bewust een
            voorbeeld-verbindingsstring bevatten (zoals ``.env.example``).
        allowed_placeholders: Waarden die geen lek zijn, ook al staan ze
            in een geheim bestand (zoals de ontwikkelsleutel).
    """

    project_root: Path
    secret_files: Sequence[str] = (".env", ".env.production", ".env.local")
    secret_env_vars: Sequence[str] = (
        "DATABASE_URL",
        "FLASK_SECRET_KEY",
        "SMTP_PASSWORD",
        "SUPABASE_STORAGE_KEY",
    )
    excluded_from_connection_string_check: Collection[str] = (".env.example",)
    allowed_placeholders: Collection[str] = field(default=(DEV_SECRET_KEY_PLACEHOLDER,))


def _git(config: SecretsCheckConfig, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=config.project_root, capture_output=True, text=True)


def read_env_file(path: Path) -> dict[str, str]:
    """Lees een ``.env``-bestand als ``{naam: waarde}``.

    Lege regels en regels die met ``#`` beginnen worden overgeslagen;
    aanhalingstekens rond een waarde blijven staan.

    Args:
        path: Het bestand; bestaat het niet, dan komt er een leeg dict terug.

    Returns:
        De variabelen uit het bestand.
    """
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip()
    return values


def find_unignored_secret_files(config: SecretsCheckConfig) -> list[str]:
    """Meld geheime bestanden die bestaan maar níet door git worden genegeerd.

    Args:
        config: De projectinstellingen.

    Returns:
        Eén melding per bestand dat bij een commit zou meegaan.
    """
    findings = []
    for filename in config.secret_files:
        if not (config.project_root / filename).exists():
            continue
        if _git(config, "check-ignore", "-q", filename).returncode != 0:
            findings.append(
                f"{filename} bestaat lokaal maar wordt NIET genegeerd door git "
                "en zou bij een commit meegaan. Voeg het toe aan .gitignore."
            )
    return findings


def find_hardcoded_secret_values(config: SecretsCheckConfig) -> list[str]:
    """Meld echte geheime waarden die letterlijk in een bijgehouden bestand staan.

    Leest de waarden van ``secret_env_vars`` uit ``secret_files`` en zoekt
    ze met ``git grep``. Waarden korter dan 8 tekens en
    ``allowed_placeholders`` tellen niet mee.

    Args:
        config: De projectinstellingen.

    Returns:
        Eén melding per gelekte variabele, met de bestanden.
    """
    env_values: dict[str, str] = {}
    for filename in config.secret_files:
        env_values.update(read_env_file(config.project_root / filename))

    findings = []
    for var_name in config.secret_env_vars:
        value = env_values.get(var_name, "")
        if len(value) < _MIN_SECRET_LENGTH or value in config.allowed_placeholders:
            continue
        result = _git(config, "grep", "-F", "-l", "--", value)
        if result.returncode == 0 and result.stdout.strip():
            files = ", ".join(result.stdout.strip().splitlines())
            findings.append(
                f"De waarde van {var_name} staat letterlijk in bijgehouden bestand(en): {files}. "
                "Haal hem daar weg en vervang de sleutel (roteren)."
            )
    return findings


def find_hardcoded_connection_strings(config: SecretsCheckConfig) -> list[str]:
    """Meld bijgehouden bestanden met een PostgreSQL-verbindingsstring mét wachtwoord.

    Args:
        config: De projectinstellingen.

    Returns:
        Eén melding per bestand.
    """
    findings = []
    for relative_path in _git(config, "ls-files").stdout.splitlines():
        if not relative_path or relative_path in config.excluded_from_connection_string_check:
            continue
        path = config.project_root / relative_path
        if not path.is_file():
            continue
        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if _CONNECTION_STRING_WITH_PASSWORD.search(content):
            findings.append(
                f"{relative_path} bevat een database-verbindingsstring met wachtwoord; "
                "die hoort uit een omgevingsvariabele te komen."
            )
    return findings


def run_all_checks(config: SecretsCheckConfig) -> list[str]:
    """Voer alle drie de controles uit.

    Args:
        config: De projectinstellingen.

    Returns:
        Alle meldingen; een lege lijst betekent: niets gevonden.
    """
    return (
        find_unignored_secret_files(config)
        + find_hardcoded_secret_values(config)
        + find_hardcoded_connection_strings(config)
    )
