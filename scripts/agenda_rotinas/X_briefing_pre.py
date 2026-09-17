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

# API unificada v1 do Todoist. A REST v2 foi desligada (HTTP 410) em Setembro de 2026.
TODOIST_API_URL = "https://api.todoist.com/api/v1/tasks"
TODOIST_PAGE_SIZE = 200      # tecto por pedido imposto pela propria API
TODOIST_MAX_PAGES = 20       # travao de seguranca contra um cursor que nunca termina

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
}
# Seccoes lidas por ID de etiqueta, nao por "label:" no texto da query. O operador label:
# depende da grafia exacta (espacos viram hifens, "Paediatric" leva 'a') e parte em silencio
# se a etiqueta for renomeada: devolve zero resultados sem erro nenhum. Resolver o ID a
# partir do nome e pedir por labelIds e exacto e falha alto se o nome nao existir.
GMAIL_LABEL_SECTIONS = {
    "tarefas_sem_data": "Tarefas sem data",
    "pediatric_surgery": "Paediatric Surgery",
    "ulsasi": "ULSASI",
}
GMAIL_FORBIDDEN_LABEL = "Events"  # exclusivo da Agenda de Lazer; o briefing nunca o le
GMAIL_MAX_PER_QUERY = 60

# Conta Google que estas rotinas esperam. Serve so para assinalar em voz alta quando o
# consentimento OAuth foi dado noutra conta (o sintoma e silencioso: tudo devolve zero).
EXPECTED_GOOGLE_ACCOUNT = "rafaielcc@gmail.com"

# Classificacao de calendarios (LEITURA_CALENDARIO v1.0, seccao 5)
CALENDAR_TYPES = {
    "rafael correia": "evento",
    "cirped.ulsasi@gmail.com": "profissional",
    "todoist": "tarefa",
}
CALENDAR_SKIP = {"todoist"}  # lido directamente pela API do Todoist (que expoe prioridade)

FLAG_PATTERNS = {
    "sigic": re.compile(r"\bsigic\b", re.IGNORECASE),
    # "preven" a seco apanhava "prevent"/"prevention" em descricoes de eventos em ingles
    # (o Meetup do volei apareceu marcado como Prevencao do HFF). Exigir a palavra inteira.
    "prevencao": re.compile(r"\bpreven[c\u00e7][a\u00e3]o\b", re.IGNORECASE),
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
# A partir do 2o semestre de 2026 (confirmado pelo Rafa) o codigo passou a levar sempre as
# iniciais — deixou de depender da cor da celula para identificar quem. Letra do motivo:
# B=Baixa, F=Ferias, C=Curso, M=Madeira. "*" + iniciais = folga por compensacao de horario.
ABSENCE_RE = re.compile(r"^(?P<motive>[BFCM])(?P<who>if|rc|rr|a)$", re.IGNORECASE)
DAY_OFF_RE = re.compile(r"^\*(?P<who>if|rc|rr|a)$", re.IGNORECASE)
MOTIVE_LABELS = {"B": "Baixa", "F": "Ferias", "C": "Curso", "M": "Madeira"}
FOLGA_MOTIVO = "Compensacao de horario"
BO_WEEKDAYS = {0, 2}  # BO = segunda e quarta APENAS

# Data em qualquer ponto de uma celula, nao so no inicio (o Espelho prefixa o dia da semana)
DATE_IN_TEXT_RE = re.compile(r"(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})")
DATE_ISO_IN_TEXT_RE = re.compile(r"(\d{4})-(\d{1,2})-(\d{1,2})")
# Formato "seg., 5/jan." — o valor FORMATADO que a API do Sheets devolve para as colunas
# de data das abas Sigic e Prevencao. E' diferente do serial numerico que se ve exportando
# a folha para .xlsx (esse ignora o formato da celula); a API devolve sempre o texto tal
# como aparece na folha, e este formato de coluna especifico nunca mostra o ano.
DATE_DIA_MES_ABREV_RE = re.compile(r"(\d{1,2})\s*/\s*([A-Za-z\u00c0-\u017f]{3,})\.?")

# Um doente de cirurgia pediatrica nao tem 126 anos: quando a folha calcula a idade a
# partir de uma data de nascimento em falta, sai a idade da data-zero da folha de calculo.
MAX_IDADE_PLAUSIVEL_ANOS = 25

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
    # O Espelho HFF escreve a data como "qua., 28/10/26": dia da semana + data. O corte
    # text[:10] acima dava "qua., 28/1" e falhava tudo, deixando 26 linhas sem data e a
    # tab HFF vazia sem dizer porque. Procurar a data em qualquer ponto do texto resolve
    # esta e qualquer outra decoracao a volta dela.
    # As abas Sigic e Prevencao guardam as datas como numero de serie da folha de
    # calculo ("46027" = 2026-01-05). A API devolve-o como texto, portanto o ramo
    # numerico acima nunca via estes valores e as duas abas saiam sempre vazias.
    if text.isdigit() and 20000 <= int(text) <= 60000:
        return date(1899, 12, 30) + timedelta(days=int(text))

    m = DATE_ISO_IN_TEXT_RE.search(text)
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            pass
    m = DATE_IN_TEXT_RE.search(text)
    if m:
        day, month, year = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if year < 100:
            year += 2000
        try:
            return date(year, month, day)
        except ValueError:
            pass

    # "5/jan." — dia + mes por extenso abreviado, sem ano. So se resolve com default_year;
    # sem ele, mais vale devolver None do que adivinhar um ano.
    m = DATE_DIA_MES_ABREV_RE.search(text)
    if m and default_year:
        month = MONTHS_PT.get(norm(m.group(2)))
        if month:
            try:
                return date(default_year, month, int(m.group(1)))
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


def mark_duplicates(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """O mesmo evento importado por duas vias (ex.: Meetup + convite directo) aparece duas
    vezes, com event_id diferente. Apanhar isto e trabalho mecanico — logo faz-se aqui, e
    nao na cabeca do LLM. Marca as repeticoes com 'duplicado_de' e devolve os grupos."""
    vistos: dict[tuple[str, str, str], list[str]] = defaultdict(list)
    for item in items:
        chave = (item["date"], item.get("inicio") or "", norm(item["titulo"]))
        vistos[chave].append(item["event_id"])
    duplicados = [
        {"date": k[0], "inicio": k[1] or None, "titulo": k[2], "event_ids": ids, "n": len(ids)}
        for k, ids in vistos.items() if len(ids) > 1
    ]
    repetidos = {eid for grupo in duplicados for eid in grupo["event_ids"][1:]}
    primeiro = {eid: grupo["event_ids"][0] for grupo in duplicados for eid in grupo["event_ids"][1:]}
    for item in items:
        if item["event_id"] in repetidos:
            item["duplicado_de"] = primeiro[item["event_id"]]
    return duplicados


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

    duplicados = mark_duplicates(items)
    return {"calendarios": calendars_meta, "itens": items, "duplicados": duplicados}


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


def fetch_todoist_tasks(token: str, warnings: list[str]) -> list[dict[str, Any]]:
    """Le todas as tarefas da API unificada v1 do Todoist, seguindo a paginacao por cursor.

    A antiga REST v2 (api.todoist.com/rest/v2/tasks) foi desligada pelo Doist em Setembro
    de 2026 e passou a responder HTTP 410 Gone — foi exactamente o que apanhamos na 1a
    execucao real. A v1 devolve {"results": [...], "next_cursor": ...} em vez de uma lista
    nua, por isso aceitamos as duas formas: se um dia voltar a ser lista, continua a andar.
    """
    headers = {"Authorization": f"Bearer {token}", "User-Agent": "agenda-briefing-pre/1.0"}
    tasks: list[dict[str, Any]] = []
    cursor: str | None = None
    for _ in range(TODOIST_MAX_PAGES):
        url = f"{TODOIST_API_URL}?limit={TODOIST_PAGE_SIZE}"
        if cursor:
            url += f"&cursor={urllib.parse.quote(cursor)}"
        payload = http_get_json(url, headers=headers)
        if isinstance(payload, list):          # forma antiga (v2)
            tasks.extend(payload)
            break
        if not isinstance(payload, dict):
            raise RuntimeError(f"resposta inesperada do Todoist: {type(payload).__name__}")
        tasks.extend(payload.get("results") or [])
        cursor = payload.get("next_cursor")
        if not cursor:
            break
    else:
        warnings.append(
            f"Todoist: parei nas {TODOIST_MAX_PAGES} paginas; podem faltar tarefas."
        )
    return tasks


def collect_todoist(token: str, target: date, warnings: list[str]) -> dict[str, Any]:
    tasks = fetch_todoist_tasks(token, warnings)

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

    por_dia_local: dict[str, list[str]] = defaultdict(list)
    for item in itens:
        por_dia_local[item["date"]].append(item["texto"])
    if sem_data:
        warnings.append(f"Todoist: {sem_data} tarefa(s) sem data ignoradas (nao entram no briefing).")
    return {
        "itens": itens,
        "por_dia": dict(por_dia_local),
        "total_sem_data": sem_data,
        "total_lidas": len(tasks),
        "api": TODOIST_API_URL,
    }


# ======================================================================================
# Fonte: Gmail
# ======================================================================================
def header_value(payload: dict[str, Any], name: str) -> str:
    for header in payload.get("headers", []) or []:
        if header.get("name", "").lower() == name.lower():
            return header.get("value", "")
    return ""


def gmail_account(service: Any, warnings: list[str]) -> str | None:
    """Que caixa de correio e que esta credencial abre, afinal.

    Sem isto, consentir o OAuth na conta errada e indistinguivel de uma caixa vazia:
    todas as queries devolvem zero e nenhuma delas da erro.
    """
    try:
        profile = service.users().getProfile(userId="me").execute()
    except Exception as exc:
        warnings.append(f"Gmail: nao consegui identificar a conta autenticada ({exc})")
        return None
    account = (profile.get("emailAddress") or "").strip()
    if account and norm(account) != norm(EXPECTED_GOOGLE_ACCOUNT):
        warnings.append(
            f"Gmail: autenticado como {account}, mas as rotinas assumem "
            f"{EXPECTED_GOOGLE_ACCOUNT}. Se as seccoes vierem vazias e por isto — "
            "apagar token_agenda.json e voltar a consentir na conta certa."
        )
    return account or None


class LabelLookupError(str):
    """Marca uma seccao cujo ID de etiqueta nao pode ser resolvido por falha da API
    (e nao por a etiqueta nao existir). O texto e a mensagem de erro original."""


def gmail_label_ids(service: Any, warnings: list[str]) -> dict[str, Any]:
    """Resolve nomes de etiqueta -> IDs. Um nome que nao exista fica None e da aviso."""
    try:
        listed = service.users().labels().list(userId="me").execute()
    except Exception as exc:
        # Nao dizer "etiqueta inexistente" quando o que falhou foi a propria chamada:
        # manda a pessoa procurar o problema no Gmail quando ele esta na API.
        warnings.append(f"Gmail: listagem de etiquetas falhou ({exc})")
        return {section: LabelLookupError(f"{type(exc).__name__}: {exc}") for section in GMAIL_LABEL_SECTIONS}
    by_name = {norm(item.get("name", "")): item.get("id") for item in listed.get("labels", [])}
    resolved: dict[str, str | None] = {}
    for section, label_name in GMAIL_LABEL_SECTIONS.items():
        label_id = by_name.get(norm(label_name))
        if label_id is None:
            warnings.append(
                f"Gmail '{section}': etiqueta '{label_name}' nao existe nesta conta; "
                "seccao fica vazia (verificar o nome exacto no Gmail)."
            )
        resolved[section] = label_id
    return resolved


def gmail_sections(email: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """So as seccoes de mensagens: ignora chaves de metadados como '_conta'."""
    return {k: v for k, v in email.items() if not k.startswith("_") and isinstance(v, dict)}


def collect_gmail(service: Any, warnings: list[str]) -> dict[str, Any]:
    forbidden = norm(GMAIL_FORBIDDEN_LABEL)
    assert forbidden not in {norm(v) for v in GMAIL_LABEL_SECTIONS.values()}, \
        "O briefing nunca le a etiqueta Events (pertence em exclusivo a Agenda de Lazer)."
    assert forbidden not in norm(" ".join(GMAIL_QUERIES.values())), \
        "O briefing nunca le a etiqueta Events (pertence em exclusivo a Agenda de Lazer)."

    result: dict[str, Any] = {"_conta": gmail_account(service, warnings)}
    label_ids = gmail_label_ids(service, warnings)

    pedidos: list[tuple[str, str | None, str | None]] = [
        (section, query, None) for section, query in GMAIL_QUERIES.items()
    ] + [
        (section, None, label_ids.get(section)) for section in GMAIL_LABEL_SECTIONS
    ]

    for section, query, label_id in pedidos:
        origem = query if query else f"labelId:{label_id} ({GMAIL_LABEL_SECTIONS.get(section)})"
        if query is None and isinstance(label_id, LabelLookupError):
            result[section] = {
                "query": f"etiqueta '{GMAIL_LABEL_SECTIONS.get(section)}' (por resolver)",
                "total": 0,
                "erro": f"nao foi possivel listar etiquetas: {label_id}",
                "mensagens": [],
            }
            continue
        if query is None and label_id is None:
            result[section] = {
                "query": origem,
                "total": 0,
                "erro": "etiqueta inexistente nesta conta",
                "mensagens": [],
            }
            continue
        try:
            params: dict[str, Any] = {"userId": "me", "maxResults": GMAIL_MAX_PER_QUERY}
            if query:
                params["q"] = query
            else:
                params["labelIds"] = [label_id]
            listed = service.users().messages().list(**params).execute()
        except Exception as exc:
            warnings.append(f"Gmail '{section}': listagem falhou ({exc})")
            result[section] = {"query": origem, "total": 0, "erro": f"{type(exc).__name__}: {exc}", "mensagens": []}
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
        result[section] = {"query": origem, "total": len(mensagens), "mensagens": mensagens}
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
        raw_date_cell = cell(row, mapping, "data")
        surgery_date = parse_date(raw_date_cell, default_year=today.year)
        if surgery_date is None:
            if str(raw_date_cell or "").strip():
                # Nunca cair fora da lista em silencio: uma data ilegivel e um
                # doente a menos que ninguem repara ter desaparecido.
                anomalies.append({
                    "tipo": "data_ilegivel", "linha": row_idx, "raw": str(raw_date_cell),
                    "processo": str(cell(row, mapping, "processo") or "").strip(),
                })
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

        idade_valor = parse_float(cell(row, mapping, "idade"))
        if idade_valor is not None and idade_valor > MAX_IDADE_PLAUSIVEL_ANOS:
            anomalies.append({
                "tipo": "idade_implausivel", "linha": row_idx, "date": surgery_date.isoformat(),
                "valor": idade_valor,
                "nota": "Provavel data de nascimento em falta na folha; tratada como sem dados.",
            })
            idade_valor = None

        doente = {
            "processo": processo,
            "nome": str(cell(row, mapping, "nome") or "").strip(),
            "idade_raw": idade_valor,
            "idade_fmt": age_fmt(idade_valor),
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
    rotulo_mes: int | None = None   # a coluna MES so vem preenchida na 1a linha de cada mes
    ilegiveis = 0
    amostra_ilegiveis: list[str] = []

    for row_idx, row in enumerate(rows[header_idx + 1:], start=header_idx + 2):
        rotulo = month_from_value(cell(row, mapping, "mes"))
        if rotulo:
            rotulo_mes = rotulo
        dia_value = cell(row, mapping, "dia")
        sigic_date = parse_date(dia_value, default_year=today.year)
        if sigic_date is None and isinstance(dia_value, (int, float)) and rotulo_mes:
            try:
                sigic_date = date(today.year, rotulo_mes, int(dia_value))
            except ValueError:
                sigic_date = None

        if sigic_date is None:
            if str(dia_value or "").strip():
                ilegiveis += 1
                if len(amostra_ilegiveis) < 5:
                    amostra_ilegiveis.append(str(dia_value))
            continue

        # O rotulo do mes e a data tem de concordar. Na folha real, as linhas de Agosto a
        # Dezembro traziam datas de 2025 — o calendario do ano anterior, nunca actualizado.
        # Isto e um erro de dados, nao de leitura: assinala-se, nunca se corrige por conta
        # propria (corrigir seria inventar uma lista cirurgica que ninguem marcou).
        if rotulo_mes and sigic_date.month != rotulo_mes:
            sugerida = None
            try:
                sugerida = date(today.year, rotulo_mes, sigic_date.day).isoformat()
            except ValueError:
                pass
            anomalias.append({
                "tipo": "sigic_mes_incoerente",
                "linha": row_idx,
                "date": sigic_date.isoformat(),
                "mes_rotulado": rotulo_mes,
                "sugestao": sugerida,
                "nota": "A coluna MES e a data nao concordam; provavel ano errado na folha.",
            })
        elif rotulo_mes and sigic_date.year != today.year:
            anomalias.append({
                "tipo": "sigic_ano_incoerente",
                "linha": row_idx,
                "date": sigic_date.isoformat(),
                "ano_esperado": today.year,
                "sugestao": sigic_date.replace(year=today.year).isoformat(),
                "nota": "Linha datada de outro ano; provavel calendario do ano anterior por actualizar.",
            })

        if not (today <= sigic_date <= end):
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
    return {
        "ok": True,
        "listas": listas,
        "anomalias": anomalias,
        "linhas_data_ilegivel": ilegiveis,
        "amostra_datas_ilegiveis": amostra_ilegiveis,
    }


def month_blocks(rows: list[list[Any]]) -> list[dict[str, int]]:
    """Localiza os cabecalhos de mes da grelha (JANEIRO, FEVEREIRO, ...).

    So aceita o NOME do mes escrito por extenso: um numero de 1 a 12 nesta grelha e
    quase de certeza um dia do mes, nao um mes.
    """
    blocos = []
    for r, row in enumerate(rows):
        for c, value in enumerate(row):
            if not isinstance(value, str):
                continue
            month = MONTHS_PT.get(norm(value))
            if month:
                blocos.append({"row": r, "col": c, "month": month})
    return blocos


def grid_year(rows: list[list[Any]], default: int) -> int:
    """O ano vem do titulo da grelha ("CALENDARIO 2026"); se nao houver, usa o corrente."""
    for row in rows[:6]:
        for value in row:
            m = re.search(r"\b(20\d{2})\b", str(value or ""))
            if m:
                return int(m.group(1))
    return default


def infer_grid_date(rows: list[list[Any]], r: int, c: int, year: int,
                    blocos: list[dict[str, int]]) -> date | None:
    """A aba Ausencias e um calendario anual com tres meses lado a lado, nao uma tabela.

    Cada bloco de mes ocupa 7 colunas (D a S) e alterna linhas de numeros do dia com
    linhas de codigos. O mes de um codigo e o cabecalho mais proximo acima cuja faixa
    de colunas o cobre; o dia e o primeiro numero 1-31 que aparece a subir na MESMA
    coluna, sem sair do bloco. A heuristica anterior olhava apenas 8 linhas acima e por
    isso so datava a 1a semana de cada mes — 75 dos 83 codigos ficavam sem data.
    """
    try:
        explicit = parse_date(rows[r][c], default_year=year)
    except IndexError:
        return None
    if explicit:
        return explicit

    cobrem = [b for b in blocos if b["row"] < r and b["col"] <= c <= b["col"] + 6]
    if not cobrem:
        return None
    bloco = max(cobrem, key=lambda b: b["row"])

    for rr in range(r - 1, bloco["row"], -1):
        try:
            candidate = rows[rr][c]
        except IndexError:
            continue
        text = str(candidate or "").strip()
        if not re.fullmatch(r"\d{1,2}", text):
            continue
        day = int(text)
        if not 1 <= day <= 31:
            continue
        try:
            return date(year, bloco["month"], day)
        except ValueError:
            return None
    return None


def parse_ausencias(rows: list[list[Any]], today: date) -> dict[str, Any]:
    """Codigos: Maiuscula = motivo (B/F/C/M) + minusculas = iniciais (if/rc/rr/a). Ex: 'Mif'.
    '*if' = folga por compensacao de horario. A aba Ausencias e autoritativa."""
    end = today + timedelta(days=HFF_WINDOW_DAYS - 1)
    blocos = month_blocks(rows)
    year = grid_year(rows, today.year)
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
            # Codigo de 1 letra sem iniciais: so existia no esquema antigo (a cor da
            # celula e' que identificava a pessoa) — dados anteriores ao 2o semestre de
            # 2026, fora da janela dos 28 dias. Mantido por seguranca, nunca deve ocorrer
            # em dados novos.
            ambiguous_single = compact.upper() in {"B", "F", "C", "M"}
            if not (absence_match or day_off_match or ambiguous_single):
                continue
            parsed_date = infer_grid_date(rows, r_idx, c_idx, year, blocos)
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
                folgas.append({
                    "cir": day_off_match.group("who").upper(),
                    "motivo": FOLGA_MOTIVO,
                    **record,
                })
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
        "madeira": ["Cirurgiao na Madeira", "Cirurgião na Madeira",
                    "Cirurgiao com alguns dias da semana na Madeira (Nao pode estar de prevencao)",
                    "Cirurgião com alguns dias da semana na Madeira (Não pode estar de prevenção)"],
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


def compact_date_ranges(records: list[dict[str, Any]]) -> list[dict[str, str]]:
    """Agrupa registos diarios {"cir", "motivo", "data"} em blocos consecutivos por
    (cir, motivo), para nao listar um bullet por dia (Seccao 11: resumo.ausencias_relevantes
    e' 'ausencias_confirmadas + folgas reformatadas como bullets com datas')."""
    by_group: dict[tuple[str, str], list[str]] = defaultdict(list)
    for item in records:
        by_group[(item["cir"], item["motivo"])].append(item["data"])
    out = []
    for (cir, motivo), dates in by_group.items():
        dates = sorted(set(dates))
        start = prev = date.fromisoformat(dates[0])
        for d_str in dates[1:] + [None]:
            d = date.fromisoformat(d_str) if d_str else None
            if d is None or (d - prev).days > 1:
                datas = start.isoformat() if start == prev else f"{start.isoformat()} a {prev.isoformat()}"
                out.append({"cir": cir, "motivo": motivo, "datas": datas})
                if d:
                    start = d
            if d:
                prev = d
    out.sort(key=lambda i: (i["datas"], i["cir"]))
    return out


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

    incoerentes = sum(1 for a in sigic.get("anomalias", [])
                      if a["tipo"] in {"sigic_mes_incoerente", "sigic_ano_incoerente"})
    if incoerentes:
        warnings.append(
            f"Espelho HFF / SIGIC: {incoerentes} linha(s) com o mes rotulado a discordar da "
            "data (provavel ano por actualizar na folha). Nao foram corrigidas: ver anomalias."
        )
    if ausencias.get("codigos_sem_data"):
        warnings.append(
            f"Espelho HFF / Ausencias: {len(ausencias['codigos_sem_data'])} codigo(s) sem data "
            "atribuivel; confirmar o desenho da grelha."
        )
    if ausencias.get("codigos_ambiguos"):
        warnings.append(
            f"Espelho HFF / Ausencias: {len(ausencias['codigos_ambiguos'])} codigo(s) sem iniciais "
            "(a cor da celula e que identifica a pessoa, e a cor nao e legivel por aqui)."
        )

    tarefas_hff = [
        item for item in todoist.get("itens", [])
        if item["classificacao"] == "trabalho_hff"
        and target.isoformat() <= item["date"] <= (target + timedelta(days=2)).isoformat()
    ]

    # equipa.ausencias_provaveis (Seccao 11): sinal fraco (flag da aba Cirurgias),
    # nunca confundir com equipa.ausencias_confirmadas (aba Ausencias, fonte autoritativa).
    ausencias_provaveis = sorted(
        {
            (session["date"], initials)
            for session in cirurgias.get("sessoes", [])
            for initials in session.get("ausentes_previstos", [])
        }
    )
    ausencias_provaveis = [{"cir": cir, "dia": dia, "fonte": "flag_cirurgias"} for dia, cir in ausencias_provaveis]

    generated_at_iso = datetime.now(TZ).isoformat(timespec="seconds")

    return {
        "_diagnostico": {
            # Sem isto, "sessoes: 0" e ambiguo: cabecalho nao reconhecido? folha vazia?
            # cirurgias todas fora da janela? Agora a resposta vem no proprio JSON.
            "cirurgias_cabecalho_ok": bool(cirurgias.get("ok")),
            "cirurgias_cabecalhos_em_falta": cirurgias.get("missing_headers", []),
            "cirurgias_linhas_na_folha": max(0, len(sheets["cirurgias"] or []) - 1),
            "cirurgias_linhas_na_janela": cirurgias.get("linhas_na_janela", 0),
            "sigic_cabecalho_ok": bool(sigic.get("ok")),
            "sigic_listas_na_janela": len(sigic.get("listas", [])),
            "sigic_datas_ilegiveis": sigic.get("linhas_data_ilegivel", 0),
            "sigic_amostra_ilegiveis": sigic.get("amostra_datas_ilegiveis", []),
            "sigic_linhas_incoerentes": sum(
                1 for a in sigic.get("anomalias", [])
                if a["tipo"] in {"sigic_mes_incoerente", "sigic_ano_incoerente"}
            ),
            "ausencias_codigos_sem_data": len(ausencias.get("codigos_sem_data", [])),
            "ausencias_codigos_ambiguos": len(ausencias.get("codigos_ambiguos", [])),
            "prevencao_semanas": len(prevencao.get("semanas", [])),
            "prevencao_cabecalho_ok": bool(prevencao.get("ok")),
            "janela": {"inicio": key, "fim": (target + timedelta(days=HFF_WINDOW_DAYS - 1)).isoformat()},
            # Factos crus para o LLM rever ao escrever resumo.alertas (Seccao 8 item 1:
            # FDR, codigos ambiguos, duplicados -- nunca ausencias, essas vao em ausencias_relevantes).
            "cirurgias_fdr_total": cirurgias.get("fdr_total", 0),
            "cirurgias_anomalias": cirurgias.get("anomalias", []),
            "sigic_anomalias": sigic.get("anomalias", []),
        },
        # Esquema desta chave 'meta' para baixo segue a Seccao 11 de
        # INSTRUCOES_PAINEL_HFF.md ao pe da letra -- e' o mesmo objecto que
        # alimenta a tab do Briefing (fatia de hoje) e o X_hff_pos.py
        # (Hff/index.html + BO/index.html, 4 semanas). "briefing_resumo"/
        # "briefing_cirurgias_resumo" abaixo sao a UNICA parte especifica do
        # Briefing -- nomes deliberadamente diferentes de "resumo" para nao
        # repetir o erro de uma chave a servir dois propositos incompativeis.
        "meta": {
            "date": key,
            "weekday": weekday_pt(target),
            "day_type": tipo_dia,
            "generated_at": generated_at_iso,
        },
        "resumo": {
            "tipo_dia": tipo_dia,
            "alertas": [],  # <- LLM: frases curtas (FDR, codigos ambiguos, duplicados -- NAO ausencias)
            "ausencias_relevantes": compact_date_ranges(ausencias.get("ausencias", []) + ausencias.get("folgas", [])),
            "proximo_bo": proximo_bo,
        },
        "briefing_resumo": "",              # <- LLM: frase curta para a tab do Briefing, a partir de 'resumo'
        "briefing_cirurgias_resumo": "",    # <- LLM: frase curta sobre as cirurgias de hoje/se BO
        "tarefas_hff": {"janela": "hoje + 2 dias", "itens": tarefas_hff},
        "cirurgias": {"janela_dias": HFF_WINDOW_DAYS, "sessoes": cirurgias.get("sessoes", [])},
        "sigic": {"listas": sigic.get("listas", [])},
        "prevencao": {
            "semana_actual": prevencao.get("semana_actual", {}),
            "semanas": prevencao.get("semanas", []),
        },
        "equipa": {
            "ausencias_confirmadas": ausencias.get("ausencias", []),
            "ausencias_provaveis": ausencias_provaveis,
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
                          hff: dict[str, Any] | None, fontes: dict[str, Any],
                          avisos: list[str], erros: list[str]) -> dict[str, Any]:
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
            "alertas": [],                # <- LLM: lista de {"nivel": "urgente"|"importante"|"info", "texto": "..."},
                                           # NUNCA strings simples -- o render usa "nivel" para escolher cor/icone do banner.
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
        # A aba Diagnostico do template le directamente daqui. As tres primeiras
        # chaves sao mecanicas (o pre ja as tem prontas); notas_llm fica vazio —
        # o LLM so lhe mexe quando tem mesmo algo a assinalar, nunca por rotina.
        "diagnostico": {
            "fontes": fontes,
            "avisos": list(avisos),
            "erros": list(erros),
            "notas_llm": [],
            "tem_alertas": bool(erros) or bool(avisos) or any(
                isinstance(f, dict) and f.get("ok") is False for f in fontes.values()
            ),
        },
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
            fontes["calendario"] = {
                "ok": True,
                "calendarios": len(calendario["calendarios"]),
                "itens": len(calendario["itens"]),
                "duplicados": len(calendario.get("duplicados", [])),
            }
            if calendario.get("duplicados"):
                warnings.append(
                    f"Calendario: {len(calendario['duplicados'])} evento(s) repetido(s) "
                    "(mesma data, hora e titulo); marcados com 'duplicado_de'."
                )
        except Exception as exc:
            fontes["calendario"] = {"ok": False, "erro": f"{type(exc).__name__}: {exc}"}
            errors.append(f"Calendario: {exc}")

        try:
            email = collect_gmail(services["gmail"], warnings)
            seccoes = gmail_sections(email)
            # ok=True so quando NENHUMA seccao falhou. Antes, cinco seccoes em erro davam
            # cinco zeros e um ok=True — indistinguivel de uma caixa de correio vazia.
            falhadas = sorted(k for k, v in seccoes.items() if v.get("erro"))
            fontes["gmail"] = {
                "ok": not falhadas,
                "conta": email.get("_conta"),
                "conta_esperada": EXPECTED_GOOGLE_ACCOUNT,
                "seccoes": {k: v.get("total", 0) for k, v in seccoes.items()},
                "seccoes_em_erro": {k: seccoes[k]["erro"] for k in falhadas},
            }
            if falhadas:
                errors.append("Gmail: seccoes sem leitura: " + ", ".join(falhadas))
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
                diagnostico = hff.get("_diagnostico", {})
                fontes["espelho_hff"] = {
                    "ok": bool(diagnostico.get("cirurgias_cabecalho_ok")),
                    "spreadsheet_id": args.espelho_id,
                    "abas": list(espelho.keys()),
                    "sessoes": len(hff["cirurgias"]["sessoes"]),
                    **diagnostico,
                }
                if not hff["cirurgias"]["sessoes"]:
                    warnings.append(
                        "Espelho HFF: nenhuma sessao na janela de "
                        f"{HFF_WINDOW_DAYS} dias "
                        f"({diagnostico.get('cirurgias_linhas_na_folha', 0)} linhas na folha, "
                        f"{diagnostico.get('cirurgias_linhas_na_janela', 0)} na janela). "
                        "Nao inventar cirurgias: a tab HFF fica com o aviso."
                    )
            except Exception as exc:
                fontes["espelho_hff"] = {"ok": False, "erro": f"{type(exc).__name__}: {exc}"}
                errors.append(f"Espelho HFF: {exc}")
        else:
            fontes["espelho_hff"] = {"ok": False, "erro": "sem servicos Google"}
    else:
        fontes["espelho_hff"] = {"ok": True, "ignorado": "Modo B nao tem tab HFF"}

    generated_at = agora.isoformat(timespec="seconds")
    draft = build_canonical_draft(target, mode, generated_at, calendario, todoist, weather, hff,
                                  fontes, warnings, errors)

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
            "email_por_seccao": {k: v.get("total", 0) for k, v in gmail_sections(email).items()},
            "email_conta": email.get("_conta"),
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
                "canonical_draft.diagnostico ja tem fontes/avisos/erros/tem_alertas prontos "
                "para a aba Diagnostico — nao e preciso copiar nada disto a mao",
            ],
            "o_que_falta_ao_llm": [
                "Classificar cada email em urgente/importante/informativo/ruido (dados crus em 'email')",
                "Escrever os 3 audio_script (um por dia da janela)",
                "Escrever hoje.dias[].alertas -- cada item e um objecto "
                "{\"nivel\": \"urgente\"|\"importante\"|\"info\", \"texto\": \"...\"}, nunca uma string simples",
                "Escrever sugestoes e as listas 'conferir' das 3 janelas de rotina",
                "Modo A: escrever hff.resumo.alertas (lista de frases curtas -- FDR, codigos "
                "ambiguos, duplicados; NUNCA ausencias, essas ja vem prontas em "
                "resumo.ausencias_relevantes) a partir dos factos em _diagnostico."
                "cirurgias_fdr_total/cirurgias_anomalias/sigic_anomalias",
                "Modo A: escrever hff.briefing_resumo e hff.briefing_cirurgias_resumo como frases "
                "curtas (strings) para a tab do Briefing, a partir do que ja esta em hff.resumo "
                "-- nunca copiar o dict tal e qual para estes dois campos",
                "Cruzar duplicados evento vs tarefa e resolver ambiguidades assinaladas em 'avisos'",
                "Preencher canonical_draft.diagnostico.notas_llm SO se tiver algo a assinalar que "
                "'fontes'/'avisos'/'erros' nao dizem (ex: uma inconsistencia que reparou nos dados) "
                "— texto curto, um item por nota; ficar vazio e o normal, nao inventar conteudo",
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
    # Formato real da coluna "Data Cirurgia" do Espelho: dia da semana + data
    check("parse_date com dia da semana", parse_date("qua., 28/10/26") == date(2026, 10, 28))
    check("parse_date com dia da semana 2", parse_date("seg., 03/08/26") == date(2026, 8, 3))
    check("parse_date com dia da semana 3", parse_date("qua., 16/09/26") == date(2026, 9, 16))
    check("parse_date ISO embebida", parse_date("Dia 2026-09-16 (quarta)") == date(2026, 9, 16))
    check("parse_date sem ano nao inventa", parse_date("vem de 09/09") is None)
    # Serial da folha de calculo, que a API entrega como TEXTO (abas Sigic e Prevencao)
    check("parse_date serial em texto", parse_date("46027") == date(2026, 1, 5))
    check("parse_date serial em texto 2", parse_date("45994") == date(2025, 12, 3))
    check("parse_date serial numerico", parse_date(46027) == date(2026, 1, 5))
    check("parse_date nao confunde n.o processo", parse_date("1119760") is None)
    check("parse_date nao confunde dia solto", parse_date("14") is None)
    # Formato REAL devolvido pela API do Sheets (valueRenderOption=FORMATTED_VALUE) para
    # as colunas de data das abas Sigic/Prevencao: dia + mes abreviado, SEM ano. Descoberto
    # so na 3a corrida real — o teste anterior validava contra o serial que se ve exportando
    # a folha para .xlsx, que e' outra coisa (o export ignora o formato da celula).
    check("parse_date dia/mes abreviado", parse_date("seg., 5/jan. ", default_year=2026) == date(2026, 1, 5))
    check("parse_date dia/mes abreviado 2", parse_date("qua., 16/set.", default_year=2026) == date(2026, 9, 16))
    check("parse_date dia/mes abreviado 3", parse_date("seg., 7/out. ", default_year=2026) == date(2026, 10, 7))
    check("parse_date dia/mes abreviado sem default_year", parse_date("seg., 5/jan. ") is None)
    check("parse_date dia/mes abreviado mes invalido", parse_date("5/xis.", default_year=2026) is None)
    check("parse_date dia impossivel", parse_date("qua., 32/13/26") is None)

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

    check("ausencia Mif (Madeira)", bool(ABSENCE_RE.match(compact_norm("Mif"))))
    check("ausencia Frc (Ferias)", bool(ABSENCE_RE.match(compact_norm("Frc"))))
    check("ausencia Crr (Curso)", bool(ABSENCE_RE.match(compact_norm("Crr"))))
    check("ausencia Bif (Baixa, esquema novo)", bool(ABSENCE_RE.match(compact_norm("Bif"))))
    check("Madeira continua M, nao E", MOTIVE_LABELS["M"] == "Madeira" and "E" not in MOTIVE_LABELS)
    check("folga *if", bool(DAY_OFF_RE.match(compact_norm("*if"))))
    check("ausencia invalida", not ABSENCE_RE.match(compact_norm("Xyz")))
    check("E sozinho nao e motivo valido", not ABSENCE_RE.match(compact_norm("Eif")))

    check("classify_calendar rafael", classify_calendar("Rafael correia") == "evento")
    check("classify_calendar feriados", classify_calendar("Feriados em Portugal") == "feriado")
    check("classify_calendar cirped", classify_calendar("cirped.ulsasi@gmail.com") == "profissional")
    check("flags sigic", "sigic" in detect_flags("Sigic tarde"))
    check("flags viagem", "viagem" in detect_flags("Flight to Lisbon (FR 9903)"))
    # Regressao real: um Meetup de volei em ingles vinha marcado como Prevencao do HFF
    check("flags prevencao com cedilha", "prevencao" in detect_flags("Semana de Prevencao"))
    check("flags prevencao acentuada", "prevencao" in detect_flags("Escala de Prevencao".replace("Prevencao", "Preven\u00e7\u00e3o")))
    check("flags NAO apanha 'prevent'", "prevencao" not in detect_flags("warm up to prevent injuries"))
    check("flags NAO apanha 'prevention'", "prevencao" not in detect_flags("Prevention of infection"))

    # Duplicados de calendario
    dup_items = [
        {"date": "2026-09-16", "inicio": "2026-09-16T17:30+01:00", "titulo": "Grass Volleyball", "event_id": "A"},
        {"date": "2026-09-16", "inicio": "2026-09-16T17:30+01:00", "titulo": "grass volleyball", "event_id": "B"},
        {"date": "2026-09-16", "inicio": "2026-09-16T18:00+01:00", "titulo": "Jantar", "event_id": "C"},
    ]
    grupos = mark_duplicates(dup_items)
    check("duplicados: 1 grupo", len(grupos) == 1)
    check("duplicados: marca o segundo", dup_items[1].get("duplicado_de") == "A")
    check("duplicados: nao marca o primeiro", "duplicado_de" not in dup_items[0])
    check("duplicados: nao marca o distinto", "duplicado_de" not in dup_items[2])

    # gmail_sections ignora metadados
    check("gmail_sections ignora _conta", set(gmail_sections(
        {"_conta": "x@y.pt", "inbox": {"total": 3}, "ulsasi": {"total": 0}}
    )) == {"inbox", "ulsasi"})
    check("etiqueta Events nunca lida",
          norm(GMAIL_FORBIDDEN_LABEL) not in {norm(v) for v in GMAIL_LABEL_SECTIONS.values()})
    check("Todoist aponta para a API v1", "/api/v1/" in TODOIST_API_URL)

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

    # Cabecalho e linhas tal como estao mesmo na folha (coluna 6 vazia incluida)
    reais = [
        [""] * 14,
        ["Data Cirurgia", "Periodo (Manha/Sigic (tarde))", "Processo", "Nome doente",
         "FDR (Fora da Rotina)", "", "Tempo em Lista de Espera", "Idade", "Procedimento",
         "Status Agendamento", "Observacao", "Previsao de IF estar ausente no dia",
         "Previsao de RC estar ausente no dia", "Previsao de RR estar ausente no dia"],
        ["qua., 16/09/26", "M", "1348132", "HELOISE VITORIA SANTOS ROCHA", "FALSE", "",
         "4,6", "1,0", "Seio E Quisto Pre-Auricular", "1 - Agendado", "", "FALSE", "FALSE", "TRUE"],
        ["qua., 16/09/26", "M", "1355984", "SANJAYA SAPKOTA", "FALSE", "",
         "5,8", "", "Hernia Inguinal Bilat", "1 - Agendado", "", "FALSE", "FALSE", "TRUE"],
        ["qua., 16/09/26", "M", "1256562", "Aquiles Otchaly Candeia Pinto Andrade", "FALSE", "",
         "", "126,8", "", "7 - Planeado", "", "FALSE", "FALSE", "FALSE"],
        ["seg., 03/08/26", "S", "1074935", "RODRIGO MIGUEL AMARAL CASTRO", "TRUE", "",
         "3,8", "126,7", "Fimose", "1 - Agendado", "a confirmar", "FALSE", "FALSE", "FALSE"],
    ]
    w2: list[str] = []
    e2: list[str] = []
    real = parse_cirurgias(reais, date(2026, 9, 16), w2, e2)
    check("espelho real: cabecalho reconhecido", real["ok"] is True)
    check("espelho real: 1 sessao na janela", len(real["sessoes"]) == 1)
    check("espelho real: 3 doentes", real["sessoes"][0]["n_doentes"] == 3)
    check("espelho real: ignora a cirurgia passada", all(s["date"] >= "2026-09-16" for s in real["sessoes"]))
    check("espelho real: idade 126 anos vira sem dados",
          any(a["tipo"] == "idade_implausivel" for a in real["anomalias"]))
    check("espelho real: idade implausivel nao e impressa",
          all(d["idade_fmt"] != "126,8a" for d in real["sessoes"][0]["doentes"]))
    check("espelho real: idade valida sobrevive",
          any(d["idade_fmt"] == "1,0a" for d in real["sessoes"][0]["doentes"]))
    check("espelho real: quarta e dia de BO",
          not any(a["tipo"] == "bo_em_dia_invalido" for a in real["anomalias"]))

    # Grelha com a forma REAL da aba Ausencias: calendario anual, o dia por cima do
    # codigo na mesma coluna, e o nome do mes varias linhas acima.
    grid = [
        ["CALENDARIO 2026"],
        [],
        ["", "SETEMBRO"],
        ["", "D", "S", "T", "Q", "Q", "S", "S"],
        ["", "", "", "1", "2", "3", "4", "5"],
        ["", "", "", "Mif", "", "", "", ""],
        ["", "6", "7", "8", "9", "10", "11", "12"],
        ["", "", "*rc", "", "", "", "", ""],
        ["", "13", "14", "15", "16", "17", "18", "19"],
        ["", "", "", "", "F", "", "", ""],
        ["", "20", "21", "22", "23", "24", "25", "26"],
        ["", "", "Frr", "", "", "", "", ""],
    ]
    check("grid_year le o titulo", grid_year(grid, 1999) == 2026)
    ausencias = parse_ausencias(grid, date(2026, 9, 1))
    datas = {a["data"] for a in ausencias["ausencias"]}
    check("ausencias 2 confirmadas", len(ausencias["ausencias"]) == 2)
    check("ausencias motivo Madeira", ausencias["ausencias"][0]["motivo"] == "Madeira")
    check("ausencias 1a semana datada", "2026-09-01" in datas)
    # A regressao que interessa: antes, um codigo 9 linhas abaixo do nome do mes
    # ficava sem data (75 dos 83 codigos da folha real).
    check("ausencias 4a semana datada", "2026-09-21" in datas)
    check("folgas 1", len(ausencias["folgas"]) == 1)
    check("folga datada", ausencias["folgas"][0]["data"] == "2026-09-07")
    check("codigo sem iniciais fica ambiguo", len(ausencias["codigos_ambiguos"]) == 1)
    check("codigo ambiguo tem data", ausencias["codigos_ambiguos"][0].get("data") == "2026-09-16")
    check("nenhum codigo sem data", len(ausencias["codigos_sem_data"]) == 0)

    # SIGIC: rotulo do mes que nao bate com a data e erro de dados, nao de leitura
    sigic_rows = [
        ["MES", "DIA de Sigic", "Cirurgiao1", "Cirurgiao2"],
        ["Setembro", "46283", "Rafael", "Rodrigo"],          # 2026-09-18, coerente
        ["Outubro", "45931", "Isabel", "Afonso"],            # 2025-10-01, ano errado
    ]
    e_sig: list[str] = []
    sig = parse_sigic(sigic_rows, date(2026, 9, 16), e_sig)
    check("sigic le serial em texto", len(sig["listas"]) == 1)
    check("sigic data certa", sig["listas"][0]["date"] == "2026-09-18")
    check("sigic assinala ano incoerente",
          any(a["tipo"].startswith("sigic_") for a in sig["anomalias"]))
    check("sigic sugere a correccao",
          any(a.get("sugestao", "").startswith("2026-") for a in sig["anomalias"]))

    draft = build_canonical_draft(
        date(2026, 9, 14), "B", "2026-09-14T08:00:00+01:00",
        {"itens": [{"date": "2026-09-14", "titulo": "Sigic", "tipo": "evento", "calendario": "Rafael correia",
                    "inicio": "2026-09-14T15:30+01:00", "fim": None, "dia_inteiro": False, "local": None,
                    "flags": ["sigic"], "event_id": "x"}]},
        {"itens": [{"date": "2026-09-14", "texto": "Forxiga", "prioridade": "baixa", "classificacao": "pessoal"}]},
        None, None,
        {"calendario": {"ok": True}, "todoist": {"ok": True}}, [], [],
    )
    check("draft 3 dias hoje", len(draft["hoje"]["dias"]) == 3)
    check("draft 3 dias rotina", len(draft["rotina"]["dias"]) == 3)
    check("draft 15 dias calendario", len(draft["calendario"]["dias"]) == CALENDAR_WINDOW_DAYS)
    check("draft hff null em modo B", draft["hff"] is None)
    check("draft sigic_shift", draft["rotina"]["dias"][0]["sigic_shift"] is True)
    check("draft badge sigic", "sigic" in draft["calendario"]["dias"][0]["badges"])
    check("draft habito segunda", draft["tarefas"]["cards"][0]["extras"][0]["texto"].startswith("Leitura"))

    # diagnostico: sem erros/avisos e todas as fontes ok -> sem alerta
    check("diagnostico sem alertas quando tudo ok", draft["diagnostico"]["tem_alertas"] is False)
    check("diagnostico notas_llm comeca vazio", draft["diagnostico"]["notas_llm"] == [])
    draft_com_erro = build_canonical_draft(
        date(2026, 9, 14), "B", "2026-09-14T08:00:00+01:00",
        {"itens": []}, {"itens": []}, None, None,
        {"gmail": {"ok": False, "erro": "403"}}, ["aviso de teste"], [],
    )
    check("diagnostico com alerta quando uma fonte falha", draft_com_erro["diagnostico"]["tem_alertas"] is True)
    check("diagnostico guarda os avisos", draft_com_erro["diagnostico"]["avisos"] == ["aviso de teste"])

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
