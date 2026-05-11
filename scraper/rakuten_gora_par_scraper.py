import re
import time
import json
import logging
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# Noneにすると全件取得
MAX_COURSES = None

REQUEST_INTERVAL = 1.2

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}

PREFECTURES = {
    "ibaraki": "茨城県",
    "tochigi": "栃木県",
    "gunma":   "群馬県",
    "saitama": "埼玉県",
    "chiba":   "千葉県",
    "tokyo":   "東京都",
    "kanagawa":"神奈川県",
}

LIST_URL   = "https://gora.golf.rakuten.co.jp/doc/area/{prefecture}/"
DETAIL_URL = "https://booking.gora.golf.rakuten.co.jp/guide/course_info/disp/c_id/{c_id}/"


def fetch(url: str) -> BeautifulSoup | None:
    try:
        resp = requests.get(url, headers=HEADERS, timeout=20)
        resp.raise_for_status()
        return BeautifulSoup(resp.text, "html.parser")
    except Exception as e:
        logger.warning("fetch error %s: %s", url, e)
        return None


def collect_course_ids(prefecture_key: str) -> list[tuple[str, str]]:
    """一覧ページから (c_id, name) のリストを返す"""
    url = LIST_URL.format(prefecture=prefecture_key)
    soup = fetch(url)
    if soup is None:
        return []

    ids: dict[str, str] = {}
    pattern = re.compile(r"/guide/disp/c_id/(\d+)")
    for a in soup.find_all("a", href=True):
        m = pattern.search(a["href"])
        if m:
            c_id = m.group(1)
            if c_id not in ids:
                ids[c_id] = a.get_text(strip=True) or c_id

    return list(ids.items())


def scrape_par(c_id: str) -> dict[str, dict[str, int]]:
    """ヤーデージページからコース名 -> {H01: par, ...} を返す"""
    url = DETAIL_URL.format(c_id=c_id)
    soup = fetch(url)
    if soup is None:
        return {}

    # h2「ヤーデージ」セクションを探す
    yardage_h2 = None
    for h2 in soup.find_all("h2"):
        if "ヤーデージ" in h2.get_text():
            yardage_h2 = h2
            break
    if yardage_h2 is None:
        return {}

    courses: dict[str, dict[str, int]] = {}

    # h2の後続要素を走査してコース名(h3)とテーブルを収集
    container = yardage_h2.find_parent()
    if container is None:
        container = soup

    current_course: str | None = None
    collecting = False

    for tag in container.find_all(["h2", "h3", "table"]):
        if tag == yardage_h2:
            collecting = True
            continue
        if not collecting:
            continue
        if tag.name == "h2":
            break  # 次のセクション
        if tag.name == "h3":
            current_course = tag.get_text(strip=True)
        if tag.name == "table" and current_course:
            par_row = _extract_par_row(tag)
            if par_row:
                courses[current_course] = par_row

    return courses


def _extract_par_row(table) -> dict[str, int] | None:
    """tableからPAR行を抽出して {H01: int, ...} を返す"""
    rows = table.find_all("tr")
    par_data: dict[str, int] = {}
    header_indices: list[int] = []

    for row in rows:
        cells = row.find_all(["th", "td"])
        texts = [re.sub(r'\s+', '', c.get_text()) for c in cells]

        # ヘッダー行（H01, H02, ... または 1, 2, ... 形式）
        if texts and re.match(r"^H?\d+$", texts[0]) and not any(t == "PAR" or t == "Par" or t == "par" for t in texts):
            header_indices = []
            for i, t in enumerate(texts):
                m = re.match(r"^H?(\d+)$", t)
                if m:
                    header_indices.append((i, int(m.group(1))))
            continue

        # PAR行
        is_par = texts and texts[0].upper() in ("PAR", "パー", "ﾊﾟｰ")
        if not is_par:
            # 先頭セルに「PAR」「par」が含まれる場合も対応
            is_par = texts and re.search(r'par', texts[0], re.IGNORECASE) is not None

        if is_par and header_indices:
            nums = []
            for cell in cells[1:]:
                digits = re.findall(r'\d+', cell.get_text())
                nums.append(int(digits[0]) if digits else None)
            for list_idx, (cell_idx, hole_num) in enumerate(header_indices):
                # cells[1:] に対応するインデックス
                val_idx = cell_idx - 1
                if 0 <= val_idx < len(nums) and nums[val_idx] is not None:
                    par_data[f"H{hole_num:02d}"] = nums[val_idx]

    return par_data if par_data else None


def main():
    all_courses: list[dict] = []
    seen_ids: set[str] = set()

    for pref_key, pref_name in PREFECTURES.items():
        logger.info("=== %s (%s) ===", pref_name, pref_key)
        pairs = collect_course_ids(pref_key)
        logger.info("  found %d courses", len(pairs))
        time.sleep(REQUEST_INTERVAL)

        for c_id, raw_name in pairs:
            if c_id in seen_ids:
                continue
            seen_ids.add(c_id)
            all_courses.append({
                "c_id": c_id,
                "name": raw_name,
                "prefecture": pref_name,
                "url": DETAIL_URL.format(c_id=c_id),
                "courses": None,  # 後で埋める
            })

    total_found = len(all_courses)
    logger.info("Total unique courses: %d", total_found)

    targets = all_courses if MAX_COURSES is None else all_courses[:MAX_COURSES]

    for i, entry in enumerate(targets, 1):
        logger.info("[%d/%d] %s (c_id=%s)", i, len(targets), entry["name"], entry["c_id"])
        courses = scrape_par(entry["c_id"])
        entry["courses"] = courses if courses else {}
        time.sleep(REQUEST_INTERVAL)

    courses_with_par    = sum(1 for e in targets if e["courses"])
    courses_without_par = len(targets) - courses_with_par

    result = {
        "scraped_at": datetime.now(timezone.utc).isoformat(),
        "area": "関東",
        "total_courses_found": total_found,
        "courses_with_par": courses_with_par,
        "courses_without_par": courses_without_par,
        "data": targets,
    }

    out_path = "rakuten_gora_kanto_par.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    logger.info("Saved to %s  (with_par=%d / without=%d)", out_path, courses_with_par, courses_without_par)


if __name__ == "__main__":
    main()
