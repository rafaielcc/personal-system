from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from collections import Counter
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo


SCHEMA_VERSION = "0.1"
TIMEZONE = ZoneInfo("Europe/Lisbon")

PROJECT_ROOT = Path(r"G:\My Drive\Claude_PRJ")
AGENDA_ROOT = PROJECT_ROOT / "Agenda"
ROUTINE_DIR = AGENDA_ROOT / "X_Rotinas_Python" / "Painel_Hff"
TEMPLATES_DIR = AGENDA_ROOT / "Templates"
HFF_TEMPLATE_PATH = TEMPLATES_DIR / "hff" / "HFF_TEMPLATE_v6_render.html"
HFF_RENDER_PATH = TEMPLATES_DIR / "hff" / "render_v4.py"
BO_TEMPLATE_PATH = TEMPLATES_DIR / "bo" / "BO_TEMPLATE_v4_render.html"
BO_RENDER_PATH = TEMPLATES_DIR / "bo" / "render_v3.py"
REPO_DIR = PROJECT_ROOT / "personal-system"
REPO_HFF_PATH = Path("agendas") / "Hff" / "index.html"
REPO_BO_PATH = Path("agendas") / "BO" / "index.html"

WINDOW_DAYS = 28
VALID_PERIODS = {"M", "S"}
REQUIRED_ROOT_OBJECTS = ("meta", "resumo", "tarefas_hff", "cirurgias", "prevencao", "sigic", "equipa")
REQUIRED_HFF_TEXT = ("Painel HFF", "Resumo", "Cirurgias", "Prevencao", "SIGIC", "Equipa")
REQUIRED_BO_TEXT = ("Lista BO", "Cirurgia Pediatrica", "Tarde / SIGIC")


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
        info.update(
            {
                "name": path.name,
                "size_bytes": stat.st_size,
                "mtime": datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
            }
        )
    return info


def is_within(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise PostflightError(f"JSON invalido em {path}: {type(exc).__name__}: {exc}") from exc


def parse_iso_date(value: Any) -> date | None:
    if not isinstance(value, str):
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def validate_canonical(data: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["raiz do JSON canonico deve ser objecto"]

    for key in REQUIRED_ROOT_OBJECTS:
        if not isinstance(data.get(key), dict):
            errors.append(f"{key}: objecto obrigatorio em falta")

    meta = data.get("meta", {})
    today = parse_iso_date(meta.get("date")) if isinstance(meta, dict) else None
    if today is None:
        errors.append("meta.date ausente ou invalido")
    for field in ("weekday", "day_type", "generated_at"):
        if not meta.get(field):
            errors.append(f"meta.{field} em falta")

    cirurgias = data.get("cirurgias", {})
    if cirurgias.get("janela_dias") != WINDOW_DAYS:
        errors.append(f"cirurgias.janela_dias deve ser {WINDOW_DAYS}")
    sessions = cirurgias.get("sessoes")
    if not isinstance(sessions, list):
        errors.append("cirurgias.sessoes deve ser lista")
        sessions = []

    if today:
        end = today + timedelta(days=WINDOW_DAYS - 1)
    else:
        end = None

    session_process_keys: list[tuple[str, str, str]] = []
    for idx, session in enumerate(sessions):
        if not isinstance(session, dict):
            errors.append(f"cirurgias.sessoes[{idx}] deve ser objecto")
            continue
        session_date = parse_iso_date(session.get("date"))
        periodo = session.get("periodo")
        if session_date is None:
            errors.append(f"cirurgias.sessoes[{idx}].date invalida")
        elif today and session_date < today:
            errors.append(f"cirurgias.sessoes[{idx}] contem data passada: {session.get('date')}")
        elif end and session_date > end:
            errors.append(f"cirurgias.sessoes[{idx}] fora da janela de {WINDOW_DAYS} dias: {session.get('date')}")
        if periodo not in VALID_PERIODS:
            errors.append(f"cirurgias.sessoes[{idx}].periodo invalido: {periodo!r}")
        if not isinstance(session.get("ausentes_previstos", []), list):
            errors.append(f"cirurgias.sessoes[{idx}].ausentes_previstos deve ser lista")
        doentes = session.get("doentes")
        if not isinstance(doentes, list):
            errors.append(f"cirurgias.sessoes[{idx}].doentes deve ser lista")
            continue
        for didx, patient in enumerate(doentes):
            if not isinstance(patient, dict):
                errors.append(f"cirurgias.sessoes[{idx}].doentes[{didx}] deve ser objecto")
                continue
            processo = str(patient.get("processo") or "").strip()
            if not processo:
                errors.append(f"doente sem processo em sessoes[{idx}].doentes[{didx}]")
            if not patient.get("nome"):
                errors.append(f"doente sem nome em sessoes[{idx}].doentes[{didx}]")
            if not patient.get("idade_fmt"):
                errors.append(f"doente sem idade_fmt em sessoes[{idx}].doentes[{didx}]")
            if not isinstance(patient.get("fdr"), bool):
                errors.append(f"doente fdr nao booleano em sessoes[{idx}].doentes[{didx}]")
            if session_date and periodo and processo:
                session_process_keys.append((session_date.isoformat(), str(periodo), processo))

    for key, count in sorted(Counter(session_process_keys).items()):
        if count > 1:
            errors.append(f"processo duplicado na mesma sessao: {key[0]} {key[1]} processo {key[2]}")

    validate_prevencao(data.get("prevencao", {}), errors)
    validate_sigic(data.get("sigic", {}), today, end, errors)
    validate_equipa(data.get("equipa", {}), today, errors)
    validate_tarefas(data.get("tarefas_hff", {}), errors)
    return errors


def validate_prevencao(prevencao: dict[str, Any], errors: list[str]) -> None:
    if not isinstance(prevencao.get("semana_actual", {}), dict):
        errors.append("prevencao.semana_actual deve ser objecto")
    weeks = prevencao.get("semanas")
    if not isinstance(weeks, list):
        errors.append("prevencao.semanas deve ser lista")
        return
    for idx, week in enumerate(weeks):
        if not isinstance(week, dict):
            errors.append(f"prevencao.semanas[{idx}] deve ser objecto")
            continue
        if parse_iso_date(week.get("inicio")) is None or parse_iso_date(week.get("fim")) is None:
            errors.append(f"prevencao.semanas[{idx}] tem datas invalidas")
        if not isinstance(week.get("ausencia_notas", []), list):
            errors.append(f"prevencao.semanas[{idx}].ausencia_notas deve ser lista")


def validate_sigic(sigic: dict[str, Any], today: date | None, end: date | None, errors: list[str]) -> None:
    lists = sigic.get("listas")
    if not isinstance(lists, list):
        errors.append("sigic.listas deve ser lista")
        return
    for idx, item in enumerate(lists):
        if not isinstance(item, dict):
            errors.append(f"sigic.listas[{idx}] deve ser objecto")
            continue
        item_date = parse_iso_date(item.get("date"))
        if item_date is None:
            errors.append(f"sigic.listas[{idx}].date invalida")
        elif today and item_date < today:
            errors.append(f"sigic.listas[{idx}] contem data passada: {item.get('date')}")
        elif end and item_date > end:
            errors.append(f"sigic.listas[{idx}] fora da janela de {WINDOW_DAYS} dias: {item.get('date')}")
        if not isinstance(item.get("cirurgias", []), list):
            errors.append(f"sigic.listas[{idx}].cirurgias deve ser lista")


def validate_equipa(equipa: dict[str, Any], today: date | None, errors: list[str]) -> None:
    for field in ("ausencias_confirmadas", "ausencias_provaveis", "folgas", "codigos_ambiguos"):
        if not isinstance(equipa.get(field, []), list):
            errors.append(f"equipa.{field} deve ser lista")
    calendar = equipa.get("calendario_4_semanas")
    if not isinstance(calendar, list):
        errors.append("equipa.calendario_4_semanas deve ser lista")
        return
    if len(calendar) != WINDOW_DAYS:
        errors.append(f"equipa.calendario_4_semanas deve ter {WINDOW_DAYS} dias")
    if today:
        for offset, item in enumerate(calendar[:WINDOW_DAYS]):
            expected = today + timedelta(days=offset)
            got = parse_iso_date(item.get("date")) if isinstance(item, dict) else None
            if got != expected:
                errors.append(f"equipa.calendario_4_semanas[{offset}] esperado {expected.isoformat()}, obtido {item.get('date') if isinstance(item, dict) else item!r}")
                break


def validate_tarefas(tarefas: dict[str, Any], errors: list[str]) -> None:
    items = tarefas.get("itens")
    if not isinstance(items, list):
        errors.append("tarefas_hff.itens deve ser lista")
        return
    for idx, item in enumerate(items):
        if not isinstance(item, dict):
            errors.append(f"tarefas_hff.itens[{idx}] deve ser objecto")
            continue
        if item.get("prioridade") not in {"alta", "media"}:
            errors.append(f"tarefas_hff.itens[{idx}].prioridade invalida: {item.get('prioridade')!r}")


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
    if not render_path.exists():
        raise PostflightError(f"render script em falta: {render_path}")
    if not template_path.exists():
        raise PostflightError(f"template em falta: {template_path}")
    output_html.parent.mkdir(parents=True, exist_ok=True)
    result = run_command([sys.executable, str(render_path), str(input_json), str(template_path), str(output_html)])
    if result.returncode != 0:
        raise PostflightError((result.stderr or result.stdout or "render falhou").strip())
    return {
        "command": [sys.executable, str(render_path), str(input_json), str(template_path), str(output_html)],
        "stdout": result.stdout.strip(),
        "stderr": result.stderr.strip(),
        "output": file_info(output_html),
    }


def validate_html(path: Path, required_text: tuple[str, ...], forbidden_text: tuple[str, ...] = ()) -> list[str]:
    errors: list[str] = []
    if not path.exists():
        return [f"HTML nao encontrado: {path}"]
    html = path.read_text(encoding="utf-8", errors="replace")
    if len(html) < 5000:
        errors.append(f"HTML demasiado pequeno: {len(html)} bytes")
    html_without_comments = re.sub(r"<!--[\s\S]*?-->", "", html)
    residual_tokens = sorted(set(re.findall(r"\{\{[^{}]+\}\}", html_without_comments)))
    if residual_tokens:
        errors.append("tokens residuais no HTML: " + ", ".join(residual_tokens[:20]))
    residual_blocks = sorted(set(re.findall(r"<!--/?[A-Z0-9_]+-->", html_without_comments)))
    if residual_blocks:
        errors.append("blocos marcadores residuais no HTML: " + ", ".join(residual_blocks[:20]))
    searchable = strip_accents(html).lower()
    for text in required_text:
        if strip_accents(text).lower() not in searchable:
            errors.append(f"texto obrigatorio ausente no HTML: {text}")
    for text in forbidden_text:
        if strip_accents(text).lower() in searchable:
            errors.append(f"texto proibido encontrado no HTML: {text}")
    return errors


def strip_accents(value: str) -> str:
    import unicodedata

    text = unicodedata.normalize("NFKD", value)
    return "".join(ch for ch in text if not unicodedata.combining(ch))


def copy_to_repo(html_path: Path, repo_dir: Path, repo_relative_path: Path) -> Path:
    if not html_path.exists():
        raise PostflightError(f"HTML origem nao encontrado: {html_path}")
    if not (repo_dir / ".git").exists():
        raise PostflightError(f"checkout git nao encontrado: {repo_dir}")
    destination = repo_dir / repo_relative_path
    if not is_within(destination, repo_dir):
        raise PostflightError(f"destino fora do repo: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(html_path, destination)
    return destination


def publish(repo_dir: Path, paths: list[Path], commit_message: str) -> dict[str, Any]:
    if not paths:
        return {"status": "not_requested", "pushed": False}
    relative_paths = [str(path) for path in paths]
    add = run_command(["git", "add", *relative_paths], cwd=repo_dir)
    if add.returncode != 0:
        raise PostflightError("git add falhou: " + (add.stderr or add.stdout).strip())
    diff = run_command(["git", "diff", "--cached", "--quiet", "--", *relative_paths], cwd=repo_dir)
    if diff.returncode == 0:
        return {"status": "no_changes", "pushed": False, "paths": relative_paths}
    if diff.returncode not in {0, 1}:
        raise PostflightError("git diff falhou: " + (diff.stderr or diff.stdout).strip())
    commit = run_command(["git", "commit", "-m", commit_message, "--", *relative_paths], cwd=repo_dir)
    if commit.returncode != 0:
        raise PostflightError("git commit falhou: " + (commit.stderr or commit.stdout).strip())
    push = run_command(["git", "push", "origin", "main"], cwd=repo_dir)
    if push.returncode != 0:
        return {"status": "push_failed", "pushed": False, "error": (push.stderr or push.stdout).strip(), "paths": relative_paths}
    return {"status": "published", "pushed": True, "paths": relative_paths, "commit": commit.stdout.strip()}


def validate_against_preflight(final_data: dict[str, Any], pre_data: dict[str, Any], errors: list[str]) -> None:
    """O LLM so faz 'conferencia inteligente' (rever alertas/FDR/prioridades) --
    nunca deve reescrever os factos mecanicos que o preflight ja apurou. Sem
    isto, um erro do LLM (ex: reescrever equipa.ausencias_confirmadas a partir
    da memoria em vez de copiar) passava incolume pela validacao de esquema,
    que so olha para a FORMA dos dados, nunca para o seu CONTEUDO."""
    pre_draft = pre_data.get("canonical_draft") if isinstance(pre_data.get("canonical_draft"), dict) else {}
    pre_meta = pre_draft.get("meta") if isinstance(pre_draft.get("meta"), dict) else {}
    final_meta = final_data.get("meta") if isinstance(final_data.get("meta"), dict) else {}
    if pre_meta.get("date") and final_meta.get("date") != pre_meta.get("date"):
        errors.append(
            f"meta.date ({final_meta.get('date')!r}) nao bate com o preflight "
            f"({pre_meta.get('date')!r}) -- o LLM esta a trabalhar em cima da corrida errada."
        )
    for key in ("cirurgias", "sigic", "equipa"):
        pre_block = pre_draft.get(key)
        final_block = final_data.get(key)
        if pre_block is not None and final_block != pre_block:
            errors.append(
                f"{key} no JSON final nao e identico ao do preflight -- este bloco e mecanico "
                f"(o preflight ja o apurou da planilha), o LLM nunca deve reescreve-lo."
            )
    pre_weeks = pre_draft.get("prevencao", {}).get("semanas") if isinstance(pre_draft.get("prevencao"), dict) else None
    final_weeks = final_data.get("prevencao", {}).get("semanas") if isinstance(final_data.get("prevencao"), dict) else None
    if pre_weeks is not None and final_weeks != pre_weeks:
        errors.append(
            "prevencao.semanas no JSON final nao e identico ao do preflight -- "
            "as ausencia_notas ja vem cruzadas mecanicamente com a aba Ausencias (Seccao 7-A), "
            "o LLM nunca deve reescreve-las (nem 'corrigir' para ferias sem confirmacao)."
        )


def postflight(args: argparse.Namespace) -> dict[str, Any]:
    generated = now_lisbon()
    input_json = Path(args.json)
    data = load_json(input_json)
    errors = validate_canonical(data)
    warnings: list[str] = []
    if args.preflight_json:
        pre_data = load_json(Path(args.preflight_json))
        validate_against_preflight(data, pre_data, errors)
    else:
        warnings.append("--preflight-json nao foi passado: sem cruzamento contra o preflight, o LLM podia ter reescrito dados mecanicos sem ninguem reparar.")

    workdir = Path(args.workdir) if args.workdir else ROUTINE_DIR / ("_work_" + generated.strftime("%Y%m%d_%H%M%S"))
    hff_html = Path(args.hff_html) if args.hff_html else workdir / "hff_index.html"
    bo_html = Path(args.bo_html) if args.bo_html else workdir / "bo_index.html"
    rendered: dict[str, Any] = {}

    modules = {"hff", "bo"} if args.module == "both" else {args.module}
    if not errors:
        if "hff" in modules:
            try:
                rendered["hff"] = run_render(HFF_RENDER_PATH, input_json, HFF_TEMPLATE_PATH, hff_html)
                errors.extend("HFF HTML: " + err for err in validate_html(hff_html, REQUIRED_HFF_TEXT))
            except PostflightError as exc:
                errors.append("HFF render: " + str(exc))
        if "bo" in modules:
            try:
                rendered["bo"] = run_render(BO_RENDER_PATH, input_json, BO_TEMPLATE_PATH, bo_html)
                errors.extend("BO HTML: " + err for err in validate_html(bo_html, REQUIRED_BO_TEXT, forbidden_text=("Tarefas HFF", "On-call esta semana")))
            except PostflightError as exc:
                errors.append("BO render: " + str(exc))

    publish_result: dict[str, Any] = {"status": "not_requested", "pushed": False}
    copied: dict[str, Any] = {}
    if args.publish and not errors:
        repo_paths = []
        try:
            if "hff" in modules:
                copied_hff = copy_to_repo(hff_html, Path(args.repo), REPO_HFF_PATH)
                copied["hff"] = file_info(copied_hff)
                repo_paths.append(REPO_HFF_PATH)
            if "bo" in modules:
                copied_bo = copy_to_repo(bo_html, Path(args.repo), REPO_BO_PATH)
                copied["bo"] = file_info(copied_bo)
                repo_paths.append(REPO_BO_PATH)
            message = args.commit_message or "[agenda] actualiza painel HFF " + generated.strftime("%Y-%m-%d %H:%M")
            publish_result = publish(Path(args.repo), repo_paths, message)
            if publish_result.get("status") == "push_failed":
                warnings.append("push GitHub falhou: " + publish_result.get("error", "erro nao especificado"))
        except PostflightError as exc:
            publish_result = {"status": "failed", "pushed": False, "error": str(exc)}
            warnings.append("publicacao nao concluida: " + str(exc))

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated.isoformat(timespec="seconds"),
        "routine": "painel_hff",
        "status": "fail" if errors else ("warn" if warnings else "ok"),
        "inputs": {
            "json": file_info(input_json),
            "hff_template": file_info(HFF_TEMPLATE_PATH),
            "hff_render": file_info(HFF_RENDER_PATH),
            "bo_template": file_info(BO_TEMPLATE_PATH),
            "bo_render": file_info(BO_RENDER_PATH),
        },
        "outputs": {
            "workdir": file_info(workdir),
            "hff_html": file_info(hff_html) if "hff" in modules else {"exists": False, "path": None, "skipped": True},
            "bo_html": file_info(bo_html) if "bo" in modules else {"exists": False, "path": None, "skipped": True},
            "copied_to_repo": copied,
            "github_publication": publish_result,
        },
        "checks": {
            "window_days": WINDOW_DAYS,
            "modules": sorted(modules),
            "required_root_objects": list(REQUIRED_ROOT_OBJECTS),
            "bo_forbidden_public_text": ["Tarefas HFF", "On-call esta semana"],
        },
        "rendered": rendered,
        "warnings": warnings,
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Postflight mecanico da rotina Painel HFF.")
    parser.add_argument("--json", required=True, help="JSON canonico final aprovado pelo LLM.")
    parser.add_argument("--preflight-json", help="Manifesto do preflight_hff.py desta corrida, para cruzamento (recomendado sempre).")
    parser.add_argument("--module", choices=("both", "hff", "bo"), default="both", help="Outputs a renderizar/publicar.")
    parser.add_argument("--workdir", help="Pasta de trabalho para HTMLs gerados.")
    parser.add_argument("--hff-html", help="Destino HTML HFF gerado.")
    parser.add_argument("--bo-html", help="Destino HTML BO gerado.")
    parser.add_argument("--manifest", default=str(ROUTINE_DIR / "hff_postflight.json"), help="Manifesto postflight.")
    parser.add_argument("--publish", action="store_true", help="Copia para personal-system, faz commit e push.")
    parser.add_argument("--repo", default=str(REPO_DIR), help="Checkout local do repositorio personal-system.")
    parser.add_argument("--commit-message", help="Mensagem de commit.")
    args = parser.parse_args()

    try:
        result = postflight(args)
    except PostflightError as exc:
        result = {
            "schema_version": SCHEMA_VERSION,
            "generated_at": now_lisbon().isoformat(timespec="seconds"),
            "routine": "painel_hff",
            "status": "fail",
            "warnings": [],
            "errors": [str(exc)],
        }

    manifest_path = Path(args.manifest)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "manifest": str(manifest_path)}, ensure_ascii=False))
    return 0 if result["status"] != "fail" else 1


if __name__ == "__main__":
    raise SystemExit(main())
