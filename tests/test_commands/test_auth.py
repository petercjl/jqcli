import json

from click.testing import CliRunner

from jqcli.cli import main


def test_auth_status_json_without_credentials(tmp_path):
    result = CliRunner().invoke(main, ["--config", str(tmp_path / "c.json"), "--format", "json", "auth", "status"])

    assert result.exit_code == 0
    assert json.loads(result.output)["authenticated"] is False


def test_import_token_and_status(tmp_path):
    config = tmp_path / "config.json"
    runner = CliRunner()

    imported = runner.invoke(main, ["--config", str(config), "--format", "json", "auth", "import-token", "--token", "abc"])
    status = runner.invoke(main, ["--config", str(config), "--format", "json", "auth", "status"])

    assert imported.exit_code == 0
    assert json.loads(imported.output) == {"ok": True, "credential": "token"}
    assert json.loads(status.output)["authenticated"] is True
    assert json.loads(status.output)["credential_source"] == "token"


def test_import_cookie_from_stdin(tmp_path):
    config = tmp_path / "config.json"
    runner = CliRunner()

    imported = runner.invoke(
        main,
        ["--config", str(config), "--format", "json", "auth", "import-cookie", "--cookie-stdin"],
        input="sid=abc",
    )
    status = runner.invoke(main, ["--config", str(config), "--format", "json", "auth", "status"])

    assert imported.exit_code == 0
    assert json.loads(imported.output) == {"ok": True, "credential": "cookie"}
    assert json.loads(status.output)["credential_source"] == "cookie"


def test_import_token_requires_value(tmp_path):
    result = CliRunner().invoke(
        main,
        ["--config", str(tmp_path / "config.json"), "--format", "json", "auth", "import-token"],
    )

    assert result.exit_code == 3
    assert json.loads(result.stderr)["error"]["code"] == "usage_error"


def test_logout_clears_config_credentials(tmp_path):
    config = tmp_path / "config.json"
    runner = CliRunner()
    runner.invoke(main, ["--config", str(config), "auth", "import-token", "--token", "abc"])

    result = runner.invoke(main, ["--config", str(config), "--format", "json", "auth", "logout"])
    status = runner.invoke(main, ["--config", str(config), "--format", "json", "auth", "status"])

    assert result.exit_code == 0
    assert json.loads(status.output)["authenticated"] is False


def test_login_requires_password_or_env(tmp_path):
    result = CliRunner().invoke(
        main,
        [
            "--config",
            str(tmp_path / "c.json"),
            "--env-file",
            str(tmp_path / "missing.env"),
            "--format",
            "json",
            "auth",
            "login",
            "--username",
            "u",
        ],
    )

    assert result.exit_code == 3
    assert json.loads(result.stderr)["error"]["code"] == "usage_error"


def test_login_reads_password_stdin(monkeypatch, tmp_path):
    def fake_login(api_base, username, password, timeout=30):
        return {"payload": {"code": "00000"}, "cookie": "sid=abc"}

    monkeypatch.setattr("jqcli.commands.auth.login_with_password", fake_login)

    result = CliRunner().invoke(
        main,
        [
            "--config",
            str(tmp_path / "c.json"),
            "--format",
            "json",
            "auth",
            "login",
            "--username",
            "u",
            "--password-stdin",
        ],
        input="secret",
    )

    assert result.exit_code == 0
    assert json.loads(result.output)["ok"] is True


def test_login_rejects_password_with_custom_api_base(monkeypatch, tmp_path):
    def fake_login(api_base, username, password, timeout=30):
        raise AssertionError("login should not be called")

    monkeypatch.setattr("jqcli.commands.auth.login_with_password", fake_login)

    result = CliRunner().invoke(
        main,
        [
            "--config",
            str(tmp_path / "c.json"),
            "--api-base",
            "https://evil.example",
            "--format",
            "json",
            "auth",
            "login",
            "--username",
            "u",
            "--password-stdin",
        ],
        input="secret",
    )

    assert result.exit_code == 3
    assert "用户名/密码" in json.loads(result.stderr)["error"]["message"]


def test_login_allows_explicit_custom_api_base(monkeypatch, tmp_path):
    seen = {}

    def fake_login(api_base, username, password, timeout=30):
        seen["api_base"] = api_base
        return {"payload": {"code": "00000"}, "cookie": "sid=abc"}

    monkeypatch.setattr("jqcli.commands.auth.login_with_password", fake_login)

    result = CliRunner().invoke(
        main,
        [
            "--config",
            str(tmp_path / "c.json"),
            "--api-base",
            "https://proxy.example",
            "--allow-custom-api-base",
            "--format",
            "json",
            "auth",
            "login",
            "--username",
            "u",
            "--password-stdin",
        ],
        input="secret",
    )

    assert result.exit_code == 0
    assert seen["api_base"] == "https://proxy.example"


def test_login_reads_username_and_password_from_env_file(monkeypatch, tmp_path):
    def fake_login(api_base, username, password, timeout=30):
        return {"payload": {"code": "00000"}, "cookie": "sid=abc"}

    monkeypatch.setattr("jqcli.commands.auth.login_with_password", fake_login)
    env_file = tmp_path / ".env"
    config = tmp_path / "c.json"
    env_file.write_text('JQCLI_USERNAME="u@example.com"\nJQCLI_PASSWORD="secret"\n', encoding="utf-8")

    result = CliRunner().invoke(
        main,
        [
            "--config",
            str(config),
            "--env-file",
            str(env_file),
            "--format",
            "json",
            "auth",
            "login",
        ],
    )

    assert result.exit_code == 0
    assert json.loads(result.output)["username"] == "u@example.com"


def test_auth_status_reads_token_from_env_file(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("JQCLI_TOKEN=from-env-file\n", encoding="utf-8")

    result = CliRunner().invoke(
        main,
        ["--config", str(tmp_path / "c.json"), "--env-file", str(env_file), "--format", "json", "auth", "status"],
    )

    assert result.exit_code == 0
    assert json.loads(result.output)["authenticated"] is True
