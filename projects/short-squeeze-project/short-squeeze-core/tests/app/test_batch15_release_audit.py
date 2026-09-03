from __future__ import annotations

from pathlib import Path


def categories(result) -> set[str]:
    return {finding.category for finding in result.findings}


def test_release_audit_detects_prohibited_content_without_returning_values(
    tmp_path: Path,
) -> None:
    from tools.release_audit import audit_directory

    (tmp_path / "unsafe.txt").write_text(
        "\n".join(
            (
                "FINVIZ_API_KEY=live-secret-value",
                "Authorization: Bearer private-token-value",
                "maintainer@example.com",
                "+1 (212) 555-0199",
                r"C:\Users\someone\Desktop\project",
                "/home/someone/project/cache",
                "professor meeting transcript for class project",
            )
        ),
        encoding="utf-8",
    )
    result = audit_directory(tmp_path)

    assert {
        "CREDENTIAL",
        "EMAIL",
        "PHONE",
        "WINDOWS_USER_PATH",
        "UNIX_HOME_PATH",
        "ACADEMIC_OR_PERSONAL",
    }.issubset(categories(result))
    serialized = result.to_json()
    for sensitive in (
        "live-secret-value",
        "private-token-value",
        "maintainer@example.com",
        "someone",
        "555-0199",
    ):
        assert sensitive not in serialized


def test_release_audit_rejects_forbidden_files_and_directories(tmp_path: Path) -> None:
    from tools.release_audit import audit_directory

    for relative in (
        ".env",
        ".private/providers.env",
        ".git/config",
        "provider-cache/real-news.json",
        "__pycache__/module.pyc",
        "package.egg-info/PKG-INFO",
    ):
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"synthetic")

    result = audit_directory(tmp_path)

    assert result.passed is False
    assert sum(f.category == "FORBIDDEN_FILE" for f in result.findings) == 6


def test_release_audit_accepts_safe_templates_and_professional_docs(
    tmp_path: Path,
) -> None:
    from tools.release_audit import audit_directory

    (tmp_path / ".env.example").write_text(
        "\n".join(
            (
                "FINVIZ_API_KEY=replace_with_your_finviz_elite_export_token",
                "NEWSAPI_KEY=replace_with_your_newsapi_key",
                "SEC_USER_AGENT=YourOrganization/1.0 contact@example.invalid",
            )
        ),
        encoding="utf-8",
    )
    (tmp_path / "README.md").write_text(
        "Contact the Integration Team. Use repository-relative paths.",
        encoding="utf-8",
    )

    result = audit_directory(tmp_path)

    assert result.passed is True
    assert result.findings == ()


def test_private_extra_patterns_are_loaded_without_exposing_the_pattern(
    tmp_path: Path,
) -> None:
    from tools.release_audit import audit_directory

    release = tmp_path / "release"
    release.mkdir()
    (release / "notes.txt").write_text(
        "private-person-marker appears here",
        encoding="utf-8",
    )
    patterns = tmp_path / "private-patterns.txt"
    patterns.write_text("private-person-marker\n", encoding="utf-8")

    result = audit_directory(release, extra_patterns_path=patterns)

    assert categories(result) == {"PRIVATE_EXTRA_PATTERN"}
    assert "private-person-marker" not in result.to_json()


def test_reviewed_allowlist_suppresses_only_matching_category_path_and_line(
    tmp_path: Path,
) -> None:
    import json

    from tools.release_audit import audit_directory

    (tmp_path / "compat.py").write_text(
        'LEGACY_ROUTE = "/api/professor"\n'
        'UNRELATED = "professor meeting transcript"\n',
        encoding="utf-8",
    )
    allowlist = tmp_path / "release-audit-allowlist.json"
    allowlist.write_text(
        json.dumps(
            {
                "entries": [
                    {
                        "category": "ACADEMIC_OR_PERSONAL",
                        "path": "compat.py",
                        "line_pattern": r'LEGACY_ROUTE = "/api/professor"',
                        "reason": "Backward-compatible machine route.",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    result = audit_directory(tmp_path, allowlist_path=allowlist)

    assert sum(
        finding.category == "ACADEMIC_OR_PERSONAL"
        for finding in result.findings
    ) == 2
    assert all(finding.line == 2 for finding in result.findings)


def test_release_audit_cli_auto_loads_staged_reviewed_allowlist(
    tmp_path: Path,
    capsys,
) -> None:
    import json

    from tools.release_audit import main

    (tmp_path / "compat.py").write_text(
        'LEGACY_ROUTE = "/api/professor"\n',
        encoding="utf-8",
    )
    (tmp_path / "release-audit-allowlist.json").write_text(
        json.dumps(
            {
                "entries": [
                    {
                        "category": "ACADEMIC_OR_PERSONAL",
                        "path": "compat.py",
                        "line_pattern": r'LEGACY_ROUTE = "/api/professor"',
                        "reason": "Backward-compatible machine route.",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    exit_code = main([str(tmp_path), "--json"])

    assert exit_code == 0
    assert json.loads(capsys.readouterr().out)["status"] == "PASS"
