# jqcli API Workflows

## Local Tests

Run all tests:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Run API-only tests:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_api -q
```

## Read-Only Live Smoke Check

Use this before live write checks:

```powershell
.\codex-skill\jqcli\scripts\smoke_readonly.ps1
```

It checks:

- `auth status`
- `community latest`
- `community detail`
- `strategy ls`
- if available, `strategy show`
- if available, `backtest ls/show/stats/result/logs`
- `community clone-strategy` in non-executing check mode when a post with a backtest is found

## Write Live Smoke Check

Run only with user approval:

```powershell
.\codex-skill\jqcli\scripts\smoke_write_compile.ps1
```

It creates a temporary strategy named `jqcli_skill_smoke_<timestamp>`, edits it, runs a compile-only backtest, reads result/logs, deletes the compile record, and deletes the temporary strategy.

## Useful Direct Commands

Authentication:

```powershell
.\.venv\Scripts\jqcli.exe --format json --non-interactive auth status
.\.venv\Scripts\jqcli.exe --env-file .env --format json --non-interactive auth login
```

Community:

```powershell
.\.venv\Scripts\jqcli.exe --format json --non-interactive community latest --page-size 3 --max-pages 1
.\.venv\Scripts\jqcli.exe --format json --non-interactive community detail <post_id> --reply-pages 1
```

Strategies:

```powershell
.\.venv\Scripts\jqcli.exe --format json --non-interactive strategy ls --limit 3
.\.venv\Scripts\jqcli.exe --format json --non-interactive strategy show <strategy_id>
```

Backtests:

```powershell
.\.venv\Scripts\jqcli.exe --format json --non-interactive backtest ls <strategy_id> --limit 3
.\.venv\Scripts\jqcli.exe --format json --non-interactive backtest show <backtest_id>
.\.venv\Scripts\jqcli.exe --format json --non-interactive backtest stats <backtest_id>
.\.venv\Scripts\jqcli.exe --format json --non-interactive backtest result <backtest_id>
.\.venv\Scripts\jqcli.exe --format json --non-interactive backtest logs <backtest_id> --offset 0
```

Backtest web export files:

Use this when the user asks for the four downloadable files from the JoinQuant backtest detail page's `导出` menu. Do not substitute `backtest result` or `backtest logs`; those are lower-level JSON/log endpoints and are not the same as the web UI export artifacts.

```powershell
.\.venv\Scripts\jqcli.exe --format json --non-interactive backtest export <backtest_id> --kind all --output-dir <output_dir>
```

For strategy analysis, download and preprocess in one step:

```powershell
.\.venv\Scripts\jqcli.exe --format json --non-interactive backtest export <backtest_id> --kind all --mode all --output-dir <output_dir>
```

To preprocess a directory that already contains the four downloaded artifacts:

```powershell
.\.venv\Scripts\jqcli.exe --format json --non-interactive backtest export <backtest_id> --mode preprocess --output-dir <output_dir>
```

Single-file variants:

```powershell
.\.venv\Scripts\jqcli.exe --format json --non-interactive backtest export <backtest_id> --kind result --output-dir <output_dir>
.\.venv\Scripts\jqcli.exe --format json --non-interactive backtest export <backtest_id> --kind transaction --output-dir <output_dir>
.\.venv\Scripts\jqcli.exe --format json --non-interactive backtest export <backtest_id> --kind position --output-dir <output_dir>
.\.venv\Scripts\jqcli.exe --format json --non-interactive backtest export <backtest_id> --kind log --output-dir <output_dir>
```

Artifact mapping:

- `result`: downloads `result_*.csv`, matching `收益概述`.
- `transaction`: downloads `transaction.zip`, containing `transaction.csv`, matching `交易详情`.
- `position`: downloads `position.zip`, containing `position.csv`, matching `持仓&收益`.
- `log`: downloads `log.zip`, containing `log.txt`, matching `日志`.

Preprocess outputs under `<output_dir>/clean` by default:

- `result.normalized.csv`: UTF-8 cumulative and daily return fields.
- `transactions.normalized.csv`: parsed security code/name, side, amounts, prices, fees, status, and cancellation flag.
- `positions.normalized.csv`: parsed position rows with fixed headers, portfolio value, and weight fields.
- `logs.audit.jsonl`: parsed `JQ_AUDIT|` events as JSONL.
- `logs.human.txt`: extracted `HUMAN|` lines.
- `diagnostics.json`: rows, turnover, fees, cancellations, position concentration, and log event counts.

Implementation note for maintainers: `result` uses `/algorithm/backtest/export`; the other three use `/algorithm/backtest/addExportZip`, poll `/algorithm/backtest/getExportStatus`, then download `/algorithm/backtest/getExportZip`.
