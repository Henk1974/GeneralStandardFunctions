import subprocess
from pathlib import Path

import pytest

from general_standard_functions.security.secrets_check import (
    SecretsCheckConfig,
    read_env_file,
    run_all_checks,
)

SECRET_URL = "postgresql://postgres:Geheim-123456@db.example.supabase.co:5432/postgres"


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=root, check=True, capture_output=True)


@pytest.fixture
def repo(tmp_path):
    _git(tmp_path, "init", "-q")
    (tmp_path / ".gitignore").write_text(".env\n", encoding="utf-8")
    (tmp_path / ".env").write_text(f"# geheim\nDATABASE_URL={SECRET_URL}\nFLASK_SECRET_KEY=dev-secret-change-me\n", encoding="utf-8")
    (tmp_path / "app.py").write_text("print('hallo')\n", encoding="utf-8")
    _git(tmp_path, "add", ".")
    return tmp_path


def test_read_env_file_skips_comments(repo):
    assert read_env_file(repo / ".env")["DATABASE_URL"] == SECRET_URL
    assert read_env_file(repo / "bestaat-niet") == {}


def test_clean_repo_has_no_findings(repo):
    assert run_all_checks(SecretsCheckConfig(project_root=repo)) == []


def test_unignored_env_file_is_reported(repo):
    (repo / ".gitignore").write_text("", encoding="utf-8")
    findings = run_all_checks(SecretsCheckConfig(project_root=repo))
    assert any(".env bestaat lokaal maar wordt NIET genegeerd" in f for f in findings)


def test_hardcoded_secret_value_and_connection_string_are_reported(repo):
    (repo / "config.py").write_text(f'URL = "{SECRET_URL}"\n', encoding="utf-8")
    _git(repo, "add", "config.py")
    findings = run_all_checks(SecretsCheckConfig(project_root=repo))
    assert any("DATABASE_URL staat letterlijk" in f and "config.py" in f for f in findings)
    assert any(f.startswith("config.py bevat een database-verbindingsstring") for f in findings)


def test_placeholder_secret_key_is_not_a_leak(repo):
    (repo / "README.md").write_text("FLASK_SECRET_KEY=dev-secret-change-me\n", encoding="utf-8")
    _git(repo, "add", "README.md")
    assert run_all_checks(SecretsCheckConfig(project_root=repo)) == []
