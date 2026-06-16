import os
import subprocess
import sys

_SYSTEM_ZH = (
    "你是 Aime Multi-Agent Intelligence，专注足球市场和战术分析的 AI 分析师。"
    "针对提供的新闻，生成一句中文洞察（≤50 个汉字）。"
    "揭示非显而易见的角度：战术影响、赔率波动、历史类比或转会市场涟漪效应。"
    "不要重复标题内容。只输出洞察句本身，不加引号，不加解释。"
)

_SYSTEM_EN = (
    "You are Aime Multi-Agent Intelligence, an AI analyst specializing in football tactics and markets. "
    "Generate ONE sharp insight in English (≤80 chars) about the article. "
    "Reveal non-obvious angles: tactical implications, odds shifts, historical echoes, transfer ripple effects. "
    "Never restate the headline. Output only the insight, no quotes."
)


def _claude_env() -> dict:
    """剥离 ANTHROPIC_API_KEY，强制 CLI 使用 CC 订阅（OAuth）。"""
    env = os.environ.copy()
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


def generate_insight(article: dict, language: str = "zh") -> str:
    """用 claude -p CLI 为单篇文章生成 Aime 洞察句。失败时返回空字符串。"""
    system = _SYSTEM_ZH if language == "zh" else _SYSTEM_EN
    sm_headline = article.get("sm_headline", article.get("title", ""))
    source = article.get("source", "")
    description = article.get("description", "")[:300]

    if language == "zh":
        user_msg = f"Headline: {sm_headline}\nSource: {source}\nSummary: {description}\n\n生成一句 Aime 洞察（中文，≤50字）："
    else:
        user_msg = f"Headline: {sm_headline}\nSource: {source}\nSummary: {description}\n\nGenerate one Aime insight (English, ≤80 chars):"

    prompt = f"{system}\n\n{user_msg}"

    try:
        result = subprocess.run(
            [*_claude_cmd(), "-p", prompt],
            capture_output=True,
            text=True,
            timeout=60,
            env=_claude_env(),
        )
        output = result.stdout.strip()
        if result.returncode != 0:
            err = output or result.stderr.strip()
            print(f"[aime_insight] CLI 错误 (code {result.returncode}): {err}")
            return ""
        return output
    except FileNotFoundError:
        print("[aime_insight] claude CLI 未找到，跳过 Insight 生成")
        return ""
    except subprocess.TimeoutExpired:
        print("[aime_insight] claude CLI 超时")
        return ""
    except Exception as e:
        print(f"[aime_insight] 异常: {e}")
        return ""


def generate_insights_for_top3(articles: list[dict], language: str = "zh") -> list[str]:
    return [generate_insight(article, language) for article in articles]
