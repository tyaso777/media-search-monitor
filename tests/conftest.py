from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from news_monitor import database
from news_monitor.config import load_keywords, load_sites


@pytest.fixture()
def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


@pytest.fixture()
def fixture_html(repo_root: Path) -> str:
    return (repo_root / "tests" / "fixtures" / "sample_search_result_static.html").read_text(
        encoding="utf-8"
    )


@pytest.fixture()
def conn(tmp_path: Path):
    db_path = tmp_path / "news_monitor.sqlite"
    with database.connect(db_path) as connection:
        database.init_db(connection)
        yield connection


@pytest.fixture()
def imported_conn(conn, repo_root: Path):
    database.import_keywords(conn, load_keywords(repo_root / "config" / "keywords.csv")[:3])
    sample_sites = [
        replace(site, enabled=True)
        for site in load_sites(repo_root / "config" / "sites.yaml")[:2]
    ]
    database.import_sites(conn, sample_sites)
    return conn
