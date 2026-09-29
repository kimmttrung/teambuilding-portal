"""Preflight không sửa DB nguồn và backup an toàn bằng SQLite backup API."""

import sqlite3

import pytest

from scripts.preflight_schema_v2 import (
    MERGED_TABLES, RETAINED_TABLES, backup_database, inspect_database,
)


def test_preflight_counts_rows_without_exposing_data(tmp_path):
    source = tmp_path / "source.db"
    with sqlite3.connect(source) as conn:
        conn.execute("CREATE TABLE alembic_version (version_num TEXT NOT NULL)")
        conn.execute("INSERT INTO alembic_version VALUES ('5f3a91c7d420')")
        for name in MERGED_TABLES:
            if name == "policy_documents":
                conn.execute(
                    'CREATE TABLE policy_documents (id INTEGER PRIMARY KEY, event_id INTEGER, content TEXT)'
                )
                conn.execute(
                    "INSERT INTO policy_documents (event_id, content) VALUES (NULL, 'sensitive')"
                )
            else:
                conn.execute(f'CREATE TABLE "{name}" (id INTEGER PRIMARY KEY)')

    report = inspect_database(source)
    assert report["rows_to_archive"]["policy_documents"] == 1
    assert report["shared_policy_documents"] == 1
    assert report["ready"] is False  # 12 != 35; không cho phép migrate thử nhầm DB
    assert "sensitive" not in str(report)


def test_backup_keeps_source_intact_and_refuses_overwrite(tmp_path):
    source, destination = tmp_path / "source.db", tmp_path / "backup.db"
    with sqlite3.connect(source) as conn:
        conn.execute("CREATE TABLE data (value TEXT)")
        conn.execute("INSERT INTO data VALUES ('giữ nguyên')")

    backup_database(source, destination)
    with sqlite3.connect(destination) as copy:
        assert copy.execute("SELECT value FROM data").fetchone() == ("giữ nguyên",)
    with pytest.raises(ValueError):
        backup_database(source, destination)
    with sqlite3.connect(source) as original:
        assert original.execute("SELECT COUNT(*) FROM data").fetchone()[0] == 1


def test_backup_includes_committed_wal_rows(tmp_path):
    source, destination = tmp_path / "wal.db", tmp_path / "wal-backup.db"
    with sqlite3.connect(source) as original:
        assert original.execute("PRAGMA journal_mode=WAL").fetchone()[0] == "wal"
        original.execute("CREATE TABLE data (value TEXT)")
        original.commit()
        original.execute("INSERT INTO data VALUES ('trong WAL')")
        original.commit()
        backup_database(source, destination)
        with sqlite3.connect(destination) as copy:
            assert copy.execute("SELECT value FROM data").fetchone() == ("trong WAL",)


def test_preflight_accepts_35_tables_and_one_revision(tmp_path):
    source = tmp_path / "old.db"
    with sqlite3.connect(source) as conn:
        conn.execute("CREATE TABLE alembic_version (version_num TEXT NOT NULL)")
        conn.execute("INSERT INTO alembic_version VALUES ('5f3a91c7d420')")
        for name in MERGED_TABLES:
            if name == "policy_documents":
                conn.execute(
                    "CREATE TABLE policy_documents (id INTEGER PRIMARY KEY, event_id INTEGER)"
                )
            else:
                conn.execute(f'CREATE TABLE "{name}" (id INTEGER PRIMARY KEY)')
        for name in RETAINED_TABLES:
            conn.execute(f'CREATE TABLE "{name}" (id INTEGER PRIMARY KEY)')

    report = inspect_database(source)
    assert report["ready"] is True
    assert report["table_count"] == 35
    assert report["revisions"] == ["5f3a91c7d420"]


def test_preflight_rejects_unknown_table_even_at_35(tmp_path):
    source = tmp_path / "wrong.db"
    with sqlite3.connect(source) as conn:
        conn.execute("CREATE TABLE alembic_version (version_num TEXT NOT NULL)")
        conn.execute("INSERT INTO alembic_version VALUES ('5f3a91c7d420')")
        for name in (*MERGED_TABLES, *RETAINED_TABLES):
            if name == "policy_documents":
                conn.execute('CREATE TABLE policy_documents (id INTEGER PRIMARY KEY, event_id INTEGER)')
            elif name == "hotels":
                conn.execute('CREATE TABLE other_hotels (id INTEGER PRIMARY KEY)')
            else:
                conn.execute(f'CREATE TABLE "{name}" (id INTEGER PRIMARY KEY)')

    report = inspect_database(source)
    assert report["table_count"] == 35
    assert report["ready"] is False
    assert "hotels" in report["missing_tables"]
    assert "other_hotels" in report["unexpected_tables"]