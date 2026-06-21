import json
import zipfile

from click.testing import CliRunner

from jqcli.cli import main


def test_backtest_run_json(monkeypatch, tmp_path):
    captured = {}
    monkeypatch.setattr("jqcli.commands.backtest.make_client", lambda app: object())

    def fake_run(client, **kwargs):
        captured.update(kwargs)
        return {"id": "bt1", "status": "running"}

    monkeypatch.setattr("jqcli.commands.backtest.run_backtest", fake_run)

    result = CliRunner().invoke(
        main,
        [
            "--config",
            str(tmp_path / "c.json"),
            "--token",
            "tok",
            "--format",
            "json",
            "backtest",
            "run",
            "s1",
            "--start",
            "2023-01-01",
            "--end",
            "2023-12-31",
        ],
    )

    assert result.exit_code == 0
    assert captured["strategy_id"] == "s1"
    assert captured["compile_only"] is False
    assert captured["use_credit"] is False
    assert json.loads(result.output)["id"] == "bt1"


def test_backtest_run_compile_flag(monkeypatch, tmp_path):
    captured = {}
    monkeypatch.setattr("jqcli.commands.backtest.make_client", lambda app: object())

    def fake_run(client, **kwargs):
        captured.update(kwargs)
        return {"id": "bt1", "status": "running", "mode": "compile"}

    monkeypatch.setattr("jqcli.commands.backtest.run_backtest", fake_run)

    result = CliRunner().invoke(
        main,
        [
            "--config",
            str(tmp_path / "c.json"),
            "--token",
            "tok",
            "--format",
            "json",
            "backtest",
            "run",
            "s1",
            "--start",
            "2023-01-01",
            "--compile",
        ],
    )

    assert result.exit_code == 0
    assert captured["compile_only"] is True
    assert json.loads(result.output)["mode"] == "compile"


def test_backtest_run_use_credit_flag(monkeypatch, tmp_path):
    captured = {}
    monkeypatch.setattr("jqcli.commands.backtest.make_client", lambda app: object())

    def fake_run(client, **kwargs):
        captured.update(kwargs)
        return {"id": "bt1", "status": "running"}

    monkeypatch.setattr("jqcli.commands.backtest.run_backtest", fake_run)

    result = CliRunner().invoke(
        main,
        [
            "--config",
            str(tmp_path / "c.json"),
            "--token",
            "tok",
            "--format",
            "json",
            "backtest",
            "run",
            "s1",
            "--start",
            "2023-01-01",
            "--use-credit",
        ],
    )

    assert result.exit_code == 0
    assert captured["use_credit"] is True


def test_backtest_run_wait(monkeypatch, tmp_path):
    monkeypatch.setattr("jqcli.commands.backtest.make_client", lambda app: object())
    monkeypatch.setattr(
        "jqcli.commands.backtest.run_backtest",
        lambda client, **kwargs: {"id": "bt1", "list_id": "list-bt1", "status": "running"},
    )

    captured = {}

    def fake_wait(client, backtest_id, timeout, poll_interval, **kwargs):
        captured["backtest_id"] = backtest_id
        captured["kwargs"] = kwargs
        return {"id": backtest_id, "status": "done"}

    monkeypatch.setattr(
        "jqcli.commands.backtest.wait_for_backtest",
        fake_wait,
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
            "backtest",
            "run",
            "s1",
            "--start",
            "2023-01-01",
            "--wait",
        ],
    )

    assert result.exit_code == 0
    assert json.loads(result.output)["status"] == "done"
    assert captured["backtest_id"] == "bt1"
    assert captured["kwargs"]["list_id"] == "list-bt1"


def test_backtest_ls_json(monkeypatch, tmp_path):
    monkeypatch.setattr("jqcli.commands.backtest.make_client", lambda app: object())
    monkeypatch.setattr("jqcli.commands.backtest.list_backtests", lambda client, **kwargs: {"items": [{"id": "bt1"}]})

    result = CliRunner().invoke(
        main,
        ["--config", str(tmp_path / "c.json"), "--token", "tok", "--format", "json", "backtest", "ls", "s1"],
    )

    assert result.exit_code == 0
    assert json.loads(result.output) == {"items": [{"id": "bt1"}]}


def test_backtest_ls_compile_flag(monkeypatch, tmp_path):
    captured = {}
    monkeypatch.setattr("jqcli.commands.backtest.make_client", lambda app: object())

    def fake_list(client, **kwargs):
        captured.update(kwargs)
        return {"items": []}

    monkeypatch.setattr("jqcli.commands.backtest.list_backtests", fake_list)

    result = CliRunner().invoke(
        main,
        [
            "--config",
            str(tmp_path / "c.json"),
            "--token",
            "tok",
            "--format",
            "json",
            "backtest",
            "ls",
            "s1",
            "--compile",
        ],
    )

    assert result.exit_code == 0
    assert captured["compile_only"] is True


def test_find_backtest_list_item_matches_returned_list_id(monkeypatch):
    from jqcli.commands import backtest

    captured = {}

    def fake_list_backtests(client, **kwargs):
        captured.update(kwargs)
        return {
            "items": [
                {"id": "detail-id", "list_id": "returned-list-id", "source_id": "source-id", "status": "running"},
            ],
        }

    monkeypatch.setattr(backtest, "list_backtests", fake_list_backtests)

    payload = backtest.find_backtest_list_item(
        object(),
        "58963559",
        strategy_id="strategy-id",
        compile_only=False,
        list_id="returned-list-id",
    )

    assert payload["id"] == "detail-id"
    assert captured["strategy_id"] == "strategy-id"
    assert captured["all_items"] is True


def test_backtest_show_json(monkeypatch, tmp_path):
    monkeypatch.setattr("jqcli.commands.backtest.make_client", lambda app: object())
    monkeypatch.setattr("jqcli.commands.backtest.get_backtest", lambda client, backtest_id: {"id": backtest_id, "status": "done"})

    result = CliRunner().invoke(
        main,
        ["--config", str(tmp_path / "c.json"), "--token", "tok", "--format", "json", "backtest", "show", "bt1"],
    )

    assert result.exit_code == 0
    assert json.loads(result.output)["id"] == "bt1"


def test_backtest_stats_json(monkeypatch, tmp_path):
    monkeypatch.setattr("jqcli.commands.backtest.make_client", lambda app: object())
    monkeypatch.setattr(
        "jqcli.commands.backtest.get_backtest_stats",
        lambda client, backtest_id: {"id": backtest_id, "metrics": {"annual_algo_return": 0.3}},
    )

    result = CliRunner().invoke(
        main,
        ["--config", str(tmp_path / "c.json"), "--token", "tok", "--format", "json", "backtest", "stats", "bt1"],
    )

    assert result.exit_code == 0
    assert json.loads(result.output)["metrics"]["annual_algo_return"] == 0.3


def test_backtest_result_json(monkeypatch, tmp_path):
    captured = {}
    monkeypatch.setattr("jqcli.commands.backtest.make_client", lambda app: object())

    def fake_result(client, backtest_id, **kwargs):
        captured["backtest_id"] = backtest_id
        captured["kwargs"] = kwargs
        return {"id": backtest_id, "data": {"state": "2"}}

    monkeypatch.setattr("jqcli.commands.backtest.get_backtest_result", fake_result)

    result = CliRunner().invoke(
        main,
        [
            "--config",
            str(tmp_path / "c.json"),
            "--token",
            "tok",
            "--format",
            "json",
            "backtest",
            "result",
            "bt1",
            "--offset",
            "10",
            "--user-record-offset",
            "2",
        ],
    )

    assert result.exit_code == 0
    assert captured == {"backtest_id": "bt1", "kwargs": {"offset": 10, "user_record_offset": 2}}
    assert json.loads(result.output)["data"]["state"] == "2"


def test_backtest_export_writes_file(monkeypatch, tmp_path):
    monkeypatch.setattr("jqcli.commands.backtest.make_client", lambda app: object())

    def fake_export(client, backtest_id, **kwargs):
        return {
            "id": backtest_id,
            "resolved_id": "hex-id",
            "kind": kwargs["kind"],
            "filename": "result_1.csv",
            "content_type": "text/csv",
            "content": b"a,b\n1,2\n",
        }

    monkeypatch.setattr("jqcli.commands.backtest.export_backtest_data", fake_export)
    output_dir = tmp_path / "exports"

    result = CliRunner().invoke(
        main,
        [
            "--config",
            str(tmp_path / "c.json"),
            "--token",
            "tok",
            "--format",
            "json",
            "backtest",
            "export",
            "bt1",
            "--kind",
            "result",
            "--output-dir",
            str(output_dir),
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["files"][0]["kind"] == "result"
    assert payload["files"][0]["size"] == 8
    assert (output_dir / "result_1.csv").read_bytes() == b"a,b\n1,2\n"


def test_backtest_export_preprocess_existing_files(tmp_path):
    output_dir = tmp_path / "exports"
    output_dir.mkdir()
    (output_dir / "result_1.csv").write_text(
        "时间,基准收益,策略收益,当日盈利,当日亏损,当日买入,当日卖出,超额收益(%)\n"
        "2023-01-03 16:00:00,0.88,0,0,0,0,0,-0.87\n",
        encoding="gbk",
    )
    with zipfile.ZipFile(output_dir / "transaction.zip", "w") as archive:
        archive.writestr(
            "transaction.csv",
            (
                "日期,委托时间,品种,标的,交易类型,下单类型,成交数量,成交价,成交额,委托数量,委托价格,平仓盈亏,手续费,状态,最后更新时间\n"
                "2023-01-04,09:35:00,股票,测试股(000001.XSHG),买,市价单,100股,10,1000,100股,-,0,5,全部成交,2023-01-04 09:35:00\n"
            ).encode("gbk"),
        )
    with zipfile.ZipFile(output_dir / "position.zip", "w") as archive:
        archive.writestr(
            "position.csv",
            (
                "日期,品种,标的,多空,数量,可用数量,收盘价/结算价,市值/价值,盈亏/逐笔浮盈,开仓均价,持仓均价（期货）,保证金,当日盈亏,今手数,盈亏占比,仓位占比\n"
                "2023-01-04,股票,测试股(000001.XSHG),多,100股,0股,10,1000,0,10,-,0,0,100股,0%,10000,10%\n"
            ).encode("gbk"),
        )
    with zipfile.ZipFile(output_dir / "log.zip", "w") as archive:
        archive.writestr(
            "log.txt",
            'INFO HUMAN|hello\nINFO JQ_AUDIT|{"event":"x","value":1}\n'.encode("utf-8"),
        )

    result = CliRunner().invoke(
        main,
        [
            "--config",
            str(tmp_path / "c.json"),
            "--format",
            "json",
            "backtest",
            "export",
            "bt1",
            "--mode",
            "preprocess",
            "--output-dir",
            str(output_dir),
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["mode"] == "preprocess"
    clean_dir = output_dir / "clean"
    assert (clean_dir / "transactions.normalized.csv").exists()
    assert (clean_dir / "positions.normalized.csv").exists()
    assert (clean_dir / "logs.audit.jsonl").read_text(encoding="utf-8").strip() == '{"event": "x", "value": 1}'
    diagnostics = json.loads((clean_dir / "diagnostics.json").read_text(encoding="utf-8"))
    assert diagnostics["transactions"]["gross_turnover"] == 1000
    assert diagnostics["positions"]["max_single_weight_pct"] == 10


def test_backtest_export_all_downloads_and_preprocesses(monkeypatch, tmp_path):
    monkeypatch.setattr("jqcli.commands.backtest.make_client", lambda app: object())

    def fake_export(client, backtest_id, **kwargs):
        kind = kwargs["kind"]
        if kind == "result":
            content = (
                "时间,基准收益,策略收益,当日盈利,当日亏损,当日买入,当日卖出,超额收益(%)\n"
                "2023-01-03 16:00:00,0,1,1,0,1,0,1\n"
            ).encode("gbk")
            filename = "result_1.csv"
        else:
            content = b""
            filename = f"{kind}.zip"
            from io import BytesIO

            buffer = BytesIO()
            with zipfile.ZipFile(buffer, "w") as archive:
                if kind == "transaction":
                    archive.writestr(
                        "transaction.csv",
                        "日期,委托时间,品种,标的,交易类型,下单类型,成交数量,成交价,成交额,委托数量,委托价格,平仓盈亏,手续费,状态,最后更新时间\n",
                    )
                elif kind == "position":
                    archive.writestr(
                        "position.csv",
                        "日期,品种,标的,多空,数量,可用数量,收盘价/结算价,市值/价值,盈亏/逐笔浮盈,开仓均价,持仓均价（期货）,保证金,当日盈亏,今手数,盈亏占比,仓位占比\n",
                    )
                else:
                    archive.writestr("log.txt", "")
            content = buffer.getvalue()
        return {
            "id": backtest_id,
            "resolved_id": "hex-id",
            "kind": kind,
            "filename": filename,
            "content_type": "application/octet-stream",
            "content": content,
        }

    monkeypatch.setattr("jqcli.commands.backtest.export_backtest_data", fake_export)
    output_dir = tmp_path / "exports"

    result = CliRunner().invoke(
        main,
        [
            "--config",
            str(tmp_path / "c.json"),
            "--token",
            "tok",
            "--format",
            "json",
            "backtest",
            "export",
            "bt1",
            "--mode",
            "all",
            "--output-dir",
            str(output_dir),
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert len(payload["files"]) == 4
    assert payload["preprocess"]["output_dir"] == str((output_dir / "clean").resolve())


def test_backtest_logs_json(monkeypatch, tmp_path):
    captured = {}
    monkeypatch.setattr("jqcli.commands.backtest.make_optional_client", lambda app: object())

    def fake_logs(client, backtest_id, **kwargs):
        captured["backtest_id"] = backtest_id
        captured["kwargs"] = kwargs
        return {"id": backtest_id, "kind": "log", "logs": ["line"]}

    monkeypatch.setattr("jqcli.commands.backtest.get_backtest_logs", fake_logs)

    result = CliRunner().invoke(
        main,
        [
            "--config",
            str(tmp_path / "c.json"),
            "--token",
            "tok",
            "--format",
            "json",
            "backtest",
            "logs",
            "bt1",
            "--offset",
            "10",
            "--all",
            "--max-pages",
            "3",
        ],
    )

    assert result.exit_code == 0
    assert captured == {
        "backtest_id": "bt1",
        "kwargs": {"offset": 10, "error": False, "all_items": True, "max_pages": 3},
    }
    assert json.loads(result.output)["logs"] == ["line"]


def test_backtest_error_logs_json(monkeypatch, tmp_path):
    captured = {}
    monkeypatch.setattr("jqcli.commands.backtest.make_optional_client", lambda app: object())

    def fake_logs(client, backtest_id, **kwargs):
        captured["kwargs"] = kwargs
        return {"id": backtest_id, "kind": "error", "logs": ["Traceback"]}

    monkeypatch.setattr("jqcli.commands.backtest.get_backtest_logs", fake_logs)

    result = CliRunner().invoke(
        main,
        [
            "--config",
            str(tmp_path / "c.json"),
            "--token",
            "tok",
            "--format",
            "json",
            "backtest",
            "logs",
            "bt1",
            "--error",
        ],
    )

    assert result.exit_code == 0
    assert captured["kwargs"]["error"] is True
    assert json.loads(result.output)["kind"] == "error"


def test_backtest_rm_non_interactive_requires_yes(tmp_path):
    result = CliRunner().invoke(
        main,
        [
            "--config",
            str(tmp_path / "c.json"),
            "--token",
            "tok",
            "--format",
            "json",
            "--non-interactive",
            "backtest",
            "rm",
            "bt1",
        ],
    )

    assert result.exit_code == 7
    assert json.loads(result.stderr)["error"]["code"] == "confirmation_required"


def test_backtest_rm_with_yes(monkeypatch, tmp_path):
    monkeypatch.setattr("jqcli.commands.backtest.make_client", lambda app: object())
    monkeypatch.setattr(
        "jqcli.commands.backtest.delete_backtest_record",
        lambda client, backtest_id, compile_only=False: {"ok": True, "id": backtest_id, "compile_only": compile_only},
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
            "--non-interactive",
            "backtest",
            "rm",
            "bt1",
            "--yes",
        ],
    )

    assert result.exit_code == 0
    assert json.loads(result.output) == {"ok": True, "id": "bt1", "compile_only": False}


def test_backtest_rm_compile_flag(monkeypatch, tmp_path):
    monkeypatch.setattr("jqcli.commands.backtest.make_client", lambda app: object())
    monkeypatch.setattr(
        "jqcli.commands.backtest.delete_backtest_record",
        lambda client, backtest_id, compile_only=False: {"ok": True, "id": backtest_id, "compile_only": compile_only},
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
            "--non-interactive",
            "backtest",
            "rm",
            "bt1",
            "--yes",
            "--compile",
        ],
    )

    assert result.exit_code == 0
    assert json.loads(result.output) == {"ok": True, "id": "bt1", "compile_only": True}


def test_wait_for_backtest_reaches_done(monkeypatch):
    from jqcli.commands import backtest

    result_states = iter([
        {"id": "bt1", "data": {"state": "0"}},
    ])
    states = iter([
        {"id": "bt1", "resolved_id": "bt1", "metrics": []},
        {"id": "bt1", "resolved_id": "bt1", "metrics": {"annual_algo_return": 0.3, "sharpe": 1.2}},
    ])
    monkeypatch.setattr(backtest, "get_backtest_stats", lambda client, backtest_id: next(states))
    monkeypatch.setattr(backtest, "get_backtest", lambda client, backtest_id: {"id": backtest_id, "status": "running"})
    monkeypatch.setattr(backtest, "get_backtest_result", lambda client, backtest_id: next(result_states))
    monkeypatch.setattr(backtest.time, "sleep", lambda seconds: None)

    payload = backtest.wait_for_backtest(object(), "bt1", timeout=1, poll_interval=0)

    assert payload["status"] == "done"
    assert payload["metrics"]["sharpe"] == 1.2


def test_wait_for_backtest_returns_failed_state(monkeypatch):
    from jqcli.commands import backtest

    monkeypatch.setattr(backtest, "get_backtest_stats", lambda client, backtest_id: {"id": backtest_id, "metrics": []})
    monkeypatch.setattr(backtest, "get_backtest", lambda client, backtest_id: {"id": backtest_id, "status": "running"})
    monkeypatch.setattr(
        backtest,
        "find_backtest_list_item",
        lambda client, backtest_id, strategy_id, compile_only, list_id=None: {"id": backtest_id, "status": "failed"},
    )
    monkeypatch.setattr(
        backtest,
        "get_backtest_result",
        lambda client, backtest_id: {"id": backtest_id, "data": {"state": "1", "message": "failed"}},
    )
    monkeypatch.setattr(
        backtest,
        "get_backtest_logs",
        lambda client, backtest_id, error=False: {"id": backtest_id, "kind": "error", "logs": ["Traceback"]},
    )
    monkeypatch.setattr(backtest.time, "sleep", lambda seconds: None)

    payload = backtest.wait_for_backtest(object(), "bt1", timeout=60, poll_interval=5)

    assert payload["status"] == "failed"
    assert payload["error_logs"] == ["Traceback"]


def test_wait_for_backtest_returns_cancelled_state(monkeypatch):
    from jqcli.commands import backtest

    monkeypatch.setattr(backtest, "get_backtest_stats", lambda client, backtest_id: {"id": backtest_id, "metrics": {}})
    monkeypatch.setattr(backtest, "get_backtest", lambda client, backtest_id: {"id": backtest_id, "status": "running"})
    monkeypatch.setattr(
        backtest,
        "find_backtest_list_item",
        lambda client, backtest_id, strategy_id, compile_only, list_id=None: {"id": backtest_id, "status": "cancelled"},
    )
    monkeypatch.setattr(
        backtest,
        "get_backtest_result",
        lambda client, backtest_id: {"id": backtest_id, "data": {"state": 3}},
    )
    monkeypatch.setattr(
        backtest,
        "get_backtest_logs",
        lambda client, backtest_id, error=False: {"id": backtest_id, "kind": "error", "logs": []},
    )
    monkeypatch.setattr(backtest.time, "sleep", lambda seconds: None)

    payload = backtest.wait_for_backtest(object(), "bt1", timeout=60, poll_interval=5)

    assert payload["status"] == "cancelled"
    assert payload["error_logs"] == []


def test_wait_for_backtest_treats_cancelled_with_error_logs_as_failed(monkeypatch):
    from jqcli.commands import backtest

    monkeypatch.setattr(backtest, "get_backtest_stats", lambda client, backtest_id: {"id": backtest_id, "metrics": {}})
    monkeypatch.setattr(backtest, "get_backtest", lambda client, backtest_id: {"id": backtest_id, "status": "running"})
    monkeypatch.setattr(
        backtest,
        "find_backtest_list_item",
        lambda client, backtest_id, strategy_id, compile_only, list_id=None: None,
    )
    monkeypatch.setattr(
        backtest,
        "get_backtest_result",
        lambda client, backtest_id: {"id": backtest_id, "data": {"state": 3}},
    )
    monkeypatch.setattr(
        backtest,
        "get_backtest_logs",
        lambda client, backtest_id, error=False: {"id": backtest_id, "kind": "error", "logs": ["Traceback"]},
    )
    monkeypatch.setattr(backtest.time, "sleep", lambda seconds: None)

    payload = backtest.wait_for_backtest(object(), "bt1", timeout=60, poll_interval=5)

    assert payload["status"] == "failed"
    assert payload["result_status"] == "failed"
    assert payload["error_logs"] == ["Traceback"]


def test_wait_for_backtest_treats_result_state_one_as_running_without_list_item(monkeypatch):
    from jqcli.commands import backtest

    stats_payloads = iter([
        {"id": "bt1", "metrics": {}},
        {"id": "bt1", "metrics": {"annual_algo_return": 0.3, "sharpe": 1.2}},
    ])
    monkeypatch.setattr(backtest, "get_backtest_stats", lambda client, backtest_id: next(stats_payloads))
    monkeypatch.setattr(backtest, "get_backtest", lambda client, backtest_id: {"id": backtest_id, "status": "running"})
    monkeypatch.setattr(
        backtest,
        "find_backtest_list_item",
        lambda client, backtest_id, strategy_id, compile_only, list_id=None: None,
    )
    monkeypatch.setattr(
        backtest,
        "get_backtest_result",
        lambda client, backtest_id: {"id": backtest_id, "data": {"state": "1", "result": {"count": 70}}},
    )
    monkeypatch.setattr(backtest.time, "sleep", lambda seconds: None)

    payload = backtest.wait_for_backtest(object(), "bt1", timeout=60, poll_interval=5)

    assert payload["status"] == "done"
    assert payload["metrics"]["sharpe"] == 1.2


def test_wait_for_backtest_returns_done_list_state_before_stats_core(monkeypatch):
    from jqcli.commands import backtest

    monkeypatch.setattr(backtest, "get_backtest_stats", lambda client, backtest_id: {"id": backtest_id, "metrics": {"report_done_seconds": 1}})
    monkeypatch.setattr(backtest, "get_backtest", lambda client, backtest_id: {"id": backtest_id, "status": "running"})
    monkeypatch.setattr(
        backtest,
        "find_backtest_list_item",
        lambda client, backtest_id, strategy_id, compile_only, list_id=None: {"id": "detail-id", "status": "done"},
    )
    monkeypatch.setattr(
        backtest,
        "get_backtest_result",
        lambda client, backtest_id: {"id": backtest_id, "data": {"state": "0"}},
    )
    monkeypatch.setattr(backtest.time, "sleep", lambda seconds: None)

    payload = backtest.wait_for_backtest(object(), "bt1", timeout=60, poll_interval=5)

    assert payload["status"] == "done"
    assert payload["resolved_id"] == "detail-id"
    assert payload["metrics"] == {"report_done_seconds": 1}


def test_wait_for_backtest_prefers_failed_result_over_done_list_without_core_metrics(monkeypatch):
    from jqcli.commands import backtest

    monkeypatch.setattr(backtest, "get_backtest_stats", lambda client, backtest_id: {"id": backtest_id, "metrics": []})
    monkeypatch.setattr(backtest, "get_backtest", lambda client, backtest_id: {"id": backtest_id, "status": "running"})
    monkeypatch.setattr(
        backtest,
        "find_backtest_list_item",
        lambda client, backtest_id, strategy_id, compile_only, list_id=None: {"id": "detail-id", "status": "done"},
    )
    monkeypatch.setattr(
        backtest,
        "get_backtest_result",
        lambda client, backtest_id: {"id": backtest_id, "data": {"state": "1", "message": "failed"}},
    )
    monkeypatch.setattr(
        backtest,
        "get_backtest_logs",
        lambda client, backtest_id, error=False: {"id": backtest_id, "kind": "error", "logs": ["Traceback"]},
    )
    monkeypatch.setattr(backtest.time, "sleep", lambda seconds: None)

    payload = backtest.wait_for_backtest(object(), "bt1", timeout=60, poll_interval=5)

    assert payload["status"] == "done"
    assert payload["resolved_id"] == "detail-id"


def test_wait_for_backtest_ignores_early_failed_result_state_when_list_is_running(monkeypatch):
    from jqcli.commands import backtest

    list_items = iter([
        {"id": "detail-id", "list_id": "list-id", "status": "running"},
        {"id": "detail-id", "list_id": "list-id", "status": "done"},
    ])

    def fake_stats(client, backtest_id):
        if backtest_id == "detail-id":
            return {"id": backtest_id, "resolved_id": backtest_id, "metrics": {"annual_algo_return": 0.3, "sharpe": 1.2}}
        return {"id": backtest_id, "metrics": []}

    monkeypatch.setattr(backtest, "get_backtest_stats", fake_stats)
    monkeypatch.setattr(backtest, "get_backtest", lambda client, backtest_id: {"id": backtest_id, "status": "running"})
    monkeypatch.setattr(
        backtest,
        "find_backtest_list_item",
        lambda client, backtest_id, strategy_id, compile_only, list_id=None: next(list_items),
    )
    monkeypatch.setattr(
        backtest,
        "get_backtest_result",
        lambda client, backtest_id: {"id": backtest_id, "data": {"state": "1", "result": {"count": 0}}},
    )
    monkeypatch.setattr(backtest.time, "sleep", lambda seconds: None)

    payload = backtest.wait_for_backtest(
        object(),
        "list-id",
        timeout=60,
        poll_interval=5,
        strategy_id="s1",
    )

    assert payload["status"] == "done"
    assert payload["resolved_id"] == "detail-id"
    assert payload["metrics"]["sharpe"] == 1.2
