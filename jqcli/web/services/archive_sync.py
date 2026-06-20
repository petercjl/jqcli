from __future__ import annotations

import subprocess  # nosec B404
import sys
from pathlib import Path
from typing import Any

from .jobs import update_job
from .posts import import_posts


def default_archive_script_path() -> Path:
    return Path(__file__).resolve().parents[3] / "scripts" / "archive_community_posts.py"


def refresh_archive(
    db_path: Path,
    root: Path,
    archive_path: Path,
    candidates_path: Path,
    *,
    script_path: Path | None = None,
    job_id: str | None = None,
) -> dict[str, Any]:
    resolved_script = (script_path or default_archive_script_path()).resolve()
    if not resolved_script.exists():
        raise RuntimeError(f"archive script not found: {resolved_script}")
    cmd = [
        sys.executable,
        str(resolved_script),
        "--phase",
        "sync",
        "--store",
        str(archive_path),
        "--state",
        str(archive_path.with_suffix(archive_path.suffix + ".state.json")),
    ]
    if job_id:
        update_job(db_path, job_id, message="正在增量抓取聚宽帖子")
    # Script path is resolved from trusted config/package location; shell is never used.
    proc = subprocess.run(cmd, cwd=root, text=True, capture_output=True, check=False)  # nosec B603
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr or proc.stdout or f"archive sync failed: {proc.returncode}")
    if job_id:
        update_job(db_path, job_id, message="正在重建本地索引")
    imported = import_posts(db_path, archive_path, candidates_path, refresh_labels=False, skip_existing=True)
    return {"sync_stdout": proc.stdout[-4000:], "sync_stderr": proc.stderr[-4000:], "import": imported}
