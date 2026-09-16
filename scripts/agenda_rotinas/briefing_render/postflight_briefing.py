from __future__ import annotations

import argparse
import importlib.util
import json
import re
import shutil
import subprocess
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

SCHEMA_VERSION = "0.1"
TIMEZONE = ZoneInfo("Europe/Lisbon")

PROJECT_ROOT = Path(r"G:\My Drive\Claude_PRJ")
AGENDA_ROOT = PROJECT_ROOT / "Agenda"
ROUTINE_DIR = AGENDA_ROOT / "X_Rotinas_Python" / "Briefing"
TEMPLATES_DIR = AGENDA_ROOT / "Templates"
BRIEFING_TEMPLATE_PATH = TEMPLATES_DIR / "Briefing" / "BRIEFING_TEMPLATE_v8_render.html"
BRIEFING_TEMPLATE_FALLBACK_PATH = TEMPLATES_DIR / "Briefing" / "BRIEFING_TEMPLATE_v7_render.html"
BRIEFING_RENDER_PATH = TEMPLATES_DIR / "Briefing" / "render_v5.py"
REPO_DIR = PROJECT_ROOT / "personal-system"
REPO_BRIEFING_PATH = Path("agendas") / "briefing" / "index.html"
DAY_WINDOW_DAYS = 3
CALENDAR_WINDOW_DAYS = 15
EMAIL_SECTIONS = [
    "urgente",
    "importante",
    "informativo",
    "ruido",
    "tarefas_sem_data",
    "snoozed",
    "pediatric_surgery",
    "ulsasi",
    "events",
]
REQUIRED_HTML_TEXT = ("Briefing", "Hoje", "Tarefas", "Email", "Tempo", "Rotina")


class PostflightError(Exception):
    pass


def now_lisbon() -> datetime:
    return datetime.now(TIMEZONE)


def file_info(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {"exists": False, "path": None}
    exists = path.exists()
    info: dict[str, Any] = {"exists": exists, "path": str(path)}
    if exists:
        stat = path.stat()
        info.update({
            "name": path.name,
            "size_bytes": stat.st_size,
            "mtime": datetime.fromtimestamp(stat.st_mtime, TIMEZONE).isoformat(timespec="seconds"),
        })
    return info


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        raise PostflightError(f"JSON invalido em {path}: {type(exc).__name__}: {exc}") from exc


def parse_iso_date(value: Any) -> date | None:
    if not isinstance(value, str):
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def is_within(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def load_render_validator(render_path: Path):
    spec = importlib.util.spec_from_file_location("briefing_render_v5", render_path)
    if spec is None or spec.loader is None:
        raise PostflightError(f"Nao foi possivel importar render validator: {render_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    validator = getattr(module, "validate_canonical", None)
    if not callable(validator):
        raise PostflightError(f"Render sem validate_canonical(): {render_path}")
    return validator


def validate_sequence(days: Any, start: date, length: int, field: str, errors: list[str]) -> None:
    if not isinstance(days, list):
        errors.append(f"{field} deve ser lista")
        return
    if len(days) != length:
        errors.append(f"{field} deve ter exactamente {length} entradas")
        return
    for idx, item in enumerate(days):
        got = parse_iso_date(item.get("date")) if isinstance(item, dict) else None
        expected = start + timedelta(days=idx)
        if got != expected:
            errors.append(f"{field}[{idx}].date esperado {expected.isoformat()}, obtido {item.get('date') if isinstance(item, dict) else item!r}")
            break


def validate_calendar(days: Any, start: date, errors: list[str]) -> None:
    if not isinstance(days, list):
        errors.append("calendario.dias deve ser lista")
        return
    if len(days) < CALENDAR_WINDOW_DAYS:
        errors.append(f"calendario.dias deve cobrir pelo menos {CALENDAR_WINDOW_DAYS} dias")
    for idx, item in enumerate(days[:CALENDAR_WINDOW_DAYS]):
        got = parse_iso_date(item.get("date")) if isinstance(item, dict) else None
        expected = start + timedelta(days=idx)
        if got != expected:
            errors.append(f"calendario.dias[{idx}].date esperado {expected.isoformat()}, obtido {item.get('date') if isinstance(item, dict) else item!r}")
            break
        if not isinstance(item.get("eventos_count"), int):
            errors.append(f"calendario.dias[{idx}].eventos_count deve ser inteiro")
        if not isinstance(item.get("tarefas_count"), int):
            errors.append(f"calendario.dias[{idx}].tarefas_count deve ser inteiro")
        if not isinstance(item.get("itens"), list):
            errors.append(f"calendario.dias[{idx}].itens deve ser lista")


def validate_email(email: Any, errors: list[str]) -> None:
    if not isinstance(email, dict):
        errors.append("email deve ser objecto")
        return
    for key in EMAIL_SECTIONS:
        if not isinstance(email.get(key), list):
            errors.append(f"email.{key} deve ser lista")


def validate_task_cards(cards: Any, start: date, errors: list[str]) -> None:
    if not isinstance(cards, list):
        errors.append("tarefas.cards deve ser lista")
        return
    if len(cards) != DAY_WINDOW_DAYS:
        errors.append(f"tarefas.cards deve ter exactamente {DAY_WINDOW_DAYS} entradas")
    for idx, card in enumerate(cards[:DAY_WINDOW_DAYS]):
        if not isinstance(card, dict):
            errors.append(f"tarefas.cards[{idx}] deve ser objecto")
            continue
        card_date = card.get("date")
        if card_date:
            expected = start + timedelta(days=idx)
            got = parse_iso_date(card_date)
            if got != expected:
                errors.append(f"tarefas.cards[{idx}].date esperado {expected.isoformat()}, obtido {card_date!r}")
        for key in ("tarefas", "eventos", "extras"):
            if not isinstance(card.get(key), list):
                errors.append(f"tarefas.cards[{idx}].{key} deve ser lista")


def validate_no_private_handoff(data: Any, errors: list[str]) -> None:
    if isinstance(data, dict):
        for key in data:
            if key.startswith("_llm") or key.startswith("_preflight"):
                errors.append(f"campo auxiliar deve ser removido antes do postflight: {key}")


def validate_canonical(data: Any, render_path: Path) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["raiz do JSON canonico deve ser objecto"]

    render_validator = load_render_validator(render_path)
    errors.extend(render_validator(data))
    validate_no_private_handoff(data, errors)

    meta = data.get("meta") if isinstance(data.get("meta"), dict) else {}
    target = parse_iso_date(meta.get("date"))
    if target is None:
        errors.append("meta.date invalida")
        return errors
    mode = meta.get("mode")
    if mode not in {"A", "B"}:
        errors.append("meta.mode deve ser A ou B")

    hoje_days = data.get("hoje", {}).get("dias") if isinstance(data.get("hoje"), dict) else None
    rotina_days = data.get("rotina", {}).get("dias") if isinstance(data.get("rotina"), dict) else None
    validate_sequence(hoje_days, target, DAY_WINDOW_DAYS, "hoje.dias", errors)
    validate_sequence(rotina_days, target, DAY_WINDOW_DAYS, "rotina.dias", errors)
    validate_task_cards(data.get("tarefas", {}).get("cards") if isinstance(data.get("tarefas"), dict) else None, target, errors)
    validate_calendar(data.get("calendario", {}).get("dias") if isinstance(data.get("calendario"), dict) else None, target, errors)
    validate_email(data.get("email"), errors)

    if mode == "A" and not isinstance(data.get("hff"), dict):
        errors.append("Modo A exige hff objecto")
    if mode == "B" and data.get("hff") is not None:
        errors.append("Modo B exige hff=null")

    tempo = data.get("tempo")
    if not isinstance(tempo, dict):
        errors.append("tempo deve ser objecto")
    else:
        if not isinstance(tempo.get("tabela_7dias"), list) or len(tempo.get("tabela_7dias", [])) < 7:
            errors.append("tempo.tabela_7dias deve ter pelo menos 7 entradas")
        if not isinstance(tempo.get("janelas"), list):
            errors.append("tempo.janelas deve ser lista")

    return errors


def run_command(args: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=str(cwd) if cwd else None,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def run_render(render_path: Path, input_json: Path, template_path: Path, output_html: Path) -> dict[str, Any]:
    output_html.parent.mkdir(parents=True, exist_ok=True)
    completed = run_command([sys.executable, str(render_path), str(input_json), str(template_path), str(output_html)])
    if completed.returncode != 0:
        raise PostflightError(
            "render briefing falhou "
            f"(exit {completed.returncode})\nSTDOUT:\n{completed.stdout}\nSTDERR:\n{completed.stderr}"
        )
    return {"returncode": completed.returncode, "stdout": completed.stdout.strip(), "stderr": completed.stderr.strip()}


def validate_html(path: Path, mode: str) -> list[str]:
    errors: list[str] = []
    if not path.exists() or path.stat().st_size == 0:
        return [f"HTML nao criado ou vazio: {path}"]
    raw_html = path.read_text(encoding="utf-8", errors="replace")
    block_pattern = r"<!--/?(?:HFF_BTN|HFF_PANEL|TASK_DAY|TASK_ITEM_T|TASK_ITEM_E|TASK_ITEM_X|CAL_CELL|CAL_DAY_PANEL|WEATHER_ROW|WINDOW_ROW|EMAIL_SECTION:[a-z_]+)-->"
    match = re.search(block_pattern, raw_html)
    if match:
        errors.append(f"HTML contem bloco residual: {match.group(0)[:80]}")
    html = re.sub(r"<!--.*?-->", "", raw_html, flags=re.DOTALL)
    token_patterns = [
        r"\{\{[^{}]+\}\}",
        r"\{\{__PLACEHOLDER_[^{}]+__\}\}",
    ]
    for pattern in token_patterns:
        match = re.search(pattern, html)
        if match:
            errors.append(f"HTML contem token residual: {match.group(0)[:80]}")
            break
    for text in REQUIRED_HTML_TEXT:
        if text not in html:
            errors.append(f"HTML sem texto esperado: {text}")
    if "Calendário" not in html and "Calendario" not in html:
        errors.append("HTML sem texto esperado: Calendario")
    if mode == "A" and "Trabalho HFF" not in html:
        errors.append("Modo A sem tab Trabalho HFF no HTML")
    if mode == "B" and "Trabalho HFF" in html:
        errors.append("Modo B ainda contem tab Trabalho HFF no HTML")
    return errors


def copy_to_repo(html_path: Path, repo: Path) -> Path:
    if not repo.exists():
        raise PostflightError(f"repo nao existe: {repo}")
    target = repo / REPO_BRIEFING_PATH
    if not is_within(target, repo):
        raise PostflightError(f"destino fora do repo: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(html_path, target)
    return target


def git_publish(repo: Path, rel_path: Path, message: str) -> dict[str, Any]:
    commands = [
        ["git", "add", str(rel_path)],
        ["git", "commit", "-m", message],
        ["git", "push"],
    ]
    results = []
    for command in commands:
        completed = run_command(command, cwd=repo)
        results.append({"cmd": command, "returncode": completed.returncode, "stdout": completed.stdout.strip(), "stderr": completed.stderr.strip()})
        if completed.returncode != 0:
            raise PostflightError(f"comando falhou: {' '.join(command)}")
    return {"commands": results}


def postflight(args: argparse.Namespace) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    generated = now_lisbon()
    input_json = Path(args.json)
    template_path = Path(args.template) if args.template else (BRIEFING_TEMPLATE_PATH if BRIEFING_TEMPLATE_PATH.exists() else BRIEFING_TEMPLATE_FALLBACK_PATH)
    render_path = Path(args.render) if args.render else BRIEFING_RENDER_PATH
    output_html = Path(args.html) if args.html else ROUTINE_DIR / f"_work_{generated.strftime('%Y%m%d_%H%M%S')}" / "briefing_index.html"

    result: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated.isoformat(timespec="seconds"),
        "status": "unknown",
        "inputs": {
            "json": file_info(input_json),
            "template": file_info(template_path),
            "render": file_info(render_path),
        },
        "outputs": {},
        "errors": errors,
        "warnings": warnings,
        "actions": {"rendered": False, "copied_to_repo": False, "published": False},
    }

    for label, path in (("json", input_json), ("template", template_path), ("render", render_path)):
        if not path.exists():
            errors.append(f"{label} em falta: {path}")
    if errors:
        result["status"] = "blocked"
        return result

    try:
        data = load_json(input_json)
        mode = data.get("meta", {}).get("mode") if isinstance(data, dict) else None
        errors.extend(validate_canonical(data, render_path))
        if errors:
            result["status"] = "blocked"
            return result
        rendered = run_render(render_path, input_json, template_path, output_html)
        result["actions"]["rendered"] = True
        result["outputs"]["html"] = file_info(output_html)
        result["render"] = rendered
        errors.extend(validate_html(output_html, str(mode)))
        if errors:
            result["status"] = "blocked"
            return result
        if args.copy_to_repo or args.publish:
            repo = Path(args.repo) if args.repo else REPO_DIR
            copied = copy_to_repo(output_html, repo)
            result["actions"]["copied_to_repo"] = True
            result["outputs"]["repo_html"] = file_info(copied)
        if args.publish:
            repo = Path(args.repo) if args.repo else REPO_DIR
            message = args.commit_message or f"[agenda] actualiza briefing {generated.strftime('%Y-%m-%d %H:%M')}"
            result["publish"] = git_publish(repo, REPO_BRIEFING_PATH, message)
            result["actions"]["published"] = True
        result["status"] = "ok"
        return result
    except Exception as exc:
        errors.append(f"postflight exception: {type(exc).__name__}: {exc}")
        result["status"] = "blocked"
        return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Postflight mecanico local da rotina Briefing.")
    parser.add_argument("--json", required=True, help="JSON canonico final aprovado pelo LLM.")
    parser.add_argument("--template", help="Template HTML do Briefing. Default: v8, fallback v7.")
    parser.add_argument("--render", help="Render script do Briefing. Default: render_v5.py.")
    parser.add_argument("--html", help="Destino HTML gerado. Default: _work timestamp local.")
    parser.add_argument("--manifest", default=str(ROUTINE_DIR / "briefing_postflight.json"), help="Manifesto postflight.")
    parser.add_argument("--repo", help="Checkout personal-system para copia/publicacao.")
    parser.add_argument("--copy-to-repo", action="store_true", help="Copia HTML para agendas/briefing/index.html no repo. Nao faz commit.")
    parser.add_argument("--publish", action="store_true", help="Copia, git add/commit/push. Usar apenas quando explicitamente pedido.")
    parser.add_argument("--commit-message", help="Mensagem de commit quando --publish for usado.")
    args = parser.parse_args()

    result = postflight(args)
    manifest = Path(args.manifest)
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"OK: manifesto postflight -> {manifest}")
    if result["status"] != "ok":
        print("ERROS:")
        for error in result["errors"]:
            print(f"- {error}")
        return 2
    print(f"OK: briefing HTML -> {result['outputs']['html']['path']}")
    if result["actions"].get("copied_to_repo"):
        print(f"OK: copiado para repo -> {result['outputs']['repo_html']['path']}")
    if result["actions"].get("published"):
        print("OK: publicado via git push")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


