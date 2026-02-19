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
- MiniMax API Key（用于 AI 分析）

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

```
📊 @YuLin807 用户画像

话题分布：AI Agent (60%) | 开源工具 (25%) | 投资 (15%)
发推风格：技术向，中英混用，多代码展示
互动特征：回复率低，转发自己项目为主
活跃时间：UTC+8 白天
核心标签：#OpenClaw #AIAgent 🦞
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
