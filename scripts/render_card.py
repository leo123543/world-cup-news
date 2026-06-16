import re
from datetime import datetime
from pathlib import Path
from typing import Literal
from zoneinfo import ZoneInfo

from jinja2 import Environment, FileSystemLoader
from playwright.sync_api import sync_playwright

HKT = ZoneInfo("Asia/Hong_Kong")

LOGO_SVG_PATH = (
    Path(__file__).parent.parent.parent.parent
    / "_design-system"
    / "ainvest-design"
    / "assets"
    / "logo-white-on-black.svg"
)

Size = Literal["916", "169"]

_VIEWPORTS: dict[Size, dict] = {
    "916": {"width": 1080, "height": 1920},
    "169": {"width": 1920, "height": 1080},
}

_TEMPLATES: dict[Size, str] = {
    "916": "card_916.html.j2",
    "169": "card_169.html.j2",
}


def load_logo_svg(path: Path) -> str:
    """读取 logo SVG，修正 viewBox 偏移，使内联嵌入正常渲染。"""
    if not path.exists():
        print(f"[render] 警告: Logo 不存在 {path}，使用文字替代")
        return '<span style="font-family:JetBrains Mono,monospace;font-size:18px;font-weight:700;color:#fff;letter-spacing:.1em">AInvest</span>'
    svg = path.read_text(encoding="utf-8")
    # 原始 viewBox="790 375 985 200" 会导致内容偏出画布
    svg = re.sub(r'viewBox="[^"]*"', 'viewBox="0 0 985 200"', svg)
    return svg


def _make_env(templates_dir: Path) -> Environment:
    return Environment(loader=FileSystemLoader(str(templates_dir)), autoescape=False)


def render_card_html(
    article: dict,
    insight: str,
    card_index: int,
    logo_svg: str,
    template_env: Environment,
    size: Size,
) -> str:
    now_hkt = datetime.now(tz=HKT)
    fetch_date_hkt = now_hkt.strftime("%b %d, %Y · %I:%M %p HKT")

    template = template_env.get_template(_TEMPLATES[size])
    return template.render(
        logo_svg=logo_svg,
        card_index=card_index,
        sm_headline=article.get("sm_headline", article.get("title", "")),
        teams=article.get("teams", [])[:4],
        insight=insight,
        source=article.get("source", ""),
        virality_score=article.get("virality_score", 0),
        pub_ago=article.get("pub_ago", ""),
        fetch_date_hkt=fetch_date_hkt,
    )


def html_to_png(html: str, output_path: Path, size: Size) -> Path:
    """Playwright 截图 HTML → PNG，viewport 按尺寸规格设置。"""
    vp = _VIEWPORTS[size]
    with sync_playwright() as p:
        browser = p.chromium.launch(args=["--no-sandbox", "--disable-setuid-sandbox"])
        page = browser.new_page(viewport=vp)
        page.set_content(html, wait_until="networkidle")
        page.wait_for_timeout(2000)
        page.screenshot(
            path=str(output_path),
            clip={"x": 0, "y": 0, "width": vp["width"], "height": vp["height"]},
        )
        browser.close()
    return output_path


def render_all_cards(
    articles: list[dict],
    insights: list[str],
    output_dir: Path,
    logo_svg_path: Path = LOGO_SVG_PATH,
) -> dict[str, list[Path]]:
    """
    渲染全部卡片（9:16 和 16:9 各 3 张）。
    返回 {"916": [...], "169": [...]}。
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    templates_dir = Path(__file__).parent.parent / "templates"
    env = _make_env(templates_dir)
    logo_svg = load_logo_svg(logo_svg_path)

    now_str = datetime.now(tz=HKT).strftime("%Y%m%d_%H%M")
    result: dict[str, list[Path]] = {"916": [], "169": []}

    for size in ("916", "169"):
        for i, (article, insight) in enumerate(zip(articles, insights), start=1):
            html = render_card_html(article, insight, i, logo_svg, env, size)
            fname = f"{now_str}_card{i}_{size}.png"
            out_path = output_dir / fname
            html_to_png(html, out_path, size)
            print(f"[render] {size} 卡片 #{i}: {fname}")
            result[size].append(out_path)

    return result
