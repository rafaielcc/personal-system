"""Exporta a Espelho Radar (Google Sheets, aba "Main") via API do Sheets.

Roda 100% local (fora do Claude, sem consumir tokens). Le a aba "Main" da
planilha Espelho Radar e devolve/grava um JSON estruturado ja separado em
Carteira e Vigiar - ver AII_Z_Noticias_do_dia.md, Etapa 1A/Etapa 0, Leitura 2.

Estrutura real da folha (confirmada 18/ago/2026 via --raw):
- Uma linha-marcador de secao com UMA UNICA celula nao vazia ("----------- CARTEIRA ... -----------",
  depois mais abaixo "----------- VIGIAR ... -----------").
- Logo a seguir a cada marcador, 1 ou mais linhas de cabecalho (a Carteira tem
  o cabecalho partido em 2 linhas, ex.: "DPA"+"estimado" = "DPA estimado"; a
  Vigiar tem so 1 linha de cabecalho) - o numero de linhas de cabecalho NAO e
  fixo, por isso deteccao dinamica: a primeira linha que contem um ticker
  (padrao B3 generico, 4 letras + 1-2 digitos) e a primeira linha de dados;
  tudo antes disso, desde o marcador, e cabecalho a fundir.
- Linhas em branco podem aparecer tanto entre seccoes como DENTRO da seccao
  Vigiar (separadores visuais entre grupos sectoriais) - sao sempre
  ignoradas, nunca tratadas como fim de seccao.

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

# Pasta SSOT do Rafa = a raiz do projecto (confirmado 18/ago/2026), nao uma
# subpasta "SSOT". Ajustar aqui se um dia mudar.
DEFAULT_SSOT_DIR = Path(r"G:\My Drive\Claude_PRJ")
DEFAULT_CREDENTIALS_PATH = DEFAULT_SSOT_DIR / "credentials.json"
DEFAULT_TOKEN_PATH = DEFAULT_SSOT_DIR / "token.json"

# Uma linha-marcador de seccao tem EXACTAMENTE uma celula nao vazia contendo
# a palavra-chave (nunca uma linha de cabeçalho normal que so mencione a
# palavra numa das varias colunas - essa distincao e o que causava o falso
# positivo da versao anterior, que apanhava uma coluna qualquer com "vigiar"
# la dentro em vez do separador de seccao a serio).
CARTEIRA_MARKER_RE = re.compile(r"carteira", re.IGNORECASE)
VIGIAR_MARKER_RE = re.compile(r"vigiar", re.IGNORECASE)

# Padrao generico de ticker B3 (4 letras + 1-2 digitos, ex.: BBAS3, TAEE11) -
# usado so para decidir "esta linha e dados ou cabecalho", nao para validar
# tickers concretos (por isso nao reaproveita a lista curada de
# scripts/common/tickers.py, que so cobre os tickers ja conhecidos do Rafa).
TICKER_CELL_RE = re.compile(r"^[A-Z]{4}\d{1,2}$")


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


def find_section_marker(rows: list[list[Any]], pattern: re.Pattern[str]) -> int | None:
    for idx, row in enumerate(rows):
        non_empty = [str(cell).strip() for cell in row if str(cell).strip()]
        if len(non_empty) == 1 and pattern.search(non_empty[0]):
            return idx
    return None


def is_ticker_cell(value: Any) -> bool:
    return bool(TICKER_CELL_RE.match(str(value).strip()))


def row_has_ticker(row: list[Any]) -> bool:
    return any(is_ticker_cell(cell) for cell in row)


def merge_header_rows(header_rows: list[list[Any]]) -> list[str]:
    if not header_rows:
        return []
    width = max(len(row) for row in header_rows)
    merged: list[str] = []
    for col in range(width):
        parts = []
        for row in header_rows:
            if col < len(row):
                val = str(row[col]).strip()
                if val:
                    parts.append(val)
        merged.append(" ".join(parts))
    return merged


def parse_section(rows: list[list[Any]], start: int, end: int) -> tuple[list[str], list[dict[str, Any]]]:
    """Extrai cabecalho (1+ linhas fundidas) e dados de uma seccao [start, end).

    A primeira linha (nao vazia) com um ticker marca o inicio dos dados;
    tudo antes disso, desde `start`, e cabecalho. Linhas em branco sao
    sempre ignoradas (tanto antes de encontrar dados como dentro deles -
    a Vigiar usa-as como separador visual entre grupos sectoriais).
    """
    header_rows: list[list[Any]] = []
    data_start: int | None = None
    for i in range(start, end):
        row = rows[i] if i < len(rows) else []
        if not any(str(cell).strip() for cell in row):
            continue
        if row_has_ticker(row):
            data_start = i
            break
        header_rows.append(row)

    header = merge_header_rows(header_rows)
    if data_start is None:
        return header, []

    data_rows = [rows[i] for i in range(data_start, end) if i < len(rows) and row_has_ticker(rows[i])]
    items: list[dict[str, Any]] = []
    for row in data_rows:
        item: dict[str, Any] = {}
        for col, key in enumerate(header):
            key_str = key or f"col_{col}"
            item[key_str] = row[col] if col < len(row) else ""
        items.append(item)
    return header, items


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

    carteira_marker = find_section_marker(rows, CARTEIRA_MARKER_RE)
    vigiar_marker = find_section_marker(rows, VIGIAR_MARKER_RE)

    if carteira_marker is None or vigiar_marker is None:
        raise EspelhoRadarError(
            "Marcador de seccao nao encontrado (carteira="
            f"{carteira_marker}, vigiar={vigiar_marker}) - nao vou adivinhar a "
            "divisao. Confirma manualmente a estrutura da folha (--raw)."
        )

    carteira_header, carteira_items = parse_section(rows, carteira_marker + 1, vigiar_marker)
    vigiar_header, vigiar_items = parse_section(rows, vigiar_marker + 1, len(rows))

    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "spreadsheet_id": spreadsheet_id,
        "range": range_name,
        "marker_found": True,
        "carteira_header": carteira_header,
        "carteira": carteira_items,
        "vigiar_header": vigiar_header,
        "vigiar": vigiar_items,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Exporta Carteira/Vigiar da Espelho Radar (Sheets API).")
    parser.add_argument("--credentials", default=str(DEFAULT_CREDENTIALS_PATH), help="Caminho de credentials.json.")
    parser.add_argument("--token", default=str(DEFAULT_TOKEN_PATH), help="Caminho de token.json.")
    parser.add_argument("--spreadsheet-id", default=SPREADSHEET_ID, help="ID da planilha Espelho Radar.")
    parser.add_argument("--range", default=RANGE_NAME, help='Range/aba a ler (default: "Main").')
    parser.add_argument("--out", help="Caminho do JSON de saida; sem isto, imprime em stdout.")
    parser.add_argument(
        "--raw",
        type=int,
        metavar="N",
        help="Modo de diagnostico: imprime as primeiras N linhas em bruto (todas as colunas, com indice), sem tentar separar Carteira/Vigiar. Nao mexe em nada, so para inspeccionar a estrutura real da folha.",
    )
    args = parser.parse_args()

    if args.raw is not None:
        try:
            creds = load_credentials(Path(args.credentials), Path(args.token))
        except EspelhoRadarError as exc:
            print(json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False))
            return 1
        rows = fetch_main_tab(creds, args.spreadsheet_id, args.range)
        for idx, row in enumerate(rows[: args.raw]):
            print(json.dumps({"row": idx, "values": row}, ensure_ascii=False))
        return 0

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
