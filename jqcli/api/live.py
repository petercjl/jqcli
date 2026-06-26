from __future__ import annotations

import re
from typing import Any

from jqcli.errors import ApiError

from .client import ApiClient


STATUS_MAP = {"1": "running", "2": "stopped"}


def _require_ok(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ApiError("服务端返回格式错误")
    code = str(payload.get("code", ""))
    status = str(payload.get("status", ""))
    if code and code != "00000":
        raise ApiError(str(payload.get("msg") or "模拟交易接口请求失败"), details={"response": payload})
    if status and status not in {"0", ""}:
        raise ApiError(str(payload.get("msg") or "模拟交易接口请求失败"), details={"response": payload})
    return payload


def _normalize_live_item(item: dict[str, Any]) -> dict[str, Any]:
    raw_status = str(item.get("status", ""))
    space = item.get("spaceInfo") if isinstance(item.get("spaceInfo"), dict) else {}
    return {
        "id": item.get("backtestId"),
        "name": item.get("name"),
        "status": STATUS_MAP.get(raw_status, raw_status),
        "raw_status": raw_status,
        "frequency": item.get("frequency"),
        "capital": _number(item.get("baseCapital")),
        "start_time": item.get("startTime"),
        "end_time": item.get("endTime"),
        "overall_return": _number(item.get("overallReturn")),
        "year_return": _number(item.get("yearReturn")),
        "max_drawdown": _number(item.get("maxDrawdown")),
        "is_notice": item.get("isNotice"),
        "is_delay": item.get("isDelay"),
        "algorithm_id": item.get("algorithmId"),
        "source_backtest_id": item.get("sourceBacktestId"),
        "created_at": item.get("addTime"),
        "updated_at": item.get("modTime"),
        "cancel_time": item.get("cancelTime"),
        "py_version": item.get("pyVersion"),
        "space_id": space.get("backtestSpaceId"),
        "space_expire_time": space.get("expireTime"),
    }


def _number(value: Any) -> float | int | None:
    if value is None or value == "":
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number.is_integer():
        return int(number)
    return number


def list_live_trades(client: ApiClient, *, process: str = "running") -> dict[str, Any]:
    process_value = {"running": "1", "stopped": "0", "all": None}.get(process)
    if process_value is None and process != "all":
        raise ValueError(f"unsupported process: {process}")

    params = {} if process_value is None else {"process": process_value}
    payload = _require_ok(client.get("/algorithm/trade/list", params=params))
    data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
    items = [_normalize_live_item(item) for item in data.get("liveArr", []) if isinstance(item, dict)]
    return {
        "items": items,
        "process": process,
        "total_count": _number(data.get("totalCount")),
        "total_live_count": _number(data.get("totalLiveCount")),
        "remain_live_count": _number(data.get("remainLiveCount")),
        "is_bind_wechat": data.get("isBindWechat"),
        "has_client": data.get("hasClient"),
        "response": payload,
    }


def _normalize_position(item: dict[str, Any]) -> dict[str, Any]:
    stock = str(item.get("stock", ""))
    code = ""
    name = stock
    if "(" in stock and stock.endswith(")"):
        name, code = stock.rsplit("(", 1)
        code = code[:-1]
    return {
        "code": code,
        "name": name,
        "asset_type": item.get("security"),
        "side": item.get("side"),
        "amount": item.get("amount"),
        "closeable_amount": item.get("closeableAmount"),
        "price": _number(item.get("price")),
        "value": _number(item.get("value")),
        "gain": _number(item.get("gain")),
        "gain_percent": _number(item.get("gainPercent")),
        "gain_percent_text": item.get("gainPercentStr"),
        "avg_cost": _number(item.get("avgCost")),
        "daily_gains": _number(item.get("dailyGains")),
        "today_amount": item.get("todayAmount"),
        "weight": item.get("positionPersent"),
        "time": item.get("time"),
    }


def get_live_positions(
    client: ApiClient,
    live_id: str,
    *,
    date: str | None = None,
    is_forward: bool = True,
    limit: int = 50,
    field: str = "",
    order: str = "",
) -> dict[str, Any]:
    params: dict[str, Any] = {
        "limit": limit,
        "backtestId": live_id,
        "date": date or "",
        "isForward": "1" if is_forward else "0",
        "field": field,
        "order": order,
    }
    payload = _require_ok(client.get("/algorithm/live/position", params=params))
    data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
    positions = [_normalize_position(item) for item in data.get("position", []) if isinstance(item, dict)]
    return {
        "id": live_id,
        "date": date or "",
        "cash": _number(data.get("cash")),
        "total_value": _number(data.get("totalValue")),
        "position_count": len(positions),
        "positions": positions,
        "is_limit": data.get("isLimit"),
        "response": payload,
    }


def _normalize_log_line(line: str) -> dict[str, Any]:
    match = re.match(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) - ([A-Z]+)\s+- (.*)$", line, re.S)
    if not match:
        return {"raw": line, "time": None, "date": None, "level": None, "message": line}
    time_text, level, message = match.groups()
    return {
        "raw": line,
        "time": time_text,
        "date": time_text[:10],
        "level": level,
        "message": message,
    }


def _log_payload(client: ApiClient, live_id: str, *, offset: int, limit: int, add_log: bool) -> dict[str, Any]:
    params: dict[str, Any] = {"backtestId": live_id, "offset": offset}
    if add_log:
        params["addLog"] = "1"
        params["limit"] = limit
    payload = _require_ok(client.get("/algorithm/live/log", params=params))
    data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
    lines = [str(line) for line in data.get("logArr", [])]
    return {
        "id": live_id,
        "offset": _number(data.get("offset")),
        "state": data.get("state"),
        "logs": [_normalize_log_line(line) for line in lines],
        "response": payload,
    }


def get_live_logs(
    client: ApiClient,
    live_id: str,
    *,
    limit: int = 100,
    date: str | None = None,
    max_pages: int = 50,
) -> dict[str, Any]:
    if limit <= 0:
        raise ValueError("limit must be positive")
    page_size = min(max(limit, 1), 100)
    first_page = _log_payload(client, live_id, offset=-1, limit=page_size, add_log=False)
    pages = [first_page]

    if date:
        logs = [item for item in first_page["logs"] if item.get("date") == date]
        current_offset = int(first_page.get("offset") or 0)
        page_count = 1
        while page_count < max_pages and len(logs) < limit and current_offset > 0:
            dated = [item for item in pages[-1]["logs"] if item.get("date")]
            if dated and min(str(item["date"]) for item in dated) < date:
                break
            next_limit = min(page_size, current_offset)
            next_offset = max(0, current_offset - next_limit)
            page = _log_payload(client, live_id, offset=next_offset, limit=next_limit, add_log=True)
            pages.append(page)
            logs.extend(item for item in page["logs"] if item.get("date") == date)
            current_offset = next_offset
            page_count += 1
        logs = logs[-limit:]
    else:
        logs = first_page["logs"][-limit:]

    return {
        "id": live_id,
        "date": date,
        "limit": limit,
        "count": len(logs),
        "logs": logs,
        "offset": first_page.get("offset"),
        "state": first_page.get("state"),
        "pages_read": len(pages),
    }
