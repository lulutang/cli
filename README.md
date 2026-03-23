# SafeSkill CLI

Skill 安全扫描命令行工具 — 对接 [SafeSkill](https://safeskill.qianxin.com/) 平台。

## 系统要求

- **Python**: >= 3.6（支持 3.6 / 3.7 / 3.8 / 3.9 / 3.10 / 3.11 / 3.12）
- **依赖**: `requests` >= 2.20, `pyyaml` >= 5.0
- **系统**: Linux / macOS / Windows

## 安装

```bash
# PyPI 安装
pip3 install safeskill-cli

# 本地安装
cd safeskill-cli
pip3 install -e . # 如果本地已经安装 可以这样继续安装 pip3 install -e . --force-reinstall --no-deps


# 验证安装
safeskill --version
```

## 快速开始

```bash
# 1. 首次使用（交互式向导）
safeskill init

# 2. 或直接设置 Token（由威胁情报中心授权开通）
safeskill login --token YOUR_TOKEN

# 3. 验证 Token
safeskill whoami

# 4. 扫描文件
safeskill scan my-skill.zip

# 5. 查看报告（等待扫描完成）
safeskill report <task_id> --wait

# 6. 通过 URL 扫描 GitHub 项目
safeskill scan-url https://github.com/owner/repo/tree/main/skills/xxx

# 7. 通过 URL 扫描 GitHub 项目
safeskill scan-url https://github.com/owner/repo/tree/main/skills/xxx

# 7. 下载 Skill 资源包（需 download 权限）
safeskill download --task-id <task_id>
safeskill download --skill-name "tavily-search"
safeskill download --files-md5 9ac6e56fae6b2e619a8c4815b4dfa3a8
```

---

## API 接口对照表

CLI 完整对接 SafeSkill 全部 7 个 OpenAPI 接口：

| 序号 | API 接口 | CLI 命令 | 所需权限 |
|:----:|---------|---------|:--------:|
| 1 | `GET /openapi/v1/query` | `safeskill search <name>` | query |
| 2 | `POST /openapi/v1/submit` | `safeskill scan <file>` | submit |
| 3 | `POST /openapi/v1/submit-url` | `safeskill scan-url <url>` | submit |
| 4 | `GET /openapi/v1/judge` | `safeskill judge --md5/--sha1` | query |
| 5 | `GET /openapi/v1/report` | `safeskill report <task_id>` | query |
| 6 | `POST /openapi/v1/report/batch` | `safeskill report-batch <ids>` | query |
| 7 | `GET /openapi/v1/download` | `safeskill download --task-id/--name/--md5/--sha1` | download |

---

## 完整命令参考

### 认证管理

```bash
# 设置 Token
safeskill login --token YOUR_TOKEN

# 查看当前认证状态
safeskill whoami

# 清除 Token
safeskill logout
```

### 配置管理

```bash
# 查看所有配置
safeskill config get

# 设置 API 地址
safeskill config set api.base-url https://safeskill.qianxin.com

# 设置默认输出格式
safeskill config set output.format json

# 设置扫描策略
safeskill config set scan.default-policy strict

# 恢复默认配置
safeskill config reset
```

### 扫描投递（接口二、三）

```bash
# 上传文件扫描（接口二：POST /openapi/v1/submit）
safeskill scan my-skill.zip
safeskill scan my-skill.zip --name "custom-name" --policy strict
safeskill scan my-skill.zip --enable-llm true --enable-qax-ti true
safeskill scan my-skill.zip --callback-url "https://hook.example.com"

# URL 投递扫描（接口三：POST /openapi/v1/submit-url）
safeskill scan-url https://github.com/owner/repo/tree/main/skills/xxx
safeskill scan-url https://clawhub.ai/user/skill-name
safeskill scan-url https://skillsmp.com/skills/skill-name
safeskill scan-url https://skills.rest/skill/skill-name
safeskill scan-url https://example.com/skill.zip --source-type direct
```

**扫描参数：**

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--name` | 自动提取 | Skill 名称，留空从 SKILL.md 提取 |
| `--policy` | balanced | 扫描策略：`strict` / `balanced` / `permissive` |
| `--enable-llm` | true | 是否启用 LLM 语义分析 |
| `--enable-qax-ti` | true | 是否启用威胁情报检测 |
| `--callback-url` | — | 扫描完成回调 URL |
| `--is-public` | true | 是否公开展示 |
| `--source-type` | auto | URL 来源类型（仅 URL 扫描）：`github` / `clawhub` / `skillsmp` / `skills_rest` / `gitlab` / `direct` |

### 报告查询（接口五、六）

```bash
# 单任务报告（接口五：GET /openapi/v1/report）
safeskill report <task_id>
safeskill report <task_id> --verbose          # 含 Findings 详情
safeskill report <task_id> --json             # JSON 格式
safeskill report <task_id> --wait             # 轮询等待完成
safeskill report <task_id> --wait --timeout 600

# 批量报告（接口六：POST /openapi/v1/report/batch）
safeskill report-batch <id1> <id2> <id3>
safeskill report-batch --task-ids-file tasks.txt    # 从文件读取
safeskill report-batch <id1> <id2> --summary        # 汇总统计
```

### MD5/SHA1 研判查询（接口四）

```bash
# 接口四：GET /openapi/v1/judge
safeskill judge --md5 a5d5c01672e068f59ff621bb555bcf82
safeskill judge --sha1 e5b7c2d8a1f34690b2c8d7e4a5f12345abcde678
safeskill judge --md5 a5d5c01672e... --json
```

**用途：** 上传前检查文件是否已扫描，避免重复提交。

### 搜索历史报告（接口一）

```bash
# 接口一：GET /openapi/v1/query
safeskill search "tavily-search"
safeskill search "tavily" --json
safeskill search "apple-notes" --verbose
```

### 下载资源包（接口七）

```bash
# 接口七：GET /openapi/v1/download（需 download 权限）
safeskill download --task-id a1b2c3d4e5f678901234567890abcdef
safeskill download --skill-name "tavily-search"
safeskill download --files-md5 9ac6e56fae6b2e619a8c4815b4dfa3a8
safeskill download --package-md5 ed7f395cd05373eb250add2e62a8b4be
safeskill download --files-sha1 ff522a43fa3d79b7003f8875f5523ec364f1dcb5
safeskill download --package-sha1 c30fb674ad54f353a9bfeaccb5967390a18352b6
```

**参数优先级：** `task_id` > `files_md5` > `package_md5` > `files_sha1` > `package_sha1` > `skill_name`

---

## 输出格式

所有命令支持 4 种输出格式：

```bash
safeskill report <task_id> --output json      # JSON（适合脚本/Agent）
safeskill report <task_id> --output yaml      # YAML（人类可读）
safeskill report <task_id> --output table     # 终端表格（默认）
safeskill report <task_id> --output pretty    # 美化详细输出
safeskill report <task_id> --json             # --json 快捷方式
```

---

## 环境变量

| 变量 | 说明 | 优先级 |
|------|------|:------:|
| `SAFESKILL_TOKEN` | API Token | 高于配置文件 |
| `SAFESKILL_API_URL` | API 地址 | 高于配置文件 |
| `SAFESKILL_CONFIG_DIR` | 配置文件目录（默认 `~/.config/safeskill`） | — |

---

## 配置文件

位置: `~/.config/safeskill/config.yaml`

```yaml
api:
  base_url: https://safeskill.qianxin.com
  timeout: 30            # 请求超时秒数
  retry_count: 3         # 失败重试次数
  retry_delay: 2         # 重试间隔秒数

output:
  format: table          # json | yaml | table | pretty
  color: true            # 是否启用彩色输出

auth:
  token: "<encrypted>"   # Token 加密存储

scan:
  default_policy: balanced  # strict | balanced | permissive
  enable_llm: true
  enable_qax_ti: true
```

---

## AI Agent 集成

### JSON-First 输出

```bash
safeskill scan skill.zip --json --non-interactive
safeskill report <task_id> --wait --json
safeskill judge --md5 abc... --json
```

### Exit Code 语义化

| Exit Code | 含义 | 场景 |
|:---------:|------|------|
| 0 | 成功 / CLEAN | 正常完成 |
| 1 | 错误 / MALICIOUS | 参数错误、API 错误、恶意裁决 |
| 2 | 认证失败 | Token 缺失或过期 |
| 3 | 网络失败 | 连接超时或不可达 |
| 4 | 文件错误 | 文件不存在或格式不支持 |

### Agent 调用示例（Python）

```python
import subprocess, json

# 投递扫描
result = subprocess.run(
    ["safeskill", "scan", "skill.zip", "--json"],
    capture_output=True, text=True
)
task = json.loads(result.stdout)
task_id = task["task_id"]

# 等待报告
result = subprocess.run(
    ["safeskill", "report", task_id, "--wait", "--json"],
    capture_output=True, text=True
)
report = json.loads(result.stdout)
verdict = report.get("report", {}).get("verdict", {}).get("result", "")

if verdict == "MALICIOUS":
    print("BLOCKED!")
elif verdict == "SUSPICIOUS":
    print("NEEDS REVIEW")
else:
    print("SAFE")
```

### CI/CD 集成（GitHub Actions）

```yaml
- name: Scan Skill
  run: |
    pip install safeskill-cli
    safeskill login --token ${{ secrets.SAFESKILL_TOKEN }}
    safeskill scan ./my-skill.zip --json > scan.json
    TASK_ID=$(python -c "import json; print(json.load(open('scan.json'))['task_id'])")
    safeskill report $TASK_ID --wait --json > report.json
```

---

## Shell 自动补全

```bash
# Bash
source <(safeskill completion bash)

# Zsh
source <(safeskill completion zsh)

# Fish
safeskill completion fish > ~/.config/fish/completions/safeskill.fish
```

---

## 全局选项

| 选项 | 说明 |
|------|------|
| `--output json/yaml/table/pretty` | 输出格式 |
| `--json` | JSON 输出快捷方式 |
| `--verbose, -v` | 详细输出 |
| `--debug` | 调试模式（打印 HTTP 请求/响应） |
| `--quiet, -q` | 静默模式 |
| `--no-color` | 禁用彩色输出 |
| `--non-interactive` | 非交互模式 |
| `--token TOKEN` | 临时指定 Token |
| `--api-url URL` | 临时指定 API 地址 |
| `--version` | 显示版本号 |

---

## 联系方式

- 📧 邮箱: ti_support@qianxin.com
- 🔗 Web: https://safeskill.qianxin.com/
- 📝 申请对接需提供: Product Name + Contact Email

---

**版本**: v1.1.0 | **更新日期**: 2026-03-16
