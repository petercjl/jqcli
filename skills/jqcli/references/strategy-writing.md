# JoinQuant Strategy Rules

## Runtime Model

- Backtest engine defaults to Python 3.6 in the clipped JoinQuant API document. Write Python 3-compatible code and avoid syntax that may exceed Python 3.6.
- The platform limits filesystem, CPU, memory, stack, timeout, and bandwidth. Do not rely on arbitrary local files or long network operations.
- Strategy code is loaded dynamically. Top-level code executes at load time, so keep top-level code to imports and constants.
- `initialize(context)` runs once at strategy start. In simulation, replacing code does not rerun `initialize`; use `after_code_changed(context)` or `process_initialize(context)` for simulation-specific state repairs.
- `g` and `context` are persisted in simulation. Objects that cannot be serialized, such as query objects, file handles, and network connections, should not be stored in persistent `g` fields.

## Imports

Recommended:

```python
from jqdata import *
import pandas as pd
import numpy as np
import datetime
```

Use `jqfactor` or `jqlib` only when the strategy explicitly needs documented factor or optimizer functionality.

Avoid unverified packages such as `talib`, `sklearn`, `statsmodels`, `requests`, or local project modules unless the user confirms they exist in JoinQuant.

After `from jqdata import *`, some ordinary-looking names can be shadowed by JoinQuant/query helpers. In platform logs, a naked `sum(targets.values())` produced `TypeError: unsupported operand type(s) for *: 'dict_values' and 'int'` because `sum` did not behave like Python's built-in sum. For strategy code, prefer small local helpers such as:

```python
def safe_sum(values):
    total = 0
    for value in values:
        total += value
    return total
```

Use `safe_sum(...)` for lists, pandas slices converted to lists, and `dict.values()` in trading logic.

## Strategy Structure

- Define `initialize(context)`.
- Register scheduled global functions with `run_daily`, `run_weekly`, or `run_monthly`.
- Scheduled callbacks accept exactly one argument: `context`.
- Prefer `run_daily` over `handle_data` for normal daily/minute scheduled trading.
- Avoid using `run_daily` and `handle_data` in the same strategy unless the requested design needs both.
- Never call `run_daily(handle_data, ...)`.

## Logging Contract

Use two log streams inside JoinQuant's normal `log.info` output:

- `HUMAN|...`: Chinese, concise, for the user to read in the platform log.
- `JQ_AUDIT|{json}`: machine-readable JSON for local validation after downloading logs.

For signal decisions, `JQ_AUDIT` should include:

- `event`: for example `signal`
- `dt`
- `security`
- signal inputs such as price, moving average, factor score, or threshold
- `position_before`
- `action`
- `order_sent`
- `reason`
- `rule`

For daily state, include cash and position fields. Keep JSON values simple: strings, numbers, booleans, and nulls.

For multi-version experiments, emit a `strategy_metadata` audit event in `initialize` before scheduling callbacks. It should include `strategy_code`, `strategy_name`, `strategy_file`, `strategy_version`, `strategy_role`, and `description`. When comparing logs, first validate that this metadata matches the intended script.

## Local Strategy Workspace

Every strategy should live in its own project-local folder:

```text
strategies/<strategy_name>/
```

Default contents:

- `strategy.py`: the JoinQuant copy/paste script.
- `README.md`: Chinese strategy memory and optimization log.
- `data/`: local input data, clearly marked if it must be uploaded to JoinQuant Research.
- `notes/`: user notes, community snippets, or translation notes.
- `results/`: copied backtest metrics, screenshots, or exports.
- `research/`: original community code, pseudo-code, or research material.

Do not scatter strategy variants across the project root. If a user provides a loose file or pasted code, create or identify a strategy folder first, then place the maintained script there.

README is mandatory because these strategies are intentionally lightweight and may not deserve separate Git branches/issues. Write README content in Chinese by default. Use README to record decisions, parameter changes, validation results, and backtest observations.

## Essential Options

In `initialize(context)`, stock strategies should normally include:

```python
set_option('use_real_price', True)
set_option('avoid_future_data', True)
```

`use_real_price=True` reduces future-function risk from static forward-adjusted prices. Do not cache data API results across dates after enabling it.

`avoid_future_data=True` asks JoinQuant to enforce future-data avoidance. It may expose hidden issues; prefer fixing the strategy instead of disabling it.

## Data APIs

Use `attribute_history(security, count, unit, fields, ...)` for one security. Daily data excludes the current day even after close; minute data excludes the current minute.

Use `history(count, unit, field, security_list, ...)` for one field across multiple securities. If performance matters, `df=False` returns dict/arrays.

Use `get_price` when explicit date ranges, count/end_date, or multiple fields are needed. For multi-security calls, pass `panel=False` to avoid pandas Panel compatibility issues.

Do not pass an `end_date` later than `context.current_dt`.

Remember common field names:

- price fields: `open`, `close`, `high`, `low`, `avg`, `pre_close`
- trading fields: `volume`, `money`, `paused`
- limit fields: `high_limit`, `low_limit`
- adjustment: `factor`

## Trading APIs

Prefer:

- `order_target_value(security, value)` for target cash allocation.
- `order_target(security, amount)` for final share/contract amount.
- `order_value(security, value)` for one-time buy/sell value.

Check holdings through `context.portfolio.positions`.

Before sending a clear-position order such as `order_target_value(security, 0)` or `order_target(security, 0)`, check that the current position is non-zero. JoinQuant may report `下单失败，初步检查下单数量为0` when a strategy tries to clear an already-empty position.

Before repeating a target-value buy order for a position that is already near target, check the current position first. Small target adjustments can become less than one A-share board lot and JoinQuant may reject them with `开仓数量不能小于 100`. For simple on/off strategies, only call the buy target order when current position amount is zero.

When reading a position for logging or order guards, prefer:

```python
if security in context.portfolio.positions:
    amount = context.portfolio.positions[security].total_amount
else:
    amount = 0
```

Directly reading `context.portfolio.positions[security]` while the security is absent may produce platform warnings.

For A-shares, buy quantities normally follow board-lot constraints; selling all remaining shares is allowed by platform rules.

## Environment Boundaries

Backtest/simulation strategy code should not use research-only APIs such as:

- `create_backtest`
- `get_backtest`

`read_file` and `write_file` work with JoinQuant private/research files, not the user's local machine. If a strategy needs external CSV/JSON, the user must upload it to JoinQuant Research first.

## Common Failure Modes

- Missing `from jqdata import *` causes API names to be undefined.
- Scheduled callback has wrong signature or is a class instance method.
- `history`/`attribute_history` daily data expected to include today, but it does not.
- Multi-security `get_price` returns Panel unless `panel=False`.
- Storing `query(...)` in `g` breaks simulation persistence; initialize it in `process_initialize` with a `g.__name` field.
- `run_daily` time uses `reference_security` incorrectly; when `time` is a concrete clock time, do not set `reference_security`.
- Platform order rejection may happen for paused securities, limit-up/down, zero volume, or insufficient cash/position.
- `下单失败，初步检查下单数量为0` can happen when calling a clear-position target order while the account already has no position. Guard with `if context.portfolio.positions[security].total_amount > 0`.
- `开仓数量不能小于 100` can happen when repeatedly calling `order_target_value` while already close to target; skip the order when the strategy is already in the intended holding state.
- `TypeError: unsupported operand type(s) for *: 'dict_values' and 'int'` can happen when naked `sum()` has been shadowed after `from jqdata import *`. Replace naked `sum(...)` with a local helper such as `safe_sum(...)`.
- `科创板市价单需要指定保护限价` can happen for `688*.XSHG` stocks when using market `order_target_value`. For simple A-share experiments that do not specifically study STAR Market execution, filter out `688` stocks. If STAR Market stocks must be traded, use documented limit order styles and protection prices.

## Local Validation

Run:

```bash
python3 -m py_compile strategy.py
jqcli strategy check --file strategy.py
```
