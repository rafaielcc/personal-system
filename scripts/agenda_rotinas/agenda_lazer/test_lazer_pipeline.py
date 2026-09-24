from __future__ import annotations

import copy
import json
import subprocess
import sys
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

import postflight_lazer as postflight


HERE = Path(__file__).resolve().parent
RENDER = HERE / "render_v8.py"
TEMPLATE = HERE / "template_v9.html"
TARGET = date(2026, 9, 24)


def event(event_id: str, category: str, title: str, offset: int | None) -> dict:
    when = TARGET + timedelta(days=offset) if offset is not None else None
    return {
        "id": event_id,
        "category": category,
        "title": title,
        "date": when.isoformat() if when else None,
        "date_label": f"Dia {when.day}" if when else "Disponível agora",
        "description": f"Descrição factual para {title}.",
        "highlight": event_id.endswith("01"),
    }


def valid_canonical() -> dict:
    events: list[dict] = []
    counter = 1

    def add(category: str, count: int, *, dated: bool, prefix: str) -> None:
        nonlocal counter
        for index in range(count):
            title = f"{prefix} {index + 1}"
            if category == "meetup" and index == 0:
                title = "ActiveHive voleibol"
            events.append(event(f"ev{counter:03d}", category, title, index if dated else None))
            counter += 1

    add("meetup", 8, dated=True, prefix="Meetup")
    add("cinema_indoor", 4, dated=True, prefix="Cinema")
    add("gastro", 5, dated=False, prefix="Restaurante")
    add("streaming", 10, dated=False, prefix="Streaming")
    add("books", 5, dated=False, prefix="Livro")
    add("escape", 6, dated=False, prefix="Escapadinha")

    return {
        "meta": {
            "schema_version": "2.0",
            "run_id": "test_2026_09_24",
            "date": TARGET.isoformat(),
            "periodo_inicio": TARGET.isoformat(),
            "periodo_fim": (TARGET + timedelta(days=14)).isoformat(),
            "periodo_label": "24 Set a 8 Out",
            "hoje": TARGET.isoformat(),
            "calendario_pessoal": [],
        },
        "sources": {"test": {"ok": True}},
        "event_candidates": copy.deepcopy(events),
        "events": events,
        "futuro_guardado": [],
        "summary": {"alerta_urgente": "", "coverage_status": "ready"},
        "validation": {
            "preflight_status": "ready",
            "threshold_gaps": [],
            "debug_view": {"llm_notes": []},
            "checklist": {"status": "complete", "items": []},
        },
    }


class LazerPipelineTest(unittest.TestCase):
    def test_valid_schema_renders_with_undated_evergreen_items(self) -> None:
        data = valid_canonical()
        errors, warnings, counts = postflight.validate_canonical(
            data, RENDER, TARGET, 15, False
        )
        self.assertEqual(errors, [])
        self.assertEqual(warnings, [])
        self.assertEqual(counts["streaming"], 10)

        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            input_json = tmp_dir / "final.json"
            output_html = tmp_dir / "index.html"
            input_json.write_text(
                json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            proc = subprocess.run(
                [sys.executable, str(RENDER), str(input_json), str(TEMPLATE), str(output_html)],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            self.assertEqual(postflight.validate_html(output_html), [])

    def test_unknown_root_key_is_blocked(self) -> None:
        data = valid_canonical()
        data["_llm_handoff"] = {}
        errors, _, _ = postflight.validate_canonical(data, RENDER, TARGET, 15, False)
        self.assertTrue(any("inesperadas" in error for error in errors))

    def test_undated_non_evergreen_item_is_blocked(self) -> None:
        data = valid_canonical()
        data["events"][0]["date"] = None
        errors, _, _ = postflight.validate_canonical(data, RENDER, TARGET, 15, False)
        self.assertTrue(any("date invalida/ausente" in error for error in errors))


if __name__ == "__main__":
    unittest.main(verbosity=2)
