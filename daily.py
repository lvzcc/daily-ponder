#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
每日一问 —— 生成一道深度开放问题，推送到手机。

运行环境两种都支持：
  1. GitHub Actions : token / key 从环境变量读
  2. 本地测试        : 从 .secrets/pushplus.json 读 token，DeepSeek key 从环境变量读

纯标准库，无需 pip install。
"""
import json
import os
import random
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
HISTORY_FILE = ROOT / "history" / "questions.json"
LOCAL_SECRET = Path(r"D:\Deepseekworkspace\.secrets\pushplus.json")

TZ_CN = timezone(timedelta(hours=8))

DEEPSEEK_API = "https://api.deepseek.com/chat/completions"
PUSHPLUS_API = "https://www.pushplus.plus/send"

DOMAINS = [
    "哲学", "科学", "社会学", "经济学", "心理学",
    "历史", "技术伦理", "认知科学", "艺术", "政治哲学",
    "人类学", "语言学", "概率与决策", "建筑与空间",
]

MAX_HISTORY = 60  # 记住最近 60 条，用于去重


# ---------------------------------------------------------------- 历史记录
def load_history() -> dict:
    if HISTORY_FILE.exists():
        try:
            return json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"questions": []}


def save_history(data: dict) -> None:
    HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    HISTORY_FILE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )


# ---------------------------------------------------------------- 生成问题
PROMPT_TEMPLATE = """你是一位善于提出深刻问题的思想者。请提出**一道**能让人反复咀嚼的开放性问题。

今天是 {today}，这次的方向偏向：**{domain}**。

硬性要求：
1. **必须是开放性问题**——没有标准答案，不同立场的人会给出不同但都站得住的回答。
2. **必须拒绝平庸**——不要"人生的意义是什么"这类空泛大词，要具体、有张力、有抓手的。
3. **需要想一会儿**——读者看到后会停顿、会想反驳、会想补充。
4. **一个问题，不是一串问题**。不要在同一个问题里塞三个子问题。
5. 长度：25~70 字之间。

禁止：
- 是非题
- 常识题、知识题（有确定答案的）
- 鸡汤式提问
- 以下这些近期已经问过的问题（换个角度也不行）：
{recent}

输出**严格 JSON**，不要 markdown 代码块，不要任何解释文字：
{{"domain": "方向", "question": "问题本身", "hint": "一句 20 字以内的钩子，提示可以从哪个角度切入"}}
"""


def call_llm(prompt: str, retries: int = 3) -> dict:
    api_key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    if not api_key:
        raise SystemExit("[x] 缺少 DEEPSEEK_API_KEY")

    payload = {
        "model": os.environ.get("LLM_MODEL", "deepseek-chat"),
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 1.15,
        "max_tokens": 400,
    }
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")

    last_err = None
    for attempt in range(1, retries + 1):
        try:
            req = urllib.request.Request(
                DEEPSEEK_API,
                data=body,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {api_key}",
                },
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            text = data["choices"][0]["message"]["content"].strip()
            return parse_llm_json(text)
        except Exception as exc:  # noqa: BLE001
            last_err = exc
            print(f"[!] LLM 第 {attempt} 次失败: {exc}")
            time.sleep(5 * attempt)
    raise SystemExit(f"[x] LLM 调用最终失败: {last_err}")


def parse_llm_json(text: str) -> dict:
    """模型偶尔会包代码块，粗暴地抠出第一个 JSON 对象。"""
    text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.MULTILINE).strip()
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        raise ValueError(f"模型没返回 JSON: {text[:200]}")
    obj = json.loads(text[start : end + 1])
    for k in ("question",):
        if not obj.get(k):
            raise ValueError(f"缺少字段 {k}")
    obj.setdefault("domain", "杂")
    obj.setdefault("hint", "")
    return obj


# ---------------------------------------------------------------- 推送
def load_push_token() -> str:
    # 1) 环境变量（GitHub Actions）
    token = os.environ.get("PUSHPLUS_TOKEN", "").strip()
    if token:
        return token
    # 2) 本地文件（本机测试）
    if LOCAL_SECRET.exists():
        data = json.loads(LOCAL_SECRET.read_text(encoding="utf-8"))
        token = (data.get("token") or "").strip()
        if token and not token.startswith("PASTE_"):
            return token
    raise SystemExit("[x] 找不到 PushPlus token（环境变量 PUSHPLUS_TOKEN / 本地文件都没有）")


def push(title: str, content: str, retries: int = 3) -> dict:
    token = load_push_token()
    body = json.dumps(
        {"token": token, "title": title, "content": content, "template": "markdown"},
        ensure_ascii=False,
    ).encode("utf-8")

    last_err = None
    for attempt in range(1, retries + 1):
        try:
            req = urllib.request.Request(
                PUSHPLUS_API,
                data=body,
                headers={"Content-Type": "application/json; charset=utf-8"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                result = json.loads(resp.read().decode("utf-8"))
            if result.get("code") == 200:
                return result
            last_err = result
            print(f"[!] 推送第 {attempt} 次失败: {result}")
        except Exception as exc:  # noqa: BLE001
            last_err = exc
            print(f"[!] 推送第 {attempt} 次异常: {exc}")
        time.sleep(10 * attempt)
    raise SystemExit(f"[x] 推送最终失败: {last_err}")


# ---------------------------------------------------------------- 主流程
def main() -> int:
    now = datetime.now(TZ_CN)
    history = load_history()
    recent = history.get("questions", [])[-MAX_HISTORY:]

    # 幂等：同一天已经发过就跳过（防止双触发器重复）
    today = now.strftime("%Y-%m-%d")
    if any(q.get("date") == today for q in recent):
        print(f"[=] 今天（{today}）已经发过了，跳过。")
        return 0

    recent_text = "\n".join(f"- {q.get('question', '')}" for q in recent[-20:]) or "（暂无）"
    domain = random.choice(DOMAINS)

    prompt = PROMPT_TEMPLATE.format(
        today=today, domain=domain, recent=recent_text
    )
    item = call_llm(prompt)
    item["date"] = today

    print(f"[+] 今日问题（{item['domain']}）：{item['question']}")

    title = f"今日一问 · {item['domain']}"
    content = (
        f"**{item['question']}**\n\n"
        + (f"> {item['hint']}\n\n" if item.get("hint") else "")
        + f"<sub>{now.strftime('%Y-%m-%d')}</sub>"
    )

    result = push(title, content)
    print(f"[+] 推送成功: {result.get('msg')}")

    history.setdefault("questions", []).append(item)
    history["questions"] = history["questions"][-200:]
    save_history(history)
    print("[+] 历史已保存")
    return 0


if __name__ == "__main__":
    sys.exit(main())
