# Install jqcli for your current Agent

Send this to the Agent you use:

> Install `@petercjl/jqcli` and its jqcli Skill for the Agent I am currently using.

The Agent needs terminal and local file access, Node.js 22+, Python 3.11+ with pip, and a native Skill discovery directory. Installing from npm provides a bootstrap CLI. The Agent resolves its own exact Skill directory and runs the package's managed installer with that absolute destination and its Agent name. The installer copies the canonical Skill and installs a target-owned CLI and Python dependency set. A system Python interpreter remains a prerequisite. The same handoff applies when npm install scripts are disabled.

Verify the installed CLI entry and Python version using the receipt, check the exact Skill target and SHA-256 status, then load the installed Skill through the host's discovery mechanism. The host verifies discovery separately. An unmanaged target or local edit requires review before adoption. Keep the backup path from the receipt.

Developer entry points are discoverable with `jqcli capabilities --json` and `jqcli skill source --json`. Run the receipt's `entry` via Node for ordinary work. Local credentials stay in the existing JoinQuant configuration and installation does not sign in or grant trading authority.
