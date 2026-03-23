# -*- coding: utf-8 -*-
"""SafeSkill CLI — main command dispatcher."""

import argparse
import json
import os
import sys
import time
import logging

from safeskill.config import (
    load_config, save_config, get_token, set_token, clear_token,
    get_config_value, set_config_value, DEFAULT_CONFIG,
)
from safeskill.api import Client, APIError
from safeskill.output import (
    output_json, output_yaml, output_table, set_color,
    print_success, print_warning, print_error, print_info,
    print_report_summary, verdict_color, severity_color, action_color, c,
)

__version__ = "1.1.0"

log = logging.getLogger("safeskill")


# ═════════════════════════════════════════════════════════════════════════════
#  Argument parsing
# ═════════════════════════════════════════════════════════════════════════════

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="safeskill",
        description="SafeSkill CLI — Skill 安全扫描命令行工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  safeskill login --token YOUR_TOKEN
  safeskill scan my-skill.zip
  safeskill scan url https://github.com/owner/repo
  safeskill report abc123def456...
  safeskill judge --md5 a5d5c01672e068f59ff621bb555bcf82
  safeskill search tavily-search
  safeskill download --task-id abc123...

Docs: https://safeskill.qianxin.com/
""",
    )
    parser.add_argument("--version", action="version", version=f"safeskill {__version__}")
    parser.add_argument("--output", "-o", choices=["json", "yaml", "table", "pretty"], default=None,
                        help="输出格式 (default: table)")
    parser.add_argument("--no-color", action="store_true", help="禁用彩色输出")
    parser.add_argument("--verbose", "-v", action="store_true", help="详细输出")
    parser.add_argument("--debug", action="store_true", help="调试模式")
    parser.add_argument("--quiet", "-q", action="store_true", help="静默模式")
    parser.add_argument("--json", action="store_true", help="JSON 输出 (等同 --output json)")
    parser.add_argument("--non-interactive", action="store_true", help="非交互模式")
    parser.add_argument("--token", default=None, help="API Token (覆盖配置)")
    parser.add_argument("--api-url", default=None, help="API 地址 (覆盖配置)")

    sub = parser.add_subparsers(dest="command", help="可用命令")

    # ── login ────────────────────────────────────────────────────────────────
    p_login = sub.add_parser("login", help="设置 API Token")
    p_login.add_argument("--token", "-t", required=True, dest="login_token", help="API Token")

    # ── logout ───────────────────────────────────────────────────────────────
    sub.add_parser("logout", help="清除已存储的 Token")

    # ── whoami ───────────────────────────────────────────────────────────────
    sub.add_parser("whoami", help="查看当前 Token 状态")

    # ── config ───────────────────────────────────────────────────────────────
    p_config = sub.add_parser("config", help="配置管理")
    cfg_sub = p_config.add_subparsers(dest="config_action")
    cfg_sub.add_parser("get", help="查看所有配置")
    p_cfg_set = cfg_sub.add_parser("set", help="设置配置项")
    p_cfg_set.add_argument("key", help="配置键 (如 api.timeout)")
    p_cfg_set.add_argument("value", help="配置值")
    cfg_sub.add_parser("reset", help="恢复默认配置")

    # ── scan ─────────────────────────────────────────────────────────────────
    p_scan = sub.add_parser("scan", help="上传文件扫描")
    p_scan.add_argument("file", help="Skill 压缩包路径")
    p_scan.add_argument("--name", default="", help="Skill 名称")
    p_scan.add_argument("--policy", default="balanced", choices=["strict", "balanced", "permissive"])
    p_scan.add_argument("--enable-llm", default="true")
    p_scan.add_argument("--enable-qax-ti", default="true")
    p_scan.add_argument("--callback-url", default="")
    p_scan.add_argument("--is-public", default="true")

    # ── scan-url（独立命令，避免子命令冲突）────────────────────────────────
    p_scan_url = sub.add_parser("scan-url", help="URL 投递扫描")
    p_scan_url.add_argument("url", help="Skill URL")
    p_scan_url.add_argument("--source-type", default="auto",
                            choices=["auto", "github", "clawhub", "skillsmp", "skills_rest", "gitlab", "direct"])
    p_scan_url.add_argument("--name", default="")
    p_scan_url.add_argument("--policy", default="balanced", choices=["strict", "balanced", "permissive"])
    p_scan_url.add_argument("--enable-llm", default="true")
    p_scan_url.add_argument("--enable-qax-ti", default="true")
    p_scan_url.add_argument("--callback-url", default="")
    p_scan_url.add_argument("--is-public", default="true")

    # ── report ───────────────────────────────────────────────────────────────
    p_report = sub.add_parser("report", help="查询单个报告")
    p_report.add_argument("task_id", help="任务 ID (32位十六进制)")
    p_report.add_argument("--wait", "-w", action="store_true", help="等待扫描完成")
    p_report.add_argument("--timeout", type=int, default=300, help="等待超时秒数 (default: 300)")

    # ── report-batch（独立命令）───────────────────────────────────────────
    p_batch = sub.add_parser("report-batch", help="批量查询报告")
    p_batch.add_argument("task_ids", nargs="*", help="task_id 列表")
    p_batch.add_argument("--task-ids-file", "-f", help="从文件读取 task_id (每行一个)")
    p_batch.add_argument("--summary", "-s", action="store_true", help="显示汇总统计")

    # ── judge ────────────────────────────────────────────────────────────────
    p_judge = sub.add_parser("judge", help="MD5/SHA1 研判查询")
    p_judge.add_argument("--md5", default="", help="MD5 哈希值")
    p_judge.add_argument("--sha1", default="", help="SHA1 哈希值")

    # ── search ───────────────────────────────────────────────────────────────
    p_search = sub.add_parser("search", help="按 Skill 名称搜索")
    p_search.add_argument("name", help="Skill 名称")

    # ── download ─────────────────────────────────────────────────────────────
    p_dl = sub.add_parser("download", help="下载资源包")
    p_dl.add_argument("--task-id", default="", help="任务 ID")
    p_dl.add_argument("--skill-name", "--name", default="", help="Skill 名称")
    p_dl.add_argument("--files-md5", default="", help="组合 MD5")
    p_dl.add_argument("--package-md5", default="", help="包 MD5")
    p_dl.add_argument("--files-sha1", default="", help="组合 SHA1")
    p_dl.add_argument("--package-sha1", default="", help="包 SHA1")

    # ── init ─────────────────────────────────────────────────────────────────
    sub.add_parser("init", help="首次运行向导")

    # ── completion ───────────────────────────────────────────────────────────
    p_comp = sub.add_parser("completion", help="生成 Shell 补全脚本")
    p_comp.add_argument("shell", choices=["bash", "zsh", "fish"], help="Shell 类型")

    return parser


# ═════════════════════════════════════════════════════════════════════════════
#  Command handlers
# ═════════════════════════════════════════════════════════════════════════════

def _get_fmt(args) -> str:
    if args.json:
        return "json"
    return args.output or get_config_value("output.format") or "table"


def _client(args) -> Client:
    return Client(
        token=args.token or "",
        base_url=args.api_url or "",
    )


def _bool_str(v: str) -> bool:
    return v.lower() not in ("false", "0", "no")


def cmd_login(args) -> int:
    token = args.login_token
    set_token(token)
    print_success(f"Token 已保存到 ~/.config/safeskill/config.yaml")
    # 验证
    try:
        client = Client(token=token)
        client.whoami()
        print_success("Token 验证通过")
    except APIError as e:
        print_warning(f"Token 验证失败: {e.message} (Token 已保存，请检查是否正确)")
    return 0


def cmd_logout(args) -> int:
    clear_token()
    print_success("Token 已清除")
    return 0


def cmd_whoami(args) -> int:
    token = get_token()
    if not token:
        print_error("未设置 Token，请先执行: safeskill login --token YOUR_TOKEN")
        return 2
    masked = token[:8] + "..." + token[-4:] if len(token) > 16 else "***"
    print_info(f"Token: {masked}")
    try:
        client = _client(args)
        client.whoami()
        print_success("Token 有效，连接正常")
    except APIError as e:
        print_error(f"验证失败: {e.message}")
        return 2
    return 0


def cmd_config(args) -> int:
    action = args.config_action
    if action == "get":
        cfg = load_config()
        # 脱敏 token
        if cfg.get("auth", {}).get("token"):
            cfg["auth"]["token"] = "***"
        fmt = _get_fmt(args)
        if fmt == "json":
            output_json(cfg)
        else:
            output_yaml(cfg)
    elif action == "set":
        set_config_value(args.key, args.value)
        print_success(f"已设置 {args.key} = {args.value}")
    elif action == "reset":
        save_config(DEFAULT_CONFIG.copy())
        print_success("配置已重置为默认值")
    else:
        print_error("请指定操作: config get | config set <key> <value> | config reset")
        return 1
    return 0


def _validate_task_id(task_id):
    """安全校验 task_id 格式（32位十六进制），防止注入。"""
    if not task_id or len(task_id) != 32:
        return False
    return all(c in "0123456789abcdef" for c in task_id.lower())


def _validate_hash_md5(h):
    """校验 MD5 格式。"""
    return h and len(h) == 32 and all(c in "0123456789abcdef" for c in h.lower())


def _validate_hash_sha1(h):
    """校验 SHA1 格式。"""
    return h and len(h) == 40 and all(c in "0123456789abcdef" for c in h.lower())


def _sanitize_path(filepath):
    """安全校验文件路径，防止路径遍历。"""
    real = os.path.realpath(filepath)
    if not os.path.isfile(real):
        return None
    return real


def _validate_url(url):
    """基本 URL 格式校验。"""
    if not url:
        return False
    if not (url.startswith("http://") or url.startswith("https://")):
        return False
    # 防止 SSRF：禁止内网地址
    blocked = ["127.0.0.1", "localhost", "0.0.0.0", "169.254.169.254", "metadata.google"]
    for b in blocked:
        if b in url.lower():
            return False
    return True


def cmd_scan(args) -> int:
    """上传文件扫描。"""
    fmt = _get_fmt(args)
    client = _client(args)

    filepath = _sanitize_path(args.file)
    if not filepath:
        print_error(f"文件不存在: {args.file}")
        return 4

    # 文件扩展名校验
    allowed_ext = (".zip", ".tar.gz", ".tgz", ".7z", ".rar")
    lower = filepath.lower()
    if not any(lower.endswith(ext) for ext in allowed_ext):
        print_error(f"不支持的文件格式，允许: {', '.join(allowed_ext)}")
        return 4

    size_mb = os.path.getsize(filepath) / (1024 * 1024)
    if size_mb > 10:
        print_error(f"文件过大: {size_mb:.1f}MB (最大 10MB)")
        return 4

    if not args.quiet:
        print_info(f"上传文件扫描: {filepath} ({size_mb:.1f}MB)")

    try:
        data = client.scan_file(
            filepath=filepath,
            skill_name=args.name,
            policy=args.policy,
            enable_llm=_bool_str(args.enable_llm),
            enable_qax_ti=_bool_str(args.enable_qax_ti),
            callback_url=args.callback_url,
            is_public=_bool_str(args.is_public),
        )
    except APIError as e:
        print_error(f"投递失败: {e.message}")
        return 1

    if fmt == "json":
        output_json(data)
    elif fmt == "yaml":
        output_yaml(data)
    else:
        _print_scan_result(data)
    return 0


def cmd_scan_url(args) -> int:
    """URL 投递扫描。"""
    fmt = _get_fmt(args)
    client = _client(args)

    url = args.url
    if not _validate_url(url):
        print_error(f"无效的 URL: {url}")
        print_info("URL 必须以 http:// 或 https:// 开头，且不能指向内网地址")
        return 1

    if not args.quiet:
        print_info(f"投递 URL 扫描: {url}")

    try:
        data = client.scan_url(
            url=url,
            source_type=args.source_type,
            skill_name=args.name,
            policy=args.policy,
            enable_llm=_bool_str(args.enable_llm),
            enable_qax_ti=_bool_str(args.enable_qax_ti),
            callback_url=args.callback_url,
            is_public=_bool_str(args.is_public),
        )
    except APIError as e:
        print_error(f"投递失败: {e.message}")
        return 1

    if fmt == "json":
        output_json(data)
    elif fmt == "yaml":
        output_yaml(data)
    else:
        _print_scan_result(data)
    return 0


def _print_scan_result(data: dict) -> None:
    """打印扫描投递结果。"""
    if data.get("duplicate"):
        print_warning("文件已扫描过 (SHA1 去重命中)")
        tid = data.get("existing_task_id") or data.get("task_id", "")
        v = data.get("verdict", {})
        vr = v.get("result", "") if isinstance(v, dict) else ""
        print(f"  Task ID:  {c(tid, 'cyan')}")
        if vr:
            print(f"  Verdict:  {verdict_color(vr)}")
        print()
        print_info(f"查看报告: safeskill report {tid}")
    else:
        task_id = data.get("task_id", "")
        print_success(f"任务已提交")
        print(f"  Task ID:    {c(task_id, 'cyan')}")
        print(f"  Status:     {data.get('status', 'pending')}")
        print(f"  Created:    {data.get('created_at', '')}")
        print()
        print_info(f"查看报告: safeskill report {task_id}")
        print_info(f"等待完成: safeskill report {task_id} --wait")


def cmd_report(args) -> int:
    fmt = _get_fmt(args)
    client = _client(args)

    task_id = args.task_id
    if not _validate_task_id(task_id):
        print_error("无效的 task_id (需要 32 位十六进制): %s" % task_id)
        return 1

    # --wait 模式
    if args.wait:
        return _report_wait(client, task_id, fmt, args)

    try:
        data = client.report(task_id)
    except APIError as e:
        print_error(f"查询失败: {e.message}")
        return 1

    if data.get("code") == 202:
        print_warning(f"扫描进行中... (status: {data.get('status', 'running')})")
        print_info(f"等待完成: safeskill report {task_id} --wait")
        return 0

    if fmt == "json":
        output_json(data)
    elif fmt == "yaml":
        output_yaml(data)
    elif fmt == "pretty" or args.verbose:
        print_report_summary(data, verbose=True)
    else:
        print_report_summary(data, verbose=args.verbose)
    return 0


def _report_wait(client: Client, task_id: str, fmt: str, args) -> int:
    """轮询等待报告完成。"""
    timeout = args.timeout
    start = time.time()
    interval = 3

    if not args.quiet:
        print_info(f"等待扫描完成 (超时: {timeout}s)...")

    while time.time() - start < timeout:
        try:
            data = client.report(task_id)
        except APIError as e:
            print_error(f"查询失败: {e.message}")
            return 1

        if data.get("code") != 202:
            # 完成
            if fmt == "json":
                output_json(data)
            elif fmt == "yaml":
                output_yaml(data)
            else:
                print_report_summary(data, verbose=args.verbose)

            # Exit code 语义化
            report = data.get("report") or data
            v = report.get("verdict") or {}
            if isinstance(v, dict):
                result = v.get("result", "")
            else:
                result = v
            if result == "MALICIOUS":
                return 1
            return 0

        elapsed = int(time.time() - start)
        if not args.quiet and elapsed % 10 < interval:
            print(f"\r  ⏳ 扫描中... {elapsed}s", end="", flush=True)
        time.sleep(interval)

    print()
    print_error(f"等待超时 ({timeout}s)，扫描仍在进行中")
    print_info(f"稍后查看: safeskill report {task_id}")
    return 1


def _cmd_report_batch(args, client, fmt):
    # type: (Any, Client, str) -> int
    """批量报告查询。"""
    task_ids = list(args.task_ids or [])

    # 从文件读取
    if args.task_ids_file:
        try:
            with open(args.task_ids_file, "r") as f:
                for line in f:
                    tid = line.strip()
                    if tid and not tid.startswith("#"):
                        task_ids.append(tid)
        except FileNotFoundError:
            print_error(f"文件不存在: {args.task_ids_file}")
            return 4

    if not task_ids:
        print_error("请指定 task_id: safeskill report-batch <id1> <id2> ...")
        return 1

    if len(task_ids) > 20:
        print_error(f"最多 20 个 task_id (当前 {len(task_ids)} 个)")
        return 1

    # 校验每个 task_id 格式
    invalid = [t for t in task_ids if not _validate_task_id(t)]
    if invalid:
        print_error(f"无效的 task_id (需要 32 位十六进制): {invalid[0]}")
        return 1

    try:
        data = client.report_batch(task_ids)
    except APIError as e:
        print_error(f"查询失败: {e.message}")
        return 1

    if fmt == "json":
        output_json(data)
        return 0
    if fmt == "yaml":
        output_yaml(data)
        return 0

    # 表格输出
    results = data.get("results", [])
    headers = ["Status", "Result", "Level", "Findings", "Task ID"]
    rows = []
    stats = {"MALICIOUS": 0, "SUSPICIOUS": 0, "CLEAN": 0, "pending": 0, "error": 0}

    for r in results:
        code = r.get("code", 0)
        tid = r.get("task_id", "")[:16] + "..."
        if code == 200:
            report = r.get("report") or r
            v = report.get("verdict") or {}
            if isinstance(v, dict):
                vr = v.get("result", "—")
                level = v.get("level", "—")
            else:
                vr = v
                level = "—"
            findings = (report.get("stats") or {}).get("total_findings", 0)
            rows.append(["✅", verdict_color(vr), severity_color(level), str(findings), tid])
            stats[vr] = stats.get(vr, 0) + 1
        elif code == 202:
            rows.append(["⏳", "scanning", "—", "—", tid])
            stats["pending"] += 1
        else:
            rows.append(["❌", r.get("error", "error")[:20], "—", "—", tid])
            stats["error"] += 1

    print()
    print(c(f"批量报告 ({len(results)} 个任务)", "bold"))
    print()
    output_table(headers, rows)

    if args.summary:
        print()
        total = len(results)
        print(c("建议操作:", "bold"))
        if stats.get("CLEAN", 0):
            print(f"  放行: {stats['CLEAN']} 个 ({stats['CLEAN'] * 100 // total}%)")
        if stats.get("SUSPICIOUS", 0):
            print(f"  审查: {stats['SUSPICIOUS']} 个 ({stats['SUSPICIOUS'] * 100 // total}%)")
        if stats.get("MALICIOUS", 0):
            print(f"  阻断: {stats['MALICIOUS']} 个 ({stats['MALICIOUS'] * 100 // total}%)")

    return 0


def cmd_report_batch(args):
    """独立的批量报告命令入口。"""
    fmt = _get_fmt(args)
    client = _client(args)
    return _cmd_report_batch(args, client, fmt)


def cmd_judge(args) -> int:
    fmt = _get_fmt(args)
    client = _client(args)
    md5 = args.md5.strip().lower()
    sha1 = args.sha1.strip().lower()

    if not md5 and not sha1:
        print_error("请指定 --md5 或 --sha1")
        return 1

    if md5 and not _validate_hash_md5(md5):
        print_error("无效的 MD5 格式 (需要 32 位十六进制)")
        return 1
    if sha1 and not _validate_hash_sha1(sha1):
        print_error("无效的 SHA1 格式 (需要 40 位十六进制)")
        return 1

    try:
        data = client.judge(md5=md5, sha1=sha1)
    except APIError as e:
        print_error(f"查询失败: {e.message}")
        return 1

    if fmt == "json":
        output_json(data)
        return 0
    if fmt == "yaml":
        output_yaml(data)
        return 0

    found = data.get("found", False)
    if not found:
        print_info(f"未找到匹配记录 (md5={md5 or sha1})")
        return 0

    tasks = data.get("tasks", [])
    print_success(f"找到 {len(tasks)} 条匹配记录")
    for t in tasks[:5]:
        tid = t.get("task_id", "")
        name = t.get("skill_name", "—")
        v = t.get("verdict", {})
        vr = v.get("result", "") if isinstance(v, dict) else (v or "")
        print(f"  {c(tid[:16] + '...', 'cyan')}  {name:20s}  {verdict_color(vr)}")
    if len(tasks) > 5:
        print(f"  ... 共 {len(tasks)} 条")
    return 0


def cmd_search(args) -> int:
    fmt = _get_fmt(args)
    client = _client(args)

    try:
        data = client.search(args.name)
    except APIError as e:
        print_error(f"搜索失败: {e.message}")
        return 1

    if fmt == "json":
        output_json(data)
        return 0
    if fmt == "yaml":
        output_yaml(data)
        return 0

    reports = data.get("scan_reports", [])
    total = data.get("total", 0)
    print_info(f"搜索 '{args.name}' — 共 {total} 条结果")

    if not reports:
        return 0

    headers = ["Task ID", "Skill Name", "Status", "Source", "Created"]
    rows = []
    for r in reports[:20]:
        rows.append([
            (r.get("task_id") or "")[:16] + "...",
            r.get("skill_name", "—"),
            r.get("status", "—"),
            r.get("source_type", "—"),
            (r.get("created_at") or "")[:19],
        ])
    output_table(headers, rows)
    return 0


def cmd_download(args) -> int:
    fmt = _get_fmt(args)
    client = _client(args)

    try:
        data = client.download(
            task_id=args.task_id,
            skill_name=args.skill_name,
            files_md5=args.files_md5,
            package_md5=args.package_md5,
            files_sha1=args.files_sha1,
            package_sha1=args.package_sha1,
        )
    except APIError as e:
        print_error(f"查询失败: {e.message}")
        return 1

    if fmt == "json":
        output_json(data)
        return 0
    if fmt == "yaml":
        output_yaml(data)
        return 0

    code = data.get("code", 200)
    if code == 300:
        items = data.get("items", [])
        print_warning(f"找到 {len(items)} 个不同版本，请指定 --task-id 下载:")
        headers = ["Task ID", "Skill Name", "MD5", "Source", "Created"]
        rows = []
        for it in items:
            rows.append([
                (it.get("task_id") or "")[:16] + "...",
                it.get("skill_name", "—"),
                (it.get("files_md5") or "")[:12] + "...",
                it.get("source_type", "—"),
                (it.get("created_at") or "")[:19],
            ])
        output_table(headers, rows)
        return 0

    url = data.get("download_url", "")
    print_success(f"下载链接已生成")
    print(f"  Skill:    {data.get('skill_name', '—')}")
    print(f"  Task ID:  {c(data.get('task_id', ''), 'cyan')}")
    print(f"  MD5:      {data.get('files_md5', '—')}")
    print(f"  SHA1:     {data.get('files_sha1', '—')}")
    print()
    print(f"  Download: {c(url, 'blue')}")
    return 0


def cmd_init(args) -> int:
    """首次运行向导。"""
    print()
    print(c("🛡️  Welcome to SafeSkill CLI!", "bold"))
    print()

    token = input("  Please enter your API Token: ").strip()
    if token:
        set_token(token)
        print_success("Token 已保存")

    fmt = input("  Default output format [json/table/pretty] (table): ").strip() or "table"
    set_config_value("output.format", fmt)

    print()
    print_success("配置完成！")
    print_info("试试: safeskill whoami")
    print_info("扫描: safeskill scan <file.zip>")
    return 0


def cmd_completion(args) -> int:
    """生成 Shell 补全脚本。"""
    shell = args.shell
    if shell == "bash":
        print('eval "$(register-python-argcomplete safeskill 2>/dev/null)"')
    elif shell == "zsh":
        print('eval "$(register-python-argcomplete safeskill 2>/dev/null)"')
    elif shell == "fish":
        print("# Fish completion for safeskill (add to ~/.config/fish/completions/safeskill.fish)")
        print("complete -c safeskill -n '__fish_use_subcommand' -a 'login logout whoami config scan report judge search download init'")
    return 0


# ═════════════════════════════════════════════════════════════════════════════
#  Main
# ═════════════════════════════════════════════════════════════════════════════

COMMANDS = {
    "login": cmd_login,
    "logout": cmd_logout,
    "whoami": cmd_whoami,
    "config": cmd_config,
    "scan": cmd_scan,
    "scan-url": cmd_scan_url,
    "report": cmd_report,
    "report-batch": cmd_report_batch,
    "judge": cmd_judge,
    "search": cmd_search,
    "download": cmd_download,
    "init": cmd_init,
    "completion": cmd_completion,
}


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    # 全局选项
    if args.no_color:
        set_color(False)
    if args.debug:
        logging.basicConfig(level=logging.DEBUG, format="%(levelname)s %(name)s: %(message)s")
    elif args.verbose:
        logging.basicConfig(level=logging.INFO, format="%(message)s")

    if not args.command:
        parser.print_help()
        return 0

    handler = COMMANDS.get(args.command)
    if not handler:
        print_error(f"未知命令: {args.command}")
        return 1

    try:
        return handler(args)
    except KeyboardInterrupt:
        print()
        return 130
    except APIError as e:
        if args.json or _get_fmt(args) == "json":
            output_json({"error": e.message, "code": e.code})
        else:
            print_error(f"{e.message}")
        # Exit code 语义化
        if e.code == 401:
            return 2
        if e.code == 403:
            return 2
        if e.code in (502, 503, 504):
            return 3
        return 1
    except Exception as e:
        if args.debug:
            import traceback
            traceback.print_exc()
        else:
            print_error(f"未预期的错误: {e}")
        return 1
