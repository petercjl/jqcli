from __future__ import annotations

import sys

import click

from jqcli.api.auth import login_with_password
from jqcli.cli import AppContext, validate_api_base_for_credentials
from jqcli.config import resolve_login_credentials
from jqcli.errors import UsageError
from jqcli.output import write_json


@click.group(name="auth")
def auth_group() -> None:
    """认证管理。"""


@auth_group.command("status")
@click.pass_obj
def status(app: AppContext) -> None:
    authenticated = bool(app.token or app.cookie)
    payload = {
        "authenticated": authenticated,
        "api_base": app.api_base,
        "credential_source": "token" if app.token else "cookie" if app.cookie else None,
        "username": app.config.data.get("username"),
    }
    if app.json_output:
        write_json(payload)
    elif authenticated:
        click.echo("已配置认证凭据")
    else:
        click.echo("未登录")


@auth_group.command("logout")
@click.pass_obj
def logout(app: AppContext) -> None:
    app.config.data.pop("token", None)
    app.config.data.pop("cookie", None)
    app.config.data.pop("username", None)
    app.config.save()
    if app.json_output:
        write_json({"ok": True})
    elif not app.quiet:
        click.echo("已清除本地认证凭据")


@auth_group.command("import-token")
@click.option("--token", help="要保存的 token")
@click.option("--token-stdin", is_flag=True, help="从 stdin 读取 token，避免出现在进程参数中")
@click.pass_obj
def import_token(app: AppContext, token: str | None, token_stdin: bool) -> None:
    if token and token_stdin:
        raise UsageError("--token 与 --token-stdin 不可同时使用")
    token_value = sys.stdin.read().strip() if token_stdin else token
    if not token_value:
        raise UsageError("缺少 token，请传入 --token 或 --token-stdin")
    app.config.data["token"] = token_value
    app.config.data.pop("cookie", None)
    app.config.save()
    if app.json_output:
        write_json({"ok": True, "credential": "token"})
    elif not app.quiet:
        click.echo("token 已保存")


@auth_group.command("import-cookie")
@click.option("--cookie", help="要保存的 cookie")
@click.option("--cookie-stdin", is_flag=True, help="从 stdin 读取 cookie，避免出现在进程参数中")
@click.pass_obj
def import_cookie(app: AppContext, cookie: str | None, cookie_stdin: bool) -> None:
    if cookie and cookie_stdin:
        raise UsageError("--cookie 与 --cookie-stdin 不可同时使用")
    cookie_value = sys.stdin.read().strip() if cookie_stdin else cookie
    if not cookie_value:
        raise UsageError("缺少 cookie，请传入 --cookie 或 --cookie-stdin")
    app.config.data["cookie"] = cookie_value
    app.config.data.pop("token", None)
    app.config.save()
    if app.json_output:
        write_json({"ok": True, "credential": "cookie"})
    elif not app.quiet:
        click.echo("cookie 已保存")


@auth_group.command("login")
@click.option("--username", help="用户名；省略时读取 JQCLI_USERNAME")
@click.option("--password-stdin", is_flag=True, help="从 stdin 读取密码")
@click.pass_obj
def login(app: AppContext, username: str | None, password_stdin: bool) -> None:
    password = sys.stdin.read() if password_stdin else None
    username, password = resolve_login_credentials(username=username, password=password)
    if not username:
        raise UsageError("缺少用户名，请传入 --username 或在 env 文件中设置 JQCLI_USERNAME")
    if not password:
        raise UsageError("缺少密码，请传入 --password-stdin 或在 env 文件中设置 JQCLI_PASSWORD")
    validate_api_base_for_credentials(
        app.api_base,
        token=None,
        cookie=None,
        allow_custom_api_base=app.allow_custom_api_base,
        credential_label="用户名/密码",
        credential_present=True,
    )
    result = login_with_password(app.api_base, username, password, timeout=app.timeout)
    app.config.data["username"] = username
    app.config.data["cookie"] = result["cookie"]
    app.config.data.pop("password_login_pending", None)
    app.config.save()
    if app.json_output:
        write_json({"ok": True, "username": username, "credential": "cookie"})
    elif not app.quiet:
        click.echo("登录成功，cookie 已保存")
