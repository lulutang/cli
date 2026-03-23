# -*- coding: utf-8 -*-
"""Output formatting — JSON / YAML / Table / Pretty."""

import json
import sys
from typing import Any, Dict, List, Optional

import yaml

# ANSI 颜色
_COLORS = {
    "reset": "\033[0m", "bold": "\033[1m", "dim": "\033[2m",
    "red": "\033[91m", "green": "\033[92m", "yellow": "\033[93m",
    "blue": "\033[94m", "magenta": "\033[95m", "cyan": "\033[96m",
    "gray": "\033[90m", "white": "\033[97m",
}

_use_color = sys.stdout.isatty()


def set_color(enabled: bool) -> None:
    global _use_color
    _use_color = enabled


def c(text: str, color: str) -> str:
    """着色。"""
    if not _use_color:
        return text
    return f"{_COLORS.get(color, '')}{text}{_COLORS['reset']}"


def output_json(data: Any) -> None:
    """JSON 输出。"""
    print(json.dumps(data, ensure_ascii=False, indent=2, default=str))


def output_yaml(data: Any) -> None:
    """YAML 输出。"""
    print(yaml.dump(data, default_flow_style=False, allow_unicode=True).rstrip())


def output_table(headers: List[str], rows: List[List[str]], widths: Optional[List[int]] = None) -> None:
    """简单表格输出。"""
    if not widths:
        widths = []
        for i, h in enumerate(headers):
            col_max = len(h)
            for row in rows:
                if i < len(row):
                    col_max = max(col_max, len(str(row[i])))
            widths.append(min(col_max + 2, 50))

    # Header
    hdr = "  ".join(str(h).ljust(widths[i]) for i, h in enumerate(headers))
    print(c(hdr, "bold"))
    print(c("─" * len(hdr), "dim"))

    # Rows
    for row in rows:
        parts = []
        for i, cell in enumerate(row):
            w = widths[i] if i < len(widths) else 20
            parts.append(str(cell).ljust(w))
        print("  ".join(parts))


def verdict_color(verdict: str) -> str:
    """裁决结果着色。"""
    v = (verdict or "").upper()
    if v == "MALICIOUS":
        return c("MALICIOUS", "red")
    elif v == "SUSPICIOUS":
        return c("SUSPICIOUS", "yellow")
    elif v in ("CLEAN", "SAFE"):
        return c("CLEAN", "green")
    return verdict


def severity_color(sev: str) -> str:
    """严重程度着色。"""
    s = (sev or "").upper()
    colors = {"CRITICAL": "red", "HIGH": "red", "MEDIUM": "yellow", "LOW": "cyan", "INFO": "gray"}
    return c(s, colors.get(s, "white"))


def action_color(action: str) -> str:
    """推荐操作着色。"""
    a = (action or "").upper()
    if a == "BLOCK":
        return c("BLOCK", "red")
    elif a == "REVIEW":
        return c("REVIEW", "yellow")
    elif a == "ALLOW":
        return c("ALLOW", "green")
    return action


def print_success(msg: str) -> None:
    print(c("✅ ", "green") + msg)


def print_warning(msg: str) -> None:
    print(c("⚠️  ", "yellow") + msg, file=sys.stderr)


def print_error(msg: str) -> None:
    print(c("❌ ", "red") + msg, file=sys.stderr)


def print_info(msg: str) -> None:
    print(c("ℹ  ", "blue") + msg)


def print_report_summary(data: Dict[str, Any], verbose: bool = False) -> None:
    """美化打印报告摘要。"""
    report = data.get("report") or data
    verdict = report.get("verdict") or {}
    if isinstance(verdict, str):
        verdict = {"result": verdict}
    stats = report.get("stats") or {}

    print()
    print(c("═" * 60, "dim"))
    print(c("  SAFESKILL SCAN REPORT", "bold"))
    print(c("═" * 60, "dim"))
    print()
    print(f"  Task ID:     {c(data.get('task_id', '—'), 'cyan')}")
    print(f"  Skill Name:  {data.get('skill_name', '—')}")
    print(f"  Status:      {data.get('status', '—')}")
    print()
    print(f"  Verdict:     {verdict_color(verdict.get('result', '—'))}")
    print(f"  Confidence:  {verdict.get('confidence', '—')}")
    print(f"  Level:       {severity_color(verdict.get('level', '—'))}")
    print(f"  Action:      {action_color(verdict.get('recommended_action', '—'))}")
    print()

    summary = verdict.get("summary") or verdict.get("summary_en") or ""
    if summary:
        print(f"  Summary:     {summary}")
        print()

    by_sev = stats.get("by_severity") or {}
    if by_sev:
        sev_parts = []
        for s in ["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"]:
            cnt = by_sev.get(s, 0)
            if cnt > 0:
                sev_parts.append(f"{severity_color(s)}:{cnt}")
        if sev_parts:
            print(f"  Findings:    {stats.get('total_findings', 0)} total  ({', '.join(sev_parts)})")
            print()

    findings = report.get("findings") or []
    if findings and verbose:
        print(c("  ── Findings ──", "dim"))
        for i, f in enumerate(findings[:20], 1):
            sev = severity_color(f.get("severity", ""))
            title = f.get("title") or f.get("title_en") or f.get("rule_id", "")
            loc = f.get("location", {})
            fpath = loc.get("file_path") or f.get("file_path", "")
            line = loc.get("line_number") or f.get("line", "")
            loc_str = f"{fpath}:{line}" if fpath else ""
            print(f"  #{i:2d}  [{sev}]  {title}")
            if loc_str:
                print(f"       {c(loc_str, 'cyan')}")
        if len(findings) > 20:
            print(f"  ... and {len(findings) - 20} more")
        print()

    print(c("═" * 60, "dim"))
