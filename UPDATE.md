# Update jqcli for your current Agent

Send this to the Agent you use:

> Update `@petercjl/jqcli` and its jqcli Skill for the Agent I am currently using.

Resolve the current host's exact Skill directory before running the update. The package updater acquires a registry candidate separately and activates it only for the selected target after checking ownership and local edits. It keeps a recoverable backup and returns the activated entry. Repeat the same version to reconcile missing managed files or stale receipts. A verified current target returns a no-op.

Use the activated entry to verify CLI and Python package identity and managed SHA-256 status. Reload the Skill through native host discovery. If installation is interrupted, inspect the exact target, backup and operation journal from the error receipt before retrying.

A 0.1.1 updater can hand off with its explicit `--agent` and `--target` options. The old npm-first command can replace its bootstrap package before Skill synchronization. If that happens, use the newly installed CLI to reconcile the explicitly selected target. Historical calls without a resolved Skill directory cannot complete the current lifecycle.

Ordinary strategy and backtest task entry checks the stable registry at most once per day after a successful check, with bounded timeout and a shorter offline backoff. Detection reports through stderr and installs only on explicit request. Set `JQCLI_UPDATE_CHECK=0` to disable detection.
