import anthropic

# 直接 SDK 调用，不是 subprocess，无需剥离 ANTHROPIC_API_KEY
client = anthropic.Anthropic()

_SYSTEM_ZH = """You are Aime Multi-Agent Intelligence, an AI analyst for football and sports markets.
Generate ONE sharp, non-obvious insight in Simplified Chinese about the provided article.
Reveal tactical implications, odds shifts, historical echoes, or transfer market ripple effects — never restate the headline.
Output: single sentence, ≤50 Chinese characters, no quotes, no trailing punctuation unless natural."""

_SYSTEM_EN = """You are Aime Multi-Agent Intelligence, an AI analyst for football and sports markets.
Generate ONE sharp, non-obvious insight in English about the provided article.
Reveal tactical implications, odds shifts, historical echoes, or transfer market ripple effects — never restate the headline.
Output: single sentence, ≤80 characters, no quotes."""

_USER_ZH = """Headline: {sm_headline}
Source: {source}
Summary: {description}

生成一句 Aime 洞察（简体中文，≤50字）："""

_USER_EN = """Headline: {sm_headline}
Source: {source}
Summary: {description}

Generate one Aime insight (English, ≤80 chars):"""


def generate_insight(article: dict, language: str = "zh") -> str:
    """调用 Claude SDK 为单篇文章生成 Aime 洞察句。失败时返回空字符串。"""
    system = _SYSTEM_ZH if language == "zh" else _SYSTEM_EN
    user_tmpl = _USER_ZH if language == "zh" else _USER_EN
    user_msg = user_tmpl.format(
        sm_headline=article.get("sm_headline", article.get("title", "")),
        source=article.get("source", ""),
        description=article.get("description", "")[:300],
    )
    try:
        response = client.messages.create(
            model="claude-opus-4-8",
            max_tokens=150,
            system=system,
            messages=[{"role": "user", "content": user_msg}],
        )
        for block in response.content:
            if block.type == "text":
                return block.text.strip()
        return ""
    except anthropic.APIError as e:
        print(f"[aime_insight] API 错误: {e}")
        return ""


def generate_insights_for_top3(articles: list[dict], language: str = "zh") -> list[str]:
    """为 top3 文章列表顺序生成洞察，返回等长列表。"""
    return [generate_insight(article, language) for article in articles]
