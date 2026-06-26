from __future__ import annotations

from typing import TYPE_CHECKING, Any

import click
from rich.console import Console
from rich.table import Table

from jqcli.api.client import ApiClient
from jqcli.api.live import get_live_logs, get_live_positions, list_live_trades
from jqcli.errors import NotAuthenticatedError, UsageError
from jqcli.output import write_json

if TYPE_CHECKING:
    from jqcli.cli import AppContext


@click.group(name="live")
def live_group() -> None:
    """模拟交易。"""


def make_client(app: AppContext) -> ApiClient:
    if not (app.token or app.cookie):
        raise NotAuthenticatedError()
    return ApiClient(app.api_base, token=app.token, cookie=app.cookie, timeout=app.timeout)


def close_client(client: object) -> None:
    close = getattr(client, "close", None)
    if callable(close):
        close()


def render_live_table(payload: dict[str, Any]) -> None:
    table = Table()
    for name in ("ID", "名称", "状态", "频率", "资金", "开始时间", "微信通知"):
        table.add_column(name)
    for item in payload.get("items", []):
        table.add_row(
            str(item.get("id", "")),
            str(item.get("name", "")),
            str(item.get("status", "")),
            str(item.get("frequency", "")),
            str(item.get("capital", "")),
            str(item.get("start_time", "")),
            "是" if item.get("is_notice") else "否",
        )
    Console().print(table)


def render_positions_table(payload: dict[str, Any]) -> None:
    click.echo(f"总资产: {payload.get('total_value', '')}  现金: {payload.get('cash', '')}  持仓数: {payload.get('position_count', 0)}")
    table = Table()
    for name in ("代码", "名称", "方向", "数量", "可卖", "价格", "市值", "权重", "浮盈亏", "盈亏率"):
        table.add_column(name)
    for item in payload.get("positions", []):
        table.add_row(
            str(item.get("code", "")),
            str(item.get("name", "")),
            str(item.get("side", "")),
            str(item.get("amount", "")),
            str(item.get("closeable_amount", "")),
            str(item.get("price", "")),
            str(item.get("value", "")),
            str(item.get("weight", "")),
            str(item.get("gain", "")),
            str(item.get("gain_percent_text", "")),
        )
    Console().print(table)


def render_logs(payload: dict[str, Any]) -> None:
    for item in payload.get("logs", []):
        click.echo(str(item.get("raw", "")))


def resolve_live_id(client: ApiClient, live_id: str | None, name_filter: str | None) -> tuple[str, str | None]:
    if live_id:
        return live_id, None
    if not name_filter:
        raise UsageError("请提供 live_id，或使用 --name 按名称匹配")
    live_payload = list_live_trades(client, process="running")
    matches = [item for item in live_payload.get("items", []) if name_filter in str(item.get("name", ""))]
    if not matches:
        raise UsageError(f"没有找到名称包含 {name_filter!r} 的运行中模拟交易")
    if len(matches) > 1:
        names = ", ".join(str(item.get("name", "")) for item in matches)
        raise UsageError(f"名称匹配到多个运行中模拟交易，请改用 live_id：{names}")
    return str(matches[0].get("id", "")), matches[0].get("name")


@live_group.command("ls")
@click.option("--process", "process_filter", type=click.Choice(["running", "stopped", "all"]), default="running")
@click.pass_obj
def ls(app: AppContext, process_filter: str) -> None:
    client = make_client(app)
    try:
        payload = list_live_trades(client, process=process_filter)
    finally:
        close_client(client)
    if app.json_output:
        write_json(payload)
    else:
        render_live_table(payload)


@live_group.command("positions")
@click.argument("live_id", required=False)
@click.option("--name", "name_filter", help="按模拟交易名称模糊匹配；匹配到唯一项时读取该模拟持仓")
@click.option("--date", "position_date", help="持仓日期，默认读取页面当前/最新持仓")
@click.option("--limit", type=int, default=50, show_default=True)
@click.pass_obj
def positions(app: AppContext, live_id: str | None, name_filter: str | None, position_date: str | None, limit: int) -> None:
    client = make_client(app)
    try:
        live_id, selected_name = resolve_live_id(client, live_id, name_filter)
        payload = get_live_positions(client, str(live_id), date=position_date, limit=limit)
        if selected_name:
            payload["name"] = selected_name
    finally:
        close_client(client)
    if app.json_output:
        write_json(payload)
    else:
        if payload.get("name"):
            click.echo(f"模拟交易: {payload.get('name')}")
        render_positions_table(payload)


@live_group.command("logs")
@click.argument("live_id", required=False)
@click.option("--name", "name_filter", help="按模拟交易名称模糊匹配；匹配到唯一项时读取该模拟日志")
@click.option("--limit", type=int, default=100, show_default=True, help="最多返回日志条数")
@click.option("--date", "log_date", help="按日期读取日志，格式 YYYY-MM-DD")
@click.option("--max-pages", type=int, default=50, show_default=True, help="按日期查找时最多向前翻页数")
@click.pass_obj
def logs(app: AppContext, live_id: str | None, name_filter: str | None, limit: int, log_date: str | None, max_pages: int) -> None:
    client = make_client(app)
    try:
        live_id, selected_name = resolve_live_id(client, live_id, name_filter)
        payload = get_live_logs(client, str(live_id), limit=limit, date=log_date, max_pages=max_pages)
        if selected_name:
            payload["name"] = selected_name
    finally:
        close_client(client)
    if app.json_output:
        write_json(payload)
    else:
        if payload.get("name"):
            click.echo(f"模拟交易: {payload.get('name')}")
        render_logs(payload)
