#!/usr/bin/env python3
"""
X Profile Analyzer - 用户画像分析工具
通过 Nitter (via Camofox) 抓取推文，生成结构化用户画像

Usage:
    # 完整模式（抓推文 + AI 分析）
    python3 x_profile_analyzer.py --user elonmusk

    # 纯数据模式（只抓推文，不调 AI）让龙虾自己分析
    python3 x_profile_analyzer.py --user elonmusk --no-analyze

    # 数据模式 + 保存原始 JSON
    python3 x_profile_analyzer.py --user elonmusk --no-analyze --output-json data.json

AI 配置（完整模式需要，三选一）：
    export MINIMAX_API_KEY=xxx     # MiniMax（OpenClaw 用户自动读取，无需配置）
    export OPENAI_API_KEY=xxx      # OpenAI / DeepSeek 等
    export OPENAI_BASE_URL=xxx     # 自定义接口（可选，base 或完整端点均可）
    export MINIMAX_MODEL=xxx       # MiniMax 模型名（可选，默认 MiniMax-M2.5）
    export OPENAI_MODEL=xxx        # 模型名（可选，默认 gpt-4o-mini）
"""

import json
import re
import sys
import os
import time
import argparse
import urllib.request
import urllib.error
from datetime import datetime
from typing import Optional, Dict, List, Any, Tuple
from pathlib import Path


# ── 配置 ──────────────────────────────────────────────────────────────────────

CAMOFOX_PORT = 9377
NITTER_INSTANCE = "nitter.net"
MINIMAX_API_URL = "https://api.minimax.io/anthropic/v1/messages"
OPENAI_API_URL = "https://api.openai.com/v1/chat/completions"
AUTH_PROFILES_PATH = Path.home() / ".openclaw" / "agents" / "main" / "agent" / "auth-profiles.json"
DEFAULT_MINIMAX_MODEL = "MiniMax-M2.5"
__version__ = "1.7"

# 推文时间链接（相对时间 3d / 绝对时间 Jan 19 或 Jan 19, 2025），开头与边界检测共用
TIME_LINK_RE = re.compile(
    r'link\s+"(\d+[smhd]|(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d+(?:,\s+\d{4})?)"\s+\[e\d+\]:'
)
# REFERENCE_USER 已移除（v1.1）


# ── 认证 ──────────────────────────────────────────────────────────────────────

def _normalize_openai_url(url: str) -> str:
    """OPENAI_BASE_URL 既可填 base（.../v1），也可填完整端点（.../chat/completions）"""
    url = url.strip()
    if url.rstrip("/").endswith("/chat/completions"):
        return url.rstrip("/")
    return url.rstrip("/") + "/chat/completions"


def load_api_config() -> tuple:
    """
    加载 AI API 配置，返回 (api_key, api_url, model_name, backend)
    MiniMax 模型名可用 MINIMAX_MODEL 覆盖（默认 MiniMax-M2.5）。
    优先级：
      1. MINIMAX_API_KEY 环境变量
      2. OpenClaw auth-profiles.json（OpenClaw 用户自动读取）
      3. OPENAI_API_KEY 环境变量（兼容任何 OpenAI 格式接口）
    """
    minimax_model = os.environ.get("MINIMAX_MODEL") or DEFAULT_MINIMAX_MODEL

    # 1. 环境变量 MINIMAX_API_KEY
    mm_key = os.environ.get("MINIMAX_API_KEY")
    if mm_key:
        return mm_key, MINIMAX_API_URL, minimax_model, "minimax"

    # 2. OpenClaw auth-profiles.json
    try:
        with open(AUTH_PROFILES_PATH) as f:
            data = json.load(f)
        profiles = data.get("profiles", {})
        mm = profiles.get("minimax:default", {})
        key = mm.get("key", "")
        if key:
            return key, MINIMAX_API_URL, minimax_model, "minimax"
    except Exception:
        pass

    # 3. OPENAI_API_KEY（兼容 OpenAI / DeepSeek / 任何兼容接口）
    openai_key = os.environ.get("OPENAI_API_KEY")
    openai_url = _normalize_openai_url(os.environ.get("OPENAI_BASE_URL") or OPENAI_API_URL)
    openai_model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
    if openai_key:
        return openai_key, openai_url, openai_model, "openai"

    raise RuntimeError(
        "未找到 AI API Key。请设置以下任一环境变量：\n"
        "  export MINIMAX_API_KEY=your_key   # MiniMax（推荐，免费额度多）\n"
        "  export OPENAI_API_KEY=your_key    # OpenAI / DeepSeek / 兼容接口\n"
        "  export OPENAI_BASE_URL=...        # 自定义接口地址（可选）\n"
        "  export OPENAI_MODEL=gpt-4o-mini   # 模型名称（可选）\n"
        "MiniMax 免费注册：https://www.minimaxi.com"
    )

def load_minimax_key() -> str:
    """兼容旧版调用"""
    key, _, _, _ = load_api_config()
    return key


# ── 推文抓取 (Camofox + Nitter) ────────────────────────────────────────────────

def _extract_cursor(snapshot: str, username: str) -> Optional[str]:
    """从快照中提取下一页 cursor"""
    cursors = re.findall(r'cursor=([^\"&\s\)]+)', snapshot)
    return cursors[0] if cursors else None

def fetch_user_timeline(username: str, count: int = 20, verbose: bool = False) -> Tuple[List[Dict], Dict]:
    """
    通过 Camofox + Nitter 抓取用户时间线推文（支持翻页）
    返回 (tweets_list, user_info)
    """
    MAX_PAGES = 30
    all_tweets: List[Dict] = []
    user_info: Dict = {}
    cursor: Optional[str] = None

    for page in range(1, MAX_PAGES + 1):
        if cursor:
            import urllib.parse
            nitter_url = f"https://{NITTER_INSTANCE}/{username}?cursor={urllib.parse.quote(cursor, safe='')}"
        else:
            nitter_url = f"https://{NITTER_INSTANCE}/{username}"

        if verbose:
            print(f"[Fetcher] 第{page}页: {nitter_url}", file=sys.stderr)

        tab_id = _camofox_open_tab(username, nitter_url)
        if not tab_id:
            print(f"[Fetcher] 第{page}页 Tab 创建失败，停止", file=sys.stderr)
            break

        time.sleep(8)
        snapshot = _camofox_get_snapshot(tab_id)
        _camofox_close_tab(tab_id)

        if not snapshot:
            print(f"[Fetcher] 第{page}页快照为空，停止", file=sys.stderr)
            break

        # 第一页解析用户信息
        if page == 1:
            user_info = _parse_user_info(snapshot, username)

        page_tweets = _parse_tweets(snapshot, username, count)
        if not page_tweets:
            if verbose:
                print(f"[Fetcher] 第{page}页无推文，停止翻页", file=sys.stderr)
            break

        all_tweets.extend(page_tweets)
        if verbose:
            print(f"[Fetcher] 第{page}页抓到 {len(page_tweets)} 条，累计 {len(all_tweets)} 条", file=sys.stderr)

        if len(all_tweets) >= count:
            break

        cursor = _extract_cursor(snapshot, username)
        if not cursor:
            if verbose:
                print(f"[Fetcher] 无下一页 cursor，停止", file=sys.stderr)
            break

    all_tweets = all_tweets[:count]
    if verbose:
        print(f"[Fetcher] 最终共 {len(all_tweets)} 条推文", file=sys.stderr)

    return all_tweets, user_info


def _camofox_open_tab(username: str, url: str) -> Optional[str]:
    """在 Camofox 中打开新 Tab，返回 tab_id"""
    try:
        create_data = json.dumps({
            "userId": "x-profile-analyzer",
            "sessionKey": f"profile-{username}-{int(time.time())}",
            "url": url,
        }).encode()

        req = urllib.request.Request(
            f"http://localhost:{CAMOFOX_PORT}/tabs",
            data=create_data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            tab_data = json.loads(resp.read().decode())

        return tab_data.get("tabId")
    except Exception as e:
        print(f"[Camofox] Error opening tab: {e}", file=sys.stderr)
        return None


def _camofox_get_snapshot(tab_id: str, user_id: str = "x-profile-analyzer") -> str:
    """获取 Tab 快照（userId 必须与创建时一致）"""
    try:
        snap_url = f"http://localhost:{CAMOFOX_PORT}/tabs/{tab_id}/snapshot?userId={user_id}"
        req = urllib.request.Request(snap_url)
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            snap_data = json.loads(raw)
        return snap_data.get("snapshot", "")
    except Exception as e:
        print(f"[Camofox] Error getting snapshot: {e}", file=sys.stderr)
        return ""


def _camofox_close_tab(tab_id: str):
    """关闭 Tab"""
    try:
        close_req = urllib.request.Request(
            f"http://localhost:{CAMOFOX_PORT}/tabs/{tab_id}",
            method="DELETE",
        )
        urllib.request.urlopen(close_req, timeout=5)
    except Exception:
        pass


def _parse_user_info(snapshot: str, username: str) -> Dict:
    """从快照中解析用户基本信息"""
    info = {
        "username": username,
        "display_name": "",
        "bio": "",
        "joined": "",
        "tweets_count": 0,
        "followers": 0,
        "following": 0,
    }

    lines = snapshot.split("\n")
    for i, line in enumerate(lines):
        line = line.strip()

        # 显示名称
        if not info["display_name"]:
            m = re.search(r'link\s+"([^@"][^"]+)"\s+\[e\d+\]:', line)
            if m and username.lower() not in m.group(1).lower():
                name = m.group(1)
                if name not in ("nitter", "Logo"):
                    info["display_name"] = name

        # Bio
        if line.startswith("- paragraph:") and not info["bio"]:
            bio = line.replace("- paragraph:", "").strip()
            if bio and "Joined" not in bio:
                info["bio"] = bio

        # Joined
        if "Joined" in line and not info["joined"]:
            m = re.search(r"Joined\s+(.+)", line)
            if m:
                info["joined"] = m.group(1).strip()

        # Stats
        if "Tweets " in line:
            m = re.search(r"Tweets\s+([\d,]+)", line)
            if m:
                info["tweets_count"] = int(m.group(1).replace(",", ""))
        if "Followers " in line:
            m = re.search(r"Followers\s+([\d,]+)", line)
            if m:
                info["followers"] = int(m.group(1).replace(",", ""))
        if "Following " in line:
            m = re.search(r"Following\s+([\d,]+)", line)
            if m:
                info["following"] = int(m.group(1).replace(",", ""))

    return info


def _parse_tweets(snapshot: str, username: str, max_count: int) -> List[Dict]:
    """从快照解析推文列表"""
    tweets = []
    lines = snapshot.split("\n")

    i = 0
    while i < len(lines) and len(tweets) < max_count:
        line = lines[i].strip()

        # 检测推文开头: 时间链接 (如 "27m", "9h", "3d")
        time_m = TIME_LINK_RE.search(line)
        if not time_m:
            i += 1
            continue

        # 确认这是该用户的推文 (前几行应有 @username)
        is_own_tweet = False
        for j in range(max(0, i - 5), i):
            if f'@{username.lower()}' in lines[j].lower() or f'/{username.lower()}' in lines[j].lower():
                is_own_tweet = True
                break

        if not is_own_tweet:
            i += 1
            continue

        time_str = time_m.group(1)
        tweet_url_m = re.search(r'/url:\s*(/\w+/status/\d+)', lines[i])
        tweet_url = tweet_url_m.group(1) if tweet_url_m else ""

        # 收集推文文本（接下来的文本行）
        tweet_text_parts = []
        stats_str = ""
        media_urls = []
        quoted_text = ""

        j = i + 1
        while j < min(i + 30, len(lines)):
            next_line = lines[j].strip()

            # 下一条推文开始（新的时间链接）
            if TIME_LINK_RE.search(next_line):
                break

            # 推文文本
            if next_line.startswith("- text:") and not next_line.startswith("- text:  "):
                text = next_line.replace("- text:", "").strip()
                # 跳过统计行（纯数字+空格）
                if re.match(r'^[\d\s]+$', text):
                    stats_str = text
                elif text and text not in ("Replying to", "Pinned Tweet"):
                    tweet_text_parts.append(text)

            # 媒体链接
            if "- /url: /pic/" in next_line:
                media_urls.append(next_line.strip())

            # 引用推文文本
            if "- paragraph:" in next_line and j > i + 3:
                quoted_text = next_line.replace("- paragraph:", "").strip()

            j += 1

        tweet_text = " ".join(tweet_text_parts).strip()

        # 解析互动数据（从 stats_str 提取数字）
        stats_nums = [int(x) for x in re.findall(r'\d+', stats_str)] if stats_str else []
        replies_count = stats_nums[0] if len(stats_nums) > 0 else 0
        retweets = stats_nums[1] if len(stats_nums) > 1 else 0
        views = stats_nums[2] if len(stats_nums) > 2 else 0

        if tweet_text:  # 只保留有文本的推文
            tweet = {
                "text": tweet_text,
                "time": time_str,
                "url": f"https://x.com{tweet_url}" if tweet_url else "",
                "replies": replies_count,
                "retweets": retweets,
                "views": views,
                "has_media": len(media_urls) > 0,
                "quoted_text": quoted_text,
            }
            tweets.append(tweet)

        i = j

    return tweets


# ── AI 分析（MiniMax / OpenAI 兼容） ──────────────────────────────────────────────────────────

def analyze_profile_with_minimax(
    user_info: Dict,
    tweets: List[Dict],
    api_key: str,
    verbose: bool = False,
    api_url: str = None,
    model_name: str = DEFAULT_MINIMAX_MODEL,
    backend: str = "minimax",
) -> str:
    """调用 AI API 生成用户画像分析（支持 MiniMax / OpenAI 兼容接口）"""
    if api_url is None:
        api_url = MINIMAX_API_URL

    # 构建推文摘要
    tweets_summary = _build_tweets_summary(tweets)
    user_summary = _build_user_summary(user_info)

    prompt = f"""你是一位专业的社交媒体用户分析师。请基于以下 @{user_info['username']} 的推文数据，生成一份详细的用户画像分析报告。

## 用户基本信息
{user_summary}

## 最近推文（共 {len(tweets)} 条）
{tweets_summary}

## 分析要求
请输出结构化的 Markdown 格式报告，包含以下章节：

1. **话题偏好** - 该用户最常讨论的主题、关注领域、兴趣方向，给出具体例子
2. **写作风格** - 表达方式、语言习惯、句式特点、表情符号使用，引用实际推文原文举例
3. **互动习惯** - 发推频率、回复习惯、转发行为，分析其社交定位（广播型/互动型/潜水型）
4. **技术方向** - 涉及的技术栈、工具、项目、技术观点（如无明显技术内容则标注）
5. **深层动机分析** - 基于推文内容推断：这个人发推的核心驱动力是什么？他/她在追求什么？有什么潜在的焦虑或执念？这是报告的核心章节，要有洞察力，不要泛泛而谈
6. **行为预测** - 基于历史推文，预测这个人接下来最可能做什么，会关注哪些话题，可能的转变方向
7. **AI 测算星座** - 根据推文风格、表达习惯、关注话题，用占星学视角给出"最像哪个星座"，附上 2-3 句有趣理由（娱乐向）
8. **联系切入点** - 如果你想接触这个人，最好的方式是什么？他/她最容易被什么话题吸引？什么开场白会让他/她愿意回复？给出 2-3 个具体建议，要实用，不要套话
9. **一句话人物速写** - 用一句话精准概括这个人，要有记忆点，像一个好的人物传记开头

请保持分析深刻、具体、有洞察力，基于实际推文内容，避免套话。"""

    if not api_url:
        api_url = OPENAI_API_URL if backend == "openai" else MINIMAX_API_URL

    if verbose:
        print(f"[{backend}] Sending {len(tweets)} tweets for analysis...", file=sys.stderr)

    try:
        if backend == "openai":
            request_body = json.dumps({
                "model": model_name,
                "max_tokens": 4096,
                "messages": [{"role": "user", "content": prompt}],
            }).encode("utf-8")
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            }
        else:
            request_body = json.dumps({
                "model": model_name,
                "max_tokens": 4096,
                "messages": [{"role": "user", "content": prompt}],
            }).encode("utf-8")
            headers = {
                "Content-Type": "application/json",
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
            }

        req = urllib.request.Request(api_url, data=request_body, headers=headers, method="POST")

        with urllib.request.urlopen(req, timeout=120) as resp:
            result = json.loads(resp.read().decode("utf-8"))

        # 提取文本
        if backend == "openai":
            choices = result.get("choices") or []
            if choices:
                text = (choices[0].get("message") or {}).get("content")
                if text:
                    return text
        else:
            for block in result.get("content", []):
                if block.get("type") == "text":
                    return block["text"]

        return f"[Error] Unexpected API response format: {json.dumps(result)[:500]}"

    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")[:500]
        raise RuntimeError(f"{backend} API HTTP {e.code}: {body}")
    except urllib.error.URLError as e:
        raise RuntimeError(f"{backend} API connection error: {e.reason}")
    except TimeoutError:
        raise RuntimeError(f"{backend} API request timed out (>120s). Try reducing --count.")


def _build_user_summary(user_info: Dict) -> str:
    lines = [
        f"- 用户名: @{user_info.get('username', 'unknown')}",
        f"- 显示名称: {user_info.get('display_name', 'N/A')}",
        f"- 简介: {user_info.get('bio', 'N/A')}",
        f"- 加入时间: {user_info.get('joined', 'N/A')}",
        f"- 推文数: {user_info.get('tweets_count', 0):,}",
        f"- 粉丝数: {user_info.get('followers', 0):,}",
        f"- 关注数: {user_info.get('following', 0):,}",
    ]
    return "\n".join(lines)


def _parse_tweet_date(time_str: str) -> Optional[datetime]:
    """把 Nitter 时间字符串解析成 datetime（尽力而为）"""
    from datetime import timedelta
    now = datetime.now()
    if not time_str:
        return None
    # 相对时间：2h / 15m / 3d / 5s
    m = re.match(r'^(\d+)([smhd])$', time_str.strip())
    if m:
        n, unit = int(m.group(1)), m.group(2)
        delta = {'s': timedelta(seconds=n), 'm': timedelta(minutes=n),
                 'h': timedelta(hours=n), 'd': timedelta(days=n)}[unit]
        return now - delta
    # 绝对时间：Jan 19 或 Jan 19, 2026
    for fmt in ("%b %d, %Y", "%b %d"):
        try:
            dt = datetime.strptime(time_str.strip(), fmt)
            if fmt == "%b %d":
                dt = dt.replace(year=now.year)
                # 如果解析出来是未来日期，说明是去年
                if dt > now:
                    dt = dt.replace(year=now.year - 1)
            return dt
        except ValueError:
            continue
    return None


def _build_activity_heatmap(tweets: List[Dict]) -> str:
    """生成推文星期分布 ASCII 热力图"""
    from collections import Counter
    weekday_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    weekday_cn = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]

    counts = Counter()
    parsed = 0
    for t in tweets:
        dt = _parse_tweet_date(t.get("time", ""))
        if dt:
            counts[dt.weekday()] += 1
            parsed += 1

    if parsed < 10:
        return ""  # 数据太少，不生成

    total = sum(counts.values())
    max_count = max(counts.values()) if counts else 1
    bar_width = 20

    lines = [f"\n## 活跃时间分析\n", f"发推星期分布（共 {parsed} 条有效数据）：\n"]
    for i, (name, cn) in enumerate(zip(weekday_names, weekday_cn)):
        c = counts.get(i, 0)
        pct = c / total * 100 if total else 0
        filled = int(c / max_count * bar_width)
        bar = "█" * filled + "░" * (bar_width - filled)
        lines.append(f"{name} {bar} {c:3d} 条 ({pct:.0f}%)")

    # 最活跃 / 最沉默
    if counts:
        peak_day = max(counts, key=counts.get)
        quiet_day = min(counts, key=counts.get)
        lines.append(f"\n🔥 最活跃：{weekday_cn[peak_day]}  📉 最沉默：{weekday_cn[quiet_day]}")

        # 工作日 vs 周末
        workday = sum(counts.get(i, 0) for i in range(5))
        weekend = sum(counts.get(i, 0) for i in range(5, 7))
        if total > 0:
            if workday / total > 0.7:
                lines.append("💡 工作日驱动型，周末明显减少")
            elif weekend / total > 0.4:
                lines.append("💡 周末活跃型，工作日输出少")
            else:
                lines.append("💡 全周均衡输出，无明显规律")

    return "\n".join(lines)


def _build_tweets_summary(tweets: List[Dict]) -> str:
    parts = []
    for i, t in enumerate(tweets, 1):
        text = t["text"]
        stats = f"回复:{t['replies']} 转推:{t['retweets']} 浏览:{t['views']}"
        has_media = "📷" if t.get("has_media") else ""
        quoted = f"\n  > 引用: {t['quoted_text'][:100]}" if t.get("quoted_text") else ""
        parts.append(f"{i}. [{t['time']}] {has_media}{text[:300]}{quoted}\n   ({stats})")
    return "\n\n".join(parts)


# ── 输出格式化 ──────────────────────────────────────────────────────────────────

def format_report(user_info: Dict, tweets: List[Dict], analysis: str) -> str:
    """生成最终 Markdown 报告"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    username = user_info.get("username", "unknown")
    display_name = user_info.get("display_name", username)
    tweet_count = len(tweets)

    # 数据质量标注
    if tweet_count < 50:
        data_quality = f"⚠️ 低（仅 {tweet_count} 条，Nitter 对该账号收录不足，结果仅供参考）"
    elif tweet_count < 100:
        data_quality = f"⚡ 中（{tweet_count} 条，建议 100+ 条获得更准确分析）"
    else:
        data_quality = f"✅ 高（{tweet_count} 条）"

    header = f"""# 用户画像分析报告：@{username}

> 生成时间：{now}
> 分析工具：x-profile-analyzer v{__version__}
> 数据来源：Nitter / X.com
> 数据质量：{data_quality}

## 基本信息

| 字段 | 值 |
|------|-----|
| 用户名 | @{username} |
| 显示名称 | {display_name} |
| 简介 | {user_info.get('bio', 'N/A')} |
| 加入时间 | {user_info.get('joined', 'N/A')} |
| 推文数 | {user_info.get('tweets_count', 0):,} |
| 粉丝数 | {user_info.get('followers', 0):,} |
| 关注数 | {user_info.get('following', 0):,} |

*本次分析基于最近 {len(tweets)} 条推文*

---

"""

    heatmap = _build_activity_heatmap(tweets)
    return header + analysis + heatmap + f"\n\n---\n*分析由 AI 生成 | x-profile-analyzer v{__version__}*\n"


# ── 主程序 ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="X 用户画像分析工具 - 抓取推文，可选 AI 分析"
    )
    parser.add_argument("--user", "-u", required=True, help="X/Twitter 用户名（不含 @）")
    parser.add_argument("--count", "-c", type=int, default=300, help="抓取推文数量（默认 300，Nitter 实际上限约 300）")
    parser.add_argument("--output", "-o", help="输出文件路径（默认输出到 stdout）")
    parser.add_argument("--output-json", help="同时保存原始推文 JSON 到指定路径")
    parser.add_argument("--no-analyze", action="store_true", help="只抓推文数据，不调 AI 分析（让调用方自己分析）")
    parser.add_argument("--verbose", "-v", action="store_true", help="显示详细进度信息")
    parser.add_argument("--no-camofox", action="store_true", help="跳过 Camofox 检查（调试用）")
    parser.add_argument("--version", action="version", version=__version__)
    args = parser.parse_args()

    username = args.user.lstrip("@")

    # 检查 Camofox 状态
    if not args.no_camofox:
        try:
            req = urllib.request.Request(f"http://localhost:{CAMOFOX_PORT}/")
            with urllib.request.urlopen(req, timeout=3) as resp:
                status = json.loads(resp.read().decode())
            if not status.get("running"):
                print(f"[Error] Camofox is not running. Start it first.", file=sys.stderr)
                sys.exit(1)
            if args.verbose:
                print(f"[Camofox] Status: OK (browser connected: {status.get('browserConnected')})", file=sys.stderr)
        except Exception as e:
            print(f"[Error] Cannot connect to Camofox at port {CAMOFOX_PORT}: {e}", file=sys.stderr)
            print("Make sure Camofox is running.", file=sys.stderr)
            sys.exit(1)

    # 抓取推文
    print(f"📊 正在抓取 @{username} 的推文...", file=sys.stderr)
    try:
        tweets, user_info = fetch_user_timeline(username, args.count, verbose=args.verbose)
    except RuntimeError as e:
        print(f"[Error] Failed to fetch tweets: {e}", file=sys.stderr)
        sys.exit(1)

    if not tweets:
        print(f"[Warning] No tweets found for @{username}. Account may be protected or not exist.", file=sys.stderr)
        sys.exit(1)

    print(f"✅ 成功获取 {len(tweets)} 条推文", file=sys.stderr)

    # 数据质量提示
    if len(tweets) < 50:
        print(f"⚠️  数据不足（仅 {len(tweets)} 条）：该账号在 Nitter 收录较少，可能是小账号或低活跃度账号，分析结果仅供参考", file=sys.stderr)
    elif len(tweets) < 100:
        print(f"⚠️  数据偏少（{len(tweets)} 条）：建议 100 条以上以获得更准确的分析", file=sys.stderr)

    # 保存原始 JSON（可选）
    if args.output_json:
        json_path = Path(args.output_json)
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(json.dumps({
            "user_info": user_info,
            "tweets": tweets,
            "fetched_at": time.strftime("%Y-%m-%d %H:%M"),
            "tweet_count": len(tweets),
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"✅ 原始数据已保存到: {json_path}", file=sys.stderr)

    # --no-analyze：只输出结构化数据，让调用方自己分析
    if args.no_analyze:
        output = _build_data_summary(user_info, tweets)
        if args.output:
            Path(args.output).write_text(output, encoding="utf-8")
            print(f"✅ 数据已保存到: {args.output}", file=sys.stderr)
        else:
            print(output)
        return

    # AI 分析模式：加载 API Key
    try:
        api_key, api_url, model_name, backend = load_api_config()
        if args.verbose:
            print(f"[Auth] {backend} API loaded (key ****{api_key[-4:]}) model={model_name}", file=sys.stderr)
    except RuntimeError as e:
        print(f"[Error] {e}", file=sys.stderr)
        print("提示：使用 --no-analyze 可跳过 AI 分析，直接输出推文数据", file=sys.stderr)
        sys.exit(1)

    print(f"🤖 正在分析用户画像...", file=sys.stderr)
    try:
        analysis = analyze_profile_with_minimax(user_info, tweets, api_key, verbose=args.verbose,
                                                 api_url=api_url, model_name=model_name, backend=backend)
    except RuntimeError as e:
        print(f"[Error] Analysis failed: {e}", file=sys.stderr)
        sys.exit(1)

    report = format_report(user_info, tweets, analysis)

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(report, encoding="utf-8")
        print(f"✅ 报告已保存到: {output_path}", file=sys.stderr)
    else:
        print(report)


def _build_data_summary(user_info: Dict, tweets: List[Dict]) -> str:
    """--no-analyze 模式：输出结构化推文数据，供调用方自行分析"""
    lines = [
        f"# @{user_info.get('username', 'unknown')} 推文数据",
        f"",
        f"## 基本信息",
        f"- 用户名: @{user_info.get('username')}",
        f"- 显示名称: {user_info.get('display_name', 'N/A')}",
        f"- 简介: {user_info.get('bio', 'N/A')}",
        f"- 加入时间: {user_info.get('joined', 'N/A')}",
        f"- 推文数: {user_info.get('tweets_count', 'N/A')}",
        f"- 粉丝数: {user_info.get('followers', 'N/A')}",
        f"- 关注数: {user_info.get('following', 'N/A')}",
        f"",
        f"## 推文列表（共 {len(tweets)} 条）",
        f"",
    ]
    for i, t in enumerate(tweets, 1):
        lines.append(f"### [{i}] {t.get('time', '')} | 💬{t.get('replies',0)} 🔁{t.get('retweets',0)} ❤️{t.get('views',0)}")
        lines.append(t.get('text', '').strip())
        lines.append("")
    # 加热力图
    heatmap = _build_activity_heatmap(tweets)
    if heatmap:
        lines.append(heatmap)
    lines.append("\n---")
    lines.append(f"*x-profile-analyzer v{__version__} | 数据抓取时间: {time.strftime('%Y-%m-%d %H:%M')}*")
    return "\n".join(lines)


if __name__ == "__main__":
    main()
