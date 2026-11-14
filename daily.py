#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
睡醒消息 —— 每天两推送：

  ①「第 N-1 期 · 理解」   对上一期问题的理解（不给答案，只给张力和思考维度）
  ②「第 N 期 · 问题」     今天的新问题（具体场景 + 真实取舍）

设计目标（用户指定）：
  1. 结合实际 —— 具体身份、数字、约束；形式可以是一段场景、一个小故事、一段对话
  2. 开放 —— 两个选项都有道理，没有标准答案
  3. 隔天回应 —— 第二天给出"理解"，但不给答案
  4. 按期数编号 —— 第 1 期、第 2 期……可以按编号回看
  5. 篇幅不设限 —— 由问题本身的复杂度决定，不许灌水

运行环境两种都支持：
  1. GitHub Actions : token / key 从环境变量读
  2. 本地测试        : 从 .secrets/pushplus.json 读 token

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

LETTER = "睡醒消息"

DOMAINS = [
    "商业决策", "职场博弈", "人际边界", "消费与取舍",
    "时间与精力分配", "团队管理", "谈判与让步", "风险与收益",
    "家庭与责任", "道德困境", "信息与判断", "习惯与自律",
    "技术选择", "教育与成长", "健康与代价", "承诺与信用",
    "朋友之间", "金钱观", "面子与里子", "长期与短期",
    "陌生人之间", "规则与变通", "失去与止损", "信任的边界",
]


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


def normalize_issues(questions: list) -> None:
    """给没有期号的老记录补上期号（按顺序），保证编号连续。"""
    nxt = 1
    for q in questions:
        if not q.get("issue"):
            q["issue"] = nxt
        nxt = max(nxt, int(q["issue"])) + 1


def next_issue(questions: list) -> int:
    return max((int(q.get("issue") or 0) for q in questions), default=0) + 1


# ---------------------------------------------------------------- 通用 LLM
def _chat(prompt: str, temperature: float, max_tokens: int, retries: int = 3) -> str:
    api_key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    if not api_key:
        raise SystemExit("[x] 缺少 DEEPSEEK_API_KEY")

    body = json.dumps(
        {
            "model": os.environ.get("LLM_MODEL", "deepseek-chat"),
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature,
            "max_tokens": max_tokens,
        },
        ensure_ascii=False,
    ).encode("utf-8")

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
            with urllib.request.urlopen(req, timeout=120) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            return data["choices"][0]["message"]["content"].strip()
        except Exception as exc:  # noqa: BLE001
            last_err = exc
            print(f"[!] LLM 第 {attempt} 次失败: {exc}")
            time.sleep(5 * attempt)
    raise SystemExit(f"[x] LLM 调用最终失败: {last_err}")


# ---------------------------------------------------------------- ① 出题
PROMPT_TEMPLATE = """你擅长从真实处境里提炼问题。请设计**一道**有具体场景的开放性问题。

今天是 {today}，这次方向偏向：**{domain}**。

## 结构

**A. 场景**
一个具体、能想象出画面的处境。必须有：
- 一个真实的身份（谁，什么角色）
- 具体数字或硬约束（多少钱、多少时间、多大代价、几个人）
- 一个真实的取舍点（两条路都有代价）

形式随意：一段自述、一个小故事、一段对话、一个数字的处境，都可以。
**必须落在普通人可能遇到的事上**，不要飘到宏大叙事里去。

**B. 问题**
把取舍抛出来。形式是"你会怎么选 / 你怎么看"。

## 篇幅

**不设上限。** 由题目本身决定：
- 通常 100~400 字够用
- 如果这个处境本身值得展开（比如需要交代几方关系、前因后果），写到 800~1500 字也可以
- **但绝不许灌水凑长度**。多一个字都必须有信息量。

## 硬性要求

1. **必须有数字和场景**。没有具体处境的题一律不合格。
2. **两个选项都要有道理**。一眼能看出正确答案的题就废了。
3. **要让人停下来想**。不同的人会给出不同、但都站得住的回答。
4. 贴近普通人可能遇到的事：工作中的决定、钱怎么花、关系怎么处、时间怎么分配。

## 明确禁止

- ❌ 宏大叙事：人类命运、文明走向、AI 取代人类、宇宙意义
- ❌ 没有场景的哲学空问（"什么是幸福"这种）
- ❌ 是非题、知识题（有确定答案的）
- ❌ 说教式提问（"我们应该如何成为一个更好的人"）
- ❌ 近期已经问过的题（换个说法也不行）：
{recent}
- ❌ 最近刚用过的方向，本轮必须换一个完全不同的领域：
{recent_domains}

## 合格范例（照着这个颗粒度写）

场景：你在一家外贸公司负责报价。客户目标价 1.2，报这个价你不亏不赚。老合作工厂成本 1.4，交期稳、质量好；新工厂报 1.0，但你没合作过，产能和质量都不清楚。客户三天内要答复。
问题：你会用哪家工厂的成本去报这个价？为什么？

## 输出

严格 JSON，不要 markdown 代码块，不要任何解释文字：
{{"domain": "方向", "scenario": "场景描述", "question": "问题本身", "hint": "一句 20 字以内的钩子，提示可以从哪个角度切入"}}
"""


def generate_question(domain: str, recent_text: str, recent_domains_text: str, today: str) -> dict:
    prompt = PROMPT_TEMPLATE.format(
        today=today,
        domain=domain,
        recent=recent_text,
        recent_domains=recent_domains_text,
    )
    raw = _chat(prompt, temperature=1.2, max_tokens=3000)
    return parse_question_json(raw)


def parse_question_json(text: str) -> dict:
    text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.MULTILINE).strip()
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        raise ValueError(f"模型没返回 JSON: {text[:200]}")
    obj = json.loads(text[start : end + 1])
    for k in ("scenario", "question"):
        if not obj.get(k):
            raise ValueError(f"缺少字段 {k}")
    obj.setdefault("domain", "杂")
    obj.setdefault("hint", "")
    return obj


# ---------------------------------------------------------------- ② 写理解
UNDERSTAND_TEMPLATE = """下面是我之前给出的一道题。请你写一段「理解」——**不是答案**。

## 题目

{scene_block}

## 要求

1. **不站队、不给结论。** 不要出现"应该选 A""A 更合理"这类判断。
2. **点出真正的张力**：这两个选项各自在赌什么？放弃的那条路，代价具体是什么？
3. **给 2~4 个思考维度**，例如：沉没成本、机会成本、时间尺度、可逆性、面子与里子、信息缺口、最坏情况的承受力、这件事对谁负责。
4. **指出题目里最容易被忽略的那个变量**——数字背后的东西。
5. **语气像朋友聊天**，不要教科书腔，不要写"本题考察……"。
6. **结尾不要总结**，留一句话或一个反向追问，把思考推回去。

## 篇幅

**不设上限。** 这道题值得深挖就写深，通常 300~800 字；如果它牵涉的层面多，写到 1500 字以上也可以。
**但绝不许灌水。** 不重复题面，不堆砌术语，每一句都要推进理解。

直接输出正文，不要 JSON，不要标题，不要 markdown 代码块。
"""


def generate_understanding(item: dict) -> str:
    scenario = (item.get("scenario") or "").strip()
    question = (item.get("question") or "").strip()
    if scenario:
        scene_block = f"场景：{scenario}\n\n问题：{question}"
    else:
        scene_block = f"问题：{question}"
    prompt = UNDERSTAND_TEMPLATE.format(scene_block=scene_block)
    return _chat(prompt, temperature=1.0, max_tokens=4000).strip()


# ---------------------------------------------------------------- 推送
def load_push_token() -> str:
    token = os.environ.get("PUSHPLUS_TOKEN", "").strip()
    if token:
        return token
    if LOCAL_SECRET.exists():
        data = json.loads(LOCAL_SECRET.read_text(encoding="utf-8"))
        token = (data.get("token") or "").strip()
        if token and not token.startswith("PASTE_"):
            return token
    raise SystemExit("[x] 找不到 PushPlus token")


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
            with urllib.request.urlopen(req, timeout=60) as resp:
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


# ---------------------------------------------------------------- 组装两条消息
def build_understanding_content(item: dict, understanding: str) -> str:
    parts = [
        "**题目回顾**",
        item.get("scenario", ""),
        f"> {item.get('question', '')}",
        "---",
        "**我的理解**",
        understanding,
        f"<sub>{LETTER} · 第 {item.get('issue')} 期</sub>",
    ]
    return "\n\n".join(p for p in parts if p != "")


def build_question_content(item: dict) -> str:
    parts = [
        item.get("scenario", ""),
        f"> {item.get('question', '')}",
    ]
    if item.get("hint"):
        parts.append(f"<sub>💡 {item['hint']}</sub>")
    parts.append(f"<sub>{LETTER} · 第 {item.get('issue')} 期 · {item.get('date', '')}</sub>")
    return "\n\n".join(p for p in parts if p != "")


# ---------------------------------------------------------------- 主流程
def main() -> int:
    now = datetime.now(TZ_CN)
    today = now.strftime("%Y-%m-%d")

    history = load_history()
    questions = history.setdefault("questions", [])
    normalize_issues(questions)

    # 幂等：今天已经出过题就跳过（防止重复推送）
    if any(q.get("date") == today for q in questions):
        print(f"[=] 今天（{today}）已经发过了，跳过。")
        return 0

    # ---------- ① 先发「上一期的理解」 ----------
    pending = None
    for q in reversed(questions):
        if not q.get("understanding"):
            pending = q
            break

    if pending:
        issue = pending.get("issue")
        print(f"[+] 为第 {issue} 期写理解…")
        understanding = generate_understanding(pending)
        print(f"    理解 {len(understanding)} 字")

        content = build_understanding_content(pending, understanding)
        result = push(f"第 {issue} 期 · {LETTER}（理解）", content)
        print(f"[+] 理解推送成功: {result.get('msg')}（{len(content)} 字）")

        pending["understanding"] = understanding
        save_history(history)  # 先存，防止后面失败导致重复推送
    else:
        print("[=] 没有待写理解的题（第一期或已全部写完）")

    # ---------- ② 再发「今天的新题」 ----------
    recent = questions[-60:]
    recent_lines = []
    for q in recent[-10:]:
        s = (q.get("scenario") or "")[:30]
        recent_lines.append(f"- {q.get('question', '')}（{s}…）")
    recent_text = "\n".join(recent_lines) or "（暂无）"

    used_domains = [q.get("domain", "") for q in recent[-5:] if q.get("domain")]
    recent_domains_text = "、".join(used_domains) or "（暂无）"
    fresh = [d for d in DOMAINS if d not in used_domains] or DOMAINS
    domain = random.choice(fresh)

    item = generate_question(domain, recent_text, recent_domains_text, today)
    item["date"] = today
    item["issue"] = next_issue(questions)
    questions.append(item)

    print(f"[+] 第 {item['issue']} 期新题（{item['domain']}，场景 {len(item['scenario'])} 字）")
    print(f"    问题：{item['question']}")

    content = build_question_content(item)
    result = push(f"第 {item['issue']} 期 · {LETTER}（问题）", content)
    print(f"[+] 问题推送成功: {result.get('msg')}（{len(content)} 字）")

    history["questions"] = questions[-200:]
    save_history(history)
    print("[+] 历史已保存")
    return 0


if __name__ == "__main__":
    sys.exit(main())
