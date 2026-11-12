"""Tests that the project structure matches the documented architecture."""

from __future__ import annotations

import re
import warnings
from pathlib import Path

import pytest

from config.settings import MODULES

REQUIRED_PATHS = [
    "app.py",
    "requirements.txt",
    "README.md",
    ".gitignore",
    "config/settings.py",
    "components/theme.py",
    "components/layout.py",
    "pages/home.py",
    "database/connection.py",
    "src/utils/formatting.py",
    "src/data/generator.py",
    "src/metrics/portfolio.py",
    "src/intelligence/anomaly_detection.py",
    "src/analyst/ai_analyst.py",
    "src/actions/tracker.py",
    "data",
    "tests",
    "docs",
]


@pytest.mark.parametrize("relative_path", REQUIRED_PATHS)
def test_required_path_exists(project_root: Path, relative_path: str) -> None:
    assert (project_root / relative_path).exists(), f"Missing: {relative_path}"


@pytest.mark.parametrize("module", MODULES, ids=lambda m: m.key)
def test_every_module_has_a_page(project_root: Path, module) -> None:
    assert (project_root / module.page).is_file()


# --------------------------------------------------------------------------- #
# Secret scanning
# --------------------------------------------------------------------------- #
SECRET_PATTERN = re.compile(
    r"(sk-[A-Za-z0-9]{20,}|"
    r"AIza[0-9A-Za-z_-]{30,}|"
    r"api_key\s*=\s*['\"])",
    re.IGNORECASE,
)

# Only these text formats are scanned; binaries and compiled files are never read.
SCANNED_SUFFIXES = {".py", ".toml", ".txt", ".md", ".yaml", ".yml", ".json", ".ini", ".cfg"}
SCANNED_FILENAMES = {".env.example"}

# Virtual environments, VCS metadata, caches and generated data.
EXCLUDED_DIRECTORIES = {
    ".venv",
    ".venv312",
    "venv",
    "env",
    ".git",
    "__pycache__",
    ".pytest_cache",
}
EXCLUDED_RELATIVE_DIRS = {("data", "raw"), ("data", "processed")}


def _is_excluded(relative: Path) -> bool:
    """Return True if a path sits in an excluded or generated directory."""
    parts = relative.parts[:-1]
    if any(p in EXCLUDED_DIRECTORIES or p.startswith(".venv") for p in parts):
        return True
    return any(parts[: len(prefix)] == prefix for prefix in EXCLUDED_RELATIVE_DIRS)


def _is_scannable(path: Path) -> bool:
    """Return True for text files that should be scanned for secrets."""
    return path.name in SCANNED_FILENAMES or path.suffix.lower() in SCANNED_SUFFIXES


def scan_for_secrets(root: Path) -> tuple[list[Path], list[Path]]:
    """Scan project text files under ``root`` for API-key patterns.

    A file with a text extension that is not valid UTF-8 cannot be decoded
    normally. It is recorded as unreadable for diagnostics, but its raw bytes
    are still scanned (decoded as latin-1, which never fails) so a secret
    cannot hide behind an encoding error.

    Args:
        root: Directory to scan.

    Returns:
        ``(files_with_possible_secrets, unreadable_text_files)``.
    """
    findings: list[Path] = []
    unreadable: list[Path] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if _is_excluded(path.relative_to(root)) or not _is_scannable(path):
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            unreadable.append(path)
            content = path.read_bytes().decode("latin-1")
        if SECRET_PATTERN.search(content):
            findings.append(path)
    return findings, unreadable


def test_no_secrets_committed(project_root: Path) -> None:
    """Detect obvious API-key patterns in project-owned text files."""
    findings, unreadable = scan_for_secrets(project_root)
    if unreadable:
        warnings.warn(
            "Text files that are not valid UTF-8 (byte-scanned instead): "
            + ", ".join(str(p) for p in unreadable),
            stacklevel=1,
        )
    assert not findings, "Possible secrets detected in: " + ", ".join(str(p) for p in findings)


def test_secret_scan_handles_binary_and_non_utf8_files(tmp_path: Path) -> None:
    """Regression: binary / non-UTF-8 files must not crash the secret scan."""
    # Binary and compiled files containing the byte that caused the original crash (0xa4).
    (tmp_path / "image.png").write_bytes(b"\x89PNG\xa4\x00\xff")
    cache = tmp_path / "__pycache__"
    cache.mkdir()
    (cache / "module.cpython-312.pyc").write_bytes(b"\xa4\x0d\x0d\x0a\x00")
    venv = tmp_path / ".venv312" / "Lib"
    venv.mkdir(parents=True)
    (venv / "vendor.py").write_bytes(b"\xa4\xa4")

    # A text-extension file that is not UTF-8: reported, not crashed on.
    (tmp_path / "notes.md").write_bytes(b"Budget \xa4 note")

    # A clean file is not flagged.
    (tmp_path / "clean.py").write_text("x = 1\n", encoding="utf-8")

    findings, unreadable = scan_for_secrets(tmp_path)
    assert findings == []
    assert unreadable == [tmp_path / "notes.md"]


def test_secret_scan_still_detects_secrets(tmp_path: Path) -> None:
    """The patterns still fire, including inside non-UTF-8 text files."""
    fake_key = "sk-" + "A" * 24  # built at runtime so this file never matches itself
    (tmp_path / "settings.toml").write_text(f'token = "{fake_key}"\n', encoding="utf-8")
    (tmp_path / "legacy.txt").write_bytes(b"\xa4 " + fake_key.encode())

    findings, unreadable = scan_for_secrets(tmp_path)
    assert sorted(findings) == sorted([tmp_path / "settings.toml", tmp_path / "legacy.txt"])
    assert unreadable == [tmp_path / "legacy.txt"]


def test_requirements_cover_stack(project_root: Path) -> None:
    text = (project_root / "requirements.txt").read_text(encoding="utf-8").lower()
    for package in ("streamlit", "pandas", "numpy", "plotly", "scikit-learn", "sqlalchemy", "pytest"):
        assert package in text
