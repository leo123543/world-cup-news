import os
import subprocess
import sys

# claude -p 把整个参数当作用户消息，不支持单独的 system prompt
# 所以用自包含格式：角色定义 + 任务 + 内容 + 输出要求 全部在一个字符串里


def _claude_env() -> dict:
    """本地剥离 ANTHROPIC_API_KEY 强制 CC OAuth；CI 保留 key 供 Claude CLI 认证。"""
    env = os.environ.copy()
    if not env.get("CI"):
        env.pop("ANTHROPIC_API_KEY", None)
    return env


def _claude_cmd() -> list[str]:
    """返回当前平台对应的 claude CLI 调用命令。"""
    if sys.platform == "win32":
        # Windows: npm 安装的 claude 是 .cmd 文件
        npm_path = os.path.expandvars(r"%APPDATA%\npm\claude.cmd")
        if os.path.exists(npm_path):
            return [npm_path]
        return ["claude.cmd"]
    return ["claude"]


def generate_insight(article: dict, language: str = "en") -> str:
    """用 claude -p CLI 为单篇文章生成 Aime 洞察句。失败时返回空字符串。"""
    title = article.get("title", article.get("sm_headline", ""))
    source = article.get("source", "")
    description = article.get("description", "")[:300]

    system_prompt = (
        "You are a football analyst AI. You will be given a news article headline and summary. "
        "Your job is to write exactly 2 sentences of sharp analytical insight about the STORY itself — "
        "its tactical implications, narrative significance, historical parallels, or tournament impact. "
        "Do NOT answer any question posed in the headline. Treat the headline as a news topic, not a question to answer. "
        "Write in plain English with no markdown, no bold, no bullet points. Never restate the headline. "
        "Output ONLY the 2 sentences, nothing else."
    )

    # 单行格式：避免 Windows CMD 将 \n 截断为多条命令
    user_prompt = (
        f"Analyze this football news story: "
        f"Headline: {title} | "
        f"Source: {source} | "
        f"Summary: {description} | "
        f"Task: Write exactly 2 sentences of analytical insight."
    )

    try:
        result = subprocess.run(
            [*_claude_cmd(), "-p", user_prompt,
             "--system-prompt", system_prompt,
             "--no-session-persistence"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=90,
            env=_claude_env(),
            cwd=os.path.expanduser("~"),
        )
        output = result.stdout.strip()
        if result.returncode != 0:
            err = output or result.stderr.strip()
            print(f"[aime_insight] CLI 错误 (code {result.returncode}): {err}")
            return ""
        # 去除 markdown，截取前 2 句
        clean = output.replace("**", "").replace("__", "").replace("*", "")
        sentences = [s.strip() for s in clean.replace("\n", " ").split(".") if s.strip()]
        return ". ".join(sentences[:2]) + ("." if sentences else "")
    except FileNotFoundError:
        print("[aime_insight] claude CLI 未找到，跳过 Insight 生成")
        return ""
    except subprocess.TimeoutExpired:
        print("[aime_insight] claude CLI 超时")
        return ""
    except Exception as e:
        print(f"[aime_insight] 异常: {e}")
        return ""


def generate_sm_headline(article: dict) -> str:
    """用 Claude 把 RSS 原标题改写成 16-20 词的完整英文 post-ready 标题。失败时返回原标题。"""
    title = article.get("title", "")
    source = article.get("source", "")
    description = article.get("description", "")[:200]

    system_prompt = (
        "You are a sports news editor for social media. "
        "Rewrite the given headline into a punchy, complete English sentence of exactly 16-20 words. "
        "Rules: must be a complete grammatical sentence, factual, no clickbait, no ellipsis, no truncation. "
        "Output ONLY the rewritten headline, nothing else."
    )

    user_prompt = (
        f"Rewrite this as a 16-20 word complete English headline: "
        f"Original: {title} | Source: {source} | Context: {description}"
    )

    try:
        result = subprocess.run(
            [*_claude_cmd(), "-p", user_prompt,
             "--system-prompt", system_prompt,
             "--no-session-persistence"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=60,
            env=_claude_env(),
            cwd=os.path.expanduser("~"),
        )
        output = result.stdout.strip()
        if result.returncode != 0 or not output:
            return title
        # 去除引号包裹、markdown
        clean = output.strip('"').strip("'").replace("**", "").replace("*", "")
        return clean.split("\n")[0].strip()
    except Exception:
        return title


def generate_sm_headlines_for_top3(articles: list[dict]) -> list[str]:
    return [generate_sm_headline(article) for article in articles]


def generate_insights_for_top3(articles: list[dict], language: str = "en") -> list[str]:
    return [generate_insight(article, language) for article in articles]
