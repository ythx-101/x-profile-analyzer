#!/usr/bin/env python3
"""
X Profile Analyzer - 用户画像分析工具
通过 Nitter (via Camofox) 抓取推文，用 MiniMax M2.5 API 生成结构化用户画像

Usage:
    python3 x-profile-analyzer.py --user QingQ77
    python3 x-profile-analyzer.py --user QingQ77 --count 30 --output profile.md
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
AUTH_PROFILES_PATH = Path.home() / ".openclaw" / "agents" / "main" / "agent" / "auth-profiles.json"
# REFERENCE_USER 已移除（v1.1）


# ── 认证 ──────────────────────────────────────────────────────────────────────

def load_minimax_key() -> str:
    """从 auth-profiles.json 读取 MiniMax API key"""
    try:
        with open(AUTH_PROFILES_PATH) as f:
            data = json.load(f)
        profiles = data.get("profiles", {})
        mm = profiles.get("minimax:default", {})
        key = mm.get("key", "")
        if not key:
            raise ValueError("minimax:default key not found")
        return key
    except FileNotFoundError:
        raise RuntimeError(f"Auth profiles not found: {AUTH_PROFILES_PATH}")
    except (KeyError, ValueError) as e:
        raise RuntimeError(f"Cannot read MiniMax key: {e}")


# ── 推文抓取 (Camofox + Nitter) ────────────────────────────────────────────────

def _extract_cursor(snapshot: str, username: str) -> Optional[str]:
    """从快照中提取下一页 cursor"""
    import re
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
        time_m = re.search(r'link\s+"(\d+[smhd]|(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d+(?:,\s+\d{4})?)"\s+\[e\d+\]:', line)
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
            if re.search(r'link\s+"(\d+[smhd]|(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d+)"\s+\[e\d+\]:', next_line):
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


# ── MiniMax M2.5 分析 ──────────────────────────────────────────────────────────

def analyze_profile_with_minimax(
    user_info: Dict,
    tweets: List[Dict],
    api_key: str,
    verbose: bool = False,
) -> str:
    """调用 MiniMax M2.5 API 生成用户画像分析"""

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
8. **一句话人物速写** - 用一句话精准概括这个人，要有记忆点，像一个好的人物传记开头

请保持分析深刻、具体、有洞察力，基于实际推文内容，避免套话。"""

    if verbose:
        print(f"[MiniMax] Sending {len(tweets)} tweets for analysis...", file=sys.stderr)

    try:
        request_body = json.dumps({
            "model": "MiniMax-M1",
            "max_tokens": 4096,
            "messages": [
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
        }).encode("utf-8")

        req = urllib.request.Request(
            MINIMAX_API_URL,
            data=request_body,
            headers={
                "Content-Type": "application/json",
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
            },
            method="POST",
        )

        with urllib.request.urlopen(req, timeout=120) as resp:
            result = json.loads(resp.read().decode("utf-8"))

        # 提取文本
        content = result.get("content", [])
        for block in content:
            if block.get("type") == "text":
                return block["text"]

        return f"[Error] Unexpected API response format: {json.dumps(result)[:500]}"

    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")[:500]
        raise RuntimeError(f"MiniMax API HTTP {e.code}: {body}")
    except urllib.error.URLError as e:
        raise RuntimeError(f"MiniMax API connection error: {e.reason}")
    except TimeoutError:
        raise RuntimeError("MiniMax API request timed out (>120s). Try reducing --count.")


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
> 分析工具：x-profile-analyzer v1.2
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

    return header + analysis + f"\n\n---\n*分析由 MiniMax M2.5 生成 | x-profile-analyzer v1.1*\n"


# ── 主程序 ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="X 用户画像分析工具 - 抓取推文并生成结构化分析报告"
    )
    parser.add_argument("--user", "-u", required=True, help="X/Twitter 用户名（不含 @）")
    parser.add_argument("--count", "-c", type=int, default=300, help="分析推文数量（默认 300，尽可能抓最多，Nitter 实际上限约 300）")
    parser.add_argument("--output", "-o", help="输出文件路径（默认输出到 stdout）")
    parser.add_argument("--verbose", "-v", action="store_true", help="显示详细进度信息")
    parser.add_argument("--no-camofox", action="store_true", help="跳过 Camofox 检查（调试用）")
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

    # 加载 API Key
    try:
        api_key = load_minimax_key()
        if args.verbose:
            print(f"[Auth] MiniMax API key loaded: {api_key[:15]}...", file=sys.stderr)
    except RuntimeError as e:
        print(f"[Error] {e}", file=sys.stderr)
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


    # AI 分析
    print(f"🤖 正在用 MiniMax M2.5 分析用户画像...", file=sys.stderr)
    try:
        analysis = analyze_profile_with_minimax(user_info, tweets, api_key, verbose=args.verbose)
    except RuntimeError as e:
        print(f"[Error] Analysis failed: {e}", file=sys.stderr)
        sys.exit(1)

    # 格式化报告
    report = format_report(user_info, tweets, analysis)

    # 输出
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(report, encoding="utf-8")
        print(f"✅ 报告已保存到: {output_path}", file=sys.stderr)
    else:
        print(report)


if __name__ == "__main__":
    main()
