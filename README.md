# X-Profile-Analyzer 🦞

不需要 API Key，不需要登录，给一个用户名 → 输出 AI 用户画像分析。

[English](#english) | 中文

An [OpenClaw](https://github.com/openclaw/openclaw) skill. Sister tool of [X-Tweet-Fetcher](https://github.com/ythx-101/x-tweet-fetcher).

## 能做什么

- 抓取用户最近 **最多 300 条推文**（自动翻页，Nitter 硬上限）
- AI 分析用户画像：话题偏好、发推风格、互动模式
- 零依赖抓取，无需 X API、无需登录

## 快速开始

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

## 环境要求

- Python 3.7+
- [Camofox](https://github.com/openclaw/camofox) 运行在 `localhost:9377`（用于翻页抓推文）
- AI API Key（**可选**，使用 `--no-analyze` 时无需配置）：

```bash
# OpenClaw 用户：无需配置，自动读取内置凭证

# 其他用户，三选一：
export MINIMAX_API_KEY=your_key          # MiniMax（推荐，免费额度多）
export OPENAI_API_KEY=your_key           # OpenAI
export OPENAI_API_KEY=your_key \         # 任何 OpenAI 兼容接口
  OPENAI_BASE_URL=https://api.deepseek.com/v1 \
  OPENAI_MODEL=deepseek-chat
```

> 不想配 API Key？用 `--no-analyze` 只抓推文数据，让你自己的 AI 来分析：
> ```bash
> python3 x_profile_analyzer.py --user elonmusk --no-analyze | your-ai-cli
> ```

## 工作原理

```
用户名 → Camofox + Nitter 翻页 → 100条推文 → MiniMax M2.5 分析 → 用户画像
```

| 步骤 | 机制 |
|------|------|
| 抓推文 | Camofox 打开 Nitter，cursor 翻页 |
| AI 分析 | MiniMax M2.5（Thinking 模式） |
| 输出 | Markdown 格式用户画像 |

## 全部参数

```
--user USERNAME    分析的用户名（不带 @）
--count N          抓取推文数量（默认 300；推荐 100 条约 2 分钟，300 条约 5 分钟）
--json             JSON 格式输出
--verbose          显示抓取进度
--port N           Camofox 端口（默认 9377）
--nitter HOST      Nitter 实例（默认 nitter.net）
```

## 示例输出

> 基于 @Poison_2_ 的真实分析结果（31条推文）

```markdown
## 深层动机分析

@Poison_2_ 的核心驱动力并非简单的"分享生活"，而是
**"通过构建和展示AI智能体来获得某种存在感和身份认同"**。

**1. "造物主"情结与掌控欲**
反复强调 nanobot "自己优化自己"——创造一个生命体，看它自主成长。
这是一种技术掌控欲的满足：现实中无法实现的"造物"梦想，在代码世界实现了。

**2. 寻求认可的隐性渴望**
> "虽然没几个人能看到，但还是要单独发一遍😂"
知道影响力有限，但停不下来——发推是一种**自我表达的惯性**，
就像程序员写博客不是为了流量，而是为了"证明自己存在过"。

**3. 技术迭代焦虑**
持续跟进 GLM-4.7-flash、模型优化等热点，
是保持"不被淘汰"的心理防御机制。

## 一句话人物速写

> 他是一位2023年闯入AI赛道的野生开发者，用自建的智能体在Twitter上
> 建造了一座微型"数字动物园"，虽然观众寥寥，但他相信——只要代码
> 还在跑，某个角落里就有一个由他创造的数字生命正在觉醒。
```

## 限制

- 依赖 Nitter 可用性
- 无法抓私密账号
- Nitter 单账号历史上限约 300 条（与账号大小无关）
- 分析质量取决于推文数量（建议 100 条以上）

## License

MIT

---

<a name="english"></a>

## English

Give a username → get an AI-powered user profile. No X API key. No login.

### Usage

```bash
python3 scripts/x_profile_analyzer.py --user elonmusk --count 100
```

### How it works

```
username → Camofox + Nitter pagination → 100 tweets → MiniMax M2.5 → profile
```

### Requirements

- Python 3.7+
- [Camofox](https://github.com/openclaw/camofox) on `localhost:9377`
- MiniMax API Key
