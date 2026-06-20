from __future__ import annotations

import json
from pathlib import Path

from jqcli.web import create_app
from jqcli.web.db import connect, init_db
from jqcli.web.routes import valid_post_id
from jqcli.web.services.archive_sync import refresh_archive
from jqcli.web.services.code_standardizer import BEGIN, standardize_code
from jqcli.web.services.posts import import_posts


def write_headers(app):
    return {"X-JQCLI-Web-Token": app.config["JQCLI_WEB_WRITE_TOKEN"]}


def write_archive(path: Path) -> None:
    raw = {
        "id": "p1",
        "title": "策略帖子",
        "url": "https://www.joinquant.com/view/community/detail/p1",
        "published_at": "2026-01-02 03:04:05",
        "content": "这是一个有详细思路的策略，包含选股、择时、风控、调仓和代码说明。def initialize(context): pass",
        "author": {"name": "a"},
        "reply_count": 1,
        "backtest": {
            "id": "bt1",
            "name": "回测",
            "clone_count": 2,
            "stats": {"trading_days": 300, "annual_algo_return": 0.42, "sharpe": 2.3, "max_drawdown": 0.12},
        },
    }
    path.write_text(json.dumps(raw, ensure_ascii=False) + "\n", encoding="utf-8")


def test_standardize_code_injects_initialize_tail():
    code = "def initialize(context):\n    g.x = 1\n"
    standardized = standardize_code(code)
    assert BEGIN in standardized
    assert "set_slippage(FixedSlippage(0.02), type=\"stock\")" in standardized
    assert standardized.index("g.x = 1") < standardized.index(BEGIN)
    assert standardize_code(standardized).count(BEGIN) == 1


def test_import_posts_and_list_api(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    archive = data_dir / "community_posts_archive.jsonl"
    candidates = data_dir / "original_strategy_candidates_period_gt_1y.csv"
    write_archive(archive)
    candidates.write_text("id\np1\n", encoding="utf-8")
    app = create_app(
        {
            "TESTING": True,
            "JQCLI_DB_PATH": data_dir / "manager.sqlite3",
            "JQCLI_ARCHIVE_PATH": archive,
            "JQCLI_CANDIDATES_PATH": candidates,
            "JQCLI_MANAGER_DIR": data_dir / "strategy_manager",
        }
    )
    payload = import_posts(Path(app.config["JQCLI_DB_PATH"]), archive, candidates)
    assert payload["imported"] == 1

    client = app.test_client()
    response = client.get("/api/posts?min_period_years=1&label=原创候选")
    assert response.status_code == 200
    data = response.get_json()
    assert data["total"] == 1
    assert data["items"][0]["title"] == "策略帖子"
    assert "原创候选" in data["items"][0]["labels"]


def test_standardize_endpoint_uses_local_archive(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    db_path = tmp_path / "manager.sqlite3"
    source_dir = tmp_path / "strategy_manager" / "strategies" / "p1"
    source_dir.mkdir(parents=True)
    original = source_dir / "original.py"
    original.write_text("def initialize(context):\n    pass\n", encoding="utf-8")
    app = create_app(
        {
            "TESTING": True,
            "JQCLI_DB_PATH": db_path,
            "JQCLI_MANAGER_DIR": tmp_path / "strategy_manager",
            "JQCLI_ARCHIVE_PATH": tmp_path / "missing.jsonl",
            "JQCLI_CANDIDATES_PATH": tmp_path / "missing.csv",
        }
    )
    with connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO strategy_archives(post_id, source_backtest_id, original_code_path, status, updated_at)
            VALUES('p1', 'bt1', ?, 'downloaded', 'now')
            """,
            (str(original),),
        )
        conn.commit()
    response = app.test_client().post("/api/posts/p1/standardize", headers=write_headers(app))
    assert response.status_code == 200
    target = Path(response.get_json()["standardized_code_path"])
    assert BEGIN in target.read_text(encoding="utf-8")


def test_post_endpoints_require_write_token(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    app = create_app(
        {
            "TESTING": True,
            "JQCLI_DB_PATH": tmp_path / "manager.sqlite3",
            "JQCLI_MANAGER_DIR": tmp_path / "strategy_manager",
            "JQCLI_ARCHIVE_PATH": tmp_path / "missing.jsonl",
            "JQCLI_CANDIDATES_PATH": tmp_path / "missing.csv",
        }
    )

    response = app.test_client().post("/api/posts/reindex")

    assert response.status_code == 403


def test_invalid_post_id_is_rejected_before_file_paths(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    app = create_app(
        {
            "TESTING": True,
            "JQCLI_DB_PATH": tmp_path / "manager.sqlite3",
            "JQCLI_MANAGER_DIR": tmp_path / "strategy_manager",
            "JQCLI_ARCHIVE_PATH": tmp_path / "missing.jsonl",
            "JQCLI_CANDIDATES_PATH": tmp_path / "missing.csv",
        }
    )

    response = app.test_client().post("/api/posts/%2E%2E/standardize", headers=write_headers(app))

    assert response.status_code == 400
    assert valid_post_id("p1_ABC-123") is True
    assert valid_post_id("..") is False
    assert valid_post_id("a/b") is False


def test_refresh_archive_uses_explicit_script_path(tmp_path, monkeypatch):
    db_path = tmp_path / "manager.sqlite3"
    archive_path = tmp_path / "archive.jsonl"
    candidates_path = tmp_path / "candidates.csv"
    script_path = tmp_path / "trusted_archive.py"
    script_path.write_text(
        "from pathlib import Path\n"
        "import argparse\n"
        "parser=argparse.ArgumentParser()\n"
        "parser.add_argument('--phase')\n"
        "parser.add_argument('--store')\n"
        "parser.add_argument('--state')\n"
        "args=parser.parse_args()\n"
        "Path(args.store).write_text('', encoding='utf-8')\n",
        encoding="utf-8",
    )
    init_db(db_path)

    payload = refresh_archive(db_path, tmp_path, archive_path, candidates_path, script_path=script_path)

    assert payload["import"]["imported"] == 0


def test_refresh_archive_rejects_missing_script(tmp_path):
    try:
        refresh_archive(
            tmp_path / "manager.sqlite3",
            tmp_path,
            tmp_path / "archive.jsonl",
            tmp_path / "candidates.csv",
            script_path=tmp_path / "missing.py",
        )
    except RuntimeError as exc:
        assert "archive script not found" in str(exc)
    else:
        raise AssertionError("missing script should fail")


def test_posts_page_sets_page_flag_before_app_js(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    app = create_app(
        {
            "TESTING": True,
            "JQCLI_DB_PATH": data_dir / "manager.sqlite3",
            "JQCLI_ARCHIVE_PATH": data_dir / "missing.jsonl",
            "JQCLI_CANDIDATES_PATH": data_dir / "missing.csv",
            "JQCLI_MANAGER_DIR": data_dir / "strategy_manager",
        }
    )
    html = app.test_client().get("/posts").get_data(as_text=True)
    assert html.index('window.JQCLI_PAGE = "posts"') < html.index("app.js")


def test_list_posts_hides_duplicate_title_time(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    archive = data_dir / "community_posts_archive.jsonl"
    rows = [
            {
                "id": "p1",
                "title": "重复策略",
                "url": "https://example.test/p1",
                "published_at": "2026-01-01 10:00:00",
                "author": {"name": "同一作者"},
                "content": "同一篇正文",
                "backtest": {"id": "bt1", "clone_count": 1, "stats": {"trading_days": 300, "sharpe": 1}},
            },
            {
                "id": "p2",
                "title": "重复策略",
                "url": "https://example.test/p2",
                "published_at": "2026-01-01 10:00:00",
                "author": {"name": "同一作者"},
                "content": "同一篇正文",
                "backtest": {"id": "bt2", "clone_count": 5, "stats": {"trading_days": 300, "sharpe": 1}},
            },
    ]
    archive.write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n", encoding="utf-8")
    app = create_app(
        {
            "TESTING": True,
            "JQCLI_DB_PATH": data_dir / "manager.sqlite3",
            "JQCLI_ARCHIVE_PATH": archive,
            "JQCLI_CANDIDATES_PATH": data_dir / "missing.csv",
            "JQCLI_MANAGER_DIR": data_dir / "strategy_manager",
        }
    )
    data = app.test_client().get("/api/posts").get_json()
    assert data["total"] == 1
    assert data["items"][0]["id"] == "p2"
    with_dups = app.test_client().get("/api/posts?include_duplicates=1").get_json()
    assert with_dups["total"] == 2
