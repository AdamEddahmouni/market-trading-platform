from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_dockerfile_runs_cloud_mode_as_non_root():
    text = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert "FROM python:3.12-slim" in text
    assert "USER app" in text
    assert "python" in text
    assert "-m" in text
    assert "apps.research_screener" in text
    assert "CLOUD_PROVIDER_MODE" in text
    assert "--no-browser" in text
    assert "chown -R app:app /app/exports" in text


def test_production_runtime_declares_provider_import_dependencies():
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert '"requests==' in text


def test_railway_uses_dockerfile_and_health_endpoint():
    text = (ROOT / "railway.toml").read_text(encoding="utf-8")
    assert 'builder = "DOCKERFILE"' in text
    assert 'healthcheckPath = "/health"' in text
    assert 'restartPolicyType = "ON_FAILURE"' in text


def test_dockerignore_excludes_private_and_local_research_material():
    lines = {
        line.strip()
        for line in (ROOT / ".dockerignore").read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }
    assert ".private" in lines
    assert "intake/local-bars" in lines
    assert ".git" in lines
    assert ".pytest*" in lines
    assert "**/__pycache__" in lines
