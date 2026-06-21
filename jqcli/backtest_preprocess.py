from __future__ import annotations

import csv
import html
import json
import re
import zipfile
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any


POSITION_COLUMNS = [
    "日期",
    "品种",
    "标的",
    "多空",
    "数量",
    "可用数量",
    "收盘价/结算价",
    "市值/价值",
    "盈亏/逐笔浮盈",
    "开仓均价",
    "持仓均价（期货）",
    "保证金",
    "当日盈亏",
    "今手数",
    "盈亏占比",
    "组合总值",
    "仓位占比",
]


def preprocess_backtest_exports(input_dir: Path, output_dir: Path, *, backtest_id: str | None = None) -> dict[str, Any]:
    input_dir = input_dir.expanduser().resolve()
    output_dir = output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    sources = _discover_sources(input_dir)
    diagnostics: dict[str, Any] = {
        "backtest_id": backtest_id,
        "input_dir": str(input_dir),
        "output_dir": str(output_dir),
        "sources": {name: str(path) for name, path in sources.items()},
        "warnings": [],
    }

    files: list[dict[str, Any]] = []
    result_summary: dict[str, Any] = {}
    transaction_summary: dict[str, Any] = {}
    position_summary: dict[str, Any] = {}
    log_summary: dict[str, Any] = {}

    if "result" in sources:
        result_summary, result_files = _preprocess_result(sources["result"], output_dir)
        files.extend(result_files)
    else:
        diagnostics["warnings"].append("missing result csv")

    if "transaction" in sources:
        transaction_summary, transaction_files = _preprocess_transaction(sources["transaction"], output_dir)
        files.extend(transaction_files)
    else:
        diagnostics["warnings"].append("missing transaction csv")

    if "position" in sources:
        position_summary, position_files = _preprocess_position(sources["position"], output_dir)
        files.extend(position_files)
    else:
        diagnostics["warnings"].append("missing position csv")

    if "log" in sources:
        log_summary, log_files = _preprocess_log(sources["log"], output_dir)
        files.extend(log_files)
    else:
        diagnostics["warnings"].append("missing log txt")

    diagnostics.update(
        {
            "result": result_summary,
            "transactions": transaction_summary,
            "positions": position_summary,
            "logs": log_summary,
        }
    )
    diagnostics_path = output_dir / "diagnostics.json"
    diagnostics_path.write_text(json.dumps(diagnostics, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    files.append(_file_info("diagnostics", diagnostics_path))

    summary = {
        "backtest_id": backtest_id,
        "input_dir": str(input_dir),
        "output_dir": str(output_dir),
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "files": files,
        "diagnostics": str(diagnostics_path),
        "warnings": diagnostics["warnings"],
    }
    summary_path = output_dir / "summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    files.append(_file_info("summary", summary_path))
    summary["files"] = files
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    return summary


def _discover_sources(input_dir: Path) -> dict[str, Path]:
    extracted_dir = input_dir / "_extracted"
    extracted_dir.mkdir(exist_ok=True)
    for archive in input_dir.glob("*.zip"):
        if archive.name.startswith("."):
            continue
        with zipfile.ZipFile(archive) as zf:
            for info in zf.infolist():
                if info.is_dir():
                    continue
                target = extracted_dir / Path(info.filename).name
                target.write_bytes(zf.read(info))

    files = list(input_dir.glob("*")) + list(extracted_dir.glob("*"))
    sources: dict[str, Path] = {}
    for path in files:
        lower = path.name.lower()
        if path.is_file() and lower.startswith("result") and lower.endswith(".csv"):
            sources.setdefault("result", path)
        elif path.is_file() and lower == "transaction.csv":
            sources.setdefault("transaction", path)
        elif path.is_file() and lower == "position.csv":
            sources.setdefault("position", path)
        elif path.is_file() and lower == "log.txt":
            sources.setdefault("log", path)
    return sources


def _preprocess_result(path: Path, output_dir: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    rows = _read_csv_dicts(path)
    normalized: list[dict[str, Any]] = []
    previous_strategy: float | None = None
    previous_benchmark: float | None = None
    for row in rows:
        strategy = _number(row.get("策略收益"))
        benchmark = _number(row.get("基准收益"))
        normalized.append(
            {
                "datetime": row.get("时间", ""),
                "date": str(row.get("时间", ""))[:10],
                "benchmark_return_pct": benchmark,
                "strategy_return_pct": strategy,
                "daily_strategy_return_pct": _return_delta(previous_strategy, strategy),
                "daily_benchmark_return_pct": _return_delta(previous_benchmark, benchmark),
                "daily_profit": _number(row.get("当日盈利")),
                "daily_loss": _number(row.get("当日亏损")),
                "daily_buy": _number(row.get("当日买入")),
                "daily_sell": _number(row.get("当日卖出")),
                "excess_return_pct": _number(row.get("超额收益(%)")),
            }
        )
        previous_strategy = strategy
        previous_benchmark = benchmark
    output = output_dir / "result.normalized.csv"
    _write_csv(output, normalized)
    summary = {}
    if normalized:
        last = normalized[-1]
        min_row = min(normalized, key=lambda item: item["strategy_return_pct"] if item["strategy_return_pct"] is not None else 0)
        summary = {
            "rows": len(normalized),
            "start_date": normalized[0]["date"],
            "end_date": last["date"],
            "final_strategy_return_pct": last["strategy_return_pct"],
            "final_benchmark_return_pct": last["benchmark_return_pct"],
            "min_strategy_return_pct": min_row["strategy_return_pct"],
            "min_strategy_return_date": min_row["date"],
        }
    return summary, [_file_info("result_normalized", output)]


def _preprocess_transaction(path: Path, output_dir: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    rows = _read_csv_dicts(path)
    normalized = []
    status_counts: Counter[str] = Counter()
    side_counts: Counter[str] = Counter()
    yearly = defaultdict(lambda: {"rows": 0, "buy_turnover": 0.0, "sell_turnover": 0.0, "gross_turnover": 0.0, "fees": 0.0, "cancelled": 0})
    for row in rows:
        name, code = _split_security(row.get("标的", ""))
        side = str(row.get("交易类型", ""))
        filled_value = _number(row.get("成交额")) or 0.0
        fee = _number(row.get("手续费")) or 0.0
        status = str(row.get("状态", ""))
        date_value = str(row.get("日期", ""))
        year = date_value[:4]
        item = {
            "date": date_value,
            "order_time": row.get("委托时间", ""),
            "asset_type": row.get("品种", ""),
            "security_name": name,
            "code": code,
            "side": side,
            "order_type": row.get("下单类型", ""),
            "filled_amount": _share_amount(row.get("成交数量")),
            "filled_price": _number(row.get("成交价")),
            "filled_value": filled_value,
            "ordered_amount": _share_amount(row.get("委托数量")),
            "order_price": _number(row.get("委托价格")),
            "close_pnl": _number(row.get("平仓盈亏")),
            "fee": fee,
            "status": status,
            "is_cancelled": status == "已撤单",
            "last_update": row.get("最后更新时间", ""),
        }
        normalized.append(item)
        status_counts[status] += 1
        side_counts[side] += 1
        y = yearly[year]
        y["rows"] += 1
        y["fees"] += abs(fee)
        if status == "已撤单":
            y["cancelled"] += 1
        if side == "买":
            y["buy_turnover"] += abs(filled_value)
        elif side == "卖":
            y["sell_turnover"] += abs(filled_value)
        y["gross_turnover"] += abs(filled_value)
    output = output_dir / "transactions.normalized.csv"
    _write_csv(output, normalized)
    summary = {
        "rows": len(normalized),
        "status_counts": dict(status_counts),
        "side_counts": dict(side_counts),
        "cancelled": status_counts.get("已撤单", 0),
        "buy_turnover": round(sum(item["buy_turnover"] for item in yearly.values()), 2),
        "sell_turnover": round(sum(item["sell_turnover"] for item in yearly.values()), 2),
        "gross_turnover": round(sum(item["gross_turnover"] for item in yearly.values()), 2),
        "fees": round(sum(item["fees"] for item in yearly.values()), 2),
        "by_year": {year: _round_dict(values) for year, values in sorted(yearly.items())},
    }
    return summary, [_file_info("transactions_normalized", output)]


def _preprocess_position(path: Path, output_dir: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    rows = _read_csv_rows(path)
    if rows:
        rows = rows[1:]
    normalized = []
    count_by_date: Counter[str] = Counter()
    max_weight_by_date: dict[str, float] = {}
    for raw in rows:
        values = _align_position_row(raw)
        row = dict(zip(POSITION_COLUMNS, values, strict=False))
        name, code = _split_security(row.get("标的", ""))
        date_value = str(row.get("日期", ""))
        weight = _number(row.get("仓位占比"))
        item = {
            "date": date_value,
            "asset_type": row.get("品种", ""),
            "security_name": name,
            "code": code,
            "side": row.get("多空", ""),
            "amount": _share_amount(row.get("数量")),
            "available_amount": _share_amount(row.get("可用数量")),
            "close_price": _number(row.get("收盘价/结算价")),
            "market_value": _number(row.get("市值/价值")),
            "floating_pnl": _number(row.get("盈亏/逐笔浮盈")),
            "open_cost": _number(row.get("开仓均价")),
            "position_cost": _number(row.get("持仓均价（期货）")),
            "margin": _number(row.get("保证金")),
            "daily_pnl": _number(row.get("当日盈亏")),
            "today_amount": _share_amount(row.get("今手数")),
            "pnl_pct": _number(row.get("盈亏占比")),
            "portfolio_value": _number(row.get("组合总值")),
            "weight_pct": weight,
        }
        normalized.append(item)
        if code:
            count_by_date[date_value] += 1
            if weight is not None:
                max_weight_by_date[date_value] = max(max_weight_by_date.get(date_value, 0.0), weight)
    output = output_dir / "positions.normalized.csv"
    _write_csv(output, normalized)
    summary = {
        "rows": len(normalized),
        "stock_position_rows": sum(1 for item in normalized if item["code"]),
        "days_with_positions": len(count_by_date),
        "avg_position_count": round(sum(count_by_date.values()) / len(count_by_date), 2) if count_by_date else 0,
        "min_position_count": min(count_by_date.values()) if count_by_date else 0,
        "max_position_count": max(count_by_date.values()) if count_by_date else 0,
        "avg_max_single_weight_pct": round(sum(max_weight_by_date.values()) / len(max_weight_by_date), 2) if max_weight_by_date else 0,
        "max_single_weight_pct": round(max(max_weight_by_date.values()), 2) if max_weight_by_date else 0,
    }
    return summary, [_file_info("positions_normalized", output)]


def _preprocess_log(path: Path, output_dir: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    audit_path = output_dir / "logs.audit.jsonl"
    human_path = output_dir / "logs.human.txt"
    raw_path = output_dir / "logs.raw.txt"
    event_counts: Counter[str] = Counter()
    lines = _read_text_lines(path)
    audit_count = 0
    human_count = 0
    with audit_path.open("w", encoding="utf-8", newline="\n") as audit_out, human_path.open("w", encoding="utf-8", newline="\n") as human_out:
        for line in lines:
            if "JQ_AUDIT|" in line:
                payload = html.unescape(line.split("JQ_AUDIT|", 1)[1].strip())
                try:
                    item = json.loads(payload)
                except json.JSONDecodeError:
                    item = {"parse_error": True, "raw": payload}
                event = item.get("event")
                if event:
                    event_counts[str(event)] += 1
                audit_out.write(json.dumps(item, ensure_ascii=False, sort_keys=True, default=str) + "\n")
                audit_count += 1
            if "HUMAN|" in line:
                human_out.write(line.split("HUMAN|", 1)[1])
                human_out.write("\n" if not line.endswith("\n") else "")
                human_count += 1
    raw_path.write_text("".join(lines), encoding="utf-8")
    summary = {
        "lines": len(lines),
        "audit_lines": audit_count,
        "human_lines": human_count,
        "event_counts": dict(event_counts),
    }
    return summary, [_file_info("logs_audit", audit_path), _file_info("logs_human", human_path), _file_info("logs_raw", raw_path)]


def _read_csv_rows(path: Path) -> list[list[str]]:
    with path.open("r", encoding="gbk", errors="replace", newline="") as handle:
        return list(csv.reader(handle))


def _read_csv_dicts(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="gbk", errors="replace", newline="") as handle:
        return list(csv.DictReader(handle))


def _read_text_lines(path: Path) -> list[str]:
    for encoding in ("utf-8", "gbk"):
        try:
            return path.read_text(encoding=encoding).splitlines(True)
        except UnicodeDecodeError:
            continue
    return path.read_text(encoding="utf-8", errors="replace").splitlines(True)


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _align_position_row(row: list[str]) -> list[str]:
    if len(row) == len(POSITION_COLUMNS):
        return row
    if len(row) == len(POSITION_COLUMNS) - 1:
        return row[:-1] + [""] + row[-1:]
    if len(row) < len(POSITION_COLUMNS):
        return row + [""] * (len(POSITION_COLUMNS) - len(row))
    return row[: len(POSITION_COLUMNS)]


def _number(value: object) -> float | None:
    if value is None:
        return None
    text = str(value).strip().replace(",", "")
    if not text or text in {"--", "-"}:
        return None
    text = text.replace("%", "")
    negative = False
    if text.startswith("(") and text.endswith(")"):
        negative = True
        text = text[1:-1]
    try:
        number = float(text)
    except ValueError:
        return None
    return -number if negative else number


def _share_amount(value: object) -> int | None:
    number = _number(str(value).replace("股", ""))
    return int(number) if number is not None else None


def _split_security(value: str) -> tuple[str, str]:
    text = str(value or "")
    match = re.match(r"^(.*)\(([^()]+)\)$", text)
    if match:
        return match.group(1), match.group(2)
    return text, ""


def _return_delta(previous_pct: float | None, current_pct: float | None) -> float | None:
    if current_pct is None:
        return None
    if previous_pct is None:
        return current_pct
    previous_value = 1 + previous_pct / 100
    if previous_value == 0:
        return None
    return round(((1 + current_pct / 100) / previous_value - 1) * 100, 6)


def _round_dict(values: dict[str, Any]) -> dict[str, Any]:
    output = {}
    for key, value in values.items():
        output[key] = round(value, 2) if isinstance(value, float) else value
    return output


def _file_info(kind: str, path: Path) -> dict[str, Any]:
    return {"kind": kind, "path": str(path), "size": path.stat().st_size}
