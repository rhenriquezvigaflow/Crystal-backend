
from __future__ import annotations

import argparse
import ast
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List


SQL_KEYWORDS = ("SELECT", "INSERT", "UPDATE", "DELETE", "FROM", "WHERE")


@dataclass
class Finding:
    path: str
    line: int
    code: str
    message: str


class SqlInjectionVisitor(ast.NodeVisitor):
    def __init__(self, path: Path) -> None:
        self.path = path
        self.findings: List[Finding] = []

    def visit_Call(self, node: ast.Call) -> None:
        func_name = self._func_name(node.func)

        if func_name.endswith(".text") or func_name == "text":
            self._check_text_call(node)

        if func_name.endswith(".execute") or func_name == "execute":
            self._check_execute_call(node)

        self.generic_visit(node)

    def _check_text_call(self, node: ast.Call) -> None:
        if not node.args:
            return
        arg = node.args[0]
        if isinstance(arg, ast.JoinedStr):
            self._add(node, "SQLI001", "f-string used in text()")
        elif isinstance(arg, ast.BinOp):
            self._add(node, "SQLI002", "string concatenation used in text()")
        elif self._looks_like_dynamic_format(arg):
            self._add(node, "SQLI003", "dynamic format used in text()")

    def _check_execute_call(self, node: ast.Call) -> None:
        if not node.args:
            return
        sql_arg = node.args[0]
        if isinstance(sql_arg, ast.JoinedStr):
            self._add(node, "SQLI004", "f-string passed to execute()")
        elif isinstance(sql_arg, ast.BinOp):
            self._add(node, "SQLI005", "string concatenation passed to execute()")
        elif self._looks_like_dynamic_format(sql_arg):
            self._add(node, "SQLI006", "formatted string passed to execute()")

    def _looks_like_dynamic_format(self, node: ast.AST) -> bool:
        if not isinstance(node, ast.Call):
            return False
        if not isinstance(node.func, ast.Attribute):
            return False
        if node.func.attr != "format":
            return False
        if not isinstance(node.func.value, ast.Constant):
            return True
        value = node.func.value.value
        if not isinstance(value, str):
            return True
        upper = value.upper()
        return any(k in upper for k in SQL_KEYWORDS)

    def _func_name(self, node: ast.AST) -> str:
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            return f"{self._func_name(node.value)}.{node.attr}"
        return ""

    def _add(self, node: ast.AST, code: str, message: str) -> None:
        self.findings.append(
            Finding(
                path=str(self.path),
                line=getattr(node, "lineno", 1),
                code=code,
                message=message,
            )
        )


def iter_python_files(paths: Iterable[str]) -> Iterable[Path]:
    for p in paths:
        path = Path(p)
        if path.is_file() and path.suffix == ".py":
            yield path
            continue
        if path.is_dir():
            yield from path.rglob("*.py")


def scan(paths: Iterable[str]) -> List[Finding]:
    findings: List[Finding] = []
    for file_path in iter_python_files(paths):
        try:
            source = file_path.read_text(encoding="utf-8")
        except Exception:
            continue
        try:
            tree = ast.parse(source, filename=str(file_path))
        except SyntaxError:
            continue

        visitor = SqlInjectionVisitor(file_path)
        visitor.visit(tree)
        findings.extend(visitor.findings)
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Detect risky dynamic SQL patterns."
    )
    parser.add_argument(
        "paths",
        nargs="*",
        default=["app"],
        help="Files or directories to scan",
    )
    parser.add_argument(
        "--fail-on-findings",
        action="store_true",
        help="Exit with code 1 if findings are detected",
    )
    args = parser.parse_args()

    findings = scan(args.paths)
    if not findings:
        print("No SQL injection patterns detected.")
        return 0

    for f in findings:
        print(f"{f.path}:{f.line} {f.code} {f.message}")

    if args.fail_on_findings:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

