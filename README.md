# X-Profile-Analyzer 🦞

给一个 X/Twitter 用户名，**无需 X API Key、无需登录**，通过 Nitter + Camofox 抓取最近最多约 300 条公开推文，再用 MiniMax 或任意 OpenAI 兼容大模型（如 DeepSeek）生成 10 个维度的中文用户画像报告；也可用 `--no-analyze` 只导出推文数据交给你自己的 AI。适合 OpenClaw 用户、AI agent 玩家，以及做内容 / BD / 调研、需要快速了解一个账号的人。

> AI-powered X/Twitter user profile analyzer — no X API key, no login. Fetches up to ~300 public tweets via Nitter + Camofox and generates a 10-dimension persona report with MiniMax or any OpenAI-compatible LLM.

[English](#english) | 中文

An [OpenClaw](https://github.com/openclaw/openclaw) skill. Sister tool of [X-Tweet-Fetcher](https://github.com/ythx-101/x-tweet-fetcher).

## 能做什么

- 抓取用户最近 **最多约 300 条推文**（自动翻页，Nitter 上限）
- AI 生成 X 用户画像（推特账号分析）：话题偏好、写作风格、深层动机、联系切入点等，共 10 个维度
- 支持 MiniMax 与 OpenAI 兼容接口（OpenAI、DeepSeek 等）
- `--no-analyze` 数据模式：只导出结构化推文，交给你自己的 AI agent
- 无需 X API、无需登录；零 pip 依赖

## 安装与快速开始（3 步）

**① 克隆仓库**（零 pip 依赖，Python 3.7+）

```bash
git clone https://github.com/ythx-101/x-profile-analyzer
cd x-profile-analyzer
```

**② 启动 Camofox**

抓取需要 [Camofox](https://github.com/jo-inc/camofox-browser) 运行在 `localhost:9377`（用于打开 Nitter 并翻页）。启动方式请参考其 README。

**③ 配置 AI Key（可选）并运行**

```bash
# OpenClaw 用户：无需配置，自动读取内置凭证

# 其他用户，三选一：
export MINIMAX_API_KEY=your_key          # MiniMax
export OPENAI_API_KEY=your_key           # OpenAI
# 任何 OpenAI 兼容接口（如 DeepSeek）：
export OPENAI_API_KEY=your_key OPENAI_BASE_URL=https://api.deepseek.com/v1 OPENAI_MODEL=deepseek-chat

# 可选：覆盖 MiniMax 模型名（默认 MiniMax-M2.5）
export MINIMAX_MODEL=MiniMax-M1
```

`OPENAI_BASE_URL` 可填 base（如 `https://api.deepseek.com/v1`），也可填完整的 `/chat/completions` 端点。

```bash
# 快速分析（50 条，约 1 分钟）
python3 scripts/x_profile_analyzer.py --user elonmusk --count 50

# 标准分析（100 条，约 2 分钟）⭐ 推荐
python3 scripts/x_profile_analyzer.py --user YuLin807 --count 100

# 深度分析（300 条，约 5 分钟，Nitter 上限）
python3 scripts/x_profile_analyzer.py --user YuLin807

# 详细进度输出
python3 scripts/x_profile_analyzer.py --user YuLin807 --count 100 --verbose
```

> **时间参考**：每 100 条约需 2 分钟（受 Nitter 响应速度影响）。建议日常用 `--count 100`，深度研究再用默认的 300 条。

> 不想配 API Key？用 `--no-analyze` 只抓推文数据，让你自己的 AI 来分析：
> ```bash
> python3 scripts/x_profile_analyzer.py --user elonmusk --no-analyze | your-ai-cli
> ```

## 工作原理

```
用户名 → Camofox 打开 Nitter + cursor 翻页 → 最多约 300 条推文
       → LLM（MiniMax / OpenAI 兼容）生成第 1–9 维
       → 本地统计生成第 10 维热力图 → Markdown 报告
```

| 步骤 | 机制 |
|------|------|
| 抓推文 | Camofox 打开 Nitter，cursor 翻页 |
| AI 分析 | MiniMax 或 OpenAI 兼容接口，生成第 1–9 维 |
| 热力图 | 本地统计，不调用 AI |
| 输出 | Markdown 格式用户画像 |

## 全部参数

| 参数 | 说明 |
|------|------|
| `--user`, `-u` | X/Twitter 用户名（不含 @），必填 |
| `--count`, `-c` | 抓取推文数量（默认 300，Nitter 实际上限约 300） |
| `--output`, `-o` | 输出文件路径（默认输出到 stdout） |
| `--output-json` | 同时保存原始推文 JSON 到指定路径 |
| `--no-analyze` | 只抓推文数据，不调 AI 分析 |
| `--verbose`, `-v` | 显示详细进度信息 |
| `--no-camofox` | 跳过 Camofox 状态检查（调试用；抓取仍需要 Camofox） |
| `--version` | 显示版本号 |

> Nitter 实例与 Camofox 端口目前需修改脚本顶部的 `NITTER_INSTANCE` / `CAMOFOX_PORT` 常量。

## 报告维度（10个）

| # | 维度 | 内容 | 来源 |
|---|------|------|------|
| 1 | 📌 话题偏好 | 核心主题分布、百分比、具体推文例子 | AI |
| 2 | ✍️ 写作风格 | 表达习惯、标志性符号、原文引用 | AI |
| 3 | 💬 互动习惯 | 发推频率、社交定位（广播型/互动型） | AI |
| 4 | 🔧 技术方向 | 完整技术栈、自研项目列表、技术观点 | AI |
| 5 | 🧠 深层动机分析 | 底层驱动力、潜在焦虑、执念（核心章节） | AI |
| 6 | 🔮 行为预测 | 短期/中期走向、可能的转变 | AI |
| 7 | ⭐ AI测算星座 | 最像哪个星座，附有趣理由（娱乐向） | AI |
| 8 | 🤝 联系切入点 | 最佳开场白 + 反面示例 | AI |
| 9 | 💡 一句话人物速写 | 有记忆点的单句传记式概括 | AI |
| 10 | 📊 活跃时间热力图 | 星期几分布 ASCII 图 + 最活跃/最沉默 + 一句结论 | 本地统计 |

> 第 10 维按星期统计（不含小时），需至少 10 条可解析日期才会生成；`--no-analyze` 模式也会附带。

## 示例输出

> 基于 [@YuLin807](https://x.com/YuLin807) 的真实分析结果（298条推文，✅ 高质量数据）。节选，第 10 节格式已按当前版本输出排版。

````markdown
## 1. 话题偏好
OpenClaw/龙虾养成 ~35% | AI工具开发 ~25% | 技术探索 ~20% | 哲学思考 ~10% | 其他 ~10%

## 5. 深层动机分析（核心章节）
**数字永生幻想**
> "会不会智能涌现，就像奥创那样扫描自己的头颅上传自己的意识实现永生！"

他不仅在养成AI，更在投射对永恒的渴望。隐藏矛盾：花大量时间（每天熬夜到凌晨1点）
搭建"节省时间的系统"——这种元焦虑正是他推文高产的根本动力。

## 8. 联系切入点
✅ "看到你的x-tweet-fetcher，我遇到了[具体问题]，你当时怎么解决的？"
❌ 不要："大佬能分享配置教程吗？我是小白求带🙏"

## 9. 一句话人物速写
> 一位半导体工程师试图用开源代码对抗时间的熵增，在养成AI的过程中重新定义了自己存在的意义，最终发现他培育的不是龙虾，而是一面照见生命有限性的镜子。

## 活跃时间分析（第 10 维，本地统计）
Mon ████████████████░░░░  49 条 (16%)
Wed ████████████████████  60 条 (20%)
Fri ████████░░░░░░░░░░░░  26 条 (9%)

🔥 最活跃：周三  📉 最沉默：周五
````

## 适用场景 & 对比

| 方案 | 需要 X API / 登录 | 输出 | 适合 |
|------|----|----|----|
| x-profile-analyzer | 都不需要 | 10 维画像报告 / 结构化推文数据 | 快速了解一个账号 |
| 官方 X API | 需开发者账号与密钥 | 原始 JSON | 大规模、合规的数据采集 |
| [X-Tweet-Fetcher](https://github.com/ythx-101/x-tweet-fetcher)（姊妹项目） | 不需要 | 单条推文/时间线/文章等抓取 | 只要数据不要分析 |
| 手动复制推文给 ChatGPT | 不需要 | 取决于你的 prompt | 偶尔看几条 |

## FAQ

### 需要 X/Twitter API Key 或登录吗？
不需要。数据通过 Nitter + Camofox 抓取公开页面。

### 最多能分析多少条推文？为什么是 300？
默认 300 条。Nitter 单账号历史翻页上限约 300 条，与账号大小无关。

### 不配置 AI API Key 能用吗？
能。使用 `--no-analyze` 只导出推文数据，再交给你自己的 AI 分析。

### 支持 DeepSeek / OpenAI / 其他模型吗？
支持 OpenAI 兼容接口：设置 `OPENAI_API_KEY`，并按需设置 `OPENAI_BASE_URL` 和 `OPENAI_MODEL`。也支持 MiniMax。

### Camofox 是什么？必须装吗？
Camofox 是用来打开 Nitter 并翻页的浏览器服务，抓取必须依赖它。`--no-camofox` 只是跳过启动前的状态检查，抓取仍需要 Camofox。

### 能分析私密账号吗？
不能，只能处理公开推文。

### Nitter 打不开怎么办？
工具依赖 Nitter 可用性。可修改脚本顶部的 `NITTER_INSTANCE` 常量换一个实例。

### 报告准确吗？
报告是 AI 推断，星座部分为娱乐向，仅供参考。建议至少 100 条推文以获得更可靠的分析。

### 和 X-Tweet-Fetcher 有什么区别？
[X-Tweet-Fetcher](https://github.com/ythx-101/x-tweet-fetcher) 侧重抓取推文/时间线等数据；本项目在抓取之上生成用户画像报告。

### 可以拿来做什么、不该做什么？
见下方「使用须知」。

## 限制

- 依赖 Nitter 可用性
- 无法抓私密账号
- Nitter 单账号历史上限约 300 条（与账号大小无关）
- 分析质量取决于推文数量（建议 100 条以上）

## 使用须知

- 仅处理公开推文。
- 报告为 AI 推断，不代表本人真实想法。
- 请勿用于骚扰、跟踪、人肉或歧视性用途，并遵守所在地法律与平台条款。

## 开发与测试

```bash
python3 -m unittest discover -s tests -v   # 离线，无需网络 / Camofox / API Key
```

## License

MIT，见 [LICENSE](LICENSE)。

---

<a name="english"></a>

## English

**X-Profile-Analyzer** gives you an AI-generated profile of any public X/Twitter account from just a username — no X API key, no login. It fetches up to ~300 public tweets via Nitter + Camofox and writes a 10-dimension persona report using MiniMax or any OpenAI-compatible LLM (OpenAI, DeepSeek, ...). Use `--no-analyze` to export the tweet data and feed it to your own AI agent.

### Quick start (3 steps)

1. Clone: `git clone https://github.com/ythx-101/x-profile-analyzer` (no pip dependencies, Python 3.7+)
2. Start [Camofox](https://github.com/jo-inc/camofox-browser) on `localhost:9377` (see its README).
3. (Optional) set an LLM key and run:

```bash
export MINIMAX_API_KEY=your_key      # or OPENAI_API_KEY (+ OPENAI_BASE_URL / OPENAI_MODEL)
python3 scripts/x_profile_analyzer.py --user elonmusk --count 100

# no LLM key: export data only
python3 scripts/x_profile_analyzer.py --user elonmusk --no-analyze
```

`OPENAI_BASE_URL` may be a base URL (e.g. `https://api.deepseek.com/v1`) or a full `/chat/completions` endpoint. `MINIMAX_MODEL` optionally overrides the MiniMax model (default `MiniMax-M2.5`).

### Options

| Option | Description |
|--------|-------------|
| `--user`, `-u` | Username without @ (required) |
| `--count`, `-c` | Number of tweets (default 300, Nitter caps at ~300) |
| `--output`, `-o` | Output file (default stdout) |
| `--output-json` | Also save raw tweets as JSON |
| `--no-analyze` | Fetch tweets only, skip the LLM |
| `--verbose`, `-v` | Verbose progress |
| `--no-camofox` | Skip the Camofox status check (debug; fetching still needs Camofox) |
| `--version` | Print version |

The Nitter instance and Camofox port are currently constants at the top of the script (`NITTER_INSTANCE`, `CAMOFOX_PORT`).

### Report dimensions

1. Topics 2. Writing style 3. Engagement habits 4. Tech focus 5. Deep motivation 6. Behavior prediction 7. Zodiac guess (for fun) 8. How to approach them 9. One-line sketch — generated by the LLM. 10. Weekday activity heatmap — computed locally (needs ≥10 parseable dates).

### FAQ

- **Do I need an X API key or login?** No.
- **How many tweets?** Up to ~300; that is Nitter's per-account history limit.
- **Can I use it without an LLM key?** Yes, with `--no-analyze`.
- **DeepSeek / OpenAI?** Yes, any OpenAI-compatible endpoint via `OPENAI_API_KEY`, `OPENAI_BASE_URL`, `OPENAI_MODEL`.
- **Private accounts?** No, public tweets only.

Reports are AI inferences and not a statement of the person's real views. Do not use this for harassment, stalking, doxxing or discrimination.

### Requirements

- Python 3.7+
- [Camofox](https://github.com/jo-inc/camofox-browser) on `localhost:9377`
- An LLM API key is optional (not needed with `--no-analyze`)

### License

MIT — see [LICENSE](LICENSE).
