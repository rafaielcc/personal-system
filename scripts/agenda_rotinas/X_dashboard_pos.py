#!/usr/bin/env python3
"""Validate, render and publish one locally generated Dashboard JSON."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from pathlib import Path

AGENDA = Path(r"G:\My Drive\Claude_PRJ\Agenda")
OUTPUTS = AGENDA / "X_Outputs"
TEMPLATE = AGENDA / "Templates" / "dashboard" / "template.html"
RENDER = AGENDA / "Templates" / "dashboard" / "render.py"
REPO = Path(r"C:\Users\rafai\Documents\github\personal-system")
SITE = REPO / "agendas" / "index.html"


def latest_pre() -> Path:
    candidates = [p for p in OUTPUTS.glob("*_dashboard.json") if not p.name.endswith("_final_dashboard.json")]
    if not candidates:
        raise RuntimeError("Nenhum preflight Dashboard encontrado")
    return max(candidates, key=lambda p: p.stat().st_mtime)


def run(*cmd: str) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(cmd, cwd=REPO, text=True, capture_output=True, check=False)
    if result.returncode:
        detail = (result.stderr or result.stdout).strip()
        raise RuntimeError(f"{' '.join(cmd)} falhou: {detail}")
    return result


def validate(pre: dict, final: dict) -> None:
    if not final.get("meta", {}).get("date_label"):
        raise ValueError("Falta meta.date_label")
    if final.get("counts") != pre.get("counts"):
        raise ValueError("As contagens nao correspondem ao preflight")
    for slot in ("08h", "16h", "20h"):
        source = pre.get("weather", {}).get(slot, {})
        result = final.get("weather", {}).get(slot, {})
        for field in ("icon", "temp"):
            if result.get(field) != source.get(field):
                raise ValueError(f"weather.{slot}.{field} diverge do preflight")
        for field in ("activity_icon", "activity_title"):
            if field not in result:
                raise ValueError(f"Falta weather.{slot}.{field}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pre-json", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    pre_path = args.pre_json or latest_pre()
    final_path = pre_path.with_name(pre_path.stem.replace("_dashboard", "_final_dashboard") + ".json")
    if not final_path.exists() or final_path.stat().st_mtime < pre_path.stat().st_mtime:
        raise RuntimeError(f"JSON final nao gerado nesta corrida: {final_path}")
    pre = json.loads(pre_path.read_text(encoding="utf-8"))
    final = json.loads(final_path.read_text(encoding="utf-8"))
    validate(pre, final)

    if not RENDER.exists() or not TEMPLATE.exists():
        raise FileNotFoundError("Template ou render.py do Dashboard indisponivel")
    rendered = final_path.with_suffix(".html")
    subprocess.run(["python", str(RENDER), str(final_path), str(TEMPLATE), str(rendered)], check=True)
    if not rendered.exists() or rendered.stat().st_size < 1000:
        raise RuntimeError("Render do Dashboard vazio ou incompleto")
    if args.dry_run:
        print(f"OK dry-run: {rendered}")
        return

    if run("git", "status", "--porcelain", "--", "agendas/index.html").stdout.strip():
        raise RuntimeError("agendas/index.html tem alteracoes locais; nao vou sobrescreve-las")
    shutil.copyfile(rendered, SITE)
    run("git", "add", "--", "agendas/index.html")
    changed = subprocess.run(
        ["git", "diff", "--cached", "--quiet", "--", "agendas/index.html"],
        cwd=REPO, check=False,
    ).returncode
    if changed == 0:
        raise RuntimeError("Dashboard renderizado sem alteracoes; publicacao nao confirmada")
    if changed != 1:
        raise RuntimeError(f"Nao consegui comparar o Dashboard renderizado (git diff {changed})")
    run("git", "commit", "-m", f"Update dashboard {pre['data_alvo']}", "--", "agendas/index.html")
    run("git", "push", "origin", "HEAD:main")
    print(f"OK: Dashboard publicado em {run('git', 'rev-parse', '--short', 'HEAD').stdout.strip()}")


if __name__ == "__main__":
    main()
