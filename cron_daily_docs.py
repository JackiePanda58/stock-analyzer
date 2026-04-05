#!/usr/bin/env python3
"""
cron_daily_docs.py — 每天 23:30 自动更新项目文档并发送飞书通知
Usage: python3 cron_daily_docs.py
"""
import subprocess
from datetime import datetime, date
import sys
import os
import re

sys.path.insert(0, "/root/stock-analyzer")
os.chdir("/root/stock-analyzer")

TODAY = date.today().isoformat()
USER_OPEN_ID = "ou_fa14240ad1821e000cf72ccaa09addb5"

def run(cmd, check=True):
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if check and r.returncode != 0:
        print(f"[ERROR] cmd: {cmd}\n{r.stderr}")
    return r.stdout.strip(), r.returncode

def get_git_changes():
    """获取今日变更 commit 列表"""
    out, _ = run(
        f"git log --oneline --since='{TODAY} 00:00:00' --until='{TODAY} 23:59:59' 2>/dev/null",
        check=False
    )
    if not out:
        out, _ = run("git log --oneline -5 2>/dev/null", check=False)
    return out or "无新 commit"

def load_env():
    env = {}
    env_path = "/root/stock-analyzer/.env"
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    env[k.strip()] = v.strip().strip('"').strip("'")
    return env

def update_changelog():
    """在 CHANGELOG.md 插入/更新 [Unreleased] 块"""
    changelog = "/root/stock-analyzer/CHANGELOG.md"
    with open(changelog) as f:
        content = f.read()

    marker = f"## [Unreleased] - {TODAY}"
    if "## [Unreleased]" in content:
        return False  # 今日已更新

    new_block = f"""## [Unreleased] - {TODAY}

### Added
- （每日自动更新占位）

"""
    # 插在 [1.1.0] 后面
    new_content = re.sub(
        r'(## \[1\.1\.0\] - 2026-04-05)',
        rf'\1\n\n{new_block}',
        content,
        count=1
    )
    if new_content == content:
        # 如果没找到 [1.1.0]，插在最前面
        new_content = new_block + content

    with open(changelog, "w") as f:
        f.write(new_content)
    return True

def update_readme_date():
    """更新 README 最后同步时间"""
    readme = "/root/stock-analyzer/README.md"
    marker = f"*本文档自动同步：{TODAY}*"
    if not os.path.exists(readme):
        return False
    with open(readme) as f:
        content = f.read()
    new_content = re.sub(r"\*本文档自动同步：\d{4}-\d{2}-\d{2}\*", marker, content)
    if new_content != content:
        with open(readme, "w") as f:
            f.write(new_content)
        return True
    return False

def git_commit():
    """自动 git add + commit"""
    run("git add -A 2>/dev/null", check=False)
    out, _ = run("git diff --cached --stat 2>/dev/null", check=False)
    if not out:
        return False, "无变更"
    msg = f"docs: auto-sync documentation {TODAY}"
    run(f"git commit -m '{msg}' 2>/dev/null", check=False)
    return True, out

def send_feishu_message(text: str):
    """通过飞书应用 API 发送消息给用户"""
    env = load_env()
    app_id = env.get("FEISHU_APP_ID", "cli_a93566e488b81bce")
    app_secret = env.get("FEISHU_APP_SECRET", "Z4viJJFmVzrywinuZiVhHfVHZBT1YbBm")

    import json, urllib.request, urllib.error

    # 1. 获取 tenant_access_token
    try:
        token_url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
        token_req = urllib.request.Request(
            token_url,
            data=json.dumps({"app_id": app_id, "app_secret": app_secret}).encode(),
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(token_req, timeout=10) as resp:
            token_data = json.loads(resp.read())
        token = token_data.get("tenant_access_token")
        if not token:
            print(f"[WARN] No tenant_access_token: {token_data}")
            return False
    except Exception as e:
        print(f"[ERROR] Failed to get tenant_access_token: {e}")
        return False

    # 2. 发送消息
    try:
        msg_url = "https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=open_id"
        msg_body = {
            "receive_id": USER_OPEN_ID,
            "msg_type": "text",
            "content": json.dumps({"text": text})
        }
        msg_req = urllib.request.Request(
            msg_url,
            data=json.dumps(msg_body).encode(),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {token}"
            },
            method="POST"
        )
        with urllib.request.urlopen(msg_req, timeout=10) as resp:
            result = json.loads(resp.read())
        return result.get("code") == 0
    except Exception as e:
        print(f"[ERROR] Failed to send Feishu message: {e}")
        return False

def main():
    print(f"[{datetime.now().isoformat()}] Starting daily docs sync...")

    changelog_updated = update_changelog()
    readme_updated = update_readme_date()
    committed, result = git_commit()
    changes = get_git_changes()

    summary = (
        f"📋 TradingAgents-CN 文档同步完成\n"
        f"📅 {TODAY} 23:30\n"
        f"📝 今日变更：\n{changes[:400]}"
    )
    sent = send_feishu_message(summary)

    print(f"  changelog_updated: {changelog_updated}")
    print(f"  readme_updated: {readme_updated}")
    print(f"  git_committed: {committed} — {result[:100] if result else ''}")
    print(f"  feishu_notified: {sent}")
    print(f"[{datetime.now().isoformat()}] Done.")

if __name__ == "__main__":
    main()
