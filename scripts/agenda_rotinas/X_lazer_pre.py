#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Pre mecânico da Agenda de Lazer.

Este é o equivalente do ``X_briefing_pre.py`` para a Agenda de Lazer. Ele:

* executa diretamente os quatro exportadores antes agrupados em
  ``Relatorios/Sources/System/Go_All_events.bat``;
* recolhe Calendar, ``espelho_lazer``, meteorologia e páginas públicas;
* lê integralmente perfil, feedback, lista sazonal e histórico de viagens;
* normaliza/deduplica candidatos e aplica apenas filtros determinísticos;
* produz um único JSON de handoff com ``canonical_draft`` pronto para a LLM.

A LLM não volta a consultar fontes. Ela apenas cura ``events[]`` e os poucos
campos narrativos explicitamente autorizados em ``_llm_handoff``.

Uso agendado diário::

    python X_lazer_pre.py

Uso pelo launcher LLM (reutiliza o pre diário se tiver menos de 30 h)::

    python X_lazer_pre.py --ensure-fresh-hours 30

Teste sem rede::

    python X_lazer_pre.py --self-test
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import unicodedata
from collections import Counter, defaultdict
from datetime import date, datetime, time, timedelta
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urljoin
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo


SCHEMA_VERSION = "2.0"
ROUTINE = "agenda_lazer"
TZ = ZoneInfo("Europe/Lisbon")
WINDOW_DAYS = 15
RADAR_DAYS = 60

PROJECT_ROOT = Path(os.environ.get("CLAUDE_PRJ_ROOT", r"G:\My Drive\Claude_PRJ"))
AGENDA_ROOT = PROJECT_ROOT / "Agenda"
OUTPUT_DIR = AGENDA_ROOT / "X_Outputs" / "lazer"
SOURCE_SYSTEM = PROJECT_ROOT / "Relatorios" / "Sources" / "System"
SOURCES_ROOT = PROJECT_ROOT / "Relatorios" / "Sources"
GOOGLE_CREDENTIALS = PROJECT_ROOT / "credentials.json"
GOOGLE_TOKEN = PROJECT_ROOT / "token_lazer.json"

PROFILE_PATH = PROJECT_ROOT / "Rafa_profile.md"
FEEDBACK_PATH = PROJECT_ROOT / "Feedback_log.json"
SEASONAL_PATH = AGENDA_ROOT / "Lista_Sazonal.json"
LOCAL_INSTRUCTIONS_PATH = AGENDA_ROOT / "AGENDA_LAZER_INSTRUCOES_v6.0_LOCAL.md"
TRAVEL_PATHS = (
    PROJECT_ROOT / "Viagens" / "travel_log_v2.md",
    PROJECT_ROOT / "Viagens" / "travel_log.md",
)

ESPELHO_LAZER_ID = "15Y75AwcqV4l2GtuGI5kFfSftv6T3kpexKUmfDyBEp5I"
GOOGLE_SCOPES = (
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/spreadsheets.readonly",
)

VALID_CATEGORIES = {
    "tv", "streaming", "cinema_indoor", "cinema_outdoor", "meetup",
    "culture", "books", "gastro", "escape", "radar",
}
FINAL_TOP_LEVEL_KEYS = (
    "meta", "sources", "event_candidates", "events", "futuro_guardado",
    "summary", "validation",
)
MINIMUMS = {
    "meetup": 8,
    "cinema_indoor": 4,
    "web_events": 12,
    "gastro": 5,
    "tv_streaming": 10,
    "books": 5,
    "escape": 6,
    "sports": 1,
}

SPORT_TERMS = (
    "activehive", "luma", "meetup", "voleibol", "volleyball", "beach tennis",
    "hiking", "caminhada", "ciclismo", "bowling", "tenis", "tennis",
)
GASTRO_TERMS = (
    "restaurante", "gastro", "jantar", "almoco", "almoço", "brunch",
    "thefork", "tasca", "menu", "comida", "vinho",
)
TV_TERMS = (
    "sport tv", "rtp", "sic", "tvi", "eurosport", "transmissao",
    "transmissão", "canal 11", "eleven sports", "dazn", "jogo na tv",
)
ESCAPE_TERMS = (
    "sintra", "cascais", "arrabida", "arrábida", "sesimbra", "comporta",
    "ericeira", "escapadinha", "praia", "algarve",
)
LEISURE_TERMS = SPORT_TERMS + GASTRO_TERMS + TV_TERMS + ESCAPE_TERMS + (
    "cinema", "filme", "concerto", "festival", "teatro", "exposicao",
    "exposição", "museu", "festa", "feira", "livro", "book", "show",
)
HARD_PROFILE_EXCLUSIONS = (
    "corrida a pe", "corrida a pé", "running", "sushi", "comida chinesa",
    "restaurante chines", "restaurante chinês", "funk brasileiro", "sertanejo",
    "meetup online", "evento infantil",
)

EXPORTERS: dict[str, dict[str, Any]] = {
    "gmail": {
        "script": SOURCE_SYSTEM / "gmail_events_briefing" / "gmail_events_export.py",
        "directory": SOURCES_ROOT / "Gmail_events",
        "pattern": "Gmail_events_*.json",
        "max_age_days": 5,
        "timeout": 900,
    },
    "cinema": {
        "script": SOURCE_SYSTEM / "websearch_cinema_briefing" / "cinema_export.py",
        "directory": SOURCES_ROOT / "websearch_cinema",
        "pattern": "Cinema_Lisboa_*.json",
        "max_age_days": 7,
        "timeout": 900,
    },
    "streaming": {
        "script": SOURCE_SYSTEM / "websearch_streaming_briefing" / "streaming_export.py",
        "directory": SOURCES_ROOT / "websearch_streaming",
        "pattern": "Streaming_*.json",
        "max_age_days": 7,
        "timeout": 1200,
    },
    "books": {
        "script": SOURCE_SYSTEM / "websearch_livros_briefing" / "books_export.py",
        "directory": SOURCES_ROOT / "websearch_livros",
        "pattern": "Livros_*.json",
        "max_age_days": 7,
        "timeout": 1200,
    },
}

PUBLIC_SOURCES: tuple[tuple[str, str, str], ...] = (
    ("agendalx", "https://www.agendalx.pt/", "culture"),
    ("lisboa_secreta", "https://lisboasecreta.co/", "culture"),
    ("timeout_lisboa", "https://www.timeout.pt/lisboa/pt/coisas-para-fazer/calendario-interno", "culture"),
    ("fever_lisboa", "https://feverup.com/pt/lisboa", "culture"),
    ("camara_lisboa", "https://informacao.lisboa.pt/agenda", "culture"),
    ("activehive", "https://lu.ma/activehive", "meetup"),
    ("lisbon_hiking", "https://www.meetup.com/lisbonhikingmeetup/events/", "meetup"),
    ("thefork_lisboa", "https://www.thefork.pt/restaurantes/lisboa-c665920", "gastro"),
    ("fpf_selecao", "https://www.fpf.pt/pt/selecoes/futebol-masculino/selecao-a/jogos", "tv"),
)

WEEKDAYS = ("Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom")
MONTHS = ("Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez")


def now_lisbon() -> datetime:
    return datetime.now(TZ)


def norm(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"[^a-zA-Z0-9]+", " ", text.lower())
    return re.sub(r"\s+", " ", text).strip()


def parse_date(value: Any, default_year: int | None = None) -> date | None:
    if isinstance(value, datetime):
        return value.astimezone(TZ).date() if value.tzinfo else value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, dict):
        value = value.get("date") or value.get("dateTime") or value.get("datetime") or value.get("start")
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        pass
    for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%d/%m/%y", "%d-%m-%y"):
        try:
            return datetime.strptime(text[:10], fmt).date()
        except ValueError:
            pass
    match = re.search(r"\b(\d{1,2})[/-](\d{1,2})(?:[/-](\d{2,4}))?\b", text)
    if match and default_year:
        year = int(match.group(3)) if match.group(3) else default_year
        if year < 100:
            year += 2000
        try:
            return date(year, int(match.group(2)), int(match.group(1)))
        except ValueError:
            return None
    return None


def parse_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value.astimezone(TZ) if value.tzinfo else value.replace(tzinfo=TZ)
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
        return parsed.astimezone(TZ) if parsed.tzinfo else parsed.replace(tzinfo=TZ)
    except ValueError:
        return None


def date_label(value: date | None) -> str | None:
    if value is None:
        return None
    return f"{WEEKDAYS[value.weekday()]} {value.day} {MONTHS[value.month - 1]}"


def in_window(value: date | None, start: date, days: int = WINDOW_DAYS) -> bool:
    return value is not None and start <= value <= start + timedelta(days=days - 1)


def file_info(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {"exists": False, "path": None}
    info: dict[str, Any] = {"exists": path.exists(), "path": str(path)}
    if path.exists():
        stat = path.stat()
        info.update({
            "name": path.name,
            "size_bytes": stat.st_size,
            "mtime": datetime.fromtimestamp(stat.st_mtime, TZ).isoformat(timespec="seconds"),
        })
    return info


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json_atomic(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        os.replace(tmp_name, path)
    finally:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)


def write_text_atomic(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(value)
        os.replace(tmp_name, path)
    finally:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)


def latest_file(directory: Path, pattern: str) -> Path | None:
    if not directory.exists():
        return None
    files = [path for path in directory.glob(pattern) if path.is_file()]
    return max(files, key=lambda path: path.stat().st_mtime) if files else None


def generated_date(raw: Any, path: Path | None = None) -> date | None:
    if isinstance(raw, dict):
        if isinstance(raw.get("period"), dict):
            parsed = parse_date(raw["period"].get("end"))
            if parsed:
                return parsed
        for key in ("generated_at", "updated_at", "created_at", "date"):
            parsed = parse_date(raw.get(key))
            if parsed:
                return parsed
    if path and path.exists():
        return datetime.fromtimestamp(path.stat().st_mtime, TZ).date()
    return None


def run_exporter(
    name: str,
    spec: dict[str, Any],
    refresh_mode: str,
    today: date,
) -> tuple[Any | None, dict[str, Any], str | None]:
    script = Path(spec["script"])
    directory = Path(spec["directory"])
    before = latest_file(directory, str(spec["pattern"]))
    before_mtime = before.stat().st_mtime if before else 0.0
    state: dict[str, Any] = {
        "ok": False,
        "required": True,
        "script": str(script),
        "executed": False,
        "max_age_days": int(spec["max_age_days"]),
    }

    should_run = refresh_mode == "all"
    if refresh_mode == "stale":
        try:
            prior_raw = load_json(before) if before else None
        except Exception:
            prior_raw = None
        prior_date = generated_date(prior_raw, before)
        should_run = prior_date is None or (today - prior_date).days > int(spec["max_age_days"])

    if should_run:
        if not script.exists():
            return None, state, f"{name}: exportador em falta: {script}"
        try:
            proc = subprocess.run(
                [sys.executable, str(script)],
                cwd=str(script.parent),
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=int(spec["timeout"]),
                check=False,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            return None, state, f"{name}: exportador falhou: {type(exc).__name__}: {exc}"
        state.update({
            "executed": True,
            "returncode": proc.returncode,
            "stdout_tail": proc.stdout[-2000:],
            "stderr_tail": proc.stderr[-2000:],
        })
        if proc.returncode != 0:
            return None, state, f"{name}: exportador terminou com codigo {proc.returncode}"

    output = latest_file(directory, str(spec["pattern"]))
    state["file"] = file_info(output)
    if output is None:
        return None, state, f"{name}: nenhum export encontrado em {directory}"
    if should_run and output.stat().st_mtime <= before_mtime:
        return None, state, f"{name}: exportador terminou sem produzir/actualizar o ficheiro esperado"
    try:
        raw = load_json(output)
    except Exception as exc:
        return None, state, f"{name}: export invalido: {type(exc).__name__}: {exc}"
    stamp = generated_date(raw, output)
    age = (today - stamp).days if stamp else None
    state.update({
        "generated_date": stamp.isoformat() if stamp else None,
        "age_days": age,
        "fresh": age is not None and age <= int(spec["max_age_days"]),
    })
    if not state["fresh"]:
        return raw, state, f"{name}: export desactualizado ({age} dias; maximo {spec['max_age_days']})"
    state["ok"] = True
    return raw, state, None


def google_services(errors: list[str], *, reauthorize: bool = False) -> dict[str, Any]:
    try:
        from google.auth.transport.requests import Request as GoogleRequest
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build
    except ImportError as exc:
        errors.append(f"Google: bibliotecas em falta ({exc})")
        return {}

    creds = None
    try:
        if GOOGLE_TOKEN.exists() and not reauthorize:
            creds = Credentials.from_authorized_user_file(str(GOOGLE_TOKEN), list(GOOGLE_SCOPES))
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(GoogleRequest())
        if not creds or not creds.valid:
            if not GOOGLE_CREDENTIALS.exists():
                errors.append(f"Google: credentials em falta: {GOOGLE_CREDENTIALS}")
                return {}
            flow = InstalledAppFlow.from_client_secrets_file(str(GOOGLE_CREDENTIALS), list(GOOGLE_SCOPES))
            creds = flow.run_local_server(port=0, prompt="consent")
            if creds.granted_scopes is not None and set(GOOGLE_SCOPES) - set(creds.granted_scopes):
                errors.append("Google: nem todos os acessos foram concedidos; token anterior preservado.")
                return {}
        GOOGLE_TOKEN.write_text(creds.to_json(), encoding="utf-8")
        return {
            "calendar": build("calendar", "v3", credentials=creds, cache_discovery=False),
            "sheets": build("sheets", "v4", credentials=creds, cache_discovery=False),
        }
    except Exception as exc:
        errors.append(f"Google: autenticacao/servicos falharam: {type(exc).__name__}: {exc}")
        return {}


def _event_datetime(part: dict[str, Any]) -> tuple[datetime | None, bool]:
    if part.get("dateTime"):
        return parse_datetime(part["dateTime"]), False
    if part.get("date"):
        parsed = parse_date(part["date"])
        return (datetime.combine(parsed, time.min, TZ) if parsed else None), True
    return None, False


def _calendar_flags(blob: str) -> list[str]:
    cleaned = norm(blob)
    flags = []
    if "sigic" in cleaned:
        flags.append("sigic")
    if "prevencao" in cleaned:
        flags.append("prevencao")
    if any(term in cleaned for term in ("viagem", "flight", "voo", "hotel", "aeroporto")):
        flags.append("travel")
    return flags


def guess_category(text: str, fallback: str | None = "culture") -> str | None:
    cleaned = norm(text)
    if any(term in cleaned for term in SPORT_TERMS):
        return "meetup"
    if any(norm(term) in cleaned for term in GASTRO_TERMS):
        return "gastro"
    if any(norm(term) in cleaned for term in TV_TERMS):
        return "tv"
    if any(norm(term) in cleaned for term in ESCAPE_TERMS):
        return "escape"
    if "cinema" in cleaned or "filme" in cleaned:
        return "cinema_outdoor"
    if "livro" in cleaned or " book " in f" {cleaned} ":
        return "books"
    if any(term in cleaned for term in ("concerto", "festival", "teatro", "exposicao", "museu", "festa", "feira")):
        return "culture"
    return fallback


def collect_calendar(service: Any, target: date) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    start_dt = datetime.combine(target, time.min, TZ)
    end_dt = datetime.combine(target + timedelta(days=WINDOW_DAYS), time.min, TZ)
    calendars: list[dict[str, Any]] = []
    token = None
    while True:
        response = service.calendarList().list(pageToken=token, maxResults=250).execute()
        calendars.extend(response.get("items", []))
        token = response.get("nextPageToken")
        if not token:
            break

    items: list[dict[str, Any]] = []
    failures: list[dict[str, str]] = []
    for calendar in calendars:
        calendar_id = str(calendar.get("id", ""))
        summary = str(calendar.get("summary") or calendar_id)
        if norm(summary) == "todoist":
            continue
        page_token = None
        try:
            while True:
                response = service.events().list(
                    calendarId=calendar_id,
                    timeMin=start_dt.isoformat(),
                    timeMax=end_dt.isoformat(),
                    singleEvents=True,
                    orderBy="startTime",
                    maxResults=2500,
                    pageToken=page_token,
                    timeZone="Europe/Lisbon",
                ).execute()
                for event in response.get("items", []):
                    start, all_day = _event_datetime(event.get("start") or {})
                    end, _ = _event_datetime(event.get("end") or {})
                    if start is None:
                        continue
                    title = str(event.get("summary") or "(sem titulo)").strip()
                    blob = " ".join((title, str(event.get("description") or ""), str(event.get("location") or "")))
                    items.append({
                        "calendar_id": calendar_id,
                        "calendar": summary,
                        "event_id": event.get("id"),
                        "title": title,
                        "start": start.isoformat(timespec="minutes"),
                        "end": end.isoformat(timespec="minutes") if end else None,
                        "date": start.date().isoformat(),
                        "time": None if all_day else start.strftime("%H:%M"),
                        "all_day": all_day,
                        "location": event.get("location"),
                        "description": str(event.get("description") or "")[:1200],
                        "html_link": event.get("htmlLink"),
                        "flags": _calendar_flags(blob),
                    })
                page_token = response.get("nextPageToken")
                if not page_token:
                    break
        except Exception as exc:
            failures.append({"calendar": summary, "error": f"{type(exc).__name__}: {exc}"})

    seen: set[tuple[str, str, str]] = set()
    deduped = []
    for item in items:
        key = (norm(item["title"]), str(item["start"]), str(item.get("end") or ""))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)

    personal: dict[str, list[str]] = defaultdict(list)
    flags: dict[str, list[dict[str, Any]]] = {"sigic": [], "prevencao": [], "travel": []}
    candidates: list[dict[str, Any]] = []
    for item in deduped:
        prefix = "" if item["all_day"] else f"{item['time']} · "
        personal[item["date"]].append(prefix + item["title"])
        for flag in item["flags"]:
            flags[flag].append({"date": item["date"], "title": item["title"]})
        blob = " ".join((item["title"], item["description"], str(item.get("location") or "")))
        if any(norm(term) in norm(blob) for term in LEISURE_TERMS):
            category = guess_category(blob, "culture") or "culture"
            candidates.append(make_candidate(
                "calendar", category, item["title"], parse_date(item["date"]),
                time_value=item.get("time"), location=item.get("location"),
                description=item.get("description"), link=item.get("html_link"),
                flags=["confirmed"], facts={"calendar": item["calendar"], "event_id": item["event_id"]},
            ))

    context = {
        "ok": not failures,
        "calendars_seen": len(calendars),
        "events": deduped,
        "failures": failures,
        "availability_flags": flags,
        "calendario_pessoal": [
            {"date": day, "compromissos": commitments}
            for day, commitments in sorted(personal.items())
        ],
    }
    return context, candidates


def collect_espelho_lazer(service: Any) -> list[dict[str, str]]:
    meta = service.spreadsheets().get(
        spreadsheetId=ESPELHO_LAZER_ID,
        fields="sheets.properties.title",
    ).execute()
    sheets = meta.get("sheets", [])
    if not sheets:
        return []
    title = str(sheets[0]["properties"]["title"])
    escaped = title.replace("'", "''")
    values = service.spreadsheets().values().get(
        spreadsheetId=ESPELHO_LAZER_ID,
        range=f"'{escaped}'!A:H",
    ).execute().get("values", [])
    if not values:
        return []
    headers = [str(value).strip() for value in values[0]]
    rows = []
    for raw_row in values[1:]:
        padded = list(raw_row) + [""] * max(0, len(headers) - len(raw_row))
        rows.append({headers[i]: str(padded[i]).strip() for i in range(len(headers))})
    return rows


def collect_weather(target: date) -> dict[str, Any]:
    params = {
        "latitude": 38.7223,
        "longitude": -9.1393,
        "timezone": "Europe/Lisbon",
        "forecast_days": 16,
        "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max",
    }
    request = Request(
        "https://api.open-meteo.com/v1/forecast?" + urlencode(params),
        headers={"User-Agent": "AgendaLazerPre/2.0"},
    )
    with urlopen(request, timeout=25) as response:
        raw = json.loads(response.read().decode("utf-8"))
    daily = raw.get("daily") or {}
    rows = []
    for idx, day in enumerate(daily.get("time") or []):
        parsed = parse_date(day)
        if not in_window(parsed, target):
            continue
        rows.append({
            "date": day,
            "weather_code": (daily.get("weather_code") or [None] * 20)[idx],
            "temp_max": (daily.get("temperature_2m_max") or [None] * 20)[idx],
            "temp_min": (daily.get("temperature_2m_min") or [None] * 20)[idx],
            "precipitation_probability_max": (daily.get("precipitation_probability_max") or [None] * 20)[idx],
        })
    return {"ok": True, "provider": "Open-Meteo", "days": rows}


class JsonLdParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.capture = False
        self.buffer: list[str] = []
        self.blocks: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = {key.lower(): (value or "") for key, value in attrs}
        if tag.lower() == "script" and "ld+json" in attrs_dict.get("type", "").lower():
            self.capture = True
            self.buffer = []

    def handle_data(self, data: str) -> None:
        if self.capture:
            self.buffer.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "script" and self.capture:
            self.blocks.append("".join(self.buffer))
            self.capture = False
            self.buffer = []


class TimeOutTileParser(HTMLParser):
    """Extrai os cards factuais do calendário Time Out sem depender de CSS estável."""

    def __init__(self) -> None:
        super().__init__()
        self.in_article = False
        self.current: dict[str, str] = {}
        self.capture_tag: str | None = None
        self.capture_field: str | None = None
        self.buffer: list[str] = []
        self.items: list[dict[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr = {key.lower(): (value or "") for key, value in attrs}
        if tag == "article" and not self.in_article:
            marker = (attr.get("class", "") + " " + attr.get("data-testid", "")).lower()
            if "tile" in marker:
                self.in_article = True
                self.current = {}
                return
        if not self.in_article:
            return
        if tag == "a" and attr.get("href") and not self.current.get("href"):
            self.current["href"] = attr["href"]
        field = None
        if tag == "h3":
            field = "title"
        elif tag == "h5":
            field = "category_label"
        elif tag == "time":
            field = "date_label"
            if attr.get("datetime"):
                self.current["datetime"] = attr["datetime"]
        elif tag == "div":
            marker = (attr.get("class", "") + " " + attr.get("data-testid", "")).lower()
            if "summary" in marker:
                field = "description"
        if field and self.capture_tag is None:
            self.capture_tag = tag
            self.capture_field = field
            self.buffer = []

    def handle_data(self, data: str) -> None:
        if self.capture_tag:
            self.buffer.append(data)

    def handle_endtag(self, tag: str) -> None:
        if not self.in_article:
            return
        if self.capture_tag == tag and self.capture_field:
            value = re.sub(r"\s+", " ", "".join(self.buffer)).strip()
            if value:
                self.current[self.capture_field] = value
            self.capture_tag = None
            self.capture_field = None
            self.buffer = []
        if tag == "article":
            if self.current.get("title") and self.current.get("datetime"):
                self.items.append(dict(self.current))
            self.in_article = False
            self.current = {}


def walk_json(value: Any) -> Iterable[dict[str, Any]]:
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from walk_json(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk_json(child)


def location_text(value: Any) -> str | None:
    if isinstance(value, str):
        return value.strip() or None
    if not isinstance(value, dict):
        return None
    parts = [str(value.get("name") or "").strip()]
    address = value.get("address")
    if isinstance(address, str):
        parts.append(address.strip())
    elif isinstance(address, dict):
        parts.extend(str(address.get(key) or "").strip() for key in ("streetAddress", "addressLocality"))
    return ", ".join(part for part in parts if part) or None


def collect_public_source(name: str, url: str, category: str, target: date) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    request = Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; AgendaLazerPre/2.0)"})
    try:
        with urlopen(request, timeout=25) as response:
            html = response.read(2_500_000).decode(response.headers.get_content_charset() or "utf-8", errors="replace")
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        return [], {"ok": False, "url": url, "error": f"{type(exc).__name__}: {exc}", "items": 0}
    parser = JsonLdParser()
    parser.feed(html)
    events: list[dict[str, Any]] = []
    json_errors = 0
    for block in parser.blocks:
        try:
            payload = json.loads(block.strip())
        except (json.JSONDecodeError, TypeError):
            json_errors += 1
            continue
        for item in walk_json(payload):
            item_type = item.get("@type")
            types = item_type if isinstance(item_type, list) else [item_type]
            if not any(str(value).lower().endswith("event") for value in types if value):
                continue
            title = str(item.get("name") or "").strip()
            if not title:
                continue
            start = parse_date(item.get("startDate"), target.year)
            if start and not in_window(start, target, RADAR_DAYS):
                continue
            event_category = "radar" if start and not in_window(start, target) else category
            events.append(make_candidate(
                f"web:{name}", event_category, title, start,
                time_value=(parse_datetime(item.get("startDate")).strftime("%H:%M") if parse_datetime(item.get("startDate")) else None),
                location=location_text(item.get("location")),
                description=str(item.get("description") or "")[:1800],
                link=urljoin(url, str(item.get("url") or "")) if item.get("url") else url,
                date_end=parse_date(item.get("endDate"), target.year),
                facts={"source_name": name, "schema_type": types},
            ))
    html_tiles = 0
    if name == "timeout_lisboa":
        tile_parser = TimeOutTileParser()
        tile_parser.feed(html)
        html_tiles = len(tile_parser.items)
        for item in tile_parser.items:
            event_date = parse_date(item.get("datetime"), target.year)
            if event_date is None or not in_window(event_date, target, RADAR_DAYS):
                continue
            blob = " ".join(
                str(item.get(key) or "")
                for key in ("category_label", "title", "description")
            )
            event_category = guess_category(blob, category) or category
            if not in_window(event_date, target):
                event_category = "radar"
            candidate = make_candidate(
                f"web:{name}", event_category, item["title"], event_date,
                description=item.get("description"),
                link=urljoin(url, item.get("href") or ""),
                facts={
                    "source_name": name,
                    "html_card": True,
                    "category_label": item.get("category_label"),
                    "datetime": item.get("datetime"),
                },
            )
            if item.get("date_label"):
                candidate["date_label"] = item["date_label"]
            events.append(candidate)
    return events, {
        "ok": True,
        "url": url,
        "items": len(events),
        "json_ld_blocks": len(parser.blocks),
        "json_errors": json_errors,
        "html_tiles": html_tiles,
    }


def extract_profile_sections(text: str, section_numbers: Iterable[int] = (1, 6, 8, 11, 12, 14, 15, 16, 17)) -> dict[str, str]:
    wanted = set(section_numbers)
    sections: dict[str, list[str]] = {}
    current: int | None = None
    for line in text.splitlines():
        match = re.match(r"^#\s+.*?\b(\d+)\.\s+", line)
        if match:
            current = int(match.group(1))
            if current in wanted:
                sections[str(current)] = [line]
            continue
        if current in wanted:
            sections[str(current)].append(line)
    return {key: "\n".join(lines).strip() for key, lines in sections.items()}


def compact_feedback(raw: Any) -> dict[str, Any]:
    entries = raw.get("entries", []) if isinstance(raw, dict) else []
    complete_entries = []
    excluded = []
    recommendations = []
    dish_blacklist: list[str] = []
    for item in entries:
        if not isinstance(item, dict):
            continue
        flags = item.get("flags") if isinstance(item.get("flags"), dict) else {}
        status = norm(item.get("status"))
        title = str(item.get("title") or item.get("name") or "").strip()
        # Preservar cada entrada completa. Campos como context, cost, origin,
        # confidence e web_data tambem influenciam a curadoria e nao podem ser
        # substituidos por um resumo antes da LLM.
        complete = dict(item)
        complete_entries.append(complete)
        if title and (status == "excluded" or flags.get("never_again") is True):
            excluded.append({"title": title, "reason": item.get("notes"), "id": item.get("id")})
        if title and norm(item.get("source")) == "third party recommendation" and status in {"suggested", "planned"}:
            recommendations.append(complete)
        values = item.get("dish_blacklist")
        if isinstance(values, list):
            dish_blacklist.extend(str(value) for value in values if value)
        if isinstance(flags.get("dish_blacklist"), list):
            dish_blacklist.extend(str(value) for value in flags["dish_blacklist"] if value)
    return {
        "meta": raw.get("meta", {}) if isinstance(raw, dict) else {},
        "profile": raw.get("profile", {}) if isinstance(raw, dict) else {},
        "categorias_legado": raw.get("categorias_legado", {}) if isinstance(raw, dict) else {},
        "categorias": raw.get("categorias", {}) if isinstance(raw, dict) else {},
        "states": raw.get("estados_oficiais", {}) if isinstance(raw, dict) else {},
        "schema_entrada": raw.get("schema_entrada", {}) if isinstance(raw, dict) else {},
        "entries": complete_entries,
        "excluded": excluded,
        "dish_blacklist": sorted(set(dish_blacklist)),
        "third_party_recommendations": recommendations,
    }


def feedback_category(value: Any) -> str | None:
    cleaned = norm(value)
    return {
        "restaurant": "gastro",
        "drink": "gastro",
        "movie": "streaming",
        "series": "streaming",
        "book": "books",
        "place": "escape",
        "activity": "culture",
        "other": "radar",
    }.get(cleaned)


def feedback_candidates(context: dict[str, Any]) -> list[dict[str, Any]]:
    candidates = []
    for item in context.get("third_party_recommendations", []):
        category = feedback_category(item.get("category"))
        title = str(item.get("title") or "").strip()
        if not category or not title:
            continue
        candidates.append(make_candidate(
            "feedback", category, title, None,
            location=item.get("location"),
            description=item.get("notes") or item.get("web_summary"),
            flags=["third_party_recommendation"],
            facts={"feedback_id": item.get("id"), "status": item.get("status"), "source": item.get("source")},
        ))
    return candidates


def make_candidate(
    source: str,
    category: str,
    title: str,
    event_date: date | None,
    *,
    time_value: Any = None,
    location: Any = None,
    description: Any = None,
    link: Any = None,
    date_end: date | None = None,
    flags: Iterable[str] = (),
    facts: Any = None,
) -> dict[str, Any]:
    category = category if category in VALID_CATEGORIES else "culture"
    return {
        "candidate_id": None,
        "source": source,
        "category": category,
        "title": str(title or "").strip(),
        "date": event_date.isoformat() if event_date else None,
        "date_inicio": event_date.isoformat() if event_date else None,
        "date_fim": date_end.isoformat() if date_end else None,
        "date_label": date_label(event_date),
        "time": str(time_value).strip() if time_value not in (None, "") else None,
        "location": str(location).strip() if location not in (None, "") else None,
        "description": str(description or "").strip()[:2400],
        "link": str(link).strip() if link not in (None, "") else None,
        "flags": sorted(set(str(value) for value in flags if value)),
        "facts": facts if facts not in (None, "", [], {}) else {},
    }


def normalize_gmail(raw: Any, target: date) -> list[dict[str, Any]]:
    output = []
    for index, email in enumerate(raw.get("emails", []) if isinstance(raw, dict) else []):
        if not isinstance(email, dict):
            continue
        hints = email.get("event_hints") if isinstance(email.get("event_hints"), dict) else {}
        body = str(email.get("body_text") or "")
        subject = str(email.get("subject") or "").strip()
        if not subject:
            continue
        guessed_date = parse_date(hints.get("date_guess"), target.year)
        if guessed_date and not in_window(guessed_date, target, RADAR_DAYS):
            guessed_date = None
        category = guess_category(subject + " " + body, "culture") or "culture"
        links = []
        for link in email.get("links", []) if isinstance(email.get("links"), list) else []:
            if not isinstance(link, dict):
                continue
            links.append({
                "url": link.get("url") or link.get("href") or link.get("link"),
                "article_text": str(link.get("article_text") or "")[:1400] or None,
            })
        output.append(make_candidate(
            "gmail", category, subject, guessed_date,
            time_value=hints.get("time_guess"), location=hints.get("location_guess"),
            description=body[:2200], link=(links[0].get("url") if links else None),
            flags=["email_may_contain_multiple_events"] if len(links) > 1 else [],
            facts={"email_index": index, "sender": email.get("sender"), "email_date": email.get("date"), "event_hints": hints, "links": links},
        ))
    return output


def normalize_cinema(raw: Any, target: date) -> list[dict[str, Any]]:
    output = []
    indoor = raw.get("indoor", {}) if isinstance(raw, dict) else {}
    for index, movie in enumerate(indoor.get("cinecartaz", []) if isinstance(indoor, dict) else []):
        if not isinstance(movie, dict):
            continue
        title = str(movie.get("title") or movie.get("titulo") or movie.get("name") or "").strip()
        if not title:
            continue
        showings = [item for item in movie.get("showings", []) if isinstance(item, dict)] if isinstance(movie.get("showings"), list) else []
        locations = sorted({str(item.get("cinema") or item.get("sala") or item.get("venue") or "").strip() for item in showings} - {""})
        synopsis = movie.get("synopsis") or movie.get("sinopse") or movie.get("overview") or movie.get("description")
        flags = []
        if not synopsis:
            flags.append("missing_synopsis")
        if not showings:
            flags.append("missing_showings")
        output.append(make_candidate(
            "cinema", "cinema_indoor", title, None,
            location=", ".join(locations), description=synopsis,
            link=movie.get("link") or movie.get("url"), flags=flags,
            facts={
                "raw_index": index,
                "genre": movie.get("genre") or movie.get("genero"),
                "duration": movie.get("duration") or movie.get("duracao"),
                "year": movie.get("year") or movie.get("ano"),
                "country": movie.get("country") or movie.get("pais"),
                "showings": showings,
            },
        ))
    open_air = raw.get("open_air", {}) if isinstance(raw, dict) else {}
    if isinstance(open_air, dict):
        for bucket, items in open_air.items():
            for index, item in enumerate(items if isinstance(items, list) else []):
                if not isinstance(item, dict):
                    continue
                title = str(item.get("title") or item.get("titulo") or item.get("name") or "").strip()
                if not title:
                    continue
                day = parse_date(item.get("date") or item.get("data"), target.year)
                if day and not in_window(day, target):
                    continue
                output.append(make_candidate(
                    "cinema", "cinema_outdoor", title, day,
                    time_value=item.get("time") or item.get("hora"),
                    location=item.get("location") or item.get("local") or item.get("venue"),
                    description=item.get("synopsis") or item.get("sinopse") or item.get("description"),
                    link=item.get("link") or item.get("url"),
                    flags=[] if day else ["date_missing_or_unparsed"],
                    facts={"bucket": bucket, "raw_index": index},
                ))
    return output


def normalize_streaming(raw: Any) -> list[dict[str, Any]]:
    output = []
    for kind in ("movies", "series"):
        for index, item in enumerate(raw.get(kind, []) if isinstance(raw, dict) else []):
            if not isinstance(item, dict):
                continue
            title = str(item.get("title") or item.get("name") or item.get("titulo") or "").strip()
            if not title:
                continue
            platforms = item.get("platforms") if isinstance(item.get("platforms"), list) else []
            output.append(make_candidate(
                "streaming", "streaming", title, None,
                description=item.get("overview") or item.get("description") or item.get("sinopse"),
                link=item.get("link") or item.get("url"),
                flags=[] if platforms else ["platform_missing"],
                facts={
                    "kind": kind[:-1], "platforms": platforms,
                    "genres": item.get("genres") or item.get("generos"),
                    "vote_average": item.get("vote_average"),
                    "release_date": item.get("release_date") or item.get("first_air_date"),
                    "overview_em_ingles": item.get("overview_em_ingles"),
                    "raw_index": index,
                },
            ))
    return output


def normalize_books(raw: Any) -> list[dict[str, Any]]:
    output = []
    for index, item in enumerate(raw.get("books", []) if isinstance(raw, dict) else []):
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or item.get("titulo") or item.get("name") or "").strip()
        if not title:
            continue
        output.append(make_candidate(
            "books", "books", title, None,
            description=item.get("description") or item.get("descricao"),
            link=item.get("link") or item.get("url"),
            facts={
                "authors": item.get("authors") or item.get("autores"),
                "categories": item.get("categories") or item.get("categorias"),
                "published_date": item.get("published_date"),
                "average_rating": item.get("average_rating"),
                "ratings_count": item.get("ratings_count"),
                "language": item.get("language"),
                "raw_index": index,
            },
        ))
    return output


def normalize_motelx(raw: Any, target: date) -> list[dict[str, Any]]:
    output = []
    for bucket, default_category in (("sessions", "cinema_indoor"), ("sessoes", "cinema_indoor"), ("radar", "radar")):
        for index, item in enumerate(raw.get(bucket, []) if isinstance(raw, dict) else []):
            if not isinstance(item, dict):
                continue
            title = str(item.get("title") or item.get("titulo") or item.get("name") or "").strip()
            if not title:
                continue
            day = parse_date(item.get("date") or item.get("data") or item.get("starts_at"), target.year)
            if day and not in_window(day, target, RADAR_DAYS):
                continue
            category = str(item.get("category") or default_category)
            if day and not in_window(day, target):
                category = "radar"
            output.append(make_candidate(
                "motelx", category, title, day,
                time_value=item.get("time") or item.get("hora"),
                location=item.get("location") or item.get("local") or item.get("venue"),
                description=item.get("description") or item.get("descricao") or item.get("summary"),
                link=item.get("link") or item.get("url"), flags=["motelx"],
                facts={"bucket": bucket, "raw_index": index},
            ))
    return output


def month_from_text(value: Any) -> int | None:
    cleaned = norm(value)
    names = {
        "janeiro": 1, "jan": 1, "fevereiro": 2, "fev": 2, "marco": 3, "mar": 3,
        "abril": 4, "abr": 4, "maio": 5, "mai": 5, "junho": 6, "jun": 6,
        "julho": 7, "jul": 7, "agosto": 8, "ago": 8, "setembro": 9, "set": 9,
        "outubro": 10, "out": 10, "novembro": 11, "nov": 11, "dezembro": 12, "dez": 12,
    }
    for name, number in names.items():
        if re.search(rf"\b{re.escape(name)}\b", cleaned):
            return number
    return None


def normalize_seasonal(raw: Any, target: date) -> list[dict[str, Any]]:
    months = {(target + timedelta(days=index)).month for index in range(RADAR_DAYS)}
    output = []
    for index, item in enumerate(raw.get("entries", []) if isinstance(raw, dict) else []):
        if not isinstance(item, dict):
            continue
        month = month_from_text(item.get("epoca"))
        if month is not None and month not in months:
            continue
        title = str(item.get("nome") or item.get("title") or "").strip()
        if not title:
            continue
        category = "radar" if item.get("reserva_antecipada") else "escape"
        description = " · ".join(str(item.get(key)).strip() for key in ("epoca", "aviso_ideal", "observacoes") if item.get(key))
        output.append(make_candidate(
            "seasonal", category, title, None,
            description=description, link=item.get("link"), flags=["seasonal"],
            facts={"seasonal_id": item.get("id"), "month": month, "reserva_antecipada": bool(item.get("reserva_antecipada")), "raw_index": index},
        ))
    return output


def curation_key(title: Any, category: Any) -> str:
    return f"{str(title or '').strip().casefold()}::{str(category or '').strip()}"


def latest_curation(rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    latest: dict[str, dict[str, str]] = {}
    for row in rows:
        key = row.get("dedup_key") or curation_key(row.get("titulo"), row.get("categoria"))
        if not key:
            continue
        previous = latest.get(key)
        if previous is None or str(row.get("timestamp", "")) > str(previous.get("timestamp", "")):
            latest[key] = row
    return latest


def apply_curation(
    candidates: list[dict[str, Any]],
    rows: list[dict[str, str]],
    target: date,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    latest = latest_curation(rows)
    filtered = []
    future = []
    excluded = []
    elevated = []
    for candidate in candidates:
        key = curation_key(candidate.get("title"), candidate.get("category"))
        state = latest.get(key)
        action = str(state.get("acao") or "") if state else ""
        if action in {"removido", "consumido"}:
            excluded.append({"candidate_id": candidate.get("candidate_id"), "title": candidate.get("title"), "action": action})
            continue
        if action == "elevar":
            expiry = parse_date(state.get("expira_em") or state.get("data_evento"))
            if expiry is None or expiry >= target:
                candidate["flags"] = sorted(set(candidate.get("flags", []) + ["elevado", "highlight_forced"]))
                candidate["curation"] = {"elevado": True, "expira_em": expiry.isoformat() if expiry else None}
                elevated.append({"title": candidate.get("title"), "expira_em": expiry.isoformat() if expiry else None})
        filtered.append(candidate)
    for key, row in latest.items():
        if row.get("acao") != "guardado_futuro":
            continue
        title = str(row.get("titulo") or "").strip()
        category = str(row.get("categoria") or "").strip()
        if not title or category not in VALID_CATEGORIES:
            continue
        future.append({
            "title": title,
            "category": category,
            "data_guardado": row.get("data_evento") or str(row.get("timestamp") or "")[:10] or None,
        })
    details = {
        "rows_seen": len(rows),
        "latest_keys": len(latest),
        "latest_by_action": dict(sorted(Counter(str(row.get("acao") or "") for row in latest.values()).items())),
        "excluded": excluded,
        "elevated": elevated,
        "futuro_guardado_count": len(future),
    }
    return filtered, future, details


def apply_feedback_exclusions(
    candidates: list[dict[str, Any]],
    feedback: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    excluded_map = {norm(item.get("title")): item for item in feedback.get("excluded", []) if norm(item.get("title"))}
    filtered = []
    matches = []
    for candidate in candidates:
        match = excluded_map.get(norm(candidate.get("title")))
        if match:
            matches.append({"title": candidate.get("title"), "feedback_id": match.get("id"), "reason": match.get("reason")})
            continue
        filtered.append(candidate)
    return filtered, matches


def apply_profile_hard_flags(candidates: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    filtered = []
    removed = []
    for candidate in candidates:
        blob = norm(" ".join((str(candidate.get("title") or ""), str(candidate.get("description") or ""))))
        reason = next((term for term in HARD_PROFILE_EXCLUSIONS if norm(term) in blob), None)
        if reason:
            removed.append({"title": candidate.get("title"), "rule": reason})
            continue
        filtered.append(candidate)
    return filtered, removed


def dedupe_candidates(candidates: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    seen: dict[tuple[str, str, str], dict[str, Any]] = {}
    duplicates = []
    for candidate in candidates:
        if not candidate.get("title"):
            continue
        key = (norm(candidate.get("title")), str(candidate.get("date") or ""), norm(candidate.get("location")))
        if key in seen:
            duplicates.append({
                "title": candidate.get("title"),
                "source": candidate.get("source"),
                "duplicate_of": seen[key].get("source"),
            })
            sources = seen[key].setdefault("also_seen_in", [])
            if candidate.get("source") not in sources:
                sources.append(candidate.get("source"))
            continue
        payload = "|".join(key + (str(candidate.get("source") or ""),))
        candidate["candidate_id"] = "cand_" + hashlib.sha1(payload.encode("utf-8")).hexdigest()[:10]
        seen[key] = candidate
    return list(seen.values()), duplicates


def apply_calendar_conflicts(candidates: list[dict[str, Any]], calendar: dict[str, Any]) -> None:
    flags = calendar.get("availability_flags", {}) if isinstance(calendar, dict) else {}
    blocked: dict[str, set[str]] = defaultdict(set)
    for flag in ("sigic", "prevencao", "travel"):
        for item in flags.get(flag, []):
            if item.get("date"):
                blocked[str(item["date"])].add(flag)
    for candidate in candidates:
        day = candidate.get("date")
        if not day or day not in blocked:
            continue
        candidate["flags"] = sorted(set(candidate.get("flags", [])) | {f"calendar_{flag}_same_day" for flag in blocked[day]})


def coverage(candidates: list[dict[str, Any]]) -> dict[str, Any]:
    by_category = Counter(str(item.get("category")) for item in candidates)
    by_source = Counter(str(item.get("source")) for item in candidates)
    sports = sum(
        1 for item in candidates
        if any(norm(term) in norm(str(item.get("title")) + " " + str(item.get("description"))) for term in SPORT_TERMS)
    )
    basis = {
        "meetup": by_category["meetup"],
        "cinema_indoor": by_category["cinema_indoor"],
        "web_events": sum(value for key, value in by_source.items() if key.startswith("web:")),
        "gastro": by_category["gastro"],
        "tv_streaming": by_category["tv"] + by_category["streaming"],
        "books": by_category["books"],
        "escape": by_category["escape"],
        "sports": sports,
    }
    gaps = [
        {"area": key, "count": basis[key], "minimum": minimum, "missing": minimum - basis[key]}
        for key, minimum in MINIMUMS.items() if basis[key] < minimum
    ]
    return {
        "by_category": {category: by_category[category] for category in sorted(VALID_CATEGORIES)},
        "by_source": dict(sorted(by_source.items())),
        "threshold_basis": basis,
        "threshold_gaps": gaps,
    }


def load_local_context(
    path: Path,
    name: str,
    errors: list[str],
    *,
    json_file: bool,
) -> Any:
    if not path.exists():
        errors.append(f"{name}: ficheiro em falta: {path}")
        return None
    try:
        return load_json(path) if json_file else path.read_text(encoding="utf-8-sig", errors="replace")
    except Exception as exc:
        errors.append(f"{name}: leitura falhou: {type(exc).__name__}: {exc}")
        return None


def build(args: argparse.Namespace) -> dict[str, Any]:
    generated = now_lisbon()
    target = parse_date(args.target_date) if args.target_date else generated.date()
    if target is None:
        raise ValueError("--target-date deve estar em YYYY-MM-DD")
    run_id = args.run_id or generated.strftime("%Y_%m_%d_%H%M")
    output_dir = Path(args.output_dir)
    final_path = output_dir / f"{run_id}_lazer_final.json"
    warnings: list[str] = []
    errors: list[str] = []
    source_states: dict[str, Any] = {}
    candidates: list[dict[str, Any]] = []

    exporter_raw: dict[str, Any] = {}
    for name, spec in EXPORTERS.items():
        raw, state, error = run_exporter(name, spec, args.refresh_mode, generated.date())
        source_states[name] = state
        exporter_raw[name] = raw or {}
        if error:
            errors.append(error)

    candidates.extend(normalize_gmail(exporter_raw["gmail"], target))
    candidates.extend(normalize_cinema(exporter_raw["cinema"], target))
    candidates.extend(normalize_streaming(exporter_raw["streaming"]))
    candidates.extend(normalize_books(exporter_raw["books"]))

    profile_text = load_local_context(PROFILE_PATH, "profile", errors, json_file=False)
    feedback_raw = load_local_context(FEEDBACK_PATH, "feedback", errors, json_file=True)
    seasonal_raw = load_local_context(SEASONAL_PATH, "seasonal", errors, json_file=True)
    instructions_text = load_local_context(
        LOCAL_INSTRUCTIONS_PATH, "instructions", errors, json_file=False
    )
    travel_path = next((path for path in TRAVEL_PATHS if path.exists()), None)
    travel_text = load_local_context(travel_path, "travel_log", warnings, json_file=False) if travel_path else ""

    profile_context = {
        "path": str(PROFILE_PATH),
        "sha256": hashlib.sha256(profile_text.encode("utf-8")).hexdigest() if profile_text else None,
        "full_text": profile_text or "",
        "sections": extract_profile_sections(profile_text or ""),
        "hard_exclusions": list(HARD_PROFILE_EXCLUSIONS),
    }
    feedback_context = compact_feedback(feedback_raw or {})
    candidates.extend(feedback_candidates(feedback_context))
    candidates.extend(normalize_seasonal(seasonal_raw or {}, target))

    services = google_services(errors)
    calendar_context: dict[str, Any] = {"ok": False, "error": "sem servico Google", "availability_flags": {}, "calendario_pessoal": []}
    espelho_rows: list[dict[str, str]] = []
    if services:
        try:
            calendar_context, calendar_candidates = collect_calendar(services["calendar"], target)
            candidates.extend(calendar_candidates)
            source_states["calendar"] = {
                "ok": bool(calendar_context.get("ok")),
                "required": True,
                "events": len(calendar_context.get("events", [])),
                "failures": calendar_context.get("failures", []),
            }
            if not calendar_context.get("ok"):
                errors.append("calendar: um ou mais calendarios falharam")
        except Exception as exc:
            source_states["calendar"] = {"ok": False, "required": True, "error": f"{type(exc).__name__}: {exc}"}
            errors.append(f"calendar: recolha falhou: {type(exc).__name__}: {exc}")
        try:
            espelho_rows = collect_espelho_lazer(services["sheets"])
            source_states["espelho_lazer"] = {"ok": True, "required": True, "rows": len(espelho_rows), "spreadsheet_id": ESPELHO_LAZER_ID}
        except Exception as exc:
            source_states["espelho_lazer"] = {"ok": False, "required": True, "error": f"{type(exc).__name__}: {exc}"}
            errors.append(f"espelho_lazer: leitura falhou: {type(exc).__name__}: {exc}")
    else:
        source_states["calendar"] = {"ok": False, "required": True, "error": "sem servico Google"}
        source_states["espelho_lazer"] = {"ok": False, "required": True, "error": "sem servico Google"}

    try:
        weather = collect_weather(target)
        source_states["weather"] = {"ok": True, "required": False, "provider": "Open-Meteo", "days": len(weather["days"])}
    except Exception as exc:
        weather = {"ok": False, "error": f"{type(exc).__name__}: {exc}", "days": []}
        source_states["weather"] = {"ok": False, "required": False, "error": weather["error"]}
        warnings.append(f"weather: {weather['error']}")

    if not args.skip_public_sources:
        public_states = {}
        for name, url, category in PUBLIC_SOURCES:
            batch, state = collect_public_source(name, url, category, target)
            candidates.extend(batch)
            public_states[name] = state
            if not state.get("ok"):
                warnings.append(f"web:{name}: {state.get('error')}")
        source_states["public_web"] = {"ok": any(state.get("ok") for state in public_states.values()), "required": False, "sources": public_states}
    else:
        source_states["public_web"] = {"ok": False, "required": False, "skipped": True}

    motelx_path = Path(args.motelx_json) if args.motelx_json else latest_file(AGENDA_ROOT / "X_Rotinas_Python" / "Agenda_Lazer", "MotelX_*.json")
    if motelx_path:
        try:
            motelx_raw = load_json(motelx_path)
            candidates.extend(normalize_motelx(motelx_raw, target))
            source_states["motelx"] = {"ok": True, "required": False, "file": file_info(motelx_path)}
        except Exception as exc:
            source_states["motelx"] = {"ok": False, "required": False, "error": f"{type(exc).__name__}: {exc}"}
            warnings.append(f"motelx: {type(exc).__name__}: {exc}")
    else:
        source_states["motelx"] = {"ok": False, "required": False, "reason": "sem export sazonal"}

    source_states["profile"] = {"ok": profile_text is not None, "required": True, "file": file_info(PROFILE_PATH), "context": profile_context}
    source_states["feedback"] = {"ok": feedback_raw is not None, "required": True, "file": file_info(FEEDBACK_PATH), "context": feedback_context}
    source_states["instructions"] = {
        "ok": instructions_text is not None,
        "required": True,
        "file": file_info(LOCAL_INSTRUCTIONS_PATH),
        "context": {
            "sha256": hashlib.sha256(instructions_text.encode("utf-8")).hexdigest() if instructions_text else None,
            "full_text": instructions_text or "",
        },
    }
    source_states["seasonal"] = {"ok": seasonal_raw is not None, "required": False, "file": file_info(SEASONAL_PATH)}
    source_states["travel_log"] = {
        "ok": bool(travel_text), "required": False, "file": file_info(travel_path),
        "context": str(travel_text or "")[:30000],
    }
    source_states["weather"]["context"] = weather
    source_states["calendar"]["context"] = {
        "availability_flags": calendar_context.get("availability_flags", {}),
        "events": calendar_context.get("events", []),
    }

    candidates, duplicate_candidates = dedupe_candidates(candidates)
    candidates, feedback_excluded = apply_feedback_exclusions(candidates, feedback_context)
    candidates, profile_excluded = apply_profile_hard_flags(candidates)
    candidates, future, curation_details = apply_curation(candidates, espelho_rows, target)
    apply_calendar_conflicts(candidates, calendar_context)
    cov = coverage(candidates)
    for gap in cov["threshold_gaps"]:
        warnings.append(f"threshold abaixo do minimo no pool: {gap['area']} {gap['count']}/{gap['minimum']}")

    status = "blocked" if errors else ("ready_with_warnings" if warnings else "ready")
    canonical_draft = {
        "meta": {
            "schema_version": SCHEMA_VERSION,
            "run_id": run_id,
            "date": target.isoformat(),
            "periodo_inicio": target.isoformat(),
            "periodo_fim": (target + timedelta(days=WINDOW_DAYS - 1)).isoformat(),
            "periodo_label": f"{date_label(target)} a {date_label(target + timedelta(days=WINDOW_DAYS - 1))}",
            "hoje": generated.date().isoformat(),
            "timezone": "Europe/Lisbon",
            "generated_at": generated.isoformat(timespec="seconds"),
            "calendario_pessoal": calendar_context.get("calendario_pessoal", []),
        },
        "sources": source_states,
        "event_candidates": candidates,
        "events": [],
        "futuro_guardado": future,
        "summary": {
            "alerta_urgente": "",
            "coverage_status": "incomplete" if cov["threshold_gaps"] else "candidate_pool_ready",
            "source_warnings": list(warnings),
        },
        "validation": {
            "preflight_status": status,
            "coverage": cov,
            "threshold_gaps": cov["threshold_gaps"],
            "source_errors": list(errors),
            "source_warnings": list(warnings),
            "duplicates_removed": duplicate_candidates,
            "feedback_excluded": feedback_excluded,
            "profile_hard_excluded": profile_excluded,
            "curation": curation_details,
            "debug_view": {
                "mechanical": {
                    "candidate_count": len(candidates),
                    "calendar_commitments": sum(len(item.get("compromissos", [])) for item in calendar_context.get("calendario_pessoal", [])),
                    "profile_sections": sorted(profile_context["sections"]),
                    "feedback_entries": len(feedback_context["entries"]),
                },
                "llm_notes": [],
            },
            "checklist": {"status": "pending_llm", "items": []},
        },
    }
    handoff = {
        "final_output_path": str(final_path),
        "canonical_top_level_keys": list(FINAL_TOP_LEVEL_KEYS),
        "editable_paths": [
            "/events",
            "/summary/alerta_urgente",
            "/summary/coverage_status",
            "/validation/debug_view/llm_notes",
            "/validation/checklist",
        ],
        "selection_contract": {
            "allowed_categories": sorted(VALID_CATEGORIES),
            "required_event_fields": ["id", "category", "title", "date", "date_label", "description"],
            "evergreen_date_null_categories": ["books", "escape", "gastro", "streaming"],
            "minimum_final_events": {
                "meetup": MINIMUMS["meetup"],
                "cinema_indoor": MINIMUMS["cinema_indoor"],
                "gastro": MINIMUMS["gastro"],
                "tv_plus_streaming": MINIMUMS["tv_streaming"],
                "books": MINIMUMS["books"],
                "escape": MINIMUMS["escape"],
                "sports": MINIMUMS["sports"],
            },
        },
        "must_do": [
            "Usar canonical_draft como ponto de partida e devolver exactamente as mesmas chaves de topo",
            "Ler e aplicar integralmente canonical_draft.sources.instructions.context.full_text; e a instrucao LOCAL 6.0 desta corrida",
            "Ler profile e feedback apenas dentro de canonical_draft.sources; o pre incluiu o perfil completo e todas as entradas/regras do feedback",
            "Escolher events[] exclusivamente de event_candidates[]; e permitido redigir descricao, badges, with_tags e prioridade, mas nunca criar factos",
            "Atribuir ids finais ev001, ev002, ...; preservar datas/horas/links factuais e documentar qualquer lacuna",
            "Aplicar curadoria de perfil, ranking, highlights e equilibrio de categorias",
            "Preservar futuro_guardado[] e todos os campos mecanicos",
            "Preencher checklist e notas LLM; thresholds abaixo do minimo ficam explicitos, nunca preenchidos com eventos provaveis",
            "Gravar o JSON final directamente com Write no caminho final_output_path",
        ],
        "must_not_do": [
            "Nao consultar web, Gmail, Calendar, Sheets, Drive, Todoist ou qualquer outra fonte",
            "Nao escrever HTML",
            "Nao publicar, fazer commit ou push; o launcher faz postflight e publicacao automaticamente",
            "Nao criar nem executar scripts Python auxiliares, temporarios ou intermedios",
            "Nao inventar datas, sessoes, canais, precos, links, distancias ou disponibilidade",
            "Nao remover nem acrescentar chaves de topo",
        ],
        "undated_rule": "Streaming, livros, restaurantes e escapadinhas evergreen podem manter date=null; usar date_label factual como 'Disponivel agora' apenas quando a fonte sustentar disponibilidade actual.",
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "routine": ROUTINE,
        "run_id": run_id,
        "generated_at": generated.isoformat(timespec="seconds"),
        "status": status,
        "target": {
            "date": target.isoformat(),
            "window_end": (target + timedelta(days=WINDOW_DAYS - 1)).isoformat(),
            "radar_end": (target + timedelta(days=RADAR_DAYS - 1)).isoformat(),
        },
        "canonical_draft": canonical_draft,
        "_llm_handoff": handoff,
        "warnings": warnings,
        "errors": errors,
    }


def latest_pre(output_dir: Path) -> Path | None:
    return latest_file(output_dir, "*_lazer_pre.json")


def reusable_pre(
    output_dir: Path,
    max_age_hours: float,
    expected_target: date,
) -> tuple[Path, dict[str, Any]] | None:
    path = latest_pre(output_dir)
    if path is None:
        return None
    try:
        raw = load_json(path)
    except Exception:
        return None
    stamp = parse_datetime(raw.get("generated_at")) if isinstance(raw, dict) else None
    if stamp is None or raw.get("status") == "blocked" or raw.get("errors"):
        return None
    if (raw.get("target") or {}).get("date") != expected_target.isoformat():
        return None
    age_hours = (now_lisbon() - stamp).total_seconds() / 3600
    return (path, raw) if age_hours <= max_age_hours else None


def write_run_artifacts(result: dict[str, Any], output_dir: Path) -> tuple[Path, Path, Path]:
    run_id = result["run_id"]
    pre_path = output_dir / f"{run_id}_lazer_pre.json"
    draft_path = output_dir / f"{run_id}_lazer_draft.json"
    final_path = Path(result["_llm_handoff"]["final_output_path"])
    write_json_atomic(pre_path, result)
    write_json_atomic(draft_path, result["canonical_draft"])
    write_text_atomic(output_dir / "_latest_lazer_pre.txt", str(pre_path) + "\n")
    write_text_atomic(output_dir / "_latest_lazer_final.txt", str(final_path) + "\n")
    return pre_path, draft_path, final_path


def self_test() -> int:
    failures: list[str] = []

    def check(name: str, condition: bool) -> None:
        if not condition:
            failures.append(name)

    check("parse iso date", parse_date("2026-09-24T10:00:00") == date(2026, 9, 24))
    check("undated candidate", make_candidate("x", "books", "Livro", None)["date"] is None)
    profile = "# Abertura\nX\n# 🧑 1. IDENTIDADE BASE\nRafa\n# 🏥 2. TRABALHO\nIgnorar\n# 🏊 6. DESPORTO & ATIVIDADE FÍSICA\nVoleibol"
    sections = extract_profile_sections(profile)
    check("profile section 1", "Rafa" in sections.get("1", ""))
    check("profile section 6", "Voleibol" in sections.get("6", ""))
    check("profile excludes section 2", "2" not in sections)
    feedback = compact_feedback({"entries": [
        {"id": "a", "title": "Nunca", "status": "excluded", "category": "restaurant"},
        {"id": "b", "title": "Testar", "status": "suggested", "category": "restaurant", "source": "third_party_recommendation"},
    ]})
    check("feedback excluded", feedback["excluded"][0]["title"] == "Nunca")
    check("feedback recommendation", feedback["third_party_recommendations"][0]["title"] == "Testar")
    candidates = [make_candidate("x", "gastro", "Nunca", None), make_candidate("x", "gastro", "Outro", None)]
    candidates, matches = apply_feedback_exclusions(candidates, feedback)
    check("feedback filter", len(candidates) == 1 and len(matches) == 1)
    candidates, _ = dedupe_candidates([
        make_candidate("a", "culture", "Evento", date(2026, 9, 24)),
        make_candidate("b", "culture", "Evento", date(2026, 9, 24)),
    ])
    check("dedupe", len(candidates) == 1 and str(candidates[0]["candidate_id"]).startswith("cand_"))
    timeout_parser = TimeOutTileParser()
    timeout_parser.feed(
        '<article class="tile"><a href="/evento"><h3>Evento teste</h3></a>'
        '<div data-testid="tile-summary_testID">Descricao</div>'
        '<time dateTime="2026-09-27T23:59:59+01:00">Ate 27/09/2026</time></article>'
    )
    check("timeout tile parser", timeout_parser.items == [{
        "href": "/evento", "title": "Evento teste", "description": "Descricao",
        "datetime": "2026-09-27T23:59:59+01:00", "date_label": "Ate 27/09/2026",
    }])
    rows = [{"timestamp": "2026-09-24T01:00:00", "dedup_key": "evento::culture", "titulo": "Evento", "categoria": "culture", "acao": "removido"}]
    filtered, _, detail = apply_curation([make_candidate("a", "culture", "Evento", date(2026, 9, 24))], rows, date(2026, 9, 24))
    check("curation removes", not filtered and len(detail["excluded"]) == 1)
    if failures:
        print("SELF-TEST FALHOU:")
        for failure in failures:
            print(f"- {failure}")
        return 2
    print("SELF-TEST OK: X_lazer_pre.py")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Pre mecanico da Agenda de Lazer.")
    parser.add_argument("--target-date", "--date", dest="target_date")
    parser.add_argument("--run-id")
    parser.add_argument("--output-dir", default=str(OUTPUT_DIR))
    parser.add_argument("--refresh-mode", choices=("all", "stale", "none"), default="all")
    parser.add_argument("--ensure-fresh-hours", type=float)
    parser.add_argument("--skip-public-sources", action="store_true")
    parser.add_argument("--motelx-json")
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--authorize-google", action="store_true",
                        help="Abrir consentimento Google e atualizar apenas o token do Lazer.")
    args = parser.parse_args()
    if args.self_test:
        return self_test()
    if args.authorize_google:
        errors: list[str] = []
        google_services(errors, reauthorize=True)
        if errors:
            for message in errors:
                print(f"ERRO: {message}")
            return 1
        print(f"Token Google do Lazer autorizado em {GOOGLE_TOKEN}")
        return 0

    output_dir = Path(args.output_dir)
    if args.ensure_fresh_hours is not None:
        expected_target = parse_date(args.target_date) if args.target_date else now_lisbon().date()
        if expected_target is None:
            print("ERRO: --target-date deve estar em YYYY-MM-DD")
            return 2
        reusable = reusable_pre(output_dir, args.ensure_fresh_hours, expected_target)
        if reusable:
            path, raw = reusable
            final_path = Path(raw["_llm_handoff"]["final_output_path"])
            write_text_atomic(output_dir / "_latest_lazer_pre.txt", str(path) + "\n")
            write_text_atomic(output_dir / "_latest_lazer_final.txt", str(final_path) + "\n")
            print(f"OK: pre fresco reutilizado -> {path}")
            print(f"Final esperado -> {final_path}")
            return 0

    try:
        result = build(args)
    except Exception as exc:
        print(f"ERRO: X_lazer_pre falhou antes de produzir manifesto: {type(exc).__name__}: {exc}")
        return 2
    pre_path, draft_path, final_path = write_run_artifacts(result, output_dir)
    print(f"OK: pre Lazer -> {pre_path}")
    print(f"OK: canonical draft -> {draft_path}")
    print(f"Final esperado -> {final_path}")
    print(f"Status: {result['status']}")
    if result["warnings"]:
        print("AVISOS:")
        for warning in result["warnings"][:40]:
            print(f"- {warning}")
    if result["errors"]:
        print("ERROS:")
        for error in result["errors"]:
            print(f"- {error}")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
