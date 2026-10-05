# @petercjl/jqcli

CLI + bundled portable Skill for JoinQuant strategy authorship, checks and automated historical backtests.

Node.js 22+ and Python 3.11+ required. macOS command tests are exercised; Windows/NAS and fresh-session Agent parity are unverified.

```sh
npm install -g @petercjl/jqcli
jqcli setup
jqcli skill install --agent codex
jqcli doctor --json
```

Existing unmanaged Skills require reviewed `--adopt`, which creates a recoverable backup. Credentials, data and results stay outside the package. Installation grants no service permissions. Use `update check --tag latest`, then `update install --version EXACT --agent codex` to update runtime and Skill. Run `skill source/status` to verify the canonical source and managed install.

Use strategy scaffold/check for local source, strategy new/edit for user-authorized platform upload, and backtest run --wait followed by logs/stats/positions/transactions/export for evidence. Do not opt into paid credits or real/simulated orders without explicit authorization. Account setup is external.
