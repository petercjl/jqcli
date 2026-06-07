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
