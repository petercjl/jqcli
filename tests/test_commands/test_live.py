import json

from click.testing import CliRunner

from jqcli.cli import main


def test_live_ls_json(monkeypatch, tmp_path):
    monkeypatch.setattr("jqcli.commands.live.make_client", lambda app: object())
    monkeypatch.setattr(
        "jqcli.commands.live.list_live_trades",
        lambda client, process: {"items": [{"id": "live1", "name": "模拟A"}], "process": process},
    )

    result = CliRunner().invoke(
        main,
        ["--config", str(tmp_path / "c.json"), "--token", "tok", "--format", "json", "live", "ls"],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["items"][0]["id"] == "live1"
    assert payload["process"] == "running"


def test_live_positions_by_id_json(monkeypatch, tmp_path):
    monkeypatch.setattr("jqcli.commands.live.make_client", lambda app: object())
    monkeypatch.setattr(
        "jqcli.commands.live.get_live_positions",
        lambda client, live_id, **kwargs: {"id": live_id, "positions": [], "cash": 100},
    )

    result = CliRunner().invoke(
        main,
        ["--config", str(tmp_path / "c.json"), "--token", "tok", "--format", "json", "live", "positions", "live1"],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["id"] == "live1"
    assert payload["cash"] == 100


def test_live_positions_by_name_json(monkeypatch, tmp_path):
    monkeypatch.setattr("jqcli.commands.live.make_client", lambda app: object())
    monkeypatch.setattr(
        "jqcli.commands.live.list_live_trades",
        lambda client, process: {"items": [{"id": "live1", "name": "qmt四季发财v3-Clone-模拟交易"}]},
    )
    monkeypatch.setattr(
        "jqcli.commands.live.get_live_positions",
        lambda client, live_id, **kwargs: {"id": live_id, "positions": [], "cash": 100},
    )

    result = CliRunner().invoke(
        main,
        [
            "--config",
            str(tmp_path / "c.json"),
            "--token",
            "tok",
            "--format",
            "json",
            "live",
            "positions",
            "--name",
            "qmt四季发财",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["id"] == "live1"
    assert payload["name"] == "qmt四季发财v3-Clone-模拟交易"


def test_live_logs_by_name_json(monkeypatch, tmp_path):
    monkeypatch.setattr("jqcli.commands.live.make_client", lambda app: object())
    monkeypatch.setattr(
        "jqcli.commands.live.list_live_trades",
        lambda client, process: {"items": [{"id": "live1", "name": "qmt四季发财v3-Clone-模拟交易"}]},
    )
    monkeypatch.setattr(
        "jqcli.commands.live.get_live_logs",
        lambda client, live_id, **kwargs: {
            "id": live_id,
            "logs": [{"raw": "2026-06-22 09:30:00 - INFO  - 启动"}],
            "count": 1,
        },
    )

    result = CliRunner().invoke(
        main,
        [
            "--config",
            str(tmp_path / "c.json"),
            "--token",
            "tok",
            "--format",
            "json",
            "live",
            "logs",
            "--name",
            "qmt四季发财",
            "--limit",
            "100",
            "--date",
            "2026-06-22",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["id"] == "live1"
    assert payload["name"] == "qmt四季发财v3-Clone-模拟交易"
    assert payload["count"] == 1
