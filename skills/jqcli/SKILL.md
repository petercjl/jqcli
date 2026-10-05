---
name: jqcli
description: Write, review and repair JoinQuant strategies, validate callbacks and API semantics, automatically create/update specified platform strategies, run and wait for backtests, read logs/metrics/positions/trades, export evidence and iterate. Use for 聚宽 strategy coding and automated backtest research.
---

# JoinQuant strategy lifecycle

## Input → strategy → output
Accept a strategy goal, existing source/error, exact target strategy and backtest parameters. Write complete JoinQuant code, validate it, perform user-authorized platform operations, retrieve attributable results and deliver an analysis with immutable source/export evidence. Writing strategy code is the Agent's responsibility; the CLI handles checks and platform calls.

## Discover and authenticate
Run `jqcli version`, `capabilities --json`, `doctor --json` and `skill source`; `setup` installs the bundled Python runtime. Select the adapter under `adapters/`. Node 22+ and Python 3.11+ required. Credentials/configuration are external; inspect `jqcli --format json auth status`. Read [api-workflows.md](references/api-workflows.md) only at the platform execution node. Do not print cookies/tokens or credentials in status output. Installation does not authenticate an account.

## Main line
1. **Select and write.** Classify new, modify, repair or migration; identify assets/frequency/universe/benchmark/date/capital. For writing or reviewing read [strategy-writing.md](references/strategy-writing.md). Use `strategy scaffold --name NAME --root DIR`; preserve user-owned existing source with a recoverable version. Write complete strategy.py and Chinese README recording rules/parameters/version and assumptions. Use global callbacks, initialize, real-price and future-data options where applicable; respect data shape, scheduling and order semantics. Logs include concise HUMAN and structured JQ_AUDIT metadata/signals.
2. **Check.** Run `strategy check --file SOURCE` (AST only, not platform execution). Resolve errors and inspect warnings. Verify no top-level orders/research-only APIs/future data. A local syntax/check pass is not a successful broker backtest.
3. **Upload and run.** Read the platform route, inspect existing target code and identity, then use `strategy new` or `strategy edit` only for the user's requested target/action. Use `backtest run ID --start --end --capital --freq --wait` when authorized; compile-only is optional. Do not opt into paid credits without explicit authorization. Save returned strategy/backtest IDs. On timeout use the existing run ID to inspect; do not create another run blindly.
4. **Retrieve and analyze.** Read logs and error state before metrics; use show/stats/result/positions/transactions, and `backtest export --mode all` to download the four Web artifacts and normalized UTF-8 evidence. Verify dates/capital/source metadata and coverage. New runs and source versions use fresh directories. Read [research.md](references/research.md) for diagnosing or designing a comparison; distinguish data, signal, execution and accounting differences.
5. **Iterate.** Repair errors within intent or create the agreed hypothesis/version. Append a dated README entry, retain evidence, return to step 1. For local/PTrade comparison resolve the exact advertised `tushare` or `ptradecli` Skill, read its complete current contract, hand over explicit source/parameters/IDs/files, execute its supported branch and return to this result analysis. Missing dependencies report DEPENDENCY_MISSING. Do not duplicate another platform's implementation.

## Recovery, QA and evolution
Authentication failure returns to account setup; do not loop requests or expose credentials. Unexpected data or stale identities stop the comparison and retain raw exports. Syntax/compile/runtime errors return to step 1 with exact trace. Repeated fixed failures belong in the checker/CLI tests; new API behavior needs authoritative docs or an isolated platform experiment. Delete and simulation/live operations are separately authorized, not a default research cleanup.

Knowledge mode is hybrid: bundled platform rules and accepted research workflow, with live response limitations preserved. At knowledge-dependent nodes read SCHEMA/index/recent log and only the current route. The bundled Skill is the canonical source; managed Agent installs are delivery targets. Current macOS command mechanics are verified independently from fresh-session Agent behavior; Windows/SealSeek runtime remains untested. Never infer publication or profitability from a passing local checker.

Knowledge is loaded on-demand only at the current node; later-node pages remain deferred.
