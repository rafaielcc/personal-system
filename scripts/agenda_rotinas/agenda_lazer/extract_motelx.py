from __future__ import annotations

import argparse
import html
import json
import re
import sys
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo


BASE_URL = "https://www.motelx.org"
SCHEDULE_URL = f"{BASE_URL}/programa-e-horarios"
FILMS_URL = f"{BASE_URL}/filmes"
VENUES_URL = f"{BASE_URL}/bilhetes-e-locais"
TIMEZONE = ZoneInfo("Europe/Lisbon")
WINDOW_DAYS = 15
USER_AGENT = "AgendaLazerLocal/1.0 (+local routine; contact: Rafa)"


def now_lisbon() -> datetime:
    return datetime.now(TIMEZONE)


def parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def fetch(url: str, timeout: int = 30) -> str:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "pt-PT,pt;q=0.9,en;q=0.7",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        body = response.read()
    try:
        return body.decode("utf-8")
    except UnicodeDecodeError:
        return body.decode("cp1252", errors="replace")


def clean_text(value: str | None) -> str:
    if not value:
        return ""
    text = re.sub(r"<script\b.*?</script>", " ", value, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<style\b.*?</style>", " ", text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def absolute_url(href: str | None) -> str | None:
    if not href:
        return None
    href = html.unescape(href).strip()
    if href.startswith("http://") or href.startswith("https://"):
        return href
    if href.startswith("/"):
        return BASE_URL + href
    return BASE_URL + "/" + href


def split_schedule_items(markup: str) -> list[str]:
    marker = re.compile(r'(?=<section\s+class="[^"]*\bitem\b[^"]*\brow\b[^"]*\bclearfix\b[^"]*")', re.IGNORECASE)
    parts = marker.split(markup)
    items: list[str] = []
    for part in parts:
        if not part.lstrip().lower().startswith("<section"):
            continue
        end = part.lower().find("</section>")
        items.append(part[: end + len("</section>")] if end >= 0 else part)
    return items


def parse_item_links(item_html: str) -> list[dict[str, str]]:
    links: list[dict[str, str]] = []
    pattern = re.compile(
        r'<a\b[^>]*href="(?P<href>https://www\.motelx\.org/(?P<kind>filmes|eventos)/[^"]+)"[^>]*>(?P<label>.*?)</a>',
        re.IGNORECASE | re.DOTALL,
    )
    seen: set[tuple[str, str]] = set()
    for match in pattern.finditer(item_html):
        url = absolute_url(match.group("href")) or ""
        title = clean_text(match.group("label"))
        key = (url, title.lower())
        if not title or key in seen:
            continue
        seen.add(key)
        links.append({"kind": match.group("kind").lower(), "title": title, "url": url})
    return links


def parse_schedule(markup: str, start: date, days: int, radar_days: int) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, int]]:
    end = start + timedelta(days=days - 1)
    radar_end = start + timedelta(days=radar_days - 1)
    sessions: list[dict[str, Any]] = []
    radar: list[dict[str, Any]] = []
    stats = {"schedule_blocks_seen": 0, "links_seen": 0, "sessions_in_window": 0, "radar_items": 0}

    for block_idx, item_html in enumerate(split_schedule_items(markup)):
        stats["schedule_blocks_seen"] += 1
        class_match = re.search(r'<section\s+class="([^"]+)"', item_html, flags=re.IGNORECASE)
        classes = class_match.group(1).split() if class_match else []
        time_match = re.search(r'<time\b[^>]*datetime="([^"]+)"[^>]*>(.*?)</time>', item_html, flags=re.IGNORECASE | re.DOTALL)
        if not time_match:
            continue
        starts_at_raw = html.unescape(time_match.group(1)).strip()
        event_date = parse_date(starts_at_raw)
        if event_date is None:
            continue
        time_label = clean_text(time_match.group(2))
        venue_match = re.search(r'<span\b[^>]*class="[^"]*\bvenue-name\b[^"]*"[^>]*>(.*?)</span>', item_html, flags=re.IGNORECASE | re.DOTALL)
        venue = clean_text(venue_match.group(1)) if venue_match else ""
        room = ""
        location = venue
        links = parse_item_links(item_html)
        stats["links_seen"] += len(links)
        if not links:
            continue
        group_title = "; ".join(link["title"] for link in links)
        is_group = len(links) > 1
        for link_idx, link in enumerate(links):
            kind = link["kind"]
            category = "cinema_indoor" if kind == "filmes" else "culture"
            record = {
                "source": "motelx",
                "category": category,
                "title": link["title"],
                "date": event_date.isoformat(),
                "time": time_label,
                "starts_at": starts_at_raw.replace(" ", "T"),
                "venue": venue or None,
                "room": room or None,
                "location": location or venue or None,
                "link": link["url"],
                "programme_group_id": f"motelx_{event_date.isoformat()}_{block_idx:03d}",
                "programme_group_title": group_title if is_group else link["title"],
                "description": (
                    f"MOTELX 2026. Sessao em {location or venue or 'local a confirmar'}"
                    + (f"; bloco colectivo: {group_title}." if is_group else ".")
                ),
                "flags": ["motelx", "festival", "horror", "group_session" if is_group else "single_session"],
                "raw_ref": f"programa-e-horarios[{block_idx}].links[{link_idx}]",
                "classes": classes,
            }
            if start <= event_date <= end:
                stats["sessions_in_window"] += 1
                sessions.append(record)
            elif end < event_date <= radar_end:
                stats["radar_items"] += 1
                radar_record = dict(record)
                radar_record["category"] = "radar"
                radar.append(radar_record)

    return sessions, radar, stats


def parse_venues(markup: str) -> list[dict[str, Any]]:
    venues: list[dict[str, Any]] = []
    by_name: dict[str, dict[str, Any]] = {}
    coords_match = re.search(r"data-coords='([^']+)'", markup, flags=re.IGNORECASE | re.DOTALL)
    if coords_match:
        try:
            for item in json.loads(html.unescape(coords_match.group(1))):
                name = clean_text(str(item.get("title", "")))
                if not name:
                    continue
                by_name[name.lower()] = {
                    "name": name,
                    "coords": {"lat": item.get("lat"), "lng": item.get("lng")},
                    "details": "",
                }
        except json.JSONDecodeError:
            pass
    article_pattern = re.compile(
        r'<article\b[^>]*class="[^"]*\bitem\b[^"]*\brow\b[^"]*\bclearfix\b[^"]*"[^>]*>(?P<body>.*?)(?=<article\b[^>]*class="[^"]*\bitem\b[^"]*\brow\b[^"]*\bclearfix\b|</main>|</body>)',
        re.IGNORECASE | re.DOTALL,
    )
    for match in article_pattern.finditer(markup):
        body = match.group("body")
        title_match = re.search(r"<h1\b[^>]*class=\"[^\"]*\btitle\b[^\"]*\"[^>]*>(.*?)</h1>", body, flags=re.IGNORECASE | re.DOTALL)
        title = clean_text(title_match.group(1)) if title_match else ""
        if not title:
            continue
        entry = by_name.setdefault(title.lower(), {"name": title, "coords": None, "details": ""})
        entry["details"] = clean_text(body)[:800]
    venues = sorted(by_name.values(), key=lambda item: item["name"])
    return venues


def build(args: argparse.Namespace) -> dict[str, Any]:
    target = parse_date(args.date) if args.date else now_lisbon().date()
    if target is None:
        raise SystemExit("--date deve estar em YYYY-MM-DD")
    generated = now_lisbon()
    errors: list[str] = []
    warnings: list[str] = []
    pages: dict[str, dict[str, Any]] = {}

    schedule_html = ""
    venues_html = ""
    for name, url in (("schedule", SCHEDULE_URL), ("venues", VENUES_URL)):
        try:
            body = fetch(url)
            pages[name] = {"url": url, "status": "ok", "bytes": len(body)}
            if name == "schedule":
                schedule_html = body
            else:
                venues_html = body
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            pages[name] = {"url": url, "status": "error", "error": str(exc)}
            errors.append(f"{name}: erro ao descarregar {url}: {exc}")

    sessions, radar, schedule_stats = parse_schedule(schedule_html, target, args.window_days, args.radar_days) if schedule_html else ([], [], {})
    venues = parse_venues(venues_html) if venues_html else []
    if schedule_html and not sessions and not radar:
        warnings.append("MotelX descarregado, mas sem sessoes interpretaveis na janela/radar.")

    return {
        "generated_at": generated.isoformat(timespec="seconds"),
        "source": {
            "name": "motelx",
            "base_url": BASE_URL,
            "urls": {"schedule": SCHEDULE_URL, "films": FILMS_URL, "venues": VENUES_URL},
            "pages": pages,
            "status": "error" if errors else ("warn" if warnings else "ok"),
        },
        "window": {
            "start": target.isoformat(),
            "end": (target + timedelta(days=args.window_days - 1)).isoformat(),
            "days": args.window_days,
            "radar_end": (target + timedelta(days=args.radar_days - 1)).isoformat(),
            "timezone": "Europe/Lisbon",
        },
        "stats": {
            **schedule_stats,
            "venues_seen": len(venues),
            "errors": errors,
            "warnings": warnings,
        },
        "sessions": sessions,
        "radar": radar,
        "venues": venues,
    }


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Extrai a programacao MotelX para a Agenda de Lazer local.")
    parser.add_argument("--date", help="Data alvo em YYYY-MM-DD. Por defeito, hoje em Europe/Lisbon.")
    parser.add_argument("--window-days", type=int, default=WINDOW_DAYS)
    parser.add_argument("--radar-days", type=int, default=60)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()

    data = build(args)
    target = data["window"]["start"]
    out = args.out or Path(__file__).with_name(f"MotelX_{target}.json")
    write_json(out, data)
    print(f"OK: MotelX -> {out}")
    print(f"Status: {data['source']['status']}")
    print(f"Sessoes na janela: {data['stats'].get('sessions_in_window', 0)}")
    print(f"Radar: {data['stats'].get('radar_items', 0)}")
    for warning in data["stats"].get("warnings", []):
        print(f"AVISO: {warning}")
    for error in data["stats"].get("errors", []):
        print(f"ERRO: {error}")
    return 0 if data["source"]["status"] in {"ok", "warn"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
