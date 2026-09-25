#!/usr/bin/env python3
"""CIRPED preflight (local, mechanical only): reads Espelho_Cirped, applies the
independent history/charada gating, and writes a manifest for the LLM to act on.
Never decides content -- only what needs to be generated and what must not repeat."""

from __future__ import annotations

import json
import argparse
from datetime import datetime, date
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

SPREADSHEET_ID = "1svP-Vydd1oJ_gHxG5UnGS8MrhELvWIXeDqpgeJ4MJs4"
TOKEN_PATH = r"G:\My Drive\Claude_PRJ\token.json"
FRESHNESS_DAYS = 2  # gera de novo se a ultima geracao (de uma trilha ja decidida) tiver mais dias que isto


def read_tab(service, tab: str) -> list[dict]:
    result = service.spreadsheets().values().get(
        spreadsheetId=SPREADSHEET_ID, range=f"{tab}!A1:Z10000"
    ).execute()
    rows = result.get("values", [])
    if not rows:
        return []
    headers = rows[0]
    return [dict(zip(headers, row + [""] * (len(headers) - len(row)))) for row in rows[1:]]


def parse_bool(value: object) -> bool:
    return str(value).strip().upper() == "TRUE"


def days_since(iso_date: str) -> int | None:
    try:
        d = datetime.fromisoformat(iso_date[:19]).date()
        return (date.today() - d).days
    except Exception:
        return None


def evaluate_tab(rows: list[dict], key_col: str) -> dict:
    # "por decidir" = nem lido nem guardado ainda -- os dois campos sao independentes,
    # basta um dos dois ser TRUE para o item contar como "decidido" e libertar a trilha.
    pending = [r for r in rows if not parse_bool(r.get("lido")) and not parse_bool(r.get("guardado"))]
    used = sorted({r[key_col] for r in rows if r.get(key_col)})
    if pending:
        return {"needs_new": False, "pending": pending[0], "used": used, "reason": "item por decidir (lido=FALSE e guardado=FALSE)"}

    latest = max((r.get("data_geracao", "") for r in rows), default="")
    aged = days_since(latest)
    if latest and aged is not None and aged < FRESHNESS_DAYS:
        return {"needs_new": False, "pending": None, "used": used,
                "reason": f"ultima geracao ha {aged} dia(s), dentro da janela de {FRESHNESS_DAYS}"}

    return {"needs_new": True, "pending": None, "used": used, "reason": "livre para gerar"}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path(f"cirped_manifest_{date.today().isoformat()}.json"))
    args = parser.parse_args()

    # Keep the scope granted in the token; overriding it during refresh causes invalid_scope.
    creds = Credentials.from_authorized_user_file(TOKEN_PATH)
    granted = set(creds.scopes or [])
    if not granted.intersection({
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/spreadsheets.readonly",
    }):
        raise RuntimeError("O token nao tem acesso ao Google Sheets; reautorize-o.")
    if not creds.valid:
        creds.refresh(Request())
        Path(TOKEN_PATH).write_text(creds.to_json(), encoding="utf-8")
    service = build("sheets", "v4", credentials=creds)

    historias = read_tab(service, "Historias")
    charadas = read_tab(service, "Charadas")

    manifest = {
        "checked_at": datetime.now().isoformat(timespec="minutes"),
        "historia": evaluate_tab(historias, "angulo_especifico"),
        "charada": evaluate_tab(charadas, "pergunta"),
    }

    out = args.output
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Manifesto escrito em {out}")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
