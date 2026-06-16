import re
import time
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

import requests

SOURCES = [
    {"url": "https://feeds.bbci.co.uk/sport/football/rss.xml", "name": "BBC Sport"},
    {"url": "https://www.theguardian.com/football/rss", "name": "The Guardian"},
    {"url": "https://www.skysports.com/rss/12040", "name": "Sky Sports"},
]

TEAMS = [
    "Argentina", "Brazil", "France", "England", "Spain", "Germany", "Portugal",
    "Netherlands", "Belgium", "Croatia", "Morocco", "USA", "United States",
    "Mexico", "Canada", "Uruguay", "Colombia", "Ecuador", "Japan", "South Korea",
    "Australia", "Senegal", "Nigeria", "Ivory Coast", "Saudi Arabia", "Iran",
    "Serbia", "Switzerland", "Denmark", "Poland", "Wales", "Hungary", "Turkey",
    "Romania", "Scotland", "Austria", "Ukraine", "Algeria", "Tunisia", "Cameroon",
    "Egypt", "Costa Rica", "Jamaica", "Panama", "Bolivia", "Chile", "Peru",
    "Paraguay", "Venezuela", "New Zealand", "Qatar", "Ghana", "Bahrain",
]

SM_PADS = [
    "in a significant moment at the FIFA World Cup 2026 as football nations compete for glory",
    "amid all the drama at the FIFA World Cup 2026 as the tournament reaches its climax",
    "as the FIFA World Cup 2026 enters its most dramatic and exciting knockout stage this summer",
    "with all the action from the FIFA World Cup 2026 as football fans worldwide watch closely",
]

VIRAL_BOOST: dict[str, int] = {
    "record": 4, "historic": 4, "shock": 4, "stunning": 4, "eliminated": 4,
    "final": 3, "semi-final": 3, "semifinal": 3, "penalty": 3, "injury": 3,
    "controversial": 3, "red card": 3, "sacked": 3, "hat-trick": 3, "hat trick": 3,
    "breaking": 2, "exclusive": 2, "winner": 2, "brace": 2, "fired": 2,
    "goal": 1, "victory": 1, "defeat": 1, "draw": 1,
}

STARS = [
    "messi", "ronaldo", "mbappe", "haaland", "neymar", "bellingham",
    "vinicius", "yamal", "pedri", "kane", "lewandowski", "salah", "de bruyne",
    "rodri", "modric", "griezmann", "rashford", "saka",
]

SOURCE_SCORES = {"BBC Sport": 15, "The Guardian": 12, "Sky Sports": 10}

HEADERS = {"User-Agent": "Mozilla/5.0 WorldCupNews/1.0"}


def fetch_rss(url: str) -> str | None:
    """requests.get with 3 retries and redirect following."""
    for attempt in range(3):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=8, allow_redirects=True)
            resp.raise_for_status()
            return resp.text
        except Exception as e:
            if attempt == 2:
                print(f"[fetch_rss] 失败 {url}: {e}")
            time.sleep(1)
    return None


def _strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text).strip()


def _unescape(text: str) -> str:
    return (text
            .replace("&lt;", "<").replace("&gt;", ">")
            .replace("&amp;", "&").replace("&quot;", '"')
            .replace("&#39;", "'"))


def _get_tag(block: str, tag: str) -> str:
    """从 RSS item XML 块中提取标签内容，支持 CDATA。"""
    pattern = rf"<{tag}[^>]*>(?:<!\[CDATA\[([\s\S]*?)\]\]>|([\s\S]*?))</{tag}>"
    m = re.search(pattern, block, re.IGNORECASE)
    if not m:
        return ""
    return _unescape((m.group(1) or m.group(2) or "")).strip()


def parse_rss_items(xml_text: str, source_name: str) -> list[dict]:
    """从 RSS XML 解析文章列表，返回带 pub_dt(UTC-aware) 的 item 列表。"""
    items = []
    for m in re.finditer(r"<item>([\s\S]*?)</item>", xml_text, re.IGNORECASE):
        block = m.group(1)
        title = _strip_html(_get_tag(block, "title"))
        link = _get_tag(block, "link") or _get_tag(block, "guid")
        description = _strip_html(_get_tag(block, "description"))[:220]
        pub_date_str = _get_tag(block, "pubDate")

        if not title or not link:
            continue

        try:
            pub_dt = parsedate_to_datetime(pub_date_str)
            if pub_dt.tzinfo is None:
                pub_dt = pub_dt.replace(tzinfo=timezone.utc)
        except Exception:
            pub_dt = datetime.now(timezone.utc)

        items.append({
            "title": title,
            "link": link,
            "description": description,
            "pub_date": pub_date_str,
            "pub_dt": pub_dt,
            "source": source_name,
        })
    return items


def detect_teams(title: str, desc: str) -> list[str]:
    text = title + " " + desc
    return [t for t in TEAMS if re.search(rf"\b{re.escape(t)}\b", text, re.IGNORECASE)]


def to_sm_headline(title: str, pad_idx: int) -> str:
    clean = re.sub(r"\s*[-–|]\s*(BBC Sport|Guardian|Sky Sports|ESPN)[^\s]*", "", title, flags=re.IGNORECASE)
    clean = re.sub(r"^(WATCH|VIDEO|GALLERY|QUIZ|EXCLUSIVE):\s*", "", clean.strip(), flags=re.IGNORECASE)
    # 不做 padding，原始标题更干净；超过 18 词时截断
    words = clean.split()
    return " ".join(words[:18])


def virality_score(item: dict) -> float:
    text = (item["title"] + " " + item["description"]).lower()
    age_hours = (datetime.now(timezone.utc) - item["pub_dt"]).total_seconds() / 3600

    recency = max(0.0, 40 * (1 - age_hours / 12))
    source_score = SOURCE_SCORES.get(item["source"], 8)

    kw = sum(pts for word, pts in VIRAL_BOOST.items() if word in text)

    star_score = 10 if any(s in text for s in STARS) else 0
    wc_score = 15 if any(k in text for k in ["world cup", "2026", "fifa", "copa"]) else 0

    return recency + source_score + min(kw, 20) + star_score + wc_score


def dedup_key(title: str) -> str:
    return re.sub(r"\W", "", title[:40].lower())


def load_processed_urls(path: Path) -> set[str]:
    if not path.exists():
        return set()
    return {line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()}


def save_processed_urls(path: Path, urls: set[str]) -> None:
    path.write_text("\n".join(sorted(urls)) + "\n", encoding="utf-8")


def pub_time_ago(pub_dt: datetime) -> str:
    """将发布时间转为 '2h ago' 格式。"""
    delta = datetime.now(timezone.utc) - pub_dt
    hours = int(delta.total_seconds() // 3600)
    minutes = int((delta.total_seconds() % 3600) // 60)
    if hours >= 24:
        return f"{hours // 24}d ago"
    if hours >= 1:
        return f"{hours}h ago"
    return f"{minutes}m ago"


def fetch_top3(processed_urls_path: Path) -> list[dict]:
    """
    主入口：并发抓取 RSS，排序去重，返回前 3 篇未处理文章。
    同时更新 processed_urls.txt。
    """
    processed = load_processed_urls(processed_urls_path)

    # 并发抓取
    all_items: list[dict] = []
    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = {executor.submit(fetch_rss, src["url"]): src for src in SOURCES}
        for future in as_completed(futures):
            src = futures[future]
            xml = future.result()
            if xml:
                parsed = parse_rss_items(xml, src["name"])
                all_items.extend(parsed)
                print(f"[fetch] {src['name']}: {len(parsed)} 篇")

    if not all_items:
        print("[fetch] 未获取到任何文章")
        return []

    # 时效过滤：12h，不足 5 条扩到 24h
    now = datetime.now(timezone.utc)

    def within(hours: int) -> list[dict]:
        return [i for i in all_items if (now - i["pub_dt"]).total_seconds() <= hours * 3600]

    filtered = within(12)
    if len(filtered) < 5:
        filtered = within(24)
    print(f"[fetch] 时效过滤后: {len(filtered)} 篇")

    # enriched
    enriched = []
    for idx, item in enumerate(filtered):
        enriched.append({
            **item,
            "teams": detect_teams(item["title"], item["description"]),
            "sm_headline": to_sm_headline(item["title"], idx),
            "virality_score": round(virality_score(item)),
            "pub_ago": pub_time_ago(item["pub_dt"]),
        })

    # 排序
    enriched.sort(key=lambda x: x["virality_score"], reverse=True)

    # 标题去重（同批次内）
    seen_keys: set[str] = set()
    deduped = []
    for item in enriched:
        key = dedup_key(item["title"])
        if key not in seen_keys:
            seen_keys.add(key)
            deduped.append(item)

    # 过滤已处理 URL
    new_items = [i for i in deduped if i["link"] not in processed]
    print(f"[fetch] 过滤已处理后: {len(new_items)} 篇可用")

    top3 = new_items[:3]

    # 更新去重记录
    for item in top3:
        processed.add(item["link"])
    save_processed_urls(processed_urls_path, processed)

    return top3
