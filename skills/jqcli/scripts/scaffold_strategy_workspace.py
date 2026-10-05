#!/usr/bin/env python3
import argparse
import datetime as _dt
import json
import re
from pathlib import Path


def safe_name(name):
    value = name.strip()
    value = re.sub(r"[\\/:*?\"<>|]+", "-", value)
    value = re.sub(r"\s+", "-", value)
    value = value.strip(".-")
    return value or "joinquant-strategy"


def readme_template(strategy_name, script_rel):
    now = _dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    return """# {strategy_name}

## 概览

- 策略目标：
- 当前状态：草稿
- 主脚本：`{script_rel}`
- 聚宽运行频率：
- 基准：
- 标的池：
- 初始资金：

## 策略逻辑

- 入场：
- 出场：
- 调仓：
- 风控：

## 参数

| 参数 | 当前值 | 说明 |
| --- | --- | --- |

## 验证历史

| 时间 | 检查项 | 结果 | 说明 |
| --- | --- | --- | --- |

## 优化日志

### {now} - 初始化策略目录

- 需求：创建策略目录。
- 修改：创建策略文件夹、README 和辅助目录。
- 原因：将脚本、笔记、数据和结果放在同一个策略目录中，方便后续复盘。
- 验证：
- 回测结果：
- 下一步：

## 已知限制

- 
""".format(strategy_name=strategy_name, script_rel=script_rel, now=now)


def main():
    parser = argparse.ArgumentParser(description="Create a JoinQuant strategy workspace.")
    parser.add_argument("strategy_name")
    parser.add_argument("--root", default=".", help="Project root. Defaults to current directory.")
    parser.add_argument("--script-name", default="strategy.py")
    args = parser.parse_args()

    root = Path(args.root).expanduser().resolve()
    folder = root / "strategies" / safe_name(args.strategy_name)
    folder.mkdir(parents=True, exist_ok=True)

    for child in ["data", "notes", "results", "research"]:
        (folder / child).mkdir(exist_ok=True)

    script = folder / args.script_name
    if not script.exists():
        script.write_text("", encoding="utf-8")

    readme = folder / "README.md"
    script_rel = str(script.relative_to(folder))
    if not readme.exists():
        readme.write_text(readme_template(args.strategy_name, script_rel), encoding="utf-8")

    print(json.dumps({
        "strategy_name": args.strategy_name,
        "folder": str(folder),
        "script": str(script),
        "readme": str(readme),
        "created": True,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
