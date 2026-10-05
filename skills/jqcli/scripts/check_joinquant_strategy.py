#!/usr/bin/env python3
import ast
import sys
from pathlib import Path


ORDER_FUNCS = {
    "order",
    "order_value",
    "order_target",
    "order_target_value",
    "order_volume",
}

DATA_FUNCS = {
    "history",
    "attribute_history",
    "get_price",
    "get_bars",
    "get_current_data",
    "get_fundamentals",
}

RESEARCH_ONLY = {
    "create_backtest",
    "get_backtest",
}

SUSPECT_IMPORTS = {
    "talib",
    "sklearn",
    "statsmodels",
    "tensorflow",
    "torch",
    "requests",
    "yfinance",
    "akshare",
    "tushare",
}


class Checker(ast.NodeVisitor):
    def __init__(self):
        self.errors = []
        self.warnings = []
        self.functions = {}
        self.current_function = None
        self.has_initialize = False
        self.has_jq_import = False
        self.has_use_real_price = False
        self.has_avoid_future_data = False
        self.has_handle_data = False
        self.has_run_schedule = False

    def warn(self, node, msg):
        self.warnings.append((getattr(node, "lineno", 0), msg))

    def error(self, node, msg):
        self.errors.append((getattr(node, "lineno", 0), msg))

    def visit_Import(self, node):
        for alias in node.names:
            root = alias.name.split(".")[0]
            if root == "jqdata":
                self.has_jq_import = True
            if root in SUSPECT_IMPORTS:
                self.warn(node, "import `%s` may be unavailable or risky on JoinQuant" % alias.name)
        self.generic_visit(node)

    def visit_ImportFrom(self, node):
        mod = node.module or ""
        root = mod.split(".")[0]
        if root in {"jqdata", "kuanke"}:
            self.has_jq_import = True
        if root in SUSPECT_IMPORTS:
            self.warn(node, "from `%s` import may be unavailable or risky on JoinQuant" % mod)
        self.generic_visit(node)

    def visit_FunctionDef(self, node):
        self.functions[node.name] = node
        if node.name == "initialize":
            self.has_initialize = True
            if len(node.args.args) != 1:
                self.error(node, "initialize should accept exactly one argument: context")
        if node.name == "handle_data":
            self.has_handle_data = True
            if len(node.args.args) != 2:
                self.error(node, "handle_data should accept exactly two arguments: context, data")
        prev = self.current_function
        self.current_function = node.name
        self.generic_visit(node)
        self.current_function = prev

    def visit_Call(self, node):
        name = call_name(node.func)
        if not self.current_function and name in ORDER_FUNCS:
            self.error(node, "order function `%s` is called at top level" % name)
        if not self.current_function and name in DATA_FUNCS:
            self.warn(node, "data function `%s` is called at top level; JoinQuant loads top-level code before backtest callbacks" % name)
        if name in RESEARCH_ONLY:
            self.error(node, "`%s` is research-only and should not run inside a backtest strategy" % name)
        if name in {"run_daily", "run_weekly", "run_monthly"}:
            self.has_run_schedule = True
            self.check_scheduler(node, name)
        if name == "set_option":
            self.check_set_option(node)
        if name == "get_price":
            self.check_get_price(node)
        if name in DATA_FUNCS:
            self.check_future_end_date(node, name)
        if name == "sum":
            self.warn(node, "`sum()` may be shadowed by `from jqdata import *` on JoinQuant; use a local helper such as safe_sum()")
        self.generic_visit(node)

    def check_scheduler(self, node, name):
        if node.args:
            first = node.args[0]
            if isinstance(first, ast.Name) and first.id == "handle_data":
                self.error(node, "%s(handle_data, ...) is invalid; scheduled callbacks should accept only context" % name)
            if isinstance(first, ast.Attribute):
                self.error(node, "%s callback appears to be an object/class method; use a global function" % name)
        for kw in node.keywords:
            if kw.arg == "func":
                if isinstance(kw.value, ast.Name) and kw.value.id == "handle_data":
                    self.error(node, "%s(func=handle_data, ...) is invalid" % name)
                if isinstance(kw.value, ast.Attribute):
                    self.error(node, "%s callback appears to be an object/class method; use a global function" % name)
            if name == "run_daily" and kw.arg == "force":
                self.error(node, "run_daily does not support force")
        has_concrete_time = False
        has_reference = False
        if len(node.args) >= 2 and isinstance(node.args[1], ast.Constant):
            value = node.args[1].value
            has_concrete_time = isinstance(value, str) and value not in {"every_bar", "open"}
        for kw in node.keywords:
            if kw.arg == "time" and isinstance(kw.value, ast.Constant):
                value = kw.value.value
                has_concrete_time = isinstance(value, str) and value not in {"every_bar", "open"} and not value.startswith("open")
            if kw.arg == "reference_security":
                has_reference = True
        if has_concrete_time and has_reference:
            self.warn(node, "concrete scheduler time should usually not set reference_security")

    def check_set_option(self, node):
        if len(node.args) >= 2 and isinstance(node.args[0], ast.Constant):
            key = node.args[0].value
            val = node.args[1]
            if key == "use_real_price" and literal_true(val):
                self.has_use_real_price = True
            if key == "avoid_future_data" and literal_true(val):
                self.has_avoid_future_data = True
            if key in {"t0_mode", "always_match_market_order", "match_by_signal"}:
                self.warn(node, "experimental option `%s` changes normal trading rules; use only for explicit experiments" % key)
        if self.current_function != "initialize":
            self.warn(node, "set_option is usually expected inside initialize")

    def check_get_price(self, node):
        has_panel_false = False
        for kw in node.keywords:
            if kw.arg == "panel" and isinstance(kw.value, ast.Constant) and kw.value.value is False:
                has_panel_false = True
            if kw.arg == "end_date" and looks_later_than_current_dt(kw.value):
                self.warn(node, "get_price end_date may exceed context.current_dt and introduce future data")
        if not has_panel_false:
            self.warn(node, "get_price defaults to panel=True; set panel=False for multi-security compatibility")

    def check_future_end_date(self, node, name):
        for kw in node.keywords:
            if kw.arg == "end_date" and looks_later_than_current_dt(kw.value):
                self.warn(node, "%s end_date may exceed context.current_dt and introduce future data" % name)

    def finish(self):
        if not self.has_initialize:
            self.errors.append((0, "missing initialize(context)"))
        if not self.has_jq_import:
            self.warnings.append((0, "missing jqdata import; add `from jqdata import *` or `import jqdata`"))
        if self.has_handle_data and self.has_run_schedule:
            self.warnings.append((0, "strategy mixes handle_data and run_* scheduling; keep both only when intentional"))
        if not self.has_use_real_price:
            self.warnings.append((0, "missing set_option('use_real_price', True) in initialize"))
        if not self.has_avoid_future_data:
            self.warnings.append((0, "missing set_option('avoid_future_data', True) in initialize"))


def call_name(func):
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return None


def literal_true(node):
    return isinstance(node, ast.Constant) and node.value is True


def looks_later_than_current_dt(node):
    if isinstance(node, ast.Call) and call_name(node.func) in {"now", "today"}:
        return True
    if isinstance(node, ast.Attribute) and call_name(node) in {"now", "today"}:
        return True
    return False


def main(argv):
    if len(argv) != 2:
        print("Usage: check_joinquant_strategy.py <strategy.py>", file=sys.stderr)
        return 2
    path = Path(argv[1])
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except SyntaxError as exc:
        print("ERROR:%s:%s: syntax error: %s" % (path, exc.lineno, exc.msg))
        return 1
    checker = Checker()
    checker.visit(tree)
    checker.finish()
    for line, msg in sorted(checker.errors):
        print("ERROR:%s:%s: %s" % (path, line, msg))
    for line, msg in sorted(checker.warnings):
        print("WARN:%s:%s: %s" % (path, line, msg))
    if checker.errors:
        return 1
    print("OK:%s: %d warning(s)" % (path, len(checker.warnings)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
