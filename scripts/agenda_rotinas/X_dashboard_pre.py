#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
X_dashboard_pre.py — Recolha mecanica do Dashboard (Modulo 5) + pre-filtro de acao
====================================================================================

O que este ficheiro e
----------------------
A rotina "pre" do Dashboard, no mesmo espirito de X_briefing_pre.py: faz o trabalho
mecanico fora do LLM e grava um unico JSON em "G:/My Drive/Claude_PRJ/Agenda/X_Outputs"
com o nome AAAA_MM_DD_HHMM_dashboard.json.

Duas responsabilidades:

1. **Dados do hub** (contagens + tempo) — lidos do "_briefing.json" mais recente
   (produzido pela corrida separada e independente de X_briefing_pre.py, ja agendada
   as 06:00) em vez de repetir a leitura de Calendar/Todoist: reaproveita
   "calendario.itens" e "tarefas_todoist.itens" filtrando pela data de HOJE (nao pela
   DATA_ALVO do briefing, que pode ja ter rolado para o proximo dia util apos as 16h —
   o Dashboard mostra sempre o dia real). O tempo (08h/16h/20h) e pedido de novo aqui,
   directamente ao Open-Meteo, porque os "horas_chave" do briefing usam outros
   horarios (08:00/13:00/16:30/21:00) que nao coincidem com os 3 periodos do template
   do Dashboard.

2. **Pre-filtro de accao** para TestMe / CIRPED / Artigos — o pedido do Rafa: antes de
   o LLM ler a rotina inteira de qualquer um destes tres modulos, este script decide
   mecanicamente se ha alguma coisa por fazer. Se `needs_action` vier False para um
   modulo, o LLM nao deve ler a respectiva rotina nessa corrida — poupa a leitura
   completa de TESTME.md / INSTRUCOES_CIRPED.md / INSTRUCOES_ARTIGOS quando nada mudou
   desde a ultima corrida.

   - Artigos: mecanico e directo — compara a data do ultimo commit git que tocou
     `agendas/artigos/index.html` contra a janela de 7 dias (mesma regra ja descrita
     em INSTRUCOES_DASHBOARD). Nao le nenhum Sheet.
   - CIRPED: chama `preflight_cirped.py` (ja existe, mesma pasta X_Rotinas_Python,
     ver INSTRUCOES_CIRPED.md Seccao 3/4) como subprocesso e le o manifesto que ele
     produz — reaproveita o gating oficial em vez de o duplicar aqui.
   - TestMe: HEURISTICA NOVA, proposta nesta sessao, ainda por confirmar com o Rafa
     (TESTME.md nao define um "preflight" de frescura — descreve so o que a rotina
     `Atualizar TestMe` faz quando corre). Le `Espelho_testme` e considera que ha
     accao se: (a) a aba `simulado_atual` tiver `status = terminado` (simulado por
     corrigir), ou (b) `acoes_pergunta` tiver alguma linha mais recente do que a
     ultima entrada de `runs_log` (o Rafa interagiu com a pergunta actual desde a
     ultima corrida). Falhar a favor de correr a rotina (needs_action=True) sempre
     que a leitura do Sheet falhar ou os campos nao existirem, nunca ao contrario —
     nunca "esconder" trabalho pendente por um erro de leitura.

Principio (igual a X_briefing_pre.py): zero julgamento. Nunca decide o que e
importante, nunca escreve texto para o Rafa. Se uma fonte falhar, grava o erro e
marca needs_action=True para essa trilha (falha nunca deve silenciar trabalho real).

Uso
---
    python3 X_dashboard_pre.py                # dia real
    python3 X_dashboard_pre.py --target-date 2026-09-22
    python3 X_dashboard_pre.py --self-test     # testa a logica pura, sem rede

Credenciais
-----------
Mesmas do resto da Agenda: PROJECT_ROOT/credentials.json + PROJECT_ROOT/token_agenda.json
(scope spreadsheets.readonly, ja coberto pelas rotinas existentes).
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

SCHEMA_VERSION = "1.0"
ROTINA = "dashboard"
TZ = ZoneInfo("Europe/Lisbon")

PROJECT_ROOT = Path(r"G:\My Drive\Claude_PRJ")
AGENDA_ROOT = PROJECT_ROOT / "Agenda"
DEFAULT_OUT_DIR = AGENDA_ROOT / "X_Outputs"
CIRPED_PREFLIGHT = AGENDA_ROOT / "X_Rotinas_Python" / "cirped" / "preflight_cirped.py"

# Checkout fora do Drive de proposito -- mesma razao das outras rotinas locais desta
# sessao (checkout git dentro da pasta sincronizada do Drive corrompe-se).
REPO_DIR = Path(r"C:\Users\rafai\Documents\github\personal-system")
ARTIGOS_PUBLISHED_PATH = REPO_DIR / "agendas" / "artigos" / "index.html"

ARTIGOS_FRESHNESS_DAYS = 7
TESTME_ESPELHO_ID = "1umzy0T45iQlN2Fv52OV73PzRpWmgF5GWHUUMBO0Y7wo"

OUT_SUFFIX = "_dashboard.json"
BRIEFING_SUFFIX = "_briefing.json"
BRIEFING_FINAL_SUFFIX = "_final_briefing.json"

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
DASHBOARD_WEATHER_SLOTS = ("08:00", "16:00", "20:00")


def now_lisbon() -> datetime:
    return datetime.now(TZ)


def norm(value: Any) -> str:
    text = "" if value is None else str(value)
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return " ".join(text.strip().lower().split())


def http_get_json(url: str, timeout: int = 20) -> Any:
    req = urllib.request.Request(url, headers={"User-Agent": "agenda-dashboard-pre/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def icon_for(code: Any) -> str:
    try:
        return WEATHERCODE_ICON.get(int(code), "indefinido")
    except (TypeError, ValueError):
        return "indefinido"


# ======================================================================================
# 1. Tempo (Open-Meteo, sem chave, 3 periodos proprios do template do Dashboard)
# ======================================================================================
def collect_weather_slots(errors: list[str]) -> dict[str, Any] | None:
    url = (
        "https://api.open-meteo.com/v1/forecast"
        f"?latitude={LAT}&longitude={LON}"
        "&hourly=temperature_2m,weathercode"
        "&timezone=" + urllib.parse.quote("Europe/Lisbon") +
        "&forecast_days=2"
    )
    try:
        raw = http_get_json(url)
    except (urllib.error.URLError, TimeoutError, ValueError) as exc:
        errors.append(f"tempo: {type(exc).__name__}: {exc}")
        return None

    hourly = raw.get("hourly") or {}
    times = hourly.get("time") or []
    if not times:
        errors.append("tempo: resposta da Open-Meteo sem 'hourly.time'")
        return None

    today_str = now_lisbon().date().isoformat()
    slots: dict[str, Any] = {}
    for hhmm in DASHBOARD_WEATHER_SLOTS:
        prefix = f"{today_str}T{hhmm[:2]}"
        idx = next((i for i, t in enumerate(times) if t.startswith(prefix)), None)
        key = f"{hhmm[:2]}h"
        if idx is None:
            slots[key] = None
            continue
        slots[key] = {
            "icon": icon_for(hourly["weathercode"][idx]),
            "temp": round(hourly["temperature_2m"][idx]),
        }
    return slots


# ======================================================================================
# 2. Contagens (reaproveita o "_briefing.json" mais recente, nao repete leitura)
# ======================================================================================
def find_latest_briefing_pre(out_dir: Path) -> Path | None:
    """O mais recente que termine em _briefing.json mas NAO em _final_briefing.json
    (esse ultimo e o output do passo LLM do Briefing, nao o pre mecanico)."""
    candidates = [
        p for p in out_dir.glob(f"*{BRIEFING_SUFFIX}")
        if not p.name.endswith(BRIEFING_FINAL_SUFFIX)
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda p: p.stat().st_mtime)


def counts_from_briefing_pre(briefing_pre: dict[str, Any], today: date, warnings: list[str]) -> dict[str, int]:
    today_str = today.isoformat()

    calendario_itens = (briefing_pre.get("calendario") or {}).get("itens") or []
    events_today = sum(1 for item in calendario_itens if item.get("date") == today_str)

    todoist_itens = (briefing_pre.get("tarefas_todoist") or {}).get("itens") or []
    tasks_pending = sum(
        1 for item in todoist_itens
        if item.get("date") == today_str or item.get("atrasada")
    )

    briefing_data_alvo = ((briefing_pre.get("modo") or {}).get("data_alvo"))
    if briefing_data_alvo and briefing_data_alvo != today_str:
        warnings.append(
            f"_briefing.json mais recente tem data_alvo={briefing_data_alvo}, "
            f"diferente de hoje ({today_str}) — contagens filtradas pela data real de hoje, "
            "nao pela data_alvo do briefing (pode ja ter rolado para o Modo C apos as 16h)."
        )
    return {"events_today": events_today, "tasks_pending": tasks_pending}


# ======================================================================================
# 3. Artigos — mecanico, via data do ultimo commit git que tocou a pagina publicada
# ======================================================================================
def artigos_needs_action(today: date, warnings: list[str], errors: list[str]) -> dict[str, Any]:
    if not ARTIGOS_PUBLISHED_PATH.exists():
        errors.append(f"artigos: pagina publicada nao encontrada em {ARTIGOS_PUBLISHED_PATH}")
        return {"needs_action": True, "razao": "pagina publicada nao encontrada — a corrigir a favor de accao"}

    try:
        result = subprocess.run(
            ["git", "log", "-1", "--format=%cI", "--", str(ARTIGOS_PUBLISHED_PATH)],
            cwd=str(REPO_DIR), capture_output=True, text=True, timeout=20, check=True,
        )
    except (subprocess.SubprocessError, OSError) as exc:
        errors.append(f"artigos: git log falhou ({exc})")
        return {"needs_action": True, "razao": f"git log falhou: {exc}"}

    stamp = result.stdout.strip()
    if not stamp:
        warnings.append("artigos: git log nao devolveu data (ficheiro talvez nunca commitado)")
        return {"needs_action": True, "razao": "sem historico git para a pagina publicada"}

    last_publish = datetime.fromisoformat(stamp).astimezone(TZ).date()
    dias = (today - last_publish).days
    needs = dias > ARTIGOS_FRESHNESS_DAYS
    return {
        "needs_action": needs,
        "ultima_publicacao": last_publish.isoformat(),
        "dias_desde_publicacao": dias,
        "janela_dias": ARTIGOS_FRESHNESS_DAYS,
    }


# ======================================================================================
# 4. CIRPED — reaproveita preflight_cirped.py (nao duplica o gating oficial)
# ======================================================================================
def cirped_needs_action(today: date, out_dir: Path, warnings: list[str], errors: list[str]) -> dict[str, Any]:
    if not CIRPED_PREFLIGHT.exists():
        warnings.append(f"cirped: preflight_cirped.py nao encontrado em {CIRPED_PREFLIGHT}")
        return {"needs_action": True, "razao": "preflight_cirped.py em falta — a corrigir a favor de accao"}

    try:
        result = subprocess.run(
            [sys.executable, str(CIRPED_PREFLIGHT)],
            cwd=str(CIRPED_PREFLIGHT.parent), capture_output=True, text=True, timeout=60, check=True,
        )
    except (subprocess.SubprocessError, OSError) as exc:
        errors.append(f"cirped: preflight_cirped.py falhou ({exc})")
        return {"needs_action": True, "razao": f"preflight_cirped.py falhou: {exc}"}

    manifest_path = out_dir / f"cirped_manifest_{today.isoformat()}.json"
    if not manifest_path.exists():
        # Nome pode variar; tenta o manifesto mais recente na pasta como fallback.
        candidates = sorted(out_dir.glob("cirped_manifest_*.json"), key=lambda p: p.stat().st_mtime)
        manifest_path = candidates[-1] if candidates else None

    if not manifest_path or not manifest_path.exists():
        warnings.append("cirped: preflight correu mas nao encontrei o manifesto gerado")
        return {"needs_action": True, "razao": "manifesto do preflight nao encontrado apos correr"}

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"cirped: manifesto ilegivel ({exc})")
        return {"needs_action": True, "razao": f"manifesto ilegivel: {exc}"}

    needs_historia = bool(manifest.get("historia", {}).get("needs_new"))
    needs_charada = bool(manifest.get("charada", {}).get("needs_new"))
    return {
        "needs_action": needs_historia or needs_charada,
        "needs_new_historia": needs_historia,
        "needs_new_charada": needs_charada,
        "manifesto": str(manifest_path),
    }


# ======================================================================================
# 5. TestMe — HEURISTICA NOVA (ver docstring), le Espelho_testme via Sheets API
# ======================================================================================
def testme_needs_action(warnings: list[str], errors: list[str]) -> dict[str, Any]:
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build
    except ImportError as exc:
        errors.append(f"testme: bibliotecas Google em falta ({exc})")
        return {"needs_action": True, "razao": f"bibliotecas Google em falta: {exc}"}

    token_path = PROJECT_ROOT / "token_agenda.json"
    creds_path = PROJECT_ROOT / "credentials.json"
    scopes = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
    if not token_path.exists():
        errors.append(f"testme: {token_path} nao encontrado")
        return {"needs_action": True, "razao": "token_agenda.json em falta"}

    try:
        creds = Credentials.from_authorized_user_file(str(token_path), scopes)
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
        service = build("sheets", "v4", credentials=creds, cache_discovery=False)

        def read_tab(tab: str) -> list[list[Any]]:
            resp = service.spreadsheets().values().get(
                spreadsheetId=TESTME_ESPELHO_ID, range=f"'{tab}'!A1:Z200",
            ).execute()
            return resp.get("values", [])

        simulado_rows = read_tab("simulado_atual")
        acoes_rows = read_tab("acoes_pergunta")
        runs_rows = read_tab("runs_log")
    except Exception as exc:  # noqa: BLE001 — qualquer falha aqui deve cair a favor de accao
        errors.append(f"testme: leitura de Espelho_testme falhou ({exc})")
        return {"needs_action": True, "razao": f"leitura da Sheet falhou: {type(exc).__name__}: {exc}"}

    def col_index(rows: list[list[Any]], name: str) -> int | None:
        if not rows:
            return None
        header = [norm(c) for c in rows[0]]
        return header.index(norm(name)) if norm(name) in header else None

    def last_timestamp(rows: list[list[Any]], col_names: tuple[str, ...]) -> str | None:
        if len(rows) < 2:
            return None
        for name in col_names:
            idx = col_index(rows, name)
            if idx is None:
                continue
            values = [r[idx] for r in rows[1:] if len(r) > idx and r[idx]]
            if values:
                return max(values)
        return None

    status_idx = col_index(simulado_rows, "status")
    simulado_status = None
    if status_idx is not None and len(simulado_rows) > 1:
        row = simulado_rows[1]
        simulado_status = row[status_idx] if len(row) > status_idx else None
    simulado_terminado = norm(simulado_status) == "terminado"

    last_action_ts = last_timestamp(acoes_rows, ("timestamp", "data", "quando"))
    last_run_ts = last_timestamp(runs_rows, ("timestamp", "data", "quando"))

    action_since_last_run = False
    if last_action_ts and (not last_run_ts or last_action_ts > last_run_ts):
        action_since_last_run = True
    elif not last_run_ts and last_action_ts:
        action_since_last_run = True
    elif not runs_rows or len(runs_rows) < 2:
        # Nunca correu antes nesta Sheet — falhar a favor de correr pelo menos uma vez.
        action_since_last_run = True

    needs = simulado_terminado or action_since_last_run
    return {
        "needs_action": needs,
        "simulado_status": simulado_status,
        "simulado_terminado": simulado_terminado,
        "accao_desde_ultima_corrida": action_since_last_run,
        "nota": (
            "heuristica nova desta sessao, TESTME.md nao define um preflight de frescura — "
            "confirmar com o Rafa se o criterio (simulado terminado OU accao na pergunta atual "
            "desde a ultima corrida registada em runs_log) esta correcto."
        ),
    }


# ======================================================================================
# Main
# ======================================================================================
def build_payload(target: date, out_dir: Path) -> dict[str, Any]:
    warnings: list[str] = []
    errors: list[str] = []

    weather = collect_weather_slots(errors)

    briefing_pre_path = find_latest_briefing_pre(out_dir)
    counts = {"events_today": None, "tasks_pending": None}
    if briefing_pre_path is None:
        errors.append(f"nenhum *{BRIEFING_SUFFIX} encontrado em {out_dir} — contagens indisponiveis")
    else:
        try:
            briefing_pre = json.loads(briefing_pre_path.read_text(encoding="utf-8"))
            counts = counts_from_briefing_pre(briefing_pre, target, warnings)
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"nao consegui ler {briefing_pre_path} ({exc})")

    artigos = artigos_needs_action(target, warnings, errors)
    cirped = cirped_needs_action(target, out_dir, warnings, errors)
    testme = testme_needs_action(warnings, errors)

    return {
        "schema_version": SCHEMA_VERSION,
        "rotina": ROTINA,
        "gerado_em": now_lisbon().isoformat(timespec="seconds"),
        "data_alvo": target.isoformat(),
        "briefing_pre_usado": str(briefing_pre_path) if briefing_pre_path else None,
        "counts": counts,
        "weather": weather,
        "pre_filtro": {
            "artigos": artigos,
            "cirped": cirped,
            "testme": testme,
        },
        "avisos": warnings,
        "erros": errors,
    }


def cleanup_previous(out_dir: Path, keep: Path) -> list[str]:
    removed = []
    for path in sorted(out_dir.glob(f"*{OUT_SUFFIX}")):
        if path != keep:
            path.unlink(missing_ok=True)
            removed.append(path.name)
    return removed


def self_test() -> int:
    ok_count = 0
    fail_count = 0

    def check(label: str, condition: bool) -> None:
        nonlocal ok_count, fail_count
        if condition:
            ok_count += 1
        else:
            fail_count += 1
            print(f"FALHOU: {label}")

    warnings: list[str] = []
    briefing_pre_sample = {
        "modo": {"data_alvo": "2026-09-22"},
        "calendario": {"itens": [
            {"date": "2026-09-22", "titulo": "A"},
            {"date": "2026-09-23", "titulo": "B"},
        ]},
        "tarefas_todoist": {"itens": [
            {"date": "2026-09-22", "atrasada": False},
            {"date": "2026-09-20", "atrasada": True},
            {"date": "2026-09-25", "atrasada": False},
        ]},
    }
    counts = counts_from_briefing_pre(briefing_pre_sample, date(2026, 9, 22), warnings)
    check("events_today conta so hoje", counts["events_today"] == 1)
    check("tasks_pending conta hoje + atrasadas", counts["tasks_pending"] == 2)

    print(f"\n{ok_count} passaram, {fail_count} falharam.")
    return 0 if fail_count == 0 else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target-date", help="AAAA-MM-DD; por omissao, hoje (Lisboa)")
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        return self_test()

    target = date.fromisoformat(args.target_date) if args.target_date else now_lisbon().date()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    payload = build_payload(target, out_dir)

    stamp = now_lisbon().strftime("%Y_%m_%d_%H%M")
    out_path = out_dir / f"{stamp}{OUT_SUFFIX}"
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    removed = cleanup_previous(out_dir, keep=out_path)

    print(f"OK: dashboard pre gravado -> {out_path}")
    if removed:
        print(f"    limpos {len(removed)} ficheiro(s) *{OUT_SUFFIX} anteriores")
    if payload["erros"]:
        print(f"    {len(payload['erros'])} erro(s):")
        for e in payload["erros"]:
            print(f"      - {e}")
    if payload["avisos"]:
        print(f"    {len(payload['avisos'])} aviso(s):")
        for w in payload["avisos"]:
            print(f"      - {w}")
    pf = payload["pre_filtro"]
    print(
        "    pre-filtro: artigos="
        f"{pf['artigos'].get('needs_action')}, cirped={pf['cirped'].get('needs_action')}, "
        f"testme={pf['testme'].get('needs_action')}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
