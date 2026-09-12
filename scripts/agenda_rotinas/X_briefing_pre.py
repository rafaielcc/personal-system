#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
X_briefing_pre.py — Recolha mecanica UNICA do Briefing Diario (+ Painel HFF + Lista BO)
=======================================================================================

O que este ficheiro e
---------------------
A rotina "pre" do Briefing. Faz TODO o trabalho mecanico fora do LLM: autentica,
le as fontes vivas (Google Calendar, Gmail, Todoist, Espelho HFF no Google Sheets,
meteorologia), normaliza tudo para hora de Lisboa, calcula janelas/datas/modo e
grava UM unico JSON em "G:/My Drive/Claude_PRJ/Agenda/X_Outputs" com o nome
    AAAA_MM_DD_HHMM_briefing.json
apagando os briefings anteriores da mesma pasta (nao toca em ficheiros de outras
rotinas, porque so apaga o sufixo "_briefing.json").

Substitui:
  - preflight_briefing.py  (que NAO lia fontes: so validava exports ja feitos a mao)
  - preflight_hff.py       (idem: dependia de um xlsx exportado ou de um dump do LLM)
  - weather.py             (a chamada Open-Meteo esta agora embutida aqui)

O LLM deixa de recolher seja o que for. Recebe este JSON e so interpreta: classifica
email, escreve os audio_scripts, os alertas, as sugestoes e emite o JSON canonico final.

Data-alvo
---------
Sem flags, a data-alvo e o dia real ate as 16h e o PROXIMO DIA UTIL a partir das 16h
(a regra vive aqui, nao no LLM). --today, --target-date e --next-business-day sobrepoem-se.

Uso
---
    python3 X_briefing_pre.py                      # modo automatico (A em dia util, B ao fim de semana)
    python3 X_briefing_pre.py --mode B             # forcar modo
    python3 X_briefing_pre.py --next-business-day  # Modo C: briefing do proximo dia util
    python3 X_briefing_pre.py --target-date 2026-09-15
    python3 X_briefing_pre.py --today          # forcar o dia real mesmo depois das 16h
    python3 X_briefing_pre.py --self-test          # testa a logica pura, sem rede

Credenciais
-----------
  Google : PROJECT_ROOT/credentials.json  (o mesmo OAuth client que as rotinas AII ja usam)
           PROJECT_ROOT/token_agenda.json (token PROPRIO desta rotina — deliberadamente
           separado de token.json para nao mexer nos scopes das rotinas AII)
           Na 1a execucao abre o browser uma vez para consentir Calendar+Gmail+Sheets.
  Todoist: variavel de ambiente TODOIST_API_TOKEN, ou ficheiro PROJECT_ROOT/token_todoist.md
           (tambem aceite: todoist_token.md)
           (mesmo padrao do github_token.md; a 1a linha nao-comentario e o token).

Dependencias
------------
    pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib
(Open-Meteo e Todoist usam so urllib da stdlib.)

Principio
---------
Zero julgamento. Este script nunca decide o que e urgente, nunca redige texto para o
Rafa e nunca inventa dados: se uma fonte falhar, grava o erro em "fontes" e continua,
deixando a seccao vazia e um aviso explicito. Melhor um buraco assinalado do que um
valor inventado.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

SCHEMA_VERSION = "1.0"
ROTINA = "briefing"
TZ = ZoneInfo("Europe/Lisbon")

# --------------------------------------------------------------------------------------
# Caminhos e IDs fixos
# --------------------------------------------------------------------------------------
PROJECT_ROOT = Path(os.environ.get("CLAUDE_PRJ_ROOT", r"G:\My Drive\Claude_PRJ"))
AGENDA_ROOT = PROJECT_ROOT / "Agenda"
DEFAULT_OUT_DIR = AGENDA_ROOT / "X_Outputs"

GOOGLE_CREDENTIALS_PATH = PROJECT_ROOT / "credentials.json"
GOOGLE_TOKEN_PATH = PROJECT_ROOT / "token_agenda.json"
# Aceita as duas convencoes de nome que existem na pasta-raiz dos projectos:
# token_todoist.md (a que o Rafa criou) e todoist_token.md (padrao do github_token.md).
TODOIST_TOKEN_NAMES = ("token_todoist.md", "todoist_token.md")
TODOIST_TOKEN_PATH = PROJECT_ROOT / TODOIST_TOKEN_NAMES[0]

GOOGLE_SCOPES = [
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/spreadsheets.readonly",
]

ESPELHO_HFF_ID = "1culq10MksUxSd05P1_ejqOEzaoQrFLKT-vP0brqp7iU"

OUT_SUFFIX = "_briefing.json"  # o que distingue os ficheiros desta rotina na pasta X_Outputs

# --------------------------------------------------------------------------------------
# Janelas e tabelas do dominio (BRIEFING_DIARIO v13.0 + INSTRUCOES_PAINEL_HFF + perfil)
# --------------------------------------------------------------------------------------
# Depois desta hora, um briefing pedido sem data explicita passa a ser do proximo dia util
# (regra do BRIEFING_DIARIO; vive aqui, no Python, e nao no julgamento do LLM).
CUTOFF_HOUR = 16

CALENDAR_WINDOW_DAYS = 15
DAY_WINDOW_DAYS = 3
HFF_WINDOW_DAYS = 28
EMAIL_RECENT_DAYS = 7
TODOIST_LOOKAHEAD_DAYS = 3

DAY_LABELS = ["Hoje", "Amanha", "Depois de amanha"]
WEEKDAYS_PT = ["segunda", "terca", "quarta", "quinta", "sexta", "sabado", "domingo"]

# Habitos por dia da semana (Rafa_profile.md, seccao 7)
HABITS_BY_WEEKDAY = {
    0: "Leitura de artigos/videos de Cirurgia Pediatrica (manha, entre cirurgias)",
    1: "CV Update, Gym 7h30, cafe com a Clara, ciclo de lazer a tarde",
    2: "Leitura de artigos de Cirurgia Pediatrica (manha), ciclo lazer/reabilitacao a tarde",
    3: "Gym 7h30, ver projectos, happy hour com a Vanessa",
    4: "Gym 7h30, revisao semanal (tarefas/emails/pendentes)",
    5: "Leg & Core Reinforcement",
    6: "Leg & Core Reinforcement",
}

# Gmail: as 5 queries da Seccao 3.3. label:events NUNCA e lido (pertence a Agenda de Lazer).
GMAIL_QUERIES = {
    "inbox": f"in:inbox newer_than:{EMAIL_RECENT_DAYS}d",
    "snoozed": "in:snoozed",
    "tarefas_sem_data": "label:tarefas-sem-data",
    "pediatric_surgery": "label:pediatric-surgery",
    "ulsasi": "label:ULSASI",
}
GMAIL_MAX_PER_QUERY = 60

# Classificacao de calendarios (LEITURA_CALENDARIO v1.0, seccao 5)
CALENDAR_TYPES = {
    "rafael correia": "evento",
    "cirped.ulsasi@gmail.com": "profissional",
    "todoist": "tarefa",
}
CALENDAR_SKIP = {"todoist"}  # lido directamente pela API do Todoist (que expoe prioridade)

FLAG_PATTERNS = {
    "sigic": re.compile(r"\bsigic\b", re.IGNORECASE),
    "prevencao": re.compile(r"preven", re.IGNORECASE),
    "viagem": re.compile(r"\b(voo|flight|viagem|check-?in|boarding)\b", re.IGNORECASE),
}

# Espelho HFF
TEAM = {"IF": "Isabel Franca", "RC": "Rafael Correia", "RR": "Rodrigo Roquette", "A": "Afonso"}
NAME_TO_INITIALS = {
    "isabel": "IF", "isabel franca": "IF",
    "rafael": "RC", "rafael correia": "RC",
    "rodrigo": "RR", "rodrigo roquette": "RR",
    "afonso": "A",
}
ABSENCE_RE = re.compile(r"^(?P<motive>[FCM])(?P<who>if|rc|rr|a)$", re.IGNORECASE)
DAY_OFF_RE = re.compile(r"^\*(?P<who>if|rc|rr|a)$", re.IGNORECASE)
MOTIVE_LABELS = {"F": "Ferias", "C": "Curso", "M": "Madeira"}
BO_WEEKDAYS = {0, 2}  # BO = segunda e quarta APENAS

MONTHS_PT = {
    "janeiro": 1, "jan": 1, "fevereiro": 2, "fev": 2, "marco": 3, "mar": 3,
    "abril": 4, "abr": 4, "maio": 5, "mai": 5, "junho": 6, "jun": 6,
    "julho": 7, "jul": 7, "agosto": 8, "ago": 8, "setembro": 9, "set": 9,
    "outubro": 10, "out": 10, "novembro": 11, "nov": 11, "dezembro": 12, "dez": 12,
}

# Meteorologia (Open-Meteo, sem chave)
LAT, LON = 38.7223, -9.1393
DIAS_ABR = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sab", "Dom"]
WEATHERCODE_ICON = {
    0: "sol", 1: "sol-nuvens", 2: "nuvens-sol", 3: "nublado",
    45: "nevoeiro", 48: "nevoeiro",
    51: "chuvisco", 53: "chuvisco", 55: "chuvisco", 56: "chuvisco", 57: "chuvisco",
    61: "chuva", 63: "chuva", 65: "chuva", 66: "chuva", 67: "chuva",
    71: "neve", 73: "neve", 75: "neve", 77: "neve",
    80: "aguaceiros", 81: "chuva", 82: "chuva",
    85: "neve", 86: "neve",
    95: "trovoada", 96: "trovoada", 99: "trovoada",
}


# ======================================================================================
# Utilitarios
# ======================================================================================
def now_lisbon() -> datetime:
    return datetime.now(TZ)


def norm(value: Any) -> str:
    text = "" if value is None else str(value)
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", text.strip().lower())


def compact_norm(value: Any) -> str:
    return re.sub(r"[^a-z0-9*]+", "", norm(value))


def parse_date(value: Any, default_year: int | None = None) -> date | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, (int, float)):
        if 20000 <= float(value) <= 60000:  # serial do Excel
            return date(1899, 12, 30) + timedelta(days=int(value))
        return None
    text = str(value).strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d/%m/%y", "%d-%m-%y"):
        try:
            return datetime.strptime(text[:10], fmt).date()
        except ValueError:
            pass
    m = re.match(r"^(\d{1,2})[/-](\d{1,2})$", text)
    if m and default_year:
        try:
            return date(default_year, int(m.group(2)), int(m.group(1)))
        except ValueError:
            return None
    return None


def parse_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return norm(value) in {"true", "t", "1", "sim", "yes", "y", "verdadeiro", "x"}


def parse_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value).strip().replace(",", "."))
    except ValueError:
        return None


def age_fmt(value: Any) -> str:
    age = parse_float(value)
    if age is None:
        return "s/d"
    if age <= 0:
        return "< 1 mes"
    if age < 1:
        months = max(1, round(age * 12))
        return f"{months} mes" if months == 1 else f"{months} meses"
    return f"{age:.1f}a".replace(".", ",")


def month_from_value(value: Any) -> int | None:
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)) and 1 <= int(value) <= 12:
        return int(value)
    text = norm(value)
    return MONTHS_PT.get(text)


def next_business_day(d: date) -> date:
    candidate = d + timedelta(days=1)
    while candidate.weekday() >= 5:
        candidate += timedelta(days=1)
    return candidate


def resolve_target_date(
    data_real: date,
    hora: int,
    target_date: str | None = None,
    next_bd: bool = False,
    today: bool = False,
) -> tuple[date, str]:
    """Decide a DATA_ALVO do briefing. Funcao pura — e o unico sitio onde esta regra vive.

    Precedencia: --target-date > --next-business-day > --today > regra automatica das 16h.
    A regra automatica: ate as CUTOFF_HOUR o briefing e do dia real; a partir dai o dia
    ja vai a meio e o que interessa e o proximo dia util (que salta sabado e domingo).
    """
    if target_date:
        return (parse_date(target_date) or data_real), "--target-date"
    if next_bd:
        return next_business_day(data_real), "--next-business-day (Modo C)"
    if today:
        return data_real, "--today (forcado)"
    if hora >= CUTOFF_HOUR:
        return next_business_day(data_real), f"automatico: corrida depois das {CUTOFF_HOUR}h -> proximo dia util"
    return data_real, f"automatico: corrida antes das {CUTOFF_HOUR}h -> dia real"


def weekday_pt(d: date) -> str:
    return WEEKDAYS_PT[d.weekday()]


def http_get_json(url: str, headers: dict[str, str] | None = None, timeout: int = 20) -> Any:
    req = urllib.request.Request(url, headers=headers or {"User-Agent": "agenda-briefing-pre/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


# ======================================================================================
# Autenticacao Google
# ======================================================================================
def google_services(errors: list[str]) -> dict[str, Any]:
    """Devolve {'calendar':..., 'gmail':..., 'sheets':...} ou {} se a auth falhar."""
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build
    except ImportError as exc:
        errors.append(
            "Bibliotecas Google em falta. Correr: pip install google-api-python-client "
            f"google-auth-httplib2 google-auth-oauthlib ({exc})"
        )
        return {}

    creds = None
    if GOOGLE_TOKEN_PATH.exists():
        try:
            creds = Credentials.from_authorized_user_file(str(GOOGLE_TOKEN_PATH), GOOGLE_SCOPES)
        except Exception as exc:
            errors.append(f"token_agenda.json ilegivel ({exc}); vai pedir novo consentimento.")
            creds = None
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception as exc:
                errors.append(f"Refresh do token falhou ({exc}); vai pedir novo consentimento.")
                creds = None
        if not creds or not creds.valid:
            if not GOOGLE_CREDENTIALS_PATH.exists():
                errors.append(f"credentials.json nao encontrado em {GOOGLE_CREDENTIALS_PATH}")
                return {}
            flow = InstalledAppFlow.from_client_secrets_file(str(GOOGLE_CREDENTIALS_PATH), GOOGLE_SCOPES)
            creds = flow.run_local_server(port=0)
        GOOGLE_TOKEN_PATH.write_text(creds.to_json(), encoding="utf-8")

    return {
        "calendar": build("calendar", "v3", credentials=creds, cache_discovery=False),
        "gmail": build("gmail", "v1", credentials=creds, cache_discovery=False),
        "sheets": build("sheets", "v4", credentials=creds, cache_discovery=False),
    }


# ======================================================================================
# Fonte: Google Calendar
# ======================================================================================
def classify_calendar(summary: str) -> str:
    key = norm(summary)
    if key in CALENDAR_TYPES:
        return CALENDAR_TYPES[key]
    if "feriado" in key or "holiday" in key:
        return "feriado"
    return "outro"


def detect_flags(text: str) -> list[str]:
    return [name for name, pattern in FLAG_PATTERNS.items() if pattern.search(text or "")]


def event_times(event: dict[str, Any]) -> tuple[str | None, str | None, bool]:
    start = event.get("start", {}) or {}
    end = event.get("end", {}) or {}
    if start.get("date"):
        return start["date"], end.get("date"), True
    s = start.get("dateTime")
    e = end.get("dateTime")

    def to_lisbon(value: str | None) -> str | None:
        if not value:
            return None
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(TZ).isoformat(timespec="minutes")
        except ValueError:
            return value

    return to_lisbon(s), to_lisbon(e), False


def collect_calendar(service: Any, start_date: date, days: int, warnings: list[str]) -> dict[str, Any]:
    """Le TODOS os calendarios (excepto os de CALENDAR_SKIP) e devolve tudo em hora de Lisboa."""
    time_min = datetime.combine(start_date, datetime.min.time(), tzinfo=TZ)
    time_max = time_min + timedelta(days=days)

    calendars_meta: list[dict[str, Any]] = []
    items: list[dict[str, Any]] = []

    page_token = None
    calendars: list[dict[str, Any]] = []
    while True:
        resp = service.calendarList().list(pageToken=page_token, maxResults=250).execute()
        calendars.extend(resp.get("items", []))
        page_token = resp.get("nextPageToken")
        if not page_token:
            break

    for cal in calendars:
        cal_id = cal.get("id", "")
        summary = cal.get("summary", cal_id)
        tipo = classify_calendar(summary)
        skipped = norm(summary) in CALENDAR_SKIP
        meta = {
            "id": cal_id,
            "nome": summary,
            "tipo": tipo,
            "timezone_origem": cal.get("timeZone"),
            "lido": not skipped,
            "motivo_ignorado": "Todoist lido directamente pela API (expoe prioridade)" if skipped else None,
            "eventos": 0,
        }
        if skipped:
            calendars_meta.append(meta)
            continue
        try:
            events: list[dict[str, Any]] = []
            token = None
            while True:
                resp = service.events().list(
                    calendarId=cal_id,
                    timeMin=time_min.isoformat(),
                    timeMax=time_max.isoformat(),
                    singleEvents=True,
                    orderBy="startTime",
                    maxResults=250,
                    timeZone="Europe/Lisbon",
                    pageToken=token,
                ).execute()
                events.extend(resp.get("items", []))
                token = resp.get("nextPageToken")
                if not token:
                    break
        except Exception as exc:
            meta["erro"] = f"{type(exc).__name__}: {exc}"
            warnings.append(f"calendario '{summary}': leitura falhou ({exc})")
            calendars_meta.append(meta)
            continue

        for event in events:
            if event.get("status") == "cancelled":
                continue
            inicio, fim, all_day = event_times(event)
            titulo = (event.get("summary") or "(sem titulo)").strip()
            day_key = (inicio or "")[:10]
            if not day_key:
                continue
            items.append({
                "date": day_key,
                "titulo": titulo,
                "tipo": tipo,
                "calendario": summary,
                "inicio": inicio,
                "fim": fim,
                "dia_inteiro": all_day,
                "local": (event.get("location") or "").strip() or None,
                "flags": detect_flags(f"{titulo} {event.get('description', '')}"),
                "event_id": event.get("id"),
            })
        meta["eventos"] = sum(1 for i in items if i["calendario"] == summary)
        calendars_meta.append(meta)

    items.sort(key=lambda i: (i["date"], i.get("inicio") or ""))
    return {"calendarios": calendars_meta, "itens": items}


# ======================================================================================
# Fonte: Todoist
# ======================================================================================
def todoist_token(errors: list[str]) -> str | None:
    token = os.environ.get("TODOIST_API_TOKEN", "").strip()
    if token:
        return token
    for name in TODOIST_TOKEN_NAMES:
        path = PROJECT_ROOT / name
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8-sig").splitlines():
            candidate = line.strip()
            if not candidate or candidate.startswith("#") or " " in candidate:
                continue
            return candidate
        errors.append(f"{path} existe mas nao tem nenhuma linha que pareca um token.")
        return None
    nomes = " ou ".join(TODOIST_TOKEN_NAMES)
    errors.append(
        "Token do Todoist nao encontrado: definir a variavel de ambiente TODOIST_API_TOKEN "
        f"ou criar {PROJECT_ROOT / nomes} com o token numa linha (obter em Todoist > "
        "Definicoes > Integracoes > Developer)."
    )
    return None


def classify_priority(value: Any) -> str:
    """Todoist: priority 4 = p1 (alta) ... 1 = p4 (nenhuma). Regra do projecto:
    alta/media = trabalho HFF; baixa/nenhuma = pessoal."""
    try:
        number = int(value)
    except (TypeError, ValueError):
        return "baixa"
    if number >= 4:
        return "alta"
    if number == 3:
        return "media"
    return "baixa"


def collect_todoist(token: str, target: date, warnings: list[str]) -> dict[str, Any]:
    url = "https://api.todoist.com/rest/v2/tasks"
    headers = {"Authorization": f"Bearer {token}", "User-Agent": "agenda-briefing-pre/1.0"}
    tasks = http_get_json(url, headers=headers)

    end = target + timedelta(days=TODOIST_LOOKAHEAD_DAYS - 1)
    itens: list[dict[str, Any]] = []
    sem_data = 0
    for task in tasks if isinstance(tasks, list) else []:
        due = task.get("due") or {}
        due_date = parse_date(due.get("date"))
        if due_date is None:
            sem_data += 1
            continue
        atrasada = due_date < target
        if not atrasada and not (target <= due_date <= end):
            continue
        prioridade = classify_priority(task.get("priority"))
        itens.append({
            "id": task.get("id"),
            "texto": (task.get("content") or "").strip(),
            "descricao": (task.get("description") or "").strip() or None,
            "date": due_date.isoformat(),
            "atrasada": atrasada,
            "prioridade": prioridade,
            "prioridade_raw": task.get("priority"),
            "classificacao": "trabalho_hff" if prioridade in {"alta", "media"} else "pessoal",
            "recorrente": bool(due.get("is_recurring")),
            "labels": task.get("labels") or [],
            "project_id": task.get("project_id"),
        })
    itens.sort(key=lambda i: (i["date"], i["texto"]))

    por_dia: dict[str, list[str]] = defaultdict(list)
    for item in itens:
        por_dia[item["date"]].append(item["texto"])
    if sem_data:
        warnings.append(f"Todoist: {sem_data} tarefa(s) sem data ignoradas (nao entram no briefing).")
    return {"itens": itens, "por_dia": dict(por_dia), "total_sem_data": sem_data}


# ======================================================================================
# Fonte: Gmail
# ======================================================================================
def header_value(payload: dict[str, Any], name: str) -> str:
    for header in payload.get("headers", []) or []:
        if header.get("name", "").lower() == name.lower():
            return header.get("value", "")
    return ""


def collect_gmail(service: Any, warnings: list[str]) -> dict[str, Any]:
    assert "label:events" not in " ".join(GMAIL_QUERIES.values()), \
        "O briefing nunca le label:events (pertence em exclusivo a Agenda de Lazer)."

    result: dict[str, Any] = {}
    for section, query in GMAIL_QUERIES.items():
        try:
            listed = service.users().messages().list(
                userId="me", q=query, maxResults=GMAIL_MAX_PER_QUERY
            ).execute()
        except Exception as exc:
            warnings.append(f"Gmail '{section}': listagem falhou ({exc})")
            result[section] = {"query": query, "erro": f"{type(exc).__name__}: {exc}", "mensagens": []}
            continue

        mensagens = []
        for ref in listed.get("messages", []) or []:
            try:
                msg = service.users().messages().get(
                    userId="me", id=ref["id"], format="metadata",
                    metadataHeaders=["From", "Subject", "Date", "To"],
                ).execute()
            except Exception as exc:
                warnings.append(f"Gmail '{section}': mensagem {ref.get('id')} ilegivel ({exc})")
                continue
            payload = msg.get("payload", {}) or {}
            internal = msg.get("internalDate")
            recebido = None
            if internal:
                recebido = datetime.fromtimestamp(int(internal) / 1000, TZ).isoformat(timespec="minutes")
            mensagens.append({
                "id": msg.get("id"),
                "thread_id": msg.get("threadId"),
                "remetente": header_value(payload, "From"),
                "assunto": header_value(payload, "Subject"),
                "recebido": recebido,
                "snippet": (msg.get("snippet") or "").strip(),
                "labels": msg.get("labelIds", []),
                "nao_lido": "UNREAD" in (msg.get("labelIds") or []),
            })
        mensagens.sort(key=lambda m: m.get("recebido") or "", reverse=True)
        result[section] = {"query": query, "total": len(mensagens), "mensagens": mensagens}
    return result


# ======================================================================================
# Fonte: meteorologia (Open-Meteo)
# ======================================================================================
def icon_for(code: Any) -> str:
    try:
        return WEATHERCODE_ICON.get(int(code), "indefinido")
    except (TypeError, ValueError):
        return "indefinido"


def collect_weather(target: date) -> dict[str, Any]:
    url = (
        "https://api.open-meteo.com/v1/forecast"
        f"?latitude={LAT}&longitude={LON}"
        "&daily=weathercode,temperature_2m_max,temperature_2m_min,precipitation_probability_max"
        "&hourly=temperature_2m,weathercode,precipitation_probability"
        "&current_weather=true"
        f"&timezone={urllib.parse.quote('Europe/Lisbon')}"
        "&forecast_days=7"
    )
    raw = http_get_json(url)
    daily = raw.get("daily") or {}
    hourly = raw.get("hourly") or {}
    current = raw.get("current_weather") or {}
    if not daily or not hourly:
        raise RuntimeError("resposta da Open-Meteo sem 'daily'/'hourly'")

    tabela = []
    for index, day_str in enumerate(daily.get("time", [])):
        dt = datetime.strptime(day_str, "%Y-%m-%d")
        tabela.append({
            "date": day_str,
            "label": f"{DIAS_ABR[dt.weekday()]} {dt.day}",
            "icone": icon_for(daily["weathercode"][index]),
            "max": round(daily["temperature_2m_max"][index]),
            "min": round(daily["temperature_2m_min"][index]),
            "chuva_pct": daily["precipitation_probability_max"][index],
        })

    horas_chave: dict[str, Any] = {}
    times = hourly.get("time", [])
    for hhmm in ("08:00", "13:00", "16:30", "21:00"):
        prefix = f"{target.isoformat()}T{hhmm[:2]}"
        idx = next((i for i, t in enumerate(times) if t.startswith(prefix)), None)
        horas_chave[hhmm] = None if idx is None else {
            "temp": round(hourly["temperature_2m"][idx]),
            "icone": icon_for(hourly["weathercode"][idx]),
            "chuva_pct": (hourly.get("precipitation_probability") or [None] * len(times))[idx],
        }

    return {
        "local": "Lisboa",
        "fonte": "open-meteo",
        "current_temp": round(current["temperature"]) if current.get("temperature") is not None else None,
        "tabela_7dias": tabela,
        "horas_chave": horas_chave,
    }


# ======================================================================================
# Fonte: Espelho HFF (Google Sheets)
# ======================================================================================
def read_espelho(service: Any, spreadsheet_id: str) -> dict[str, list[list[Any]]]:
    meta = service.spreadsheets().get(
        spreadsheetId=spreadsheet_id, fields="sheets.properties.title"
    ).execute()
    titles = [s["properties"]["title"] for s in meta.get("sheets", [])]
    ranges = [f"'{title}'!A1:ZZ2000" for title in titles]
    batch = service.spreadsheets().values().batchGet(
        spreadsheetId=spreadsheet_id,
        ranges=ranges,
        valueRenderOption="FORMATTED_VALUE",
        dateTimeRenderOption="FORMATTED_STRING",
    ).execute()
    out: dict[str, list[list[Any]]] = {}
    for title, value_range in zip(titles, batch.get("valueRanges", [])):
        out[title] = value_range.get("values", [])
    return out


def pick_sheet(sheets: dict[str, list[list[Any]]], candidates: list[str]) -> list[list[Any]] | None:
    normalized = {norm(name): name for name in sheets}
    for candidate in candidates:
        real = normalized.get(norm(candidate))
        if real is not None:
            return sheets[real]
    return None


def find_header(rows: list[list[Any]], aliases: dict[str, list[str]], minimum: int) -> tuple[int | None, dict[str, int]]:
    lookup: dict[str, str] = {}
    for field, values in aliases.items():
        for value in values:
            lookup[compact_norm(value)] = field
    best_idx: int | None = None
    best_map: dict[str, int] = {}
    for idx, row in enumerate(rows[:20]):
        current: dict[str, int] = {}
        for col_idx, cell_value in enumerate(row):
            field = lookup.get(compact_norm(cell_value))
            if field and field not in current:
                current[field] = col_idx
        if len(current) > len(best_map):
            best_idx, best_map = idx, current
        if len(current) >= minimum:
            return idx, current
    return best_idx, best_map


def cell(row: list[Any], mapping: dict[str, int], field: str) -> Any:
    idx = mapping.get(field)
    if idx is None or idx >= len(row):
        return None
    return row[idx]


def parse_cirurgias(rows: list[list[Any]], today: date, warnings: list[str], errors: list[str]) -> dict[str, Any]:
    aliases = {
        "data": ["Data Cirurgia", "Data"],
        "periodo": ["Periodo", "Periodo (M = manha / S = SIGIC-tarde)", "Periodo (Manha/Sigic (tarde))"],
        "processo": ["Processo"],
        "nome": ["Nome doente", "Nome"],
        "fdr": ["FDR", "FDR (Fora da Rotina)"],
        "tempo_espera": ["Tempo em Lista de Espera"],
        "idade": ["Idade"],
        "procedimento": ["Procedimento"],
        "status": ["Status Agendamento"],
        "obs": ["Observacao", "Observação"],
        "if_ausente": ["Previsao IF ausente", "Previsão IF ausente", "Previsao de IF estar ausente no dia"],
        "rc_ausente": ["Previsao RC ausente", "Previsão RC ausente", "Previsao de RC estar ausente no dia"],
        "rr_ausente": ["Previsao RR ausente", "Previsão RR ausente", "Previsao de RR estar ausente no dia"],
    }
    header_idx, mapping = find_header(rows, aliases, minimum=8)
    missing = sorted(set(aliases) - set(mapping))
    if header_idx is None or len(mapping) < 8:
        errors.append("Espelho HFF / Cirurgias: cabecalho obrigatorio nao encontrado")
        return {"ok": False, "sessoes": [], "missing_headers": missing}
    if missing:
        warnings.append("Espelho HFF / Cirurgias: cabecalhos parciais: " + ", ".join(missing))

    end = today + timedelta(days=HFF_WINDOW_DAYS - 1)
    sessions: dict[tuple[str, str], dict[str, Any]] = {}
    anomalies: list[dict[str, Any]] = []
    process_keys: list[tuple[str, str, str]] = []
    rows_in_window = 0

    for row_idx, row in enumerate(rows[header_idx + 1:], start=header_idx + 2):
        surgery_date = parse_date(cell(row, mapping, "data"), default_year=today.year)
        if surgery_date is None:
            continue
        periodo = str(cell(row, mapping, "periodo") or "").strip().upper()
        processo = str(cell(row, mapping, "processo") or "").strip()
        if surgery_date < today:
            continue
        if surgery_date > end:
            continue
        rows_in_window += 1
        if periodo not in {"M", "S"}:
            anomalies.append({"tipo": "periodo_invalido", "linha": row_idx, "date": surgery_date.isoformat(), "valor": periodo})
            periodo = periodo or "M"
        if not processo:
            anomalies.append({"tipo": "processo_em_falta", "linha": row_idx, "date": surgery_date.isoformat()})
        if periodo == "M" and surgery_date.weekday() not in BO_WEEKDAYS:
            anomalies.append({
                "tipo": "bo_em_dia_invalido", "linha": row_idx, "date": surgery_date.isoformat(),
                "weekday": weekday_pt(surgery_date),
                "nota": "BO so existe segunda e quarta",
            })

        ausentes = [
            initials for initials, field in (("IF", "if_ausente"), ("RC", "rc_ausente"), ("RR", "rr_ausente"))
            if parse_bool(cell(row, mapping, field))
        ]

        doente = {
            "processo": processo,
            "nome": str(cell(row, mapping, "nome") or "").strip(),
            "idade_raw": parse_float(cell(row, mapping, "idade")),
            "idade_fmt": age_fmt(cell(row, mapping, "idade")),
            "procedimento": str(cell(row, mapping, "procedimento") or "").strip(),
            "fdr": parse_bool(cell(row, mapping, "fdr")),
            "tempo_espera": parse_float(cell(row, mapping, "tempo_espera")),
            "status": str(cell(row, mapping, "status") or "").strip(),
            "obs": str(cell(row, mapping, "obs") or "").strip(),
            "linha_origem": row_idx,
        }
        if processo:
            process_keys.append((surgery_date.isoformat(), periodo, processo))

        session = sessions.setdefault((surgery_date.isoformat(), periodo), {
            "date": surgery_date.isoformat(),
            "weekday": weekday_pt(surgery_date),
            "periodo": periodo,
            "cirurgioes": [],
            "ausentes_previstos": [],
            "doentes": [],
        })
        for initials in ausentes:
            if initials not in session["ausentes_previstos"]:
                session["ausentes_previstos"].append(initials)
        session["doentes"].append(doente)

    for key, count in Counter(process_keys).items():
        if count > 1:
            anomalies.append({"tipo": "processo_duplicado", "date": key[0], "periodo": key[1], "processo": key[2]})

    ordered = []
    for session in sessions.values():
        session["ausentes_previstos"].sort()
        session["doentes"].sort(key=lambda d: (d["idade_raw"] is None, d["idade_raw"] or 0, d["nome"]))
        session["n_doentes"] = len(session["doentes"])
        ordered.append(session)
    ordered.sort(key=lambda s: (s["date"], s["periodo"]))

    return {
        "ok": True,
        "janela": {"inicio": today.isoformat(), "fim": end.isoformat(), "dias": HFF_WINDOW_DAYS},
        "linhas_na_janela": rows_in_window,
        "sessoes": ordered,
        "fdr_total": sum(1 for s in ordered for d in s["doentes"] if d["fdr"]),
        "anomalias": anomalies,
    }


def parse_sigic(rows: list[list[Any]], today: date, errors: list[str]) -> dict[str, Any]:
    aliases = {
        "mes": ["MES", "Mes"],
        "dia": ["DIA de Sigic", "Dia de SIGIC", "Data", "Dia"],
        "cirurgiao1": ["Cirurgiao1", "Cirurgião1", "Cirurgiao 1", "Cirurgião 1"],
        "cirurgiao2": ["Cirurgiao2", "Cirurgião2", "Cirurgiao 2", "Cirurgião 2"],
    }
    header_idx, mapping = find_header(rows, aliases, minimum=3)
    if header_idx is None or len(mapping) < 3:
        errors.append("Espelho HFF / SIGIC: cabecalho obrigatorio nao encontrado")
        return {"ok": False, "listas": []}

    end = today + timedelta(days=HFF_WINDOW_DAYS - 1)
    listas = []
    anomalias = []
    for row_idx, row in enumerate(rows[header_idx + 1:], start=header_idx + 2):
        dia_value = cell(row, mapping, "dia")
        sigic_date = parse_date(dia_value, default_year=today.year)
        if sigic_date is None and isinstance(dia_value, (int, float)):
            month = month_from_value(cell(row, mapping, "mes"))
            if month:
                try:
                    sigic_date = date(today.year, month, int(dia_value))
                except ValueError:
                    sigic_date = None
        if sigic_date is None or not (today <= sigic_date <= end):
            continue
        item = {
            "date": sigic_date.isoformat(),
            "weekday": weekday_pt(sigic_date),
            "cirurgiao1": str(cell(row, mapping, "cirurgiao1") or "").strip(),
            "cirurgiao2": str(cell(row, mapping, "cirurgiao2") or "").strip(),
            "linha_origem": row_idx,
        }
        if not item["cirurgiao1"] or not item["cirurgiao2"]:
            anomalias.append({"tipo": "sigic_sem_cirurgiao", "linha": row_idx, "date": item["date"]})
        listas.append(item)
    listas.sort(key=lambda i: i["date"])
    return {"ok": True, "listas": listas, "anomalias": anomalias}


def infer_grid_date(rows: list[list[Any]], r: int, c: int, year: int) -> date | None:
    """A aba Ausencias e uma grelha, nao uma tabela: a data vem da celula a esquerda/acima."""
    explicit = parse_date(rows[r][c], default_year=year)
    if explicit:
        return explicit
    day: int | None = None
    for rr, cc in ((r, c - 1), (r, c - 2), (r - 1, c), (r - 2, c), (r - 1, c - 1)):
        if rr < 0 or cc < 0:
            continue
        try:
            candidate = rows[rr][cc]
        except IndexError:
            continue
        parsed = parse_date(candidate, default_year=year)
        if parsed:
            return parsed
        if isinstance(candidate, (int, float)) and 1 <= int(candidate) <= 31:
            day = int(candidate)
            break
        if isinstance(candidate, str) and re.fullmatch(r"\d{1,2}", candidate.strip()):
            day = int(candidate.strip())
            break
    if day is None:
        return None
    month = None
    for rr in range(max(0, r - 8), min(len(rows), r + 3)):
        for cc in range(max(0, c - 8), min(len(rows[rr]), c + 3)):
            month = month_from_value(rows[rr][cc])
            if month:
                break
        if month:
            break
    if not month:
        return None
    try:
        return date(year, month, day)
    except ValueError:
        return None


def parse_ausencias(rows: list[list[Any]], today: date) -> dict[str, Any]:
    """Codigos: Maiuscula = motivo (F/C/M) + minusculas = iniciais (if/rc/rr/a). Ex: 'Mif'.
    '*if' = folga. A aba Ausencias e autoritativa."""
    end = today + timedelta(days=HFF_WINDOW_DAYS - 1)
    ausencias: list[dict[str, Any]] = []
    folgas: list[dict[str, Any]] = []
    ambiguos: list[dict[str, Any]] = []
    sem_data: list[dict[str, Any]] = []

    for r_idx, row in enumerate(rows):
        for c_idx, value in enumerate(row):
            text = str(value or "").strip()
            if not text:
                continue
            compact = compact_norm(text)
            absence_match = ABSENCE_RE.match(compact)
            day_off_match = DAY_OFF_RE.match(compact)
            ambiguous_single = compact.upper() in {"F", "C", "M"}
            if not (absence_match or day_off_match or ambiguous_single):
                continue
            parsed_date = infer_grid_date(rows, r_idx, c_idx, today.year)
            record = {"codigo": text, "celula": f"L{r_idx + 1}C{c_idx + 1}"}
            if parsed_date is None:
                sem_data.append(record)
                continue
            if not (today <= parsed_date <= end):
                continue
            record["data"] = parsed_date.isoformat()
            if absence_match:
                code = absence_match.group("motive").upper()
                ausencias.append({
                    "cir": absence_match.group("who").upper(),
                    "motivo": MOTIVE_LABELS.get(code, code),
                    **record,
                })
            elif day_off_match:
                folgas.append({"cir": day_off_match.group("who").upper(), **record})
            else:
                ambiguos.append({"nota": "Codigo sem iniciais; nao atribuido.", **record})

    return {
        "ok": True,
        "ausencias": sorted(ausencias, key=lambda i: (i["data"], i["cir"])),
        "folgas": sorted(folgas, key=lambda i: (i["data"], i["cir"])),
        "codigos_ambiguos": ambiguos,
        "codigos_sem_data": sem_data,
        "nota_parser": "Leitura best-effort da grelha; confirmar layout se codigos_sem_data > 0.",
    }


def parse_prevencao(rows: list[list[Any]], today: date, ausencias: dict[str, Any], errors: list[str]) -> dict[str, Any]:
    aliases = {
        "semana": ["Semana"],
        "inicio": ["Data Inicio", "Data Início", "Inicio", "Início"],
        "fim": ["Data Fim", "Fim"],
        "cirurgiao": ["Cirurgiao de prevencao", "Cirurgião de prevenção", "Cirurgiao a fazer a Prevencao"],
        "madeira": ["Cirurgiao na Madeira", "Cirurgião na Madeira"],
        "ausente": ["Cirurgiao de ferias/ausente", "Cirurgião de férias/ausente", "Cirurgiao de ferias ou ausente por outro motivo"],
        "obs": ["Observacoes", "Observações"],
    }
    header_idx, mapping = find_header(rows, aliases, minimum=4)
    if header_idx is None or len(mapping) < 4:
        errors.append("Espelho HFF / Prevencao: cabecalho obrigatorio nao encontrado")
        return {"ok": False, "semanas": []}

    month_start = date(today.year, today.month, 1)
    semanas = []
    for row_idx, row in enumerate(rows[header_idx + 1:], start=header_idx + 2):
        cirurgiao = str(cell(row, mapping, "cirurgiao") or "").strip()
        if not cirurgiao:
            continue
        inicio = parse_date(cell(row, mapping, "inicio"), default_year=today.year)
        fim = parse_date(cell(row, mapping, "fim"), default_year=today.year)
        if not inicio or not fim or fim < month_start:
            continue
        notas = []
        madeira = str(cell(row, mapping, "madeira") or "").strip()
        if madeira:
            notas.append(f"{madeira}: Madeira esta semana")
        ausente = str(cell(row, mapping, "ausente") or "").strip()
        if ausente:
            initials = next((v for k, v in NAME_TO_INITIALS.items() if k in norm(ausente)), None)
            matching = [
                a for a in ausencias.get("ausencias", [])
                if initials and a.get("cir") == initials and inicio.isoformat() <= a.get("data", "") <= fim.isoformat()
            ]
            if matching:
                motivos = sorted({a["motivo"] for a in matching})
                datas = ", ".join(a["data"] for a in matching)
                notas.append(f"{ausente}: {'/'.join(motivos)} ({datas})")
            else:
                notas.append(f"{ausente}: ausencia parte da semana; motivo nao confirmado na aba Ausencias")
        semanas.append({
            "semana": cell(row, mapping, "semana"),
            "inicio": inicio.isoformat(),
            "fim": fim.isoformat(),
            "cirurgiao": cirurgiao,
            "notas_ausencia": notas,
            "obs": str(cell(row, mapping, "obs") or "").strip(),
            "linha_origem": row_idx,
        })
    semanas.sort(key=lambda s: s["inicio"])
    actual = next((s for s in semanas if s["inicio"] <= today.isoformat() <= s["fim"]), None)
    return {
        "ok": True,
        "semana_actual": {
            "cirurgiao": (actual or {}).get("cirurgiao", ""),
            "rafael_de_prevencao": "rafael" in norm((actual or {}).get("cirurgiao", "")),
            "inicio": (actual or {}).get("inicio"),
            "fim": (actual or {}).get("fim"),
        },
        "semanas": semanas,
    }


def build_hff_block(target: date, espelho: dict[str, list[list[Any]]], todoist: dict[str, Any],
                    warnings: list[str], errors: list[str]) -> dict[str, Any]:
    sheets = {
        "cirurgias": pick_sheet(espelho, ["Cirurgias"]),
        "sigic": pick_sheet(espelho, ["SIGIC", "Sigic"]),
        "prevencao": pick_sheet(espelho, ["Prevencao", "Prevenção"]),
        "ausencias": pick_sheet(espelho, ["Ausencias", "Ausências"]),
    }
    for key, rows in sheets.items():
        if rows is None:
            errors.append(f"Espelho HFF: aba obrigatoria em falta: {key}")

    ausencias = parse_ausencias(sheets["ausencias"], target) if sheets["ausencias"] else {"ausencias": [], "folgas": [], "codigos_ambiguos": [], "codigos_sem_data": []}
    cirurgias = parse_cirurgias(sheets["cirurgias"], target, warnings, errors) if sheets["cirurgias"] else {"ok": False, "sessoes": []}
    sigic = parse_sigic(sheets["sigic"], target, errors) if sheets["sigic"] else {"ok": False, "listas": []}
    prevencao = parse_prevencao(sheets["prevencao"], target, ausencias, errors) if sheets["prevencao"] else {"ok": False, "semanas": []}

    # Cruzar SIGIC com as sessoes de tarde
    sigic_by_date = {i["date"]: i for i in sigic.get("listas", [])}
    for session in cirurgias.get("sessoes", []):
        if session["periodo"] == "S" and session["date"] in sigic_by_date:
            listing = sigic_by_date[session["date"]]
            session["cirurgioes"] = [listing["cirurgiao1"], listing["cirurgiao2"]]
            listing["cirurgias"] = session["doentes"]

    key = target.isoformat()
    tem_bo = any(s["date"] == key and s["periodo"] == "M" for s in cirurgias.get("sessoes", []))
    tem_sigic = key in sigic_by_date or any(s["date"] == key and s["periodo"] == "S" for s in cirurgias.get("sessoes", []))
    if tem_bo and tem_sigic:
        tipo_dia = "BO manha + SIGIC tarde"
    elif tem_bo:
        tipo_dia = "BO manha"
    elif tem_sigic:
        tipo_dia = "SIGIC tarde"
    else:
        tipo_dia = "Sem BO"

    proximo_bo = None
    futuros = sorted(
        (s for s in cirurgias.get("sessoes", []) if s["periodo"] == "M" and s["date"] >= key),
        key=lambda s: s["date"],
    )
    if futuros:
        proximo_bo = {
            "date": futuros[0]["date"],
            "weekday": futuros[0]["weekday"],
            "n_cirurgias": futuros[0]["n_doentes"],
        }

    ausencias_por_dia: dict[str, list[dict[str, str]]] = defaultdict(list)
    for item in ausencias.get("ausencias", []):
        ausencias_por_dia[item["data"]].append({"cir": item["cir"], "motivo": item["motivo"]})
    manha_por_dia: dict[str, int] = defaultdict(int)
    for session in cirurgias.get("sessoes", []):
        if session["periodo"] == "M":
            manha_por_dia[session["date"]] += session["n_doentes"]

    calendario_4_semanas = []
    for offset in range(HFF_WINDOW_DAYS):
        day = target + timedelta(days=offset)
        day_key = day.isoformat()
        calendario_4_semanas.append({
            "date": day_key,
            "weekday": weekday_pt(day),
            "ausencias": sorted(ausencias_por_dia.get(day_key, []), key=lambda a: a["cir"]),
            "n_cirurgias_manha": manha_por_dia.get(day_key, 0),
            "sigic_tarde": sigic_by_date.get(day_key),
        })

    tarefas_hff = [
        item for item in todoist.get("itens", [])
        if item["classificacao"] == "trabalho_hff"
        and target.isoformat() <= item["date"] <= (target + timedelta(days=2)).isoformat()
    ]

    return {
        "meta": {
            "date": key,
            "weekday": weekday_pt(target),
            "tipo_dia": tipo_dia,
            "janela_dias": HFF_WINDOW_DAYS,
        },
        "resumo": {
            "tipo_dia": tipo_dia,
            "proximo_bo": proximo_bo,
            "fdr_total": cirurgias.get("fdr_total", 0),
            "anomalias": cirurgias.get("anomalias", []) + sigic.get("anomalias", []),
        },
        "tarefas_hff": {"janela": "hoje + 2 dias", "itens": tarefas_hff},
        "cirurgias": {"janela_dias": HFF_WINDOW_DAYS, "sessoes": cirurgias.get("sessoes", [])},
        "sigic": {"listas": sigic.get("listas", [])},
        "prevencao": {
            "semana_actual": prevencao.get("semana_actual", {}),
            "semanas": prevencao.get("semanas", []),
        },
        "equipa": {
            "ausencias_confirmadas": ausencias.get("ausencias", []),
            "folgas": ausencias.get("folgas", []),
            "codigos_ambiguos": ausencias.get("codigos_ambiguos", []),
            "codigos_sem_data": ausencias.get("codigos_sem_data", []),
            "calendario_4_semanas": calendario_4_semanas,
        },
    }


def build_bo_block(hff: dict[str, Any]) -> dict[str, Any]:
    """Lista cirurgica da equipa. Regras de visibilidade (Seccao 9 do doc do Painel HFF):
    nunca Prevencao, nunca tarefas pessoais, motivo de ausencia so se for 'Ferias'."""
    semanas: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for session in hff.get("cirurgias", {}).get("sessoes", []):
        day = date.fromisoformat(session["date"])
        week_start = day - timedelta(days=day.weekday())
        semanas[week_start.isoformat()].append({
            "date": session["date"],
            "weekday": session["weekday"],
            "periodo": session["periodo"],
            "cirurgioes": session.get("cirurgioes", []),
            "n_doentes": session["n_doentes"],
            "doentes": [
                {
                    "processo": d["processo"],
                    "nome": d["nome"],
                    "idade_fmt": d["idade_fmt"],
                    "procedimento": d["procedimento"],
                    "fdr": d["fdr"],
                    "obs": d["obs"],
                }
                for d in session["doentes"]
            ],
        })
    ausencias_publicas = [
        {"cir": a["cir"], "data": a["data"], "motivo": "Ferias"}
        for a in hff.get("equipa", {}).get("ausencias_confirmadas", [])
        if a.get("motivo") == "Ferias"
    ]
    return {
        "meta": hff.get("meta", {}),
        "semanas": [{"inicio": k, "sessoes": sorted(v, key=lambda s: (s["date"], s["periodo"]))}
                    for k, v in sorted(semanas.items())],
        "ausencias_publicas": ausencias_publicas,
        "regras_aplicadas": [
            "Prevencao nunca aparece na lista da equipa",
            "Tarefas pessoais nunca aparecem",
            "Motivo de ausencia so exibido quando e 'Ferias'",
        ],
    }


# ======================================================================================
# Draft canonico (esqueleto que o LLM so tem de preencher com texto)
# ======================================================================================
def build_canonical_draft(target: date, mode: str, generated_at: str, calendario: dict[str, Any],
                          todoist: dict[str, Any], weather: dict[str, Any] | None,
                          hff: dict[str, Any] | None) -> dict[str, Any]:
    itens = calendario.get("itens", [])
    eventos_por_dia: dict[str, list[dict[str, Any]]] = defaultdict(list)
    feriados_por_dia: dict[str, list[str]] = defaultdict(list)
    for item in itens:
        if item["tipo"] == "feriado":
            feriados_por_dia[item["date"]].append(item["titulo"])
        else:
            eventos_por_dia[item["date"]].append(item)

    tarefas_por_dia: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in todoist.get("itens", []):
        tarefas_por_dia[item["date"]].append(item)

    dias_calendario = []
    for offset in range(CALENDAR_WINDOW_DAYS):
        day = target + timedelta(days=offset)
        key = day.isoformat()
        eventos = eventos_por_dia.get(key, [])
        tarefas = tarefas_por_dia.get(key, [])
        badges = []
        if feriados_por_dia.get(key):
            badges.append("holiday")
        if any("sigic" in e["flags"] for e in eventos):
            badges.append("sigic")
        dias_calendario.append({
            "date": key,
            "eventos_count": len(eventos),
            "tarefas_count": len(tarefas),
            "badges": badges,
            "itens": (
                [{"tipo": "evento", "titulo": e["titulo"]} for e in eventos]
                + [{"tipo": "tarefa", "titulo": t["texto"]} for t in tarefas]
            ),
        })

    cards = []
    hoje_dias = []
    rotina_dias = []
    for offset, label in enumerate(DAY_LABELS):
        day = target + timedelta(days=offset)
        key = day.isoformat()
        eventos = eventos_por_dia.get(key, [])
        tarefas = tarefas_por_dia.get(key, [])
        sigic_no_dia = any("sigic" in e["flags"] for e in eventos)
        cards.append({
            "dia": label,
            "date": key,
            "tarefas": [{"texto": t["texto"], "feito": False} for t in tarefas],
            "eventos": [{"texto": e["titulo"], "feito": False} for e in eventos],
            "extras": [{"tipo": "habito", "texto": HABITS_BY_WEEKDAY[day.weekday()], "feito": False}],
        })
        hoje_dias.append({
            "dia": label,
            "date": key,
            "weekday": weekday_pt(day),
            "audio_script": "",          # <- LLM
            "alertas": [],               # <- LLM
            "feriado": (feriados_por_dia.get(key) or [None])[0],
            "proximo_evento": (
                {"titulo": eventos[0]["titulo"], "date_label": label, "time": (eventos[0].get("inicio") or "")[11:16]}
                if eventos else None
            ),
        })
        rotina_dias.append({
            "dia": label,
            "date": key,
            "weekday": weekday_pt(day),
            "janelas": [
                {"id": "matinal", "hora": "08h00", "conferir": [], "habito_dia": HABITS_BY_WEEKDAY[day.weekday()], "sugestao": ""},
                {"id": "processamento", "hora": "~21h" if sigic_no_dia else "~15h30", "conferir": [], "habito_dia": None, "sugestao": ""},
                {"id": "descompressao", "hora": "~21h30" if sigic_no_dia else "21h30", "conferir": [], "habito_dia": None, "sugestao": ""},
            ],
            "sigic_shift": sigic_no_dia,
        })

    tempo = {"tabela_7dias": [], "janelas": []}
    if weather:
        tempo = {
            "tabela_7dias": [
                {"date": row["label"], "icone": row["icone"], "max": row["max"], "min": row["min"], "chuva_pct": row["chuva_pct"]}
                for row in weather.get("tabela_7dias", [])
            ],
            "janelas": [
                {"hora": hora, "actividade": "", "temp": (info or {}).get("temp"), "nota": ""}
                for hora, info in (weather.get("horas_chave") or {}).items()
            ],
        }

    return {
        "meta": {
            "date": target.isoformat(),
            "weekday": weekday_pt(target),
            "mode": mode,
            "generated_at": generated_at,
        },
        "hoje": {"dias": hoje_dias},
        "tarefas": {"cards": cards},
        "calendario": {"mes": target.strftime("%Y-%m"), "dias": dias_calendario},
        "email": {  # <- LLM classifica a partir de "email" na raiz deste ficheiro
            "urgente": [], "importante": [], "informativo": [], "ruido": [],
            "tarefas_sem_data": [], "snoozed": [], "pediatric_surgery": [], "ulsasi": [], "events": [],
        },
        "hff": hff if mode == "A" else None,
        "tempo": tempo,
        "rotina": {"dias": rotina_dias},
    }


# ======================================================================================
# Escrita e limpeza
# ======================================================================================
def cleanup_previous(out_dir: Path, keep: Path) -> list[str]:
    removed = []
    for path in sorted(out_dir.glob(f"*{OUT_SUFFIX}")):
        if path.resolve() == keep.resolve():
            continue
        try:
            path.unlink()
            removed.append(path.name)
        except OSError as exc:
            print(f"AVISO: nao foi possivel apagar {path.name}: {exc}", file=sys.stderr)
    return removed


# ======================================================================================
# Orquestracao
# ======================================================================================
def run(args: argparse.Namespace) -> dict[str, Any]:
    warnings: list[str] = []
    errors: list[str] = []
    agora = now_lisbon()
    data_real = parse_date(args.real_date) or agora.date()

    target, origem_alvo = resolve_target_date(
        data_real=data_real,
        hora=agora.hour,
        target_date=args.target_date,
        next_bd=args.next_business_day,
        today=args.today,
    )

    if args.mode:
        mode = args.mode.upper()
        origem_modo = "--mode"
    else:
        mode = "B" if target.weekday() >= 5 else "A"
        origem_modo = "automatico: fim de semana -> B" if target.weekday() >= 5 else "automatico: dia util -> A"

    fontes: dict[str, Any] = {}
    calendario: dict[str, Any] = {"calendarios": [], "itens": []}
    email: dict[str, Any] = {}
    todoist: dict[str, Any] = {"itens": [], "por_dia": {}}
    weather: dict[str, Any] | None = None
    hff: dict[str, Any] | None = None
    bo: dict[str, Any] | None = None

    services = google_services(errors)

    if services:
        try:
            calendario = collect_calendar(services["calendar"], target, CALENDAR_WINDOW_DAYS, warnings)
            fontes["calendario"] = {"ok": True, "calendarios": len(calendario["calendarios"]), "itens": len(calendario["itens"])}
        except Exception as exc:
            fontes["calendario"] = {"ok": False, "erro": f"{type(exc).__name__}: {exc}"}
            errors.append(f"Calendario: {exc}")

        try:
            email = collect_gmail(services["gmail"], warnings)
            fontes["gmail"] = {"ok": True, "seccoes": {k: v.get("total", 0) for k, v in email.items()}}
        except Exception as exc:
            fontes["gmail"] = {"ok": False, "erro": f"{type(exc).__name__}: {exc}"}
            errors.append(f"Gmail: {exc}")
    else:
        fontes["calendario"] = {"ok": False, "erro": "sem servicos Google"}
        fontes["gmail"] = {"ok": False, "erro": "sem servicos Google"}

    token = todoist_token(errors)
    if token:
        try:
            todoist = collect_todoist(token, target, warnings)
            fontes["todoist"] = {"ok": True, "itens": len(todoist["itens"])}
        except Exception as exc:
            fontes["todoist"] = {"ok": False, "erro": f"{type(exc).__name__}: {exc}"}
            errors.append(f"Todoist: {exc}")
    else:
        fontes["todoist"] = {"ok": False, "erro": "token em falta"}

    try:
        weather = collect_weather(target)
        fontes["tempo"] = {"ok": True, "dias": len(weather["tabela_7dias"])}
    except Exception as exc:
        fontes["tempo"] = {"ok": False, "erro": f"{type(exc).__name__}: {exc}"}
        warnings.append(f"Tempo: previsao indisponivel ({exc}); a seccao fica vazia, nao inventar valores.")

    if mode == "A":
        if services:
            try:
                espelho = read_espelho(services["sheets"], args.espelho_id)
                hff = build_hff_block(target, espelho, todoist, warnings, errors)
                bo = build_bo_block(hff)
                fontes["espelho_hff"] = {
                    "ok": True,
                    "spreadsheet_id": args.espelho_id,
                    "abas": list(espelho.keys()),
                    "sessoes": len(hff["cirurgias"]["sessoes"]),
                }
            except Exception as exc:
                fontes["espelho_hff"] = {"ok": False, "erro": f"{type(exc).__name__}: {exc}"}
                errors.append(f"Espelho HFF: {exc}")
        else:
            fontes["espelho_hff"] = {"ok": False, "erro": "sem servicos Google"}
    else:
        fontes["espelho_hff"] = {"ok": True, "ignorado": "Modo B nao tem tab HFF"}

    generated_at = agora.isoformat(timespec="seconds")
    draft = build_canonical_draft(target, mode, generated_at, calendario, todoist, weather, hff)

    return {
        "schema_version": SCHEMA_VERSION,
        "rotina": ROTINA,
        "gerado_em": generated_at,
        "passo_zero": {
            "agora_lisboa": generated_at,
            "data_real": data_real.isoformat(),
            "dia_semana_real": weekday_pt(data_real),
            "hora": agora.strftime("%H:%M"),
            "depois_das_16h": agora.hour >= 16,
        },
        "modo": {
            "valor": mode,
            "origem": origem_modo,
            "data_alvo": target.isoformat(),
            "dia_semana_alvo": weekday_pt(target),
            "origem_data_alvo": origem_alvo,
            "janela_3_dias": [(target + timedelta(days=i)).isoformat() for i in range(DAY_WINDOW_DAYS)],
            "janela_calendario": {
                "inicio": target.isoformat(),
                "fim": (target + timedelta(days=CALENDAR_WINDOW_DAYS - 1)).isoformat(),
                "dias": CALENDAR_WINDOW_DAYS,
            },
        },
        "fontes": fontes,
        "calendario": calendario,
        "tarefas_todoist": todoist,
        "email": email,
        "tempo": weather,
        "hff": hff,
        "bo": bo,
        "habitos_por_dia_semana": {WEEKDAYS_PT[k]: v for k, v in HABITS_BY_WEEKDAY.items()},
        "cobertura": {
            "calendario_itens": len(calendario.get("itens", [])),
            "todoist_itens": len(todoist.get("itens", [])),
            "email_por_seccao": {k: v.get("total", 0) for k, v in email.items()},
            "tempo_presente": weather is not None,
            "hff_presente": hff is not None,
            "bo_presente": bo is not None,
        },
        "avisos": warnings,
        "erros": errors,
        "canonical_draft": draft,
        "_llm_handoff": {
            "o_que_o_python_ja_fez": [
                "Passo Zero (data/hora reais em Europe/Lisbon) e resolucao do Modo A/B/C",
                "Leitura de todos os calendarios Google, normalizada para hora de Lisboa",
                "Leitura directa do Todoist com prioridade (o calendario Todoist foi ignorado)",
                "Leitura das 5 labels de Gmail (nunca label:events)",
                "Previsao Open-Meteo (7 dias + horas-chave)",
                "Leitura e parsing do Espelho HFF (Cirurgias/SIGIC/Prevencao/Ausencias) e derivacao da lista BO",
                "Esqueleto do JSON canonico ja preenchido com tudo o que e mecanico",
            ],
            "o_que_falta_ao_llm": [
                "Classificar cada email em urgente/importante/informativo/ruido (dados crus em 'email')",
                "Escrever os 3 audio_script (um por dia da janela)",
                "Escrever alertas, sugestoes e as listas 'conferir' das 3 janelas de rotina",
                "Cruzar duplicados evento vs tarefa e resolver ambiguidades assinaladas em 'avisos'",
                "Emitir o JSON canonico final (sem este bloco) para o render/publicacao",
            ],
            "o_llm_nunca_deve": [
                "Voltar a ler Gmail/Calendario/Todoist/Sheets: ja esta tudo aqui",
                "Escrever HTML ou publicar",
                "Inventar dados quando 'fontes' marcar ok=false — usar aviso explicito",
            ],
        },
    }


# ======================================================================================
# Self-test (logica pura, sem rede)
# ======================================================================================
def self_test() -> int:
    failures: list[str] = []

    def check(name: str, condition: bool) -> None:
        if not condition:
            failures.append(name)

    check("parse_date ISO", parse_date("2026-09-14") == date(2026, 9, 14))
    check("parse_date PT", parse_date("14/09/2026") == date(2026, 9, 14))
    check("parse_date serial", parse_date(46000) == date(1899, 12, 30) + timedelta(days=46000))
    check("parse_date lixo", parse_date("nao e data") is None)

    check("next_business_day sexta->segunda", next_business_day(date(2026, 9, 11)) == date(2026, 9, 14))
    check("next_business_day sabado->segunda", next_business_day(date(2026, 9, 12)) == date(2026, 9, 14))
    check("next_business_day segunda->terca", next_business_day(date(2026, 9, 14)) == date(2026, 9, 15))

    # Regra das 16h (a que antes vivia na cabeca do LLM)
    seg, sex, sab = date(2026, 9, 14), date(2026, 9, 11), date(2026, 9, 12)
    check("16h: segunda 06h -> proprio dia", resolve_target_date(seg, 6)[0] == seg)
    check("16h: segunda 15h59 -> proprio dia", resolve_target_date(seg, 15)[0] == seg)
    check("16h: segunda 16h -> terca", resolve_target_date(seg, 16)[0] == date(2026, 9, 15))
    check("16h: sexta 18h -> segunda", resolve_target_date(sex, 18)[0] == seg)
    check("16h: sabado 10h -> proprio sabado (Modo B)", resolve_target_date(sab, 10)[0] == sab)
    check("16h: sabado 19h -> segunda", resolve_target_date(sab, 19)[0] == seg)
    check("--today vence a regra das 16h", resolve_target_date(seg, 20, today=True)[0] == seg)
    check("--target-date vence tudo", resolve_target_date(seg, 20, target_date="2026-12-25", today=True)[0] == date(2026, 12, 25))
    check("--next-business-day vence --today", resolve_target_date(seg, 6, next_bd=True, today=True)[0] == date(2026, 9, 15))

    check("weekday_pt sabado", weekday_pt(date(2026, 9, 12)) == "sabado")
    check("prioridade p1", classify_priority(4) == "alta")
    check("prioridade p2", classify_priority(3) == "media")
    check("prioridade p4", classify_priority(1) == "baixa")

    check("ausencia Mif", bool(ABSENCE_RE.match(compact_norm("Mif"))))
    check("ausencia Frc", bool(ABSENCE_RE.match(compact_norm("Frc"))))
    check("folga *if", bool(DAY_OFF_RE.match(compact_norm("*if"))))
    check("ausencia invalida", not ABSENCE_RE.match(compact_norm("Xyz")))

    check("classify_calendar rafael", classify_calendar("Rafael correia") == "evento")
    check("classify_calendar feriados", classify_calendar("Feriados em Portugal") == "feriado")
    check("classify_calendar cirped", classify_calendar("cirped.ulsasi@gmail.com") == "profissional")
    check("flags sigic", "sigic" in detect_flags("Sigic tarde"))
    check("flags viagem", "viagem" in detect_flags("Flight to Lisbon (FR 9903)"))

    rows = [
        ["Data Cirurgia", "Periodo", "Processo", "Nome doente", "Idade", "Procedimento",
         "FDR", "Tempo em Lista de Espera", "Status Agendamento", "Observacao",
         "Previsao IF ausente", "Previsao RC ausente", "Previsao RR ausente"],
        ["14/09/2026", "M", "12345", "Doente A", "3,5", "Hernia inguinal", "FALSE", "120", "Agendado", "", "FALSE", "FALSE", "FALSE"],
        ["14/09/2026", "M", "67890", "Doente B", "0,5", "Fimose", "TRUE", "30", "Agendado", "", "FALSE", "TRUE", "FALSE"],
        ["15/09/2026", "M", "11111", "Doente C", "7", "Apendicectomia", "FALSE", "10", "Agendado", "", "FALSE", "FALSE", "FALSE"],
    ]
    warnings: list[str] = []
    errors: list[str] = []
    parsed = parse_cirurgias(rows, date(2026, 9, 14), warnings, errors)
    check("cirurgias ok", parsed["ok"] is True)
    check("cirurgias 2 sessoes", len(parsed["sessoes"]) == 2)
    check("cirurgias ordena por idade", parsed["sessoes"][0]["doentes"][0]["nome"] == "Doente B")
    check("cirurgias FDR", parsed["fdr_total"] == 1)
    check("cirurgias anomalia terca", any(a["tipo"] == "bo_em_dia_invalido" for a in parsed["anomalias"]))
    check("cirurgias ausente previsto", parsed["sessoes"][0]["ausentes_previstos"] == ["RC"])

    grid = [
        ["Setembro", "", ""],
        ["14", "Mif", ""],
        ["15", "*rc", ""],
    ]
    ausencias = parse_ausencias(grid, date(2026, 9, 14))
    check("ausencias 1 confirmada", len(ausencias["ausencias"]) == 1)
    check("ausencias motivo Madeira", ausencias["ausencias"][0]["motivo"] == "Madeira")
    check("folgas 1", len(ausencias["folgas"]) == 1)

    draft = build_canonical_draft(
        date(2026, 9, 14), "B", "2026-09-14T08:00:00+01:00",
        {"itens": [{"date": "2026-09-14", "titulo": "Sigic", "tipo": "evento", "calendario": "Rafael correia",
                    "inicio": "2026-09-14T15:30+01:00", "fim": None, "dia_inteiro": False, "local": None,
                    "flags": ["sigic"], "event_id": "x"}]},
        {"itens": [{"date": "2026-09-14", "texto": "Forxiga", "prioridade": "baixa", "classificacao": "pessoal"}]},
        None, None,
    )
    check("draft 3 dias hoje", len(draft["hoje"]["dias"]) == 3)
    check("draft 3 dias rotina", len(draft["rotina"]["dias"]) == 3)
    check("draft 15 dias calendario", len(draft["calendario"]["dias"]) == CALENDAR_WINDOW_DAYS)
    check("draft hff null em modo B", draft["hff"] is None)
    check("draft sigic_shift", draft["rotina"]["dias"][0]["sigic_shift"] is True)
    check("draft badge sigic", "sigic" in draft["calendario"]["dias"][0]["badges"])
    check("draft habito segunda", draft["tarefas"]["cards"][0]["extras"][0]["texto"].startswith("Leitura"))

    if failures:
        print("SELF-TEST FALHOU:")
        for name in failures:
            print(f"  - {name}")
        return 1
    print("SELF-TEST OK (todas as verificacoes passaram)")
    return 0


# ======================================================================================
# CLI
# ======================================================================================
def main() -> int:
    parser = argparse.ArgumentParser(
        description="Recolha mecanica unica do Briefing Diario (+ Painel HFF e Lista BO)."
    )
    parser.add_argument("--mode", choices=["A", "B", "a", "b"], help="Forcar modo. Por omissao: A em dia util, B ao fim de semana.")
    parser.add_argument("--real-date", help="Data real YYYY-MM-DD (default: hoje em Lisboa).")
    parser.add_argument("--target-date", help="DATA_ALVO YYYY-MM-DD.")
    parser.add_argument("--next-business-day", action="store_true", help="Modo C: DATA_ALVO = proximo dia util.")
    parser.add_argument("--today", action="store_true",
                        help=f"Forcar DATA_ALVO = dia real, mesmo depois das {CUTOFF_HOUR}h.")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR, help=f"Pasta de saida (default: {DEFAULT_OUT_DIR}).")
    parser.add_argument("--espelho-id", default=ESPELHO_HFF_ID, help="ID do Espelho HFF no Google Sheets.")
    parser.add_argument("--no-cleanup", action="store_true", help="Nao apagar os briefings anteriores.")
    parser.add_argument("--stdout", action="store_true", help="Imprimir o JSON tambem no stdout.")
    parser.add_argument("--self-test", action="store_true", help="Testar a logica pura, sem rede nem credenciais.")
    args = parser.parse_args()

    if args.self_test:
        return self_test()

    payload = run(args)

    out_dir: Path = args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.fromisoformat(payload["gerado_em"]).strftime("%Y_%m_%d_%H%M")
    out_path = out_dir / f"{stamp}{OUT_SUFFIX}"
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    removed: list[str] = []
    if not args.no_cleanup:
        removed = cleanup_previous(out_dir, keep=out_path)

    if args.stdout:
        print(json.dumps(payload, ensure_ascii=False, indent=2))

    resumo = {
        "ficheiro": str(out_path),
        "modo": payload["modo"]["valor"],
        "data_alvo": payload["modo"]["data_alvo"],
        "apagados": removed,
        "fontes_ok": {k: bool(v.get("ok")) for k, v in payload["fontes"].items()},
        "avisos": len(payload["avisos"]),
        "erros": len(payload["erros"]),
    }
    print(json.dumps(resumo, ensure_ascii=False, indent=2))
    for message in payload["erros"]:
        print(f"ERRO: {message}", file=sys.stderr)
    for message in payload["avisos"]:
        print(f"AVISO: {message}", file=sys.stderr)

    return 1 if payload["erros"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
