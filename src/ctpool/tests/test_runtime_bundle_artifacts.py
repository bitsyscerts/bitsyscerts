"""Artifact-level tests for the packaged runtime bundles."""

from __future__ import annotations

import subprocess
import zipfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
PACKAGE_SCRIPT = REPO_ROOT / "src/package-runtime-bundles.sh"
BASH_EXECUTABLE = "/usr/bin/bash"


@pytest.fixture(scope="module")
def runtime_bundles(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Path]:
    """Build one pair of runtime bundles for artifact inspection."""
    output_dir = tmp_path_factory.mktemp("runtime-bundles")
    version = "pytest-build"

    subprocess.run(  # noqa: S603
        [
            BASH_EXECUTABLE,
            str(PACKAGE_SCRIPT),
            "--version",
            version,
            "--output-dir",
            str(output_dir),
        ],
        check=True,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )

    return {
        "compose": output_dir / f"bitsyscerts-compose-{version}.zip",
        "python": output_dir / f"bitsyscerts-python-{version}.zip",
    }


def _bundle_members(bundle_path: Path) -> set[str]:
    with zipfile.ZipFile(bundle_path) as archive:
        return set(archive.namelist())


def test_release_bundle_script_creates_expected_archives(
    runtime_bundles: dict[str, Path],
) -> None:
    """The runtime bundle script should create both supported release artifacts."""
    assert runtime_bundles["compose"].is_file()
    assert runtime_bundles["python"].is_file()


@pytest.mark.parametrize(
    ("bundle_key", "required_members"),
    [
        (
            "compose",
            {
                "docker-compose.yml",
                "server-deploy.sh",
                ".env.compose.example",
                "README.md",
                "docs/OPERATIONS.md",
                "LICENSE",
            },
        ),
        (
            "python",
            {
                "src/api/pyproject.toml",
                "src/ctpool/pyproject.toml",
                "src/app/package.json",
                ".env.local.example",
                ".env.development.example",
                "README.md",
                "docs/OPERATIONS.md",
                "docs/ARCHITECTURE.md",
                "LICENSE",
            },
        ),
    ],
)
def test_runtime_bundles_include_required_files(
    runtime_bundles: dict[str, Path],
    bundle_key: str,
    required_members: set[str],
) -> None:
    """Each runtime bundle should ship the files its documented mode requires."""
    members = _bundle_members(runtime_bundles[bundle_key])

    assert required_members <= members


@pytest.mark.parametrize(
    ("bundle_key", "unexpected_fragments"),
    [
        ("compose", ("src/", "node_modules/", "coverage/", ".venv/", "__pycache__/")),
        ("python", ("node_modules/", "coverage/", ".venv/", "__pycache__/")),
    ],
)
def test_runtime_bundles_exclude_checkout_and_build_noise(
    runtime_bundles: dict[str, Path],
    bundle_key: str,
    unexpected_fragments: tuple[str, ...],
) -> None:
    """Release artifacts should stay free of local checkout and cache directories."""
    members = _bundle_members(runtime_bundles[bundle_key])

    for fragment in unexpected_fragments:
        assert all(fragment not in member for member in members)
