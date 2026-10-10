"""A backup downloads for an administrator only (2.18.0 gate).

A backup is the whole company: every record, the sign-ins' password
hashes, the encrypted keys, the payroll and HR records only an
administrator may read, and since 2.18.0 every stored file. Any signed-in
role could download one: a read-only sign-in took the whole database. The
server refuses anyone but an administrator, and Settings offers Download
to an administrator only."""

from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app

ROOT = Path(__file__).resolve().parents[1]


def _as(client, role):
    r = client.post("/api/tokens", json={"label": f"as-{role}", "role": role})
    assert r.status_code == 201, r.text
    c = TestClient(app)
    c.headers["Authorization"] = f"Bearer {r.json()['token']}"
    return c


def test_only_an_administrator_downloads_a_backup(
    client, seed_accounts, tmp_path, monkeypatch
):
    # the suite's database is in memory; a backup file stands in for one
    from app.routes import backups

    backup = tmp_path / "harbor-light-bakery_2026-09-27_0900.db"
    backup.write_bytes(b"SQLite format 3\x00" + b"\x00" * 64)
    monkeypatch.setattr(backups, "_company_backup_path", lambda db, name: backup)
    url = f"/api/backups/download/{backup.name}"
    assert client.get(url).status_code == 200  # the administrator's session
    for role in ("readonly", "bookkeeper"):
        r = _as(client, role).get(url)
        assert r.status_code == 403, (role, r.status_code)
        assert not r.content.startswith(b"SQLite format 3"), role


def test_settings_offers_download_to_an_administrator_only():
    js = (ROOT / "app/static/js/settings.js").read_text(encoding="utf-8")
    assert '${SettingsPage._isAdmin() ? `<a href="/api/backups/download/' in js
    app_js = (ROOT / "app/static/js/app.js").read_text(encoding="utf-8")
    assert """document.querySelectorAll('#sidebar a[href="#/audit"]')""" in app_js
    assert "const entry = letter('KeyN') || letter('KeyP') || letter('KeyQ');" in app_js
    assert "if (entry && App.isReadOnly())" in app_js
