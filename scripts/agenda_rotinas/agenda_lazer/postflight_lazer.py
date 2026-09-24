from __future__ import annotations

import argparse
import importlib.util
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
ROUTINE_DIR = AGENDA_ROOT / "X_Rotinas_Python" / "Agenda_Lazer"
OUTPUT_DIR = AGENDA_ROOT / "X_Outputs" / "lazer"
TEMPLATE_PATH = AGENDA_ROOT / "Templates" / "agenda_lazer" / "template_v9.html"
RENDER_PATH = AGENDA_ROOT / "Templates" / "agenda_lazer" / "render_v8.py"
REPO_DIR = Path(r"C:\Users\rafai\Documents\github\personal-system")
REPO_LAZER_PATH = Path("agendas") / "lazer" / "index.html"
PUBLIC_URL = "https://personal-system-hs5.pages.dev/lazer/"
WINDOW_DAYS = 15
RADAR_DAYS = 60
VALID_CATEGORIES = {"tv", "streaming", "cinema_indoor", "cinema_outdoor", "meetup", "culture", "books", "gastro", "escape", "radar"}
REQUIRED_EVENT_FIELDS = ("id", "category", "title", "date_label", "description")
REQUIRED_ROOT_FIELDS = ("meta", "sources", "event_candidates", "events", "futuro_guardado", "summary", "validation")
ALLOWED_ROOT_FIELDS = set(REQUIRED_ROOT_FIELDS)
UNDATED_CATEGORIES = {"streaming", "books", "gastro", "escape"}
REQUIRED_HTML_TEXT = ("Agenda de Lazer", "Highlights")
MINIMUMS = {"meetup": 8, "cinema_indoor": 4, "gastro": 5, "tv_streaming": 10, "books": 5, "escape": 6, "sports": 1}
SPORT_TERMS = ("activehive", "luma", "meetup", "voleibol", "volleyball", "beach tennis", "hiking", "caminhada")


class PostflightError(Exception):
    pass


def now_lisbon() -> datetime:
    return datetime.now(TIMEZONE)


def parse_date(value: Any) -> date | None:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if not isinstance(value, str):
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def file_info(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {"exists": False, "path": None}
    exists = path.exists()
    info: dict[str, Any] = {"exists": exists, "path": str(path)}
    if exists:
        stat = path.stat()
        info.update({"name": path.name, "size_bytes": stat.st_size, "mtime": datetime.fromtimestamp(stat.st_mtime, TIMEZONE).isoformat(timespec="seconds")})
    return info


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        raise PostflightError(f"JSON invalido em {path}: {type(exc).__name__}: {exc}") from exc


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def is_within(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def norm(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().lower())


def load_render_validator(render_path: Path):
    spec = importlib.util.spec_from_file_location("agenda_lazer_render", render_path)
    if spec is None or spec.loader is None:
        raise PostflightError(f"Nao foi possivel importar render: {render_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    validator = getattr(module, "validate_canonical", None)
    if not callable(validator):
        raise PostflightError(f"Render sem validate_canonical(): {render_path}")
    return validator


def has_threshold_explanation(validation: Any, area: str) -> bool:
    if not isinstance(validation, dict):
        return False
    blob = json.dumps(validation, ensure_ascii=False).lower()
    return area.lower() in blob and any(word in blob for word in ("fallback", "motivo", "abaixo", "bloque", "lacuna"))


def validate_root(data: Any, errors: list[str], warnings: list[str]) -> None:
    if not isinstance(data, dict):
        errors.append("raiz do JSON canonico deve ser objecto")
        return
    for key in REQUIRED_ROOT_FIELDS:
        if key not in data:
            errors.append(f"campo raiz obrigatorio em falta: {key}")
    unexpected = sorted(set(data) - ALLOWED_ROOT_FIELDS)
    if unexpected:
        errors.append("chaves de topo inesperadas: " + ", ".join(unexpected))
    missing = sorted(ALLOWED_ROOT_FIELDS - set(data))
    if missing:
        errors.append("chaves de topo em falta: " + ", ".join(missing))
    if not isinstance(data.get("meta"), dict):
        errors.append("meta deve ser objecto")
    else:
        for key in ("schema_version", "run_id", "date", "periodo_inicio", "periodo_fim", "hoje", "calendario_pessoal"):
            if key not in data["meta"]:
                errors.append(f"meta.{key} em falta")
        if not isinstance(data["meta"].get("calendario_pessoal", []), list):
            errors.append("meta.calendario_pessoal deve ser lista")
    if not isinstance(data.get("sources"), dict):
        errors.append("sources deve ser objecto")
    if not isinstance(data.get("events"), list):
        errors.append("events deve ser lista")
    if not isinstance(data.get("event_candidates", []), list):
        errors.append("event_candidates deve ser lista")
    if not isinstance(data.get("futuro_guardado", []), list):
        errors.append("futuro_guardado deve ser lista")
    if not isinstance(data.get("validation"), dict):
        errors.append("validation deve ser objecto")
    elif not any(k in data["validation"] for k in ("debug_view", "checklist", "threshold_gaps", "preflight_status")):
        warnings.append("validation nao contem debug_view/checklist/threshold_gaps explicitos")
    if not isinstance(data.get("summary"), dict):
        errors.append("summary deve ser objecto")
    for key in data:
        if str(key).startswith("_llm") or str(key).startswith("_preflight"):
            errors.append(f"campo auxiliar deve ser removido antes do postflight: {key}")


def validate_events(data: dict[str, Any], target: date | None, window_days: int, errors: list[str], warnings: list[str]) -> dict[str, int]:
    counts = Counter()
    ids = Counter()
    dupes = Counter()
    events = data.get("events", [])
    for idx, ev in enumerate(events):
        if not isinstance(ev, dict):
            errors.append(f"events[{idx}] deve ser objecto")
            continue
        for field in REQUIRED_EVENT_FIELDS:
            if ev.get(field) in (None, ""):
                errors.append(f"events[{idx}] falta campo obrigatorio: {field}")
        if ev.get("id"):
            ids[str(ev["id"])] += 1
        cat = ev.get("category")
        if cat not in VALID_CATEGORIES:
            errors.append(f"events[{idx}] categoria invalida: {cat!r}")
            continue
        counts[str(cat)] += 1
        if "date" not in ev:
            errors.append(f"events[{idx}] deve conter a chave date (pode ser null em categorias evergreen)")
        d = parse_date(ev.get("date"))
        if d is None and cat not in UNDATED_CATEGORIES:
            errors.append(f"events[{idx}] date invalida/ausente para categoria {cat}: {ev.get('date')!r}")
        elif d is not None and target:
            normal_end = target + timedelta(days=window_days - 1)
            radar_end = target + timedelta(days=RADAR_DAYS - 1)
            if d < target:
                errors.append(f"events[{idx}] contem data passada face ao alvo: {d.isoformat()}")
            elif cat == "radar" and d > radar_end:
                warnings.append(f"radar fora da janela de {RADAR_DAYS} dias: {ev.get('title')}")
            elif cat != "radar" and d > normal_end:
                warnings.append(f"evento fora da janela principal: {ev.get('title')} ({d.isoformat()})")
        dupes[(norm(ev.get("title")), str(ev.get("date") or ""), norm(ev.get("location")))] += 1
        if ev.get("link") is not None and not str(ev.get("link")).startswith(("http://", "https://")):
            warnings.append(f"events[{idx}] link nao parece URL http(s): {ev.get('link')!r}")
        if ev.get("logistics") not in (None, "") and not isinstance(ev.get("logistics"), dict):
            errors.append(f"events[{idx}].logistics deve ser objecto quando presente")
        for field in ("highlight", "confirmed", "saved", "elevado"):
            if field in ev and not isinstance(ev.get(field), bool):
                errors.append(f"events[{idx}].{field} deve ser booleano")
    for event_id, count in ids.items():
        if count > 1:
            errors.append(f"id duplicado em events[]: {event_id}")
    duplicate_count = sum(count - 1 for count in dupes.values() if count > 1)
    if duplicate_count:
        warnings.append(f"{duplicate_count} possivel(is) duplicado(s) por titulo/data/local em events[]")
    return dict(counts)


def validate_thresholds(data: dict[str, Any], counts: dict[str, int], errors: list[str], warnings: list[str], allow_warnings: bool) -> None:
    validation = data.get("validation", {})
    sports_count = 0
    for ev in data.get("events", []):
        blob = norm(str(ev.get("title", "")) + " " + str(ev.get("description", "")) + " " + str(ev.get("location", "")))
        if any(term in blob for term in SPORT_TERMS):
            sports_count += 1
    basis = {"meetup": counts.get("meetup", 0), "cinema_indoor": counts.get("cinema_indoor", 0), "gastro": counts.get("gastro", 0), "tv_streaming": counts.get("tv", 0) + counts.get("streaming", 0), "books": counts.get("books", 0), "escape": counts.get("escape", 0), "sports": sports_count}
    for area, minimum in MINIMUMS.items():
        count = basis.get(area, 0)
        if count >= minimum:
            continue
        message = f"threshold abaixo do minimo: {area} {count}/{minimum}"
        if allow_warnings or has_threshold_explanation(validation, area):
            warnings.append(message)
        else:
            errors.append(message + " sem justificacao/fallback em validation")


def validate_canonical(data: Any, render_path: Path, target: date | None, window_days: int, allow_threshold_warnings: bool) -> tuple[list[str], list[str], dict[str, int]]:
    errors: list[str] = []
    warnings: list[str] = []
    counts: dict[str, int] = {}
    validate_root(data, errors, warnings)
    if errors:
        return errors, warnings, counts
    render_validator = load_render_validator(render_path)
    errors.extend(render_validator(data))
    counts = validate_events(data, target, window_days, errors, warnings)
    validate_thresholds(data, counts, errors, warnings, allow_threshold_warnings)
    return errors, warnings, counts


def run_command(args: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=str(cwd) if cwd else None, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)


def run_render(render_path: Path, input_json: Path, template_path: Path, output_html: Path) -> dict[str, Any]:
    output_html.parent.mkdir(parents=True, exist_ok=True)
    proc = run_command([sys.executable, str(render_path), str(input_json), str(template_path), str(output_html)])
    if proc.returncode != 0:
        raise PostflightError(f"render Lazer falhou (exit {proc.returncode})\nSTDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}")
    return {"returncode": proc.returncode, "stdout": proc.stdout.strip(), "stderr": proc.stderr.strip()}


def validate_html(path: Path) -> list[str]:
    if not path.exists() or path.stat().st_size == 0:
        return [f"HTML nao criado ou vazio: {path}"]
    raw = path.read_text(encoding="utf-8", errors="replace")
    html = re.sub(r"<!--.*?-->", "", raw, flags=re.DOTALL)
    errors: list[str] = []
    tokens = sorted(set(re.findall(r"\{\{[^{}]+\}\}", html)))
    if tokens:
        errors.append("HTML contem tokens residuais: " + ", ".join(tokens[:20]))
    blocks = sorted(set(re.findall(r"<!--/?(?:CARD|SECTION:[a-z_]+|PILL:[a-z_]+)-->", raw)))
    if blocks:
        errors.append("HTML contem blocos residuais: " + ", ".join(blocks[:20]))
    for text in REQUIRED_HTML_TEXT:
        if text not in raw:
            errors.append(f"HTML sem texto esperado: {text}")
    if len(raw) < 4000:
        errors.append(f"HTML demasiado pequeno: {len(raw)} bytes")
    return errors


def copy_to_repo(html_path: Path, repo: Path) -> Path:
    if not repo.exists() or not (repo / ".git").exists():
        raise PostflightError(f"checkout git nao encontrado: {repo}")
    target = repo / REPO_LAZER_PATH
    if not is_within(target, repo):
        raise PostflightError(f"destino fora do repo: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(html_path, target)
    return target


def git_publish(repo: Path, message: str) -> dict[str, Any]:
    rel_path = str(REPO_LAZER_PATH).replace("\\", "/")
    branch = run_command(["git", "branch", "--show-current"], cwd=repo)
    if branch.returncode != 0:
        raise PostflightError(f"nao foi possivel identificar o branch actual: {branch.stderr.strip()}")
    if branch.stdout.strip() != "main":
        raise PostflightError(
            f"publicacao recusada fora de main (branch actual: {branch.stdout.strip() or '(detached)'})"
        )
    staged = run_command(["git", "diff", "--cached", "--name-only"], cwd=repo)
    if staged.returncode != 0:
        raise PostflightError(f"nao foi possivel inspeccionar staging: {staged.stderr.strip()}")
    unrelated = [line.strip() for line in staged.stdout.splitlines() if line.strip() and line.strip() != rel_path]
    if unrelated:
        raise PostflightError("existem ficheiros alheios ja staged; publicacao recusada: " + ", ".join(unrelated))
    commands = [["git", "add", rel_path]]
    results = []
    for cmd in commands:
        proc = run_command(cmd, cwd=repo)
        item = {"cmd": cmd, "returncode": proc.returncode, "stdout": proc.stdout.strip(), "stderr": proc.stderr.strip()}
        results.append(item)
        if proc.returncode != 0:
            raise PostflightError(f"comando falhou: {' '.join(cmd)}\n{proc.stderr.strip()}")
    changed = run_command(["git", "diff", "--cached", "--quiet", "--", rel_path], cwd=repo)
    if changed.returncode == 0:
        return {"commands": results, "no_change": True}
    if changed.returncode != 1:
        raise PostflightError(f"git diff --cached falhou: {changed.stderr.strip()}")
    for cmd in (["git", "commit", "-m", message], ["git", "push", "origin", "main"]):
        proc = run_command(cmd, cwd=repo)
        item = {"cmd": cmd, "returncode": proc.returncode, "stdout": proc.stdout.strip(), "stderr": proc.stderr.strip()}
        results.append(item)
        if proc.returncode != 0:
            raise PostflightError(f"comando falhou: {' '.join(cmd)}\n{proc.stderr.strip()}")
    return {"commands": results, "no_change": False}


def postflight(args: argparse.Namespace) -> dict[str, Any]:
    generated = now_lisbon()
    errors: list[str] = []
    warnings: list[str] = []
    target = parse_date(args.date) if args.date else None
    if args.date and target is None:
        errors.append("--date deve estar em YYYY-MM-DD")
    input_json = Path(args.json)
    template = Path(args.template) if args.template else TEMPLATE_PATH
    render = Path(args.render) if args.render else RENDER_PATH
    stamp = target.isoformat() if target else generated.strftime("%Y-%m-%d_%H%M%S")
    output_html = Path(args.html) if args.html else OUTPUT_DIR / f"lazer_index_{stamp}.html"
    manifest = Path(args.manifest) if args.manifest else OUTPUT_DIR / f"lazer_postflight_{stamp}.json"
    result: dict[str, Any] = {"schema_version": SCHEMA_VERSION, "generated_at": generated.isoformat(timespec="seconds"), "routine": "agenda_lazer", "status": "unknown", "inputs": {"json": file_info(input_json), "template": file_info(template), "render": file_info(render)}, "outputs": {}, "checks": {"target_date": target.isoformat() if target else None, "window_days": args.window_days, "allow_threshold_warnings": args.allow_threshold_warnings}, "actions": {"rendered": False, "copied_to_repo": False, "published": False}, "warnings": warnings, "errors": errors, "manifest_path": str(manifest)}
    for name, path in (("json", input_json), ("template", template), ("render", render)):
        if not path.exists():
            errors.append(f"{name} em falta: {path}")
    if errors:
        result["status"] = "blocked"
        return result
    try:
        data = load_json(input_json)
        if target is None and isinstance(data, dict) and isinstance(data.get("meta"), dict):
            target = parse_date(data["meta"].get("date"))
            result["checks"]["target_date"] = target.isoformat() if target else None
        validation_errors, validation_warnings, counts = validate_canonical(data, render, target, args.window_days, args.allow_threshold_warnings)
        errors.extend(validation_errors)
        warnings.extend(validation_warnings)
        result["checks"]["event_counts"] = counts
        if errors:
            result["status"] = "blocked"
            return result
        result["render"] = run_render(render, input_json, template, output_html)
        result["actions"]["rendered"] = True
        result["outputs"]["html"] = file_info(output_html)
        errors.extend(validate_html(output_html))
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
            message = args.commit_message or f"[agenda] actualiza lazer {generated.strftime('%Y-%m-%d %H:%M')}"
            result["publish"] = git_publish(repo, message)
            result["actions"]["published"] = True
            result["public_url"] = PUBLIC_URL
        result["status"] = "warn" if warnings else "ok"
        return result
    except Exception as exc:
        errors.append(f"postflight exception: {type(exc).__name__}: {exc}")
        result["status"] = "blocked"
        return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Postflight local mecanico da Agenda de Lazer.")
    parser.add_argument("--json", required=True)
    parser.add_argument("--date")
    parser.add_argument("--window-days", type=int, default=WINDOW_DAYS)
    parser.add_argument("--template")
    parser.add_argument("--render")
    parser.add_argument("--html")
    parser.add_argument("--manifest")
    parser.add_argument("--repo")
    parser.add_argument("--copy-to-repo", action="store_true")
    parser.add_argument("--publish", action="store_true")
    parser.add_argument("--commit-message")
    parser.add_argument("--allow-threshold-warnings", action="store_true")
    args = parser.parse_args()
    if args.publish:
        args.copy_to_repo = True
    result = postflight(args)
    manifest = Path(result.pop("manifest_path"))
    write_json(manifest, result)
    print(f"OK: manifesto postflight -> {manifest}")
    if result["status"] == "blocked":
        print("ERROS:")
        for error in result["errors"]:
            print(f"- {error}")
        return 2
    print(f"OK: Lazer HTML -> {result['outputs']['html']['path']}")
    if result["warnings"]:
        print("AVISOS:")
        for warning in result["warnings"]:
            print(f"- {warning}")
    if result["actions"].get("copied_to_repo"):
        print(f"OK: copiado para repo -> {result['outputs']['repo_html']['path']}")
    if result["actions"].get("published"):
        print(f"OK: publicado -> {PUBLIC_URL}")
    return 0 if result["status"] in {"ok", "warn"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
