"""Exporta a Espelho Radar (Google Sheets, aba "Main") via API do Sheets.

Roda 100% local (fora do Claude, sem consumir tokens). Le a aba "Main" da
planilha Espelho Radar e devolve/grava um JSON estruturado ja separado em
Carteira e Vigiar pela linha-marcador "vigiar" - ver AII_Z_Noticias_do_dia.md,
Etapa 1A/Etapa 0, Leitura 2.

Autenticacao: OAuth "installed app" via credentials.json + token.json
(token.json ja contem client_id/client_secret/refresh_token, por isso
credentials.json so e necessario se for preciso refazer o consentimento
interativo do zero - o fluxo normal so usa o token.json para refrescar).
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

SPREADSHEET_ID = "1g7JBnpEkaYZQl2SBGYmooZhOBYqOa0ER2o3F1yPkSnA"
RANGE_NAME = "Main"
SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]

# Ajustar se a pasta SSOT estiver noutro caminho.
DEFAULT_SSOT_DIR = Path(r"G:\My Drive\Claude_PRJ\SSOT")
DEFAULT_CREDENTIALS_PATH = DEFAULT_SSOT_DIR / "credentials.json"
DEFAULT_TOKEN_PATH = DEFAULT_SSOT_DIR / "token.json"

# Deteccao tolerante da linha-marcador: a rotina ja viu variacoes de
# formatacao ("------vigiar - - - - -", "----------- VIGIAR - - - - - - - - - -")
# entre execucoes, por isso procuramos so a palavra "vigiar", case-insensitive,
# nunca o traco exacto.
MARKER_RE = re.compile(r"vigiar", re.IGNORECASE)


class EspelhoRadarError(Exception):
    pass


def load_credentials(credentials_path: Path, token_path: Path) -> Credentials:
    if not token_path.exists():
        raise EspelhoRadarError(
            f"token.json nao encontrado: {token_path}. Corre o fluxo de consentimento "
            f"interativo primeiro (fora deste script) para o gerar."
        )
    creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        # Persistir o access_token renovado para a proxima execucao nao ter
        # de refrescar de novo antes do tempo.
        token_path.write_text(creds.to_json(), encoding="utf-8")
    return creds


def fetch_main_tab(creds: Credentials, spreadsheet_id: str, range_name: str) -> list[list[Any]]:
    service = build("sheets", "v4", credentials=creds)
    result = (
        service.spreadsheets()
        .values()
        .get(spreadsheetId=spreadsheet_id, range=range_name)
        .execute()
    )
    return result.get("values", [])


def find_marker_row(rows: list[list[Any]]) -> int | None:
    for idx, row in enumerate(rows):
        joined = " ".join(str(cell) for cell in row)
        if MARKER_RE.search(joined):
            return idx
    return None


def rows_to_dicts(header: list[Any], rows: list[list[Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in rows:
        if not any(str(cell).strip() for cell in row):
            continue
        item: dict[str, Any] = {}
        for i, key in enumerate(header):
            key_str = str(key).strip() or f"col_{i}"
            item[key_str] = row[i] if i < len(row) else ""
        out.append(item)
    return out


def build_snapshot(
    credentials_path: Path,
    token_path: Path,
    spreadsheet_id: str,
    range_name: str,
) -> dict[str, Any]:
    creds = load_credentials(credentials_path, token_path)
    rows = fetch_main_tab(creds, spreadsheet_id, range_name)

    if not rows:
        raise EspelhoRadarError("Nenhuma linha devolvida pela API para o range pedido.")

    header = rows[0]
    body = rows[1:]
    marker_idx = find_marker_row(body)

    if marker_idx is None:
        carteira_rows, vigiar_rows, marker_found = body, [], False
    else:
        carteira_rows = body[:marker_idx]
        vigiar_rows = body[marker_idx + 1 :]
        marker_found = True

    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "spreadsheet_id": spreadsheet_id,
        "range": range_name,
        "marker_found": marker_found,
        "header": header,
        "carteira": rows_to_dicts(header, carteira_rows),
        "vigiar": rows_to_dicts(header, vigiar_rows),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Exporta Carteira/Vigiar da Espelho Radar (Sheets API).")
    parser.add_argument("--credentials", default=str(DEFAULT_CREDENTIALS_PATH), help="Caminho de credentials.json.")
    parser.add_argument("--token", default=str(DEFAULT_TOKEN_PATH), help="Caminho de token.json.")
    parser.add_argument("--spreadsheet-id", default=SPREADSHEET_ID, help="ID da planilha Espelho Radar.")
    parser.add_argument("--range", default=RANGE_NAME, help='Range/aba a ler (default: "Main").')
    parser.add_argument("--out", help="Caminho do JSON de saida; sem isto, imprime em stdout.")
    args = parser.parse_args()

    try:
        snapshot = build_snapshot(
            Path(args.credentials), Path(args.token), args.spreadsheet_id, args.range
        )
    except EspelhoRadarError as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False))
        return 1

    payload = json.dumps(snapshot, ensure_ascii=False, indent=2)
    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(payload, encoding="utf-8", newline="\n")
        print(
            json.dumps(
                {
                    "status": "ok",
                    "out": str(out_path),
                    "marker_found": snapshot["marker_found"],
                    "carteira_rows": len(snapshot["carteira"]),
                    "vigiar_rows": len(snapshot["vigiar"]),
                },
                ensure_ascii=False,
            )
        )
    else:
        print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
