# -*- coding: utf-8 -*-
"""Configuration and token management."""

import os
import base64
import hashlib
import json
from pathlib import Path
from typing import Any, Optional

import yaml

CONFIG_DIR = Path(os.environ.get("SAFESKILL_CONFIG_DIR", os.path.expanduser("~/.config/safeskill")))
CONFIG_FILE = CONFIG_DIR / "config.yaml"

DEFAULT_CONFIG = {
    "api": {
        "base_url": "https://safeskill.qianxin.com",
        "timeout": 30,
        "retry_count": 3,
        "retry_delay": 2,
    },
    "output": {
        "format": "table",
        "color": True,
    },
    "auth": {
        "token": "",
    },
    "scan": {
        "default_policy": "balanced",
        "enable_llm": True,
        "enable_qax_ti": True,
    },
}

# 简单的混淆密钥（非高安全加密，仅防止明文泄露）
_OBFUSCATE_KEY = b"safeskill-cli-2026"


def _obfuscate(plain: str) -> str:
    """简单 XOR 混淆 + base64 编码，防止明文存储。"""
    key = hashlib.sha256(_OBFUSCATE_KEY).digest()
    data = plain.encode("utf-8")
    xored = bytes(d ^ key[i % len(key)] for i, d in enumerate(data))
    return base64.b64encode(xored).decode("ascii")


def _deobfuscate(encoded: str) -> str:
    """反混淆。"""
    try:
        key = hashlib.sha256(_OBFUSCATE_KEY).digest()
        xored = base64.b64decode(encoded)
        data = bytes(d ^ key[i % len(key)] for i, d in enumerate(xored))
        return data.decode("utf-8")
    except Exception:
        return encoded  # fallback：可能是明文


def load_config() -> dict:
    """加载配置文件，不存在则返回默认配置。"""
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            # 合并默认值
            merged = _deep_merge(DEFAULT_CONFIG.copy(), data)
            return merged
        except Exception:
            pass
    return DEFAULT_CONFIG.copy()


def save_config(cfg: dict) -> None:
    """保存配置到文件。"""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        yaml.dump(cfg, f, default_flow_style=False, allow_unicode=True)
    os.chmod(CONFIG_FILE, 0o600)


def get_token() -> str:
    """获取 Token，优先级：环境变量 > 配置文件。"""
    env_token = os.environ.get("SAFESKILL_TOKEN", "").strip()
    if env_token:
        return env_token
    cfg = load_config()
    stored = (cfg.get("auth") or {}).get("token", "")
    if stored:
        return _deobfuscate(stored)
    return ""


def set_token(token: str) -> None:
    """加密存储 Token。"""
    cfg = load_config()
    if "auth" not in cfg:
        cfg["auth"] = {}
    cfg["auth"]["token"] = _obfuscate(token)
    save_config(cfg)


def clear_token() -> None:
    """清除存储的 Token。"""
    cfg = load_config()
    if "auth" in cfg:
        cfg["auth"]["token"] = ""
    save_config(cfg)


def get_base_url() -> str:
    """获取 API 基础 URL。"""
    env_url = os.environ.get("SAFESKILL_API_URL", "").strip()
    if env_url:
        return env_url.rstrip("/")
    cfg = load_config()
    return ((cfg.get("api") or {}).get("base_url") or DEFAULT_CONFIG["api"]["base_url"]).rstrip("/")


def get_config_value(key: str) -> Any:
    """通过点分路径获取配置值，如 api.timeout。"""
    cfg = load_config()
    parts = key.split(".")
    node = cfg
    for p in parts:
        p_underscore = p.replace("-", "_")
        if isinstance(node, dict):
            node = node.get(p_underscore, node.get(p))
        else:
            return None
    return node


def set_config_value(key: str, value: str) -> None:
    """通过点分路径设置配置值。"""
    cfg = load_config()
    parts = key.replace("-", "_").split(".")
    node = cfg
    for p in parts[:-1]:
        if p not in node or not isinstance(node[p], dict):
            node[p] = {}
        node = node[p]
    # 类型推断
    if value.lower() in ("true", "false"):
        node[parts[-1]] = value.lower() == "true"
    elif value.isdigit():
        node[parts[-1]] = int(value)
    else:
        try:
            node[parts[-1]] = float(value)
        except ValueError:
            node[parts[-1]] = value
    save_config(cfg)


def _deep_merge(base: dict, override: dict) -> dict:
    """递归合并字典。"""
    result = base.copy()
    for k, v in override.items():
        if k in result and isinstance(result[k], dict) and isinstance(v, dict):
            result[k] = _deep_merge(result[k], v)
        else:
            result[k] = v
    return result
