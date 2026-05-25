from __future__ import annotations

from pathlib import Path

from swedish_parcels.folder_cli import main


def test_runs_against_fixtures_dir(capsys, tmp_path) -> None:
    fixtures = Path(__file__).resolve().parent.parent / "fixtures"
    if not fixtures.exists() or not any(fixtures.rglob("*.eml")):
        # Allow running without fixtures present (CI).
        return
    rc = main([str(fixtures), "--open-only"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "scanned" in out
    assert "parcels" in out


def test_missing_path_returns_2(capsys) -> None:
    rc = main(["/nonexistent/path/12345"])
    assert rc == 2


def test_single_file_input(capsys) -> None:
    fixtures = Path(__file__).resolve().parent.parent / "fixtures" / "bring"
    if not fixtures.exists():
        return
    files = list(fixtures.glob("*.eml"))
    if not files:
        return
    rc = main([str(files[0])])
    out = capsys.readouterr().out
    assert rc == 0
    assert "[bring]" in out
