#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
merge_feedback.py - Rotina Python LOCAL (Agenda de Lazer / Modulo 2)

v2 - 28 Ago 2026. O botao antigo "Salvar" / Zapier / pasta Guardados da
Agenda fica legado. A fonte viva de curadoria passa a ser o export CSV da
sheet `espelho_lazer`.

O QUE FAZ
---------
1. Le o export CSV da sheet `espelho_lazer`.
2. Considera apenas a linha mais recente por `dedup_key`.
3. Para linhas atuais `consumido`, pergunta interativamente:
   - guardar este item no Feedback_log.json? [s/N]
   - se sim, nota 0-5 opcional e comentario opcional.
4. Linhas atuais `removido` nao viram feedback: servem so para excluir o item.
5. Pode gerar um CSV limpo, mantendo apenas `elevar` e `guardado_futuro`
   ainda ativos. `removido`, `consumido` e `limpo` saem desse ficheiro.

O script nao fala com Google Sheets/Drive API, nao usa credenciais e nao
publica nada. Se for preciso atualizar a sheet real, usar o CSV limpo como
base para uma etapa explicita separada.

USO
---
    python merge_feedback.py ^
        --feedback-log "G:\\My Drive\\Claude_PRJ\\Feedback_log.json" ^
        --espelho-lazer-csv "C:\\Users\\rafa\\Downloads\\espelho_lazer.csv" ^
        --espelho-lazer-clean-out "C:\\Users\\rafa\\Downloads\\espelho_lazer_limpo.csv"

Legado opcional, para uma ultima ingestao de ficheiros antigos do antigo
botao "Salvar":

    python merge_feedback.py ... --guardados-dir "G:\\My Drive\\Claude_PRJ\\Guardados da Agenda"

--dry-run lista pendencias e limpeza sem perguntar nem escrever.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import unicodedata
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any


CATEGORY_MAP: dict[str, dict[str, str]] = {
    "gastro": {"category": "restaurant", "subcategory": ""},
    "cinema_indoor": {"category": "movie", "subcategory": "indoor"},
    "cinema_outdoor": {"category": "movie", "subcategory": "outdoor"},
    "streaming": {"category": "other", "subcategory": "streaming"},
    "books": {"category": "book", "subcategory": ""},
    "escape": {"category": "travel", "subcategory": "escapadinha"},
    "meetup": {"category": "activity", "subcategory": "desporto"},
    "culture": {"category": "activity", "subcategory": "cultura"},
    "tv": {"category": "other", "subcategory": "tv"},
    "radar": {"category": "other", "subcategory": "radar"},
}

SHEET_HEADERS = ["timestamp", "dedup_key", "titulo", "categoria", "acao", "data_evento", "expira_em", "nota"]
KEEP_ACTIONS_IN_CLEAN_SHEET = {"elevar", "guardado_futuro"}


def norm_title(title: str) -> str:
    text = unicodedata.normalize("NFKD", title or "")
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return " ".join(text.strip().casefold().split())


def parse_iso_date(value: str) -> date | None:
    raw = (value or "").strip()
    if not raw:
        return None
    try:
        return date.fromisoformat(raw[:10])
    except ValueError:
        return None


class PendingItem:
    def __init__(self, source: str, title: str, agenda_category: str, date_evento: str, extra_notes: str = ""):
        self.source = source
        self.title = title
        self.agenda_category = agenda_category
        self.date_evento = date_evento
        self.extra_notes = extra_notes

    @property
    def mapping(self) -> dict[str, str]:
        return CATEGORY_MAP.get(self.agenda_category, {"category": "other", "subcategory": self.agenda_category})


def resolve_mapping(item: PendingItem) -> dict[str, str]:
    if item.agenda_category.startswith("__feedback_cat__:"):
        _, cat, subcat = item.agenda_category.split(":", 2)
        return {"category": cat or "other", "subcategory": subcat}
    return item.mapping


def load_espelho_lazer_rows(csv_path: Path, warnings: list[str]) -> tuple[list[dict[str, str]], list[str]]:
    if not csv_path.exists():
        warnings.append(f"espelho_lazer CSV nao encontrado: {csv_path}")
        return [], SHEET_HEADERS

    try:
        with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            fieldnames = [str(x or "").strip() for x in (reader.fieldnames or [])]
            required = {"timestamp", "dedup_key", "titulo", "categoria", "acao", "data_evento"}
            if not required.issubset(set(fieldnames)):
                warnings.append(
                    f"espelho_lazer CSV nao tem as colunas esperadas ({sorted(required)}); "
                    f"tem: {fieldnames}. Ficheiro ignorado."
                )
                return [], fieldnames or SHEET_HEADERS
            rows = [{str(k or "").strip(): str(v or "").strip() for k, v in row.items()} for row in reader]
        return rows, fieldnames or SHEET_HEADERS
    except Exception as exc:
        warnings.append(f"espelho_lazer CSV nao pode ser lido: {type(exc).__name__}: {exc}")
        return [], SHEET_HEADERS


def latest_espelho_rows(rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    latest_by_key: dict[str, dict[str, str]] = {}
    for row in rows:
        key = row.get("dedup_key", "")
        if not key:
            continue
        prev = latest_by_key.get(key)
        if prev is None or row.get("timestamp", "") > prev.get("timestamp", ""):
            latest_by_key[key] = row
    return latest_by_key


def is_current_elevado(row: dict[str, str], today: date, warnings: list[str]) -> bool:
    expira = row.get("expira_em", "").strip()
    if not expira:
        warnings.append(f"Linha 'elevar' sem expira_em mantida por prudencia: {row.get('titulo', '?')}")
        return True
    parsed = parse_iso_date(expira)
    if parsed is None:
        warnings.append(f"Linha 'elevar' com expira_em invalido mantida por prudencia: {row.get('titulo', '?')} ({expira})")
        return True
    return parsed >= today


def pending_from_espelho(latest: dict[str, dict[str, str]]) -> list[PendingItem]:
    items: list[PendingItem] = []
    for row in latest.values():
        if row.get("acao") != "consumido":
            continue
        items.append(
            PendingItem(
                source="espelho_lazer",
                title=row.get("titulo", "").strip(),
                agenda_category=row.get("categoria", "").strip(),
                date_evento=row.get("data_evento", "").strip(),
            )
        )
    return items


def clean_espelho_rows(latest: dict[str, dict[str, str]], today: date, warnings: list[str]) -> tuple[list[dict[str, str]], Counter]:
    kept: list[dict[str, str]] = []
    removed = Counter()
    for row in latest.values():
        action = row.get("acao", "")
        if action == "elevar" and not is_current_elevado(row, today, warnings):
            removed["elevar_expirado"] += 1
            continue
        if action in KEEP_ACTIONS_IN_CLEAN_SHEET:
            kept.append(row)
        else:
            removed[action or "acao_vazia"] += 1
    kept.sort(key=lambda r: (r.get("acao", ""), r.get("timestamp", ""), r.get("titulo", "")))
    return kept, removed


def write_clean_csv(path: Path, rows: list[dict[str, str]], headers: list[str]) -> None:
    final_headers = list(headers)
    for header in SHEET_HEADERS:
        if header not in final_headers:
            final_headers.append(header)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=final_headers, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def load_guardados_da_agenda(dir_path: Path, warnings: list[str]) -> list[PendingItem]:
    if not dir_path.exists():
        warnings.append(f"Pasta 'Guardados da Agenda' nao encontrada: {dir_path}")
        return []

    items = []
    for file_path in sorted(dir_path.iterdir()):
        if not file_path.is_file():
            continue
        try:
            raw = file_path.read_text(encoding="utf-8")
            payload = json.loads(raw)
        except (OSError, json.JSONDecodeError):
            warnings.append(f"Guardados da Agenda: '{file_path.name}' nao e JSON valido; ignorado.")
            continue
        if not isinstance(payload, dict) or not payload.get("title"):
            warnings.append(
                f"Guardados da Agenda: '{file_path.name}' sem campo 'title' utilizavel "
                f"(payload: {raw[:80]!r}...); ignorado, provavel bug do Zapier."
            )
            continue
        items.append(
            PendingItem(
                source="guardados_da_agenda_legacy",
                title=str(payload.get("title", "")).strip(),
                agenda_category=f"__feedback_cat__:{payload.get('category','other')}:{payload.get('subcategory','')}",
                date_evento=str(payload.get("date", "")).strip(),
                extra_notes=str(payload.get("notes", "")).strip(),
            )
        )
    return items


def load_feedback_log(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise SystemExit(f"ERRO: Feedback_log.json nao encontrado em {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if "entries" not in data or not isinstance(data["entries"], list):
        raise SystemExit("ERRO: Feedback_log.json nao tem 'entries' (lista); ficheiro inesperado, abortado.")
    data.setdefault("meta", {})
    return data


def existing_keys(entries: list[dict[str, Any]]) -> set[tuple[str, str]]:
    keys = set()
    for entry in entries:
        title = entry.get("title") or entry.get("name") or ""
        category = entry.get("category") or ""
        if title:
            keys.add((norm_title(title), category))
    return keys


def next_entry_id(entries: list[dict[str, Any]]) -> str:
    max_n = 0
    for entry in entries:
        eid = str(entry.get("id", ""))
        if eid.startswith("ent_"):
            try:
                max_n = max(max_n, int(eid[4:]))
            except ValueError:
                pass
    return f"ent_{max_n + 1:03d}"


def build_entry(
    item: PendingItem,
    mapping: dict[str, str],
    entries: list[dict[str, Any]],
    today_iso: str,
    rating: int | None,
    note_text: str,
) -> dict[str, Any]:
    return {
        "id": next_entry_id(entries),
        "date": item.date_evento or today_iso,
        "title": item.title,
        "category": mapping["category"],
        "subcategory": mapping.get("subcategory", ""),
        "status": "tested",
        "rating": rating,
        "companions": [],
        "context": {},
        "cost": {"total": "", "per_person": ""},
        "consumption": [],
        "experience": {},
        "notes": note_text or item.extra_notes,
        "flags": {},
        "source": "self",
        "origin": {
            "platform": "Agenda de Lazer",
            "agent": "merge_feedback.py",
            "method": item.source,
        },
    }


def ask_yes_no(prompt: str, default: bool = False) -> bool:
    suffix = " [S/n]: " if default else " [s/N]: "
    raw = input(prompt + suffix).strip().casefold()
    if not raw:
        return default
    return raw in {"s", "sim", "y", "yes"}


def ask_feedback_decision(item: PendingItem, mapping: dict[str, str]) -> tuple[bool, int | None, str]:
    print()
    print(
        f"- {item.title} [{mapping['category']}{'/' + mapping['subcategory'] if mapping.get('subcategory') else ''}] "
        f"(fonte: {item.source}, data: {item.date_evento or '?'})"
    )
    keep = ask_yes_no("  Guardar este consumo no Feedback_log?", default=False)
    if not keep:
        return False, None, ""

    rating: int | None = None
    raw = input("  Nota 0-5 (Enter para sem nota): ").strip()
    if raw:
        try:
            val = int(raw)
            if 0 <= val <= 5:
                rating = val
            else:
                print("  Fora de 0-5; vou gravar sem nota.")
        except ValueError:
            print("  Nao percebi como numero; vou gravar sem nota.")
    note = input("  Comentario curto (Enter para saltar): ").strip()
    return True, rating, note


def collect_pending(
    items: list[PendingItem],
    have_feedback: set[tuple[str, str]],
) -> list[tuple[PendingItem, dict[str, str]]]:
    pending: list[tuple[PendingItem, dict[str, str]]] = []
    for item in items:
        if not item.title:
            continue
        mapping = resolve_mapping(item)
        key = (norm_title(item.title), mapping["category"])
        if key in have_feedback:
            continue
        pending.append((item, mapping))
    return pending


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--feedback-log", required=True, help="Caminho local para o Feedback_log.json.")
    parser.add_argument("--espelho-lazer-csv", required=True, help="Export CSV da sheet espelho_lazer.")
    parser.add_argument("--espelho-lazer-clean-out", help="Opcional: grava CSV limpo com apenas elevar/guardado_futuro ativos.")
    parser.add_argument("--guardados-dir", help="Opcional e legado: pasta antiga 'Guardados da Agenda' do botao Salvar/Zapier.")
    parser.add_argument("--today", default=None, help="Data YYYY-MM-DD (default: data real do sistema).")
    parser.add_argument("--dry-run", action="store_true", help="Lista pendencias e limpeza sem perguntar nem escrever.")
    args = parser.parse_args()

    today_iso = args.today or date.today().isoformat()
    today = parse_iso_date(today_iso)
    if today is None:
        raise SystemExit(f"ERRO: --today invalido: {today_iso}")

    warnings: list[str] = []
    rows, headers = load_espelho_lazer_rows(Path(args.espelho_lazer_csv), warnings)
    latest = latest_espelho_rows(rows)
    clean_rows, clean_removed = clean_espelho_rows(latest, today, warnings)

    sheet_items = pending_from_espelho(latest)
    legacy_items: list[PendingItem] = []
    if args.guardados_dir:
        legacy_items = load_guardados_da_agenda(Path(args.guardados_dir), warnings)

    feedback_path = Path(args.feedback_log)
    data = load_feedback_log(feedback_path)
    entries = data["entries"]
    have_feedback = existing_keys(entries)
    pending = collect_pending(sheet_items + legacy_items, have_feedback)

    action_counts = Counter(row.get("acao", "") or "acao_vazia" for row in latest.values())

    for warning in warnings:
        print(f"[aviso] {warning}")

    print(f"\nespelho_lazer: {len(rows)} linha(s), {len(latest)} item(ns) atuais.")
    if action_counts:
        print("Acoes atuais: " + ", ".join(f"{key}={value}" for key, value in sorted(action_counts.items())))
    print(
        "Limpeza preparada: "
        f"manter {len(clean_rows)} linha(s); remover "
        + (", ".join(f"{key}={value}" for key, value in sorted(clean_removed.items())) or "0")
        + "."
    )

    if pending:
        print(f"\n{len(pending)} consumo(s) sem decisao no Feedback_log:")
        for item, mapping in pending:
            print(f"  - [{item.source}] {item.title} ({mapping['category']})")
    else:
        print("\nNao ha consumos pendentes para perguntar.")

    if args.dry_run:
        if args.espelho_lazer_clean_out:
            print(f"\n--dry-run: CSV limpo seria gravado em {args.espelho_lazer_clean_out}")
        print("--dry-run: nada foi perguntado nem gravado.")
        return 0

    added = 0
    ignored = 0
    for item, mapping in pending:
        keep, rating, note = ask_feedback_decision(item, mapping)
        if not keep:
            ignored += 1
            print("  ignorado; na limpeza do espelho, este consumido pode sair da fila.")
            continue
        entry = build_entry(item, mapping, entries, today_iso, rating, note)
        entries.append(entry)
        have_feedback.add((norm_title(item.title), mapping["category"]))
        added += 1
        print(f"  gravado como {entry['id']} (rating={rating!r})")

    if added:
        data["meta"]["ultima_entrada_em"] = today_iso
        feedback_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"\n{added} entrada(s) nova(s) gravada(s) em {feedback_path}.")
    else:
        print("\nFeedback_log.json nao foi alterado.")

    if args.espelho_lazer_clean_out:
        write_clean_csv(Path(args.espelho_lazer_clean_out), clean_rows, headers)
        print(f"CSV limpo gravado em {args.espelho_lazer_clean_out}.")

    if ignored:
        print(f"{ignored} consumo(s) ignorado(s) e elegiveis para sair da sheet na limpeza.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
