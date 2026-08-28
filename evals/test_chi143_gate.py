#!/usr/bin/env python3
"""CHI-143: chart tick/label fallbacks must never be dash or empty.

Scans site/*.js Chart data.labels construction (not legend.labels).
A tick built from a name helper that last-resorts to "—", "-", or ""
is a ship block — this is the CHI-112 class of fail.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
BAD = {"—", "-", ""}
fails: list[str] = []


def fail(msg: str) -> None:
    fails.append(msg)


def grab_fn(src: str, name: str) -> str | None:
    for pat in (
        rf"function {re.escape(name)}\s*\([^)]*\)\s*\{{",
        rf"const {re.escape(name)}\s*=\s*(?:function\s*)?\([^)]*\)\s*=>\s*\{{",
        rf"const {re.escape(name)}\s*=\s*\([^)]*\)\s*=>",
    ):
        m = re.search(pat, src)
        if not m:
            continue
        if src[m.end() - 1] != "{":
            # one-line arrow: take to semicolon
            end = src.find(";", m.end())
            return src[m.start() : end if end > 0 else m.end() + 120]
        brace = src.find("{", m.start())
        depth = 0
        for i in range(brace, len(src)):
            if src[i] == "{":
                depth += 1
            elif src[i] == "}":
                depth -= 1
                if depth == 0:
                    return src[m.start() : i + 1]
    return None


def last_string_fallback(body: str) -> list[str]:
    return re.findall(r"""\|\|\s*(["'])(.*?)\1""", body)


def helper_names(expr: str) -> list[str]:
    return re.findall(r"\b([A-Za-z_$][\w$]*)\s*\(", expr)


def data_label_exprs(src: str) -> list[tuple[int, str]]:
    out = []
    for m in re.finditer(r"\blabels:\s*", src):
        pre = src[max(0, m.start() - 80) : m.start()]
        if re.search(r"legend\s*:\s*\{[^}]*$", pre, re.S):
            continue
        if "legend" in pre.split("\n")[-1] and "data:" not in pre.split("\n")[-1]:
            continue
        rest = src[m.end() :]
        # skip legend.labels object
        if rest.lstrip().startswith("{"):
            continue
        # take one expression
        end = rest.find("\n")
        expr = rest[: end if end >= 0 else 160].strip().rstrip(",")
        out.append((src[: m.start()].count("\n") + 1, expr))
    return out


def resolve_ident(src: str, ident: str) -> str | None:
    m = re.search(rf"(?:const|let|var)\s+{re.escape(ident)}\s*=\s*([^;]+);", src)
    return m.group(1).strip() if m else None


def check_file(path: Path) -> None:
    if path.name.endswith(".min.js") or path.name == "chart.umd.min.js":
        return
    src = path.read_text(encoding="utf-8", errors="replace")
    for lineno, expr in data_label_exprs(src):
        if re.search(r"""\|\|\s*(["'])(?:—|-|)\1""", expr):
            fail(f"{path.name}:{lineno} tick labels fallback is dash/empty: {expr}")
            continue
        idents = helper_names(expr)
        if re.fullmatch(r"[A-Za-z_$][\w$]*", expr or ""):
            assigned = resolve_ident(src, expr)
            if assigned:
                idents.extend(helper_names(assigned))
                if re.search(r"""\|\|\s*(["'])(?:—|-|)\1""", assigned):
                    fail(f"{path.name}:{lineno} labels {expr} assigned with dash fallback")
        for name in idents:
            if name in {"map", "String", "Number", "Array", "Object", "Math", "Boolean"}:
                continue
            body = grab_fn(src, name)
            if not body:
                continue
            # only treat as a *name* helper if it looks like one
            if not re.search(r"franchiseName|tName|name|owner|shortTeam|shortName", body):
                continue
            for _q, val in last_string_fallback(body):
                if val in BAD:
                    fail(
                        f"{path.name}:{lineno} helper {name}() last-resorts to {val!r} for chart ticks"
                    )
            if re.search(r'return\s+["\']—["\']', body) or re.search(r'return\s+["\']-["\']', body):
                fail(f"{path.name}:{lineno} helper {name}() returns a dash for chart ticks")


def main() -> int:
    trades = (SITE / "trades.js").read_text()
    if "tid: +tid" in trades:
        fail("trades.js still coerces owner ids with tid: +tid")
    tname = grab_fn(trades, "tName") or ""
    if "—" in tname or re.search(r'return\s+["\']-["\']', tname):
        fail("trades.js tName still paints a dash")
    if "labels: names" not in trades:
        fail("trades.js Activity chart missing labels: names")
    if "unavailable" not in tname:
        fail("trades.js tName last resort is not unavailable")

    for p in sorted(SITE.glob("*.js")):
        check_file(p)

    if fails:
        print("FAIL CHI-143")
        for item in fails:
            print(" -", item)
        return 1
    print("PASS")
    print("CHI-143: no chart tick/label fallback is dash or empty")
    return 0


if __name__ == "__main__":
    sys.exit(main())
