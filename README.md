# 每日一问

每天自动生成一道**深度、开放、无标准答案**的问题，推送到手机微信。

跑在 **GitHub Actions** 上 —— 你的电脑关机、断网、出门没带，都不影响。

---

## 它是怎么工作的

```
GitHub 服务器（每天 UTC 00:00 = 北京时间 08:00）
   ↓
① 调 DeepSeek API 生成一道问题
   ↓
② 读 history/questions.json，避开最近问过的
   ↓
③ POST 到 PushPlus → 手机微信收到
   ↓
④ 把今天的问题写进 history 并提交回仓库
```

---

## 你需要做的 3 步

### 第 1 步：建一个**私有**仓库

到 https://github.com/new

- Repository name：随意，比如 `daily-question`
- **选 Private**（⚠️ 重要：公开仓库 60 天无活动会自动停用定时任务）
- 不要勾 "Add a README file"

### 第 2 步：上传这些文件

把这个文件夹里的**全部内容**拖进仓库页面（GitHub 支持拖拽上传）：

```
.github/workflows/daily.yml
daily.py
history/.gitkeep
README.md
```

⚠️ **`.github` 这个隐藏文件夹很容易漏**。如果拖拽上传没带上它，就用网页编辑器手动建：
`Add file` → `Create new file` → 文件名填 `.github/workflows/daily.yml`

### 第 3 步：配置两个 Secret

仓库页面 → **Settings** → 左侧 **Secrets and variables** → **Actions** → **New repository secret**

| Name | Value |
|---|---|
| `PUSHPLUS_TOKEN` | 你的 PushPlus token |
| `DEEPSEEK_API_KEY` | 你的 DeepSeek API key |

⚠️ **建议专门为这个任务新建一个 DeepSeek API key**（不要用主 key）。万一泄露可以单独吊销，不影响别处。

---

## 测试

1. 仓库页面 → **Actions** 标签
2. 左侧点「每日一问」
3. 右侧 **Run workflow** → 绿色按钮
4. 等 30 秒左右刷新，能看到运行记录
5. 点进去看日志，手机应该收到推送

---

## 常用调整

### 改时间

`.github/workflows/daily.yml` 里的 cron：

```yaml
- cron: '0 0 * * *'
```

**cron 用 UTC**，换算公式：`北京时间 - 8 小时 = UTC`

| 北京时间 | UTC | cron |
|---|---|---|
| 08:00 | 00:00 | `0 0 * * *` |
| 07:00 | 23:00（前一天） | `0 23 * * *` |
| 12:30 | 04:30 | `30 4 * * *` |

### 改问题风格

编辑 `daily.py` 里的 `PROMPT_TEMPLATE`，那是给模型的指令。改完提交即可。

想调整的常见方向：
- 更偏某一领域 → 改 `DOMAINS` 列表
- 更长/更短 → 改"长度：25~70 字"
- 更学术/更口语 → 改"硬性要求"那几条

### 改推送时间之外的行为

- 每天只发一条的逻辑在 `main()` 开头的**幂等判断**里
- 重试次数在 `call_llm()` / `push()` 的 `retries` 参数

---

## 排查

**没收到推送**
1. 看 Actions 运行日志有没有红叉
2. 检查 Secret 名字是否完全一致（大小写敏感）
3. PushPlus 是否还实名有效

**Actions 没按时跑**
- GitHub 的 cron **会延迟**，高峰可能晚十几分钟，这是官方的行为，不是 bug
- 定时任务只在**默认分支**（main）上生效

**报 `Bad credentials` / 推送 403**
- `PUSHPLUS_TOKEN` 填错了

**报 `401` 或 `Insufficient Balance`**
- `DEEPSEEK_API_KEY` 填错了，或余额不足

---

## 费用

| 项 | 费用 |
|---|---|
| GitHub Actions（私有仓库） | 免费额度 2000 分钟/月，本任务约 **15 分钟/月** |
| PushPlus | 免费 |
| DeepSeek API | 每次约几百 token，**几分钱/月** |

**合计：基本等于免费。**

---

## 停用

- 临时暂停：仓库 → Actions → 右侧 `...` → Disable workflow
- 彻底删除：删掉仓库即可
