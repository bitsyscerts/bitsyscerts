"""Static contract tests for Sprint 7 runtime packaging and docs."""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]


def _read_text(relative_path: str) -> str:
    return (REPO_ROOT / relative_path).read_text(encoding="utf-8")


@pytest.mark.parametrize(
    ("relative_path", "expected_mode_marker", "expected_disk_path"),
    [
        ("src/.env.development.example", "developer-mode", "CT_DISK_CHECK_PATH=/"),
        ("src/.env.local.example", "local Python runtime", "CT_DISK_CHECK_PATH=/"),
        (
            "src/.env.compose.example",
            "Docker Compose runtime",
            "CT_DISK_CHECK_PATH=/data/pgcheck",
        ),
    ],
)
def test_env_examples_publish_mode_specific_runtime_defaults(
    relative_path: str,
    expected_mode_marker: str,
    expected_disk_path: str,
) -> None:
    """Each runtime env example should advertise the approved shared defaults."""
    content = _read_text(relative_path)

    assert expected_mode_marker in content
    assert "BITSYSCERTS_EXPOSE_STATS_API=true" in content
    assert "BITSYSCERTS_BOOTSTRAP_PROFILE=lite" in content
    assert "CT_BACKFILL_DAYS=30" in content
    assert "CT_BACKFILL_DISPATCH_MODE=per-log" in content
    assert "BITSYSCERTS_ENABLE_SCHEDULED_AUDIT=false" in content
    assert expected_disk_path in content


def test_env_examples_document_first_run_snapshot_guidance() -> None:
    """Runtime env templates should explain first-run snapshot behavior."""
    compose_content = _read_text("src/.env.compose.example")
    local_content = _read_text("src/.env.local.example")
    development_content = _read_text("src/.env.development.example")

    assert "./server-deploy.sh" in compose_content
    assert "dashboard still says no snapshot yet" in compose_content
    assert "ctpool stats-snapshot" in local_content
    assert "ctpool maintenance" in local_content
    assert "ctpool stats-snapshot" in development_content


def test_compatibility_env_example_points_to_mode_specific_templates() -> None:
    """The compatibility env example should direct operators to mode-specific files."""
    content = _read_text("src/.env.example")

    assert "Developer mode:    cp .env.development.example .env" in content
    assert "Local Python mode: cp .env.local.example .env" in content
    assert "Docker Compose:    cp .env.compose.example .env" in content


def test_readme_describes_all_supported_runtime_modes() -> None:
    """The README should separate the three supported runtime modes."""
    content = _read_text("README.md")

    assert "## Runtime Modes" in content
    assert "## Docker Compose Quick Start (Preferred)" in content
    assert "## Local Python Quick Start" in content
    assert "## Developer Mode" in content
    assert "bitsyscerts-compose-<version>.zip" in content
    assert "bitsyscerts-python-<version>.zip" in content
    assert "docker compose run --rm migrate ctpool status" in content
    assert "docker compose run --rm migrate ctpool workers list" in content
    assert "docker compose run --rm migrate ctpool backfill-state" in content
    assert (
        "docker compose run --rm migrate ctpool prune-for-storage-profile "
        "--dry-run" in content
    )
    assert "./server-deploy.sh" in content
    assert "docker compose exec api ctpool" not in content
    assert "current-osint" not in content


def test_operations_guide_covers_smoke_reset_and_scaling() -> None:
    """The operations guide should document runtime verification and recovery flows."""
    content = _read_text("docs/OPERATIONS.md")

    assert "## Runtime Modes" in content
    assert "## Smoke Commands" in content
    assert "## Reset Workflows" in content
    assert "## Scaling Guidance" in content
    assert "docker compose run --rm migrate ctpool maintenance" in content
    assert "ctpool workers list" in content
    assert "ctpool backfill-state" in content
    assert "ctpool prune-for-storage-profile --dry-run" in content
    assert "ctpool init-db --force" in content
    assert "docker compose up -d --scale backfill=2" in content
    assert "ctpool maintenance --once" not in content
    assert "ctpool stats-snapshot --once" not in content


def test_architecture_doc_uses_current_service_names_and_env_contract() -> None:
    """The architecture guide should match the implemented topology and env files."""
    content = _read_text("docs/ARCHITECTURE.md")

    assert "stats-snapshotter" in content
    assert "src/.env.development.example" in content
    assert "src/.env.local.example" in content
    assert "src/.env.compose.example" in content
    assert "BITSYSCERTS_EXPOSE_STATS_API" in content
    assert "CT_BACKFILL_DISPATCH_MODE" in content


def test_compose_contract_uses_migrate_service_and_lite_backfill_default() -> None:
    """The compose runtime should reflect the approved operator contract."""
    content = _read_text("src/docker-compose.yml")

    assert "migrate:" in content
    assert "stats-snapshotter:" in content
    # migrate runs three bootstrap steps via a shell script
    assert "ctpool apply-migrations" in content
    assert "ctpool sync-logs" in content
    assert "ctpool stats-snapshot" in content
    assert 'command: ["ctpool", "stats-snapshot", "--loop"]' in content
    assert 'command: ["ctpool", "maintenance", "--loop"]' in content
    assert 'CT_BACKFILL_DAYS: "${CT_BACKFILL_DAYS:-30}"' in content
    assert "/workspaces/" not in content


def test_api_packaging_contract_has_no_workspace_path_dependency_or_rewrite() -> None:
    """The API package and image build should not rely on workspace-specific paths."""
    pyproject = _read_text("src/api/pyproject.toml")
    dockerfile = _read_text("src/api/Dockerfile")

    assert "ctpool==" in pyproject
    assert "file:///workspaces" not in pyproject
    assert "sed -i" not in dockerfile
    assert "--find-links /wheels" in dockerfile


def test_bundle_packager_uses_tracked_files_and_ships_runtime_templates() -> None:
    """The bundle script should avoid cache leakage and ship runtime env files."""
    content = _read_text("src/package-runtime-bundles.sh")

    assert 'git -C "${ROOT_DIR}" ls-files' in content
    assert "src/.env.compose.example" in content
    assert "src/.env.local.example" in content
    assert "src/.env.development.example" in content
    assert "bitsyscerts-compose-${VERSION}.zip" in content
    assert "bitsyscerts-python-${VERSION}.zip" in content


def test_ci_workflow_packages_runtime_bundles_and_links_to_new_readme_anchor() -> None:
    """CI should validate compose, build runtime zips, and link to the current docs."""
    content = _read_text(".github/workflows/ci.yml")

    assert "package-runtime-bundles:" in content
    assert (
        "docker compose -f src/docker-compose.yml --env-file "
        "src/.env.compose.example config >/dev/null" in content
    )
    assert "bash src/package-runtime-bundles.sh" in content
    assert "bash src/validate-runtime-bundles.sh" in content
    assert (
        "bitsyscerts-compose-${{ needs.version.outputs.version_docker }}.zip" in content
    )
    assert (
        "bitsyscerts-python-${{ needs.version.outputs.version_docker }}.zip" in content
    )
    assert "#docker-compose-quick-start-preferred" in content


def test_bundle_validator_checks_extracted_runtime_contract() -> None:
    """The bundle validator should inspect extracted archives and compose config."""
    content = _read_text("src/validate-runtime-bundles.sh")

    assert "docker compose config >/dev/null" in content
    assert "Compose bundle missing docker-compose.yml" in content
    assert "Python bundle missing src/api" in content
    assert "node_modules" in content
    assert "coverage" in content
    assert ".venv" in content
    assert "__pycache__" in content


def test_deploy_scripts_seed_snapshot_and_maintenance_before_service_start() -> None:
    """Deploy helpers should seed one snapshot and one maintenance pass."""
    for relative_path in ("src/deploy.sh", "src/server-deploy.sh"):
        content = _read_text(relative_path)

        assert "compose run --rm migrate ctpool stats-snapshot" in content
        assert "compose run --rm migrate ctpool maintenance" in content


def test_runtime_surfaces_do_not_embed_workspace_absolute_paths() -> None:
    """Shipped runtime assets should not assume a specific checkout directory."""
    for relative_path in (
        "README.md",
        "docs/OPERATIONS.md",
        "src/deploy.sh",
        "src/server-deploy.sh",
        "src/package-runtime-bundles.sh",
    ):
        assert "/workspaces/" not in _read_text(relative_path)
