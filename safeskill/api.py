# -*- coding: utf-8 -*-
"""HTTP API client for SafeSkill backend."""

import os
import time
import json
import hashlib
import logging
from typing import Any, Dict, List, Optional, Tuple

import requests

from safeskill.config import get_token, get_base_url, load_config

log = logging.getLogger("safeskill")


class APIError(Exception):
    """API 调用错误。"""
    def __init__(self, code: int, message: str, detail: str = ""):
        self.code = code
        self.message = message
        self.detail = detail
        super().__init__(f"[{code}] {message}")


class Client:
    """SafeSkill API 客户端。"""

    def __init__(self, token: str = "", base_url: str = ""):
        self.token = token or get_token()
        self.base_url = (base_url or get_base_url()).rstrip("/")
        cfg = load_config()
        api_cfg = cfg.get("api") or {}
        self.timeout = api_cfg.get("timeout", 30)
        self.retry_count = api_cfg.get("retry_count", 3)
        self.retry_delay = api_cfg.get("retry_delay", 2)
        self.session = requests.Session()
        self.session.headers.update({
            "X-API-Token": self.token,
            "User-Agent": "SafeSkill-CLI/1.0",
        })

    def _url(self, path: str) -> str:
        return f"{self.base_url}/openapi/v1{path}"

    def _request(self, method: str, path: str, **kwargs) -> Dict[str, Any]:
        """带重试的 HTTP 请求。"""
        url = self._url(path)
        kwargs.setdefault("timeout", self.timeout)

        last_err = None
        for attempt in range(1, self.retry_count + 1):
            try:
                log.debug("[HTTP] %s %s attempt=%d", method, url, attempt)
                resp = self.session.request(method, url, **kwargs)
                data = resp.json()

                # API 层错误码
                code = data.get("code", resp.status_code)
                if resp.status_code >= 400 or (isinstance(code, int) and code >= 400):
                    err_msg = data.get("error") or data.get("message") or resp.text[:200]
                    raise APIError(code, err_msg)

                return data

            except requests.exceptions.ConnectionError as e:
                last_err = APIError(503, f"连接失败: {self.base_url}", str(e))
                if attempt < self.retry_count:
                    time.sleep(self.retry_delay)
            except requests.exceptions.Timeout as e:
                last_err = APIError(504, f"请求超时 ({self.timeout}s)", str(e))
                if attempt < self.retry_count:
                    time.sleep(self.retry_delay)
            except APIError:
                raise
            except Exception as e:
                raise APIError(500, "请求异常", str(e))

        raise last_err  # type: ignore

    # ── 认证 ─────────────────────────────────────────────────────────────────

    def whoami(self) -> Dict[str, Any]:
        """查询当前 Token 状态（通过 query 接口验证）。"""
        return self._request("GET", "/query", params={"name": "__whoami_check__"})

    # ── 扫描投递 ─────────────────────────────────────────────────────────────

    def scan_file(self, filepath: str, skill_name: str = "", policy: str = "balanced",
                  enable_llm: bool = True, enable_qax_ti: bool = True,
                  callback_url: str = "", is_public: bool = True) -> Dict[str, Any]:
        """上传文件扫描。"""
        with open(filepath, "rb") as f:
            files = {"file": (os.path.basename(filepath), f)}
            data = {
                "policy": policy,
                "enable_llm": str(enable_llm).lower(),
                "enable_qax_ti": str(enable_qax_ti).lower(),
                "is_public": str(is_public).lower(),
            }
            if skill_name:
                data["skill_name"] = skill_name
            if callback_url:
                data["callback_url"] = callback_url
            return self._request("POST", "/submit", files=files, data=data)

    def scan_url(self, url: str, source_type: str = "auto", skill_name: str = "",
                 policy: str = "balanced", enable_llm: bool = True,
                 enable_qax_ti: bool = True, callback_url: str = "",
                 is_public: bool = True) -> Dict[str, Any]:
        """URL 投递扫描。"""
        body = {
            "url": url,
            "policy": policy,
            "enable_llm": enable_llm,
            "enable_qax_ti": enable_qax_ti,
            "is_public": is_public,
        }
        if source_type != "auto":
            body["source_type"] = source_type
        if skill_name:
            body["skill_name"] = skill_name
        if callback_url:
            body["callback_url"] = callback_url
        return self._request("POST", "/submit-url", json=body)

    # ── 报告查询 ─────────────────────────────────────────────────────────────

    def report(self, task_id: str) -> Dict[str, Any]:
        """查询单个报告。"""
        return self._request("GET", "/report", params={"task_id": task_id})

    def report_batch(self, task_ids):
        # type: (List[str]) -> Dict[str, Any]
        """批量查询报告。"""
        return self._request("POST", "/report/batch", json={"task_ids": task_ids})

    # ── 研判查询 ─────────────────────────────────────────────────────────────

    def judge(self, md5: str = "", sha1: str = "") -> Dict[str, Any]:
        """根据 MD5/SHA1 查询研判结果。"""
        if md5:
            return self._request("GET", "/judge", params={"md5": md5})
        # SHA1 暂时用 md5 参数传（后端兼容）
        return self._request("GET", "/judge", params={"md5": sha1})

    # ── 搜索 ─────────────────────────────────────────────────────────────────

    def search(self, name: str) -> Dict[str, Any]:
        """按 Skill 名称搜索。"""
        return self._request("GET", "/query", params={"name": name})

    # ── 下载 ─────────────────────────────────────────────────────────────────

    def download(self, task_id: str = "", skill_name: str = "",
                 files_md5: str = "", package_md5: str = "",
                 files_sha1: str = "", package_sha1: str = "") -> Dict[str, Any]:
        """下载资源包。"""
        params = {}
        if task_id:
            params["task_id"] = task_id
        elif files_md5:
            params["files_md5"] = files_md5
        elif package_md5:
            params["package_md5"] = package_md5
        elif files_sha1:
            params["files_sha1"] = files_sha1
        elif package_sha1:
            params["package_sha1"] = package_sha1
        elif skill_name:
            params["skill_name"] = skill_name
        return self._request("GET", "/download", params=params)

    # ── 工具方法 ─────────────────────────────────────────────────────────────

    @staticmethod
    def compute_file_hashes(filepath):
        # type: (str) -> Tuple[str, str]
        """计算文件的 MD5 和 SHA1。"""
        md5 = hashlib.md5()
        sha1 = hashlib.sha1()
        with open(filepath, "rb") as f:
            while True:
                chunk = f.read(8192)
                if not chunk:
                    break
                md5.update(chunk)
                sha1.update(chunk)
        return md5.hexdigest(), sha1.hexdigest()
