import json
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).parent))

from aime_insight import generate_insights_for_top3
from fetch_top3 import fetch_top3
from render_card import render_all_cards

ROOT = Path(__file__).parent.parent
HKT = ZoneInfo("Asia/Hong_Kong")


def write_meta_json(
    articles: list[dict],
    png_paths: dict[str, list[Path]],
    cards_dir: Path,
) -> None:
    """生成 meta.json 供前端读取。"""
    now_hkt = datetime.now(tz=HKT)
    cards_data = []

    for i, article in enumerate(articles):
        files: dict[str, str] = {}
        for size in ("916", "169"):
            paths = png_paths.get(size, [])
            if i < len(paths):
                # 前端访问路径相对于网站根目录
                files[size] = "cards/" + paths[i].name
        cards_data.append({
            "rank": i + 1,
            "title": article.get("sm_headline", article.get("title", "")),
            "source": article.get("source", ""),
            "virality_score": article.get("virality_score", 0),
            "pub_ago": article.get("pub_ago", ""),
            "teams": article.get("teams", []),
            "files": files,
        })

    meta = {
        "generated_at": now_hkt.isoformat(),
        "generated_at_display": now_hkt.strftime("%b %d, %Y · %I:%M %p HKT"),
        "cards": cards_data,
    }

    meta_path = cards_dir / "meta.json"
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[main] meta.json 已写入: {meta_path}")


def main() -> None:
    cards_dir = ROOT / "cards"
    processed_urls_path = ROOT / "processed_urls.txt"

    print("=" * 50)
    print("[main] Daily Top 3 Cards 流水线启动")

    # 1. 抓取 Top 3 文章
    articles = fetch_top3(processed_urls_path)
    if not articles:
        print("[main] 无新文章，跳过本次运行")
        return

    print(f"[main] 抓取到 {len(articles)} 篇文章")

    # 2. Aime Insight 生成
    insights = generate_insights_for_top3(articles, language="zh")
    print("[main] Aime Insight 生成完毕")

    # 3. 渲染 6 张 PNG（9:16 × 3 + 16:9 × 3）
    png_paths = render_all_cards(articles, insights, cards_dir)
    total = sum(len(v) for v in png_paths.values())
    print(f"[main] 渲染完毕: 共 {total} 张 PNG")

    # 4. 写入 meta.json
    write_meta_json(articles, png_paths, cards_dir)

    print("[main] 流水线完成 ✓")
    print("=" * 50)


if __name__ == "__main__":
    main()
