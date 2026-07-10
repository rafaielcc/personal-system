#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
render.py — Render Layer do Briefing Diário (Modulo Briefing / Rotina de Publicação)

Le o JSON canonico (produzido pela LLM, schema Seccao 7 de BRIEFING_DIARIO_v12.0.md)
+ template.html (estatico, sem logica de negocio) e produz o index.html final por
substituicao mecanica de texto. Nao usa Jinja2 nem qualquer dependencia externa —
apenas a stdlib do Python, para correr sem instalacao em qualquer sandbox bash.
Segue o mesmo padrao do render.py da Agenda de Lazer.

A LLM nunca volta a escrever HTML livremente: a unica camada onde a LLM exerce
juizo e o JSON canonico. Este script e puramente mecanico e deve produzir o
mesmo HTML sempre que receber o mesmo JSON + template.

Pressupostos sobre sub-campos nao detalhados na Seccao 7 (documentar ao promover
esta rotina, para alinhar com o modulo Painel HFF quando o seu render.py existir):
  - hff: {"tipo_dia": str, "resumo": str, "cirurgias_resumo": str}
  - email.<secao>[]: {"remetente": str, "assunto": str, "resumo": str,
      "reagendado_para": str (snoozed), "tipo_badge": str (pediatric_surgery)}
  - email.events[]: {"titulo": str, "date_label": str, "time": str,
      "status": str, "link": str|null}
  - calendario.dias[].itens[]: {"tipo": "evento"|"tarefa", "titulo": str}

Uso:
    python3 render.py <input.json> <template.html> <output.html>

Codigo de saida 0 = sucesso. Qualquer falha de validacao do JSON aborta
com mensagem clara (nao tenta "adivinhar" campos em falta).
"""

import sys
import json
import re
import html as html_lib
from datetime import datetime

MESES_PT = {
    1: "Janeiro", 2: "Fevereiro", 3: "Março", 4: "Abril", 5: "Maio", 6: "Junho",
    7: "Julho", 8: "Agosto", 9: "Setembro", 10: "Outubro", 11: "Novembro", 12: "Dezembro",
}
MESES_ABR = {
    1: "Jan", 2: "Fev", 3: "Mar", 4: "Abr", 5: "Mai", 6: "Jun",
    7: "Jul", 8: "Ago", 9: "Set", 10: "Out", 11: "Nov", 12: "Dez",
}

TASK_TYPE_CLASS = {
    "todoist": "",
    "sugestao": "ti-sugestao",
    "habito": "ti-habito",
    "desporto": "ti-desporto",
}

BADGE_CLASS = {
    "special": "cb-special",
    "holiday": "cb-holiday",
    "sport": "cb-sport",
    "sigic": "cb-sigic",
    "show": "cb-show",
}

EMAIL_SIMPLE_SECTIONS = ["urgente", "importante", "snoozed", "pediatric_surgery", "ulsasi"]


# --------------------------------------------------------------------------
# Validacao
# --------------------------------------------------------------------------
def validate_canonical(data):
    errors = []

    meta = data.get("meta")
    if not isinstance(meta, dict):
        errors.append("Falta o objecto 'meta'.")
        return errors
    for field in ("date", "weekday", "mode"):
        if not meta.get(field):
            errors.append(f"meta.{field} em falta.")
    mode = meta.get("mode")
    if mode not in ("A", "B"):
        errors.append(f"meta.mode invalido: {mode!r} (esperado 'A' ou 'B').")

    hoje = data.get("hoje")
    if not isinstance(hoje, dict) or not hoje.get("audio_script"):
        errors.append("hoje.audio_script em falta.")
    if not isinstance(hoje, dict) or not isinstance(hoje.get("proximos_3_dias"), list):
        errors.append("hoje.proximos_3_dias em falta (lista).")

    tarefas = data.get("tarefas")
    if not isinstance(tarefas, dict) or not isinstance(tarefas.get("board"), list):
        errors.append("tarefas.board em falta (lista).")
    if not isinstance(tarefas, dict) or not isinstance(tarefas.get("cards"), list):
        errors.append("tarefas.cards em falta (lista).")

    calendario = data.get("calendario")
    if not isinstance(calendario, dict) or not calendario.get("mes"):
        errors.append("calendario.mes em falta.")
    if not isinstance(calendario, dict) or not isinstance(calendario.get("dias"), list):
        errors.append("calendario.dias em falta (lista).")

    email = data.get("email")
    if not isinstance(email, dict):
        errors.append("email em falta.")
    else:
        for key in EMAIL_SIMPLE_SECTIONS + ["informativo", "ruido", "tarefas_sem_data", "events"]:
            if not isinstance(email.get(key), list):
                errors.append(f"email.{key} em falta (lista).")

    tempo = data.get("tempo")
    if not isinstance(tempo, dict) or not isinstance(tempo.get("tabela_7dias"), list):
        errors.append("tempo.tabela_7dias em falta (lista).")
    if not isinstance(tempo, dict) or not isinstance(tempo.get("janelas"), list):
        errors.append("tempo.janelas em falta (lista).")

    rotina = data.get("rotina")
    if not isinstance(rotina, dict) or not isinstance(rotina.get("janelas"), list):
        errors.append("rotina.janelas em falta (lista).")
    else:
        ids_presentes = {j.get("id") for j in rotina["janelas"]}
        for req_id in ("matinal", "processamento", "descompressao"):
            if req_id not in ids_presentes:
                errors.append(f"rotina.janelas sem janela id={req_id!r}.")

    if mode == "A" and not isinstance(data.get("hff"), dict):
        errors.append("meta.mode=='A' mas 'hff' em falta ou nao e objecto.")
    if mode == "B" and data.get("hff") is not None:
        errors.append("meta.mode=='B' mas 'hff' nao e null (deve omitir a tab).")

    return errors


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------
def esc(text):
    return html_lib.escape(str(text) if text is not None else "", quote=True)


def fmt_data_label(date_str, weekday):
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    return f"{weekday.capitalize()}, {dt.day} {MESES_ABR[dt.month]}"


def fmt_mes_ano(mes_str):
    dt = datetime.strptime(mes_str, "%Y-%m")
    return f"{MESES_PT[dt.month]} {dt.year}"


def extract_block(template, marker):
    pattern = re.compile(r"<!--" + re.escape(marker) + r"-->(.*?)<!--/" + re.escape(marker) + r"-->", re.DOTALL)
    m = pattern.search(template)
    if not m:
        return None, template
    full_match = m.group(0)
    inner = m.group(1)
    stripped = template.replace(full_match, "{{__PLACEHOLDER_" + marker + "__}}", 1)
    return inner, stripped


def put_block(template, marker, content):
    return template.replace("{{__PLACEHOLDER_" + marker + "__}}", content)


# --------------------------------------------------------------------------
# Secoes
# --------------------------------------------------------------------------
def build_banner(hoje):
    alertas = hoje.get("alertas") or []
    feriado = hoje.get("feriado")
    ordem = {"urgente": 0, "importante": 1, "info": 2}
    if alertas:
        top = sorted(alertas, key=lambda a: ordem.get(a.get("nivel"), 3))[0]
        nivel = top.get("nivel", "info")
        cls = {"urgente": "banner-alert", "importante": "banner-warn", "info": "banner-info"}.get(nivel, "")
        icon = {"urgente": "🚨", "importante": "⚠️", "info": "ℹ️"}.get(nivel, "ℹ️")
        texto = top.get("texto", "")
        if feriado:
            texto = f"{esc(feriado)} — {esc(texto)}"
        else:
            texto = esc(texto)
        return cls, icon, texto
    if feriado:
        return "banner-warn", "🎌", esc(feriado)
    return "", "✅", "Sem alertas hoje"


def build_day3_cards(dias):
    parts = []
    for d in dias:
        parts.append(
            "\n          <div class=\"day3-card\">\n"
            f"            <div class=\"d3-head\"><span class=\"d3-name\">{esc(d.get('dia',''))}</span>"
            f"<span class=\"d3-date\">{esc(d.get('weekday',''))}</span></div>\n"
            f"            <p class=\"muted\">{esc(d.get('habito') or 'Sem hábito específico')}</p>\n"
            "            <div class=\"d3-pills\">\n"
            f"              <span class=\"pill-mini pm-event\">📅 {len(d.get('eventos') or [])} eventos</span>\n"
            f"              <span class=\"pill-mini pm-task\">✅ {len(d.get('tarefas') or [])} tarefas</span>\n"
            f"              <span class=\"pill-mini pm-bo\" style=\"display:{'inline-flex' if d.get('bo') else 'none'}\">🏥 BO</span>\n"
            f"              <span class=\"pill-mini pm-sigic\" style=\"display:{'inline-flex' if d.get('sigic') else 'none'}\">🕒 SIGIC</span>\n"
            "            </div>\n"
            "          </div>\n"
        )
    return "".join(parts)


def build_board_cols(board):
    parts = []
    for b in board:
        parts.append(
            "\n          <div class=\"board3-col\">\n"
            f"            <div class=\"b3-day\">{esc(b.get('dia',''))}</div>\n"
            f"            <div class=\"b3-total\">{b.get('todoist_total',0)}</div>\n"
            f"            <div class=\"b3-split\">💼 {b.get('todoist_trabalho',0)} · 👤 {b.get('todoist_pessoal',0)}</div>\n"
            f"            <div class=\"b3-extra\">💡 {b.get('sugestoes',0)} · 🌿 {b.get('habitos',0)} · 🏃 {b.get('desporto',0)}</div>\n"
            "          </div>\n"
        )
    return "".join(parts)


def build_task_days(cards, item_tpl):
    parts = []
    for c in cards:
        itens = c.get("itens") or []
        total = len(itens)
        done = sum(1 for it in itens if it.get("feito"))
        if total == 0 or done == 0:
            css_class = "tc-red"
        elif done == total:
            css_class = "tc-green"
        else:
            css_class = "tc-yellow"
        items_html = []
        for it in itens:
            row = item_tpl
            row = row.replace("{{TI_CLASS}}", TASK_TYPE_CLASS.get(it.get("tipo"), ""))
            row = row.replace("{{TI_CHECKED}}", "checked" if it.get("feito") else "")
            row = row.replace("{{TI_TEXTO}}", esc(it.get("texto", "")))
            items_html.append(row)
        parts.append(
            f"\n        <div class=\"task-section-label\">{esc(c.get('dia',''))}</div>\n"
            f"        <div class=\"task-card {css_class}\" data-task-card>\n"
            f"          <div class=\"tc-date\">{done}/{total} concluídas</div>\n"
            + "".join(items_html) +
            "        </div>\n"
        )
    return "".join(parts)


def build_cal_cells(dias, today_str, cell_tpl):
    parts = []
    for d in dias:
        date_str = d.get("date", "")
        try:
            daynum = datetime.strptime(date_str, "%Y-%m-%d").day
        except ValueError:
            daynum = "?"
        badges = d.get("badges") or []
        badge_class = BADGE_CLASS.get(badges[0], "") if badges else ""
        n_ev = d.get("eventos_count", 0)
        n_tk = d.get("tarefas_count", 0)
        cell = cell_tpl
        cell = cell.replace("{{CAL_TODAY_CLASS}}", "cal-today" if date_str == today_str else "")
        cell = cell.replace("{{CAL_DATE}}", esc(date_str))
        cell = cell.replace("{{CAL_DAYNUM}}", str(daynum))
        cell = cell.replace("{{CAL_BADGE_CLASS}}", badge_class)
        cell = cell.replace("{{CAL_BADGE_DISPLAY}}", "block" if badges else "none")
        cell = cell.replace("{{CAL_EVENT_PILL_DISPLAY}}", "flex" if n_ev else "none")
        cell = cell.replace("{{CAL_TASK_PILL_DISPLAY}}", "flex" if n_tk else "none")
        cell = cell.replace("{{CAL_N_EVENTOS}}", str(n_ev))
        cell = cell.replace("{{CAL_N_TAREFAS}}", str(n_tk))
        parts.append(cell)
    return "".join(parts)


def build_cal_detail(dias, today_str, weekday):
    today_day = next((d for d in dias if d.get("date") == today_str), None)
    if not today_day:
        return esc(f"{weekday.capitalize()}, {today_str}"), "Sem dados do dia.", "Sem dados do dia."
    itens = today_day.get("itens") or []
    eventos = [i.get("titulo", "") for i in itens if i.get("tipo") == "evento"]
    tarefas = [i.get("titulo", "") for i in itens if i.get("tipo") == "tarefa"]
    titulo = f"{weekday.capitalize()}, {today_str}"
    ev_txt = "; ".join(eventos) if eventos else "Sem eventos"
    tk_txt = "; ".join(tarefas) if tarefas else "Sem tarefas"
    return esc(titulo), esc(ev_txt), esc(tk_txt)


def fill_email_section(template, key, items, row_tpl, row_builder):
    inner, template = extract_block(template, f"EMAIL_SECTION:{key}")
    if inner is None:
        return template
    if not items:
        return put_block(template, f"EMAIL_SECTION:{key}", "")
    row_inner, section_stripped = extract_block(inner, f"EMAIL_ROW:{key}")
    if row_inner is None:
        rows_html = ""
    else:
        rows_html = "".join(row_builder(it, row_inner) for it in items)
        section_stripped = put_block(section_stripped, f"EMAIL_ROW:{key}", rows_html)
    return put_block(template, f"EMAIL_SECTION:{key}", section_stripped)


def row_simple(it, tpl, with_summary=True, extra=None):
    row = tpl
    row = row.replace("{{E_FROM}}", esc(it.get("remetente", "")))
    row = row.replace("{{E_SUBJ}}", esc(it.get("assunto", "")))
    if with_summary:
        row = row.replace("{{E_SUMMARY}}", esc(it.get("resumo", "")))
    if extra:
        for k, v in extra.items():
            row = row.replace(k, v)
    return row


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------
def main():
    if len(sys.argv) != 4:
        print("Uso: python3 render.py <input.json> <template.html> <output.html>")
        sys.exit(1)

    input_path, template_path, output_path = sys.argv[1], sys.argv[2], sys.argv[3]

    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    errors = validate_canonical(data)
    if errors:
        print("ERRO: JSON canónico inválido — render abortado.")
        for e in errors:
            print(" -", e)
        sys.exit(2)

    meta = data["meta"]
    hoje = data["hoje"]
    tarefas = data["tarefas"]
    calendario = data["calendario"]
    email = data["email"]
    tempo = data["tempo"]
    rotina = data["rotina"]
    hff = data.get("hff")

    with open(template_path, "r", encoding="utf-8") as f:
        template = f.read()

    # 1) Topbar
    data_label = fmt_data_label(meta["date"], meta["weekday"])
    template = template.replace("{{DATA_LABEL}}", esc(data_label))
    temp_actual = ""
    if tempo.get("janelas"):
        temp_actual = str(tempo["janelas"][0].get("temp", ""))
    template = template.replace("{{TEMP_ACTUAL}}", esc(temp_actual))
    tipo_dia = (hff or {}).get("tipo_dia") if meta["mode"] == "A" else "Sem HFF hoje"
    template = template.replace("{{TIPO_DIA}}", esc(tipo_dia or "—"))

    # 2) HFF tab/button (Modo A vs B)
    for marker in ("HFF_BTN", "HFF_PANEL"):
        inner, template = extract_block(template, marker)
        if inner is None:
            print(f"ERRO: template.html não contém o bloco <!--{marker}-->...<!--/{marker}-->")
            sys.exit(3)
        if meta["mode"] == "A":
            filled = inner
            filled = filled.replace("{{HFF_TIPO_DIA}}", esc(hff.get("tipo_dia", "")))
            filled = filled.replace("{{HFF_RESUMO}}", esc(hff.get("resumo", "")))
            filled = filled.replace("{{HFF_CIRURGIAS_RESUMO}}", esc(hff.get("cirurgias_resumo", "")))
            template = put_block(template, marker, filled)
        else:
            template = put_block(template, marker, "")

    # 3) Banner Hoje
    banner_class, banner_icon, banner_texto = build_banner(hoje)
    template = template.replace("{{BANNER_CLASS}}", banner_class)
    template = template.replace("{{BANNER_ICON}}", banner_icon)
    template = template.replace("{{BANNER_TEXTO}}", banner_texto)
    template = template.replace("{{AUDIO_SCRIPT}}", esc(hoje["audio_script"]))

    # 4) Próximo evento (opcional)
    inner, template = extract_block(template, "PROXIMO_EVENTO")
    proximo = hoje.get("proximo_evento")
    if inner is not None:
        if proximo:
            filled = inner
            filled = filled.replace("{{PROXIMO_EVENTO_TITULO}}", esc(proximo.get("titulo", "")))
            meta_line = " · ".join(x for x in [proximo.get("date_label"), proximo.get("time")] if x)
            filled = filled.replace("{{PROXIMO_EVENTO_META}}", esc(meta_line))
            template = put_block(template, "PROXIMO_EVENTO", filled)
        else:
            template = put_block(template, "PROXIMO_EVENTO", "")

    # 5) Próximos 3 dias
    day3_inner, template = extract_block(template, "DAY3_CARD")
    if day3_inner is None:
        print("ERRO: template.html não contém o bloco <!--DAY3_CARD-->...<!--/DAY3_CARD-->")
        sys.exit(3)
    template = put_block(template, "DAY3_CARD", build_day3_cards(hoje["proximos_3_dias"]))
    # substituir tokens dentro do bloco repetido manualmente (build_day3_cards já gera HTML final)

    # 6) Board de tarefas (3 colunas)
    board_inner, template = extract_block(template, "BOARD_COL")
    if board_inner is None:
        print("ERRO: template.html não contém o bloco <!--BOARD_COL-->...<!--/BOARD_COL-->")
        sys.exit(3)
    template = put_block(template, "BOARD_COL", build_board_cols(tarefas["board"]))

    # 7) Cards de tarefas por dia
    taskday_inner, template = extract_block(template, "TASK_DAY")
    if taskday_inner is None:
        print("ERRO: template.html não contém o bloco <!--TASK_DAY-->...<!--/TASK_DAY-->")
        sys.exit(3)
    item_tpl, taskday_body = extract_block(taskday_inner, "TASK_ITEM")
    if item_tpl is None:
        print("ERRO: template.html não contém o bloco <!--TASK_ITEM-->...<!--/TASK_ITEM-->")
        sys.exit(3)
    days_html = []
    for c in tarefas["cards"]:
        days_html.append(build_task_days([c], item_tpl))
    template = put_block(template, "TASK_DAY", "".join(days_html))

    # 8) Calendário
    template = template.replace("{{CAL_MES_ANO}}", esc(fmt_mes_ano(calendario["mes"])))
    cell_tpl, template = extract_block(template, "CAL_CELL")
    if cell_tpl is None:
        print("ERRO: template.html não contém o bloco <!--CAL_CELL-->...<!--/CAL_CELL-->")
        sys.exit(3)
    template = put_block(template, "CAL_CELL", build_cal_cells(calendario["dias"], meta["date"], cell_tpl))
    titulo, ev_txt, tk_txt = build_cal_detail(calendario["dias"], meta["date"], meta["weekday"])
    template = template.replace("{{CAL_DETAIL_TITULO}}", titulo)
    template = template.replace("{{CAL_DETAIL_EVENTOS}}", ev_txt)
    template = template.replace("{{CAL_DETAIL_TAREFAS}}", tk_txt)

    # 9) Email — secções
    template = fill_email_section(
        template, "urgente", email["urgente"], None,
        lambda it, tpl: row_simple(it, tpl),
    )
    template = fill_email_section(
        template, "importante", email["importante"], None,
        lambda it, tpl: row_simple(it, tpl),
    )
    template = fill_email_section(
        template, "informativo", email["informativo"], None,
        lambda it, tpl: row_simple(it, tpl, with_summary=False),
    )
    template = fill_email_section(
        template, "tarefas_sem_data", email["tarefas_sem_data"], None,
        lambda it, tpl: tpl.replace("{{E_SUBJ}}", esc(it.get("assunto", ""))),
    )
    template = fill_email_section(
        template, "snoozed", email["snoozed"], None,
        lambda it, tpl: row_simple(it, tpl, extra={"{{E_REAGENDADO}}": esc(it.get("reagendado_para", ""))}),
    )
    template = fill_email_section(
        template, "pediatric_surgery", email["pediatric_surgery"], None,
        lambda it, tpl: row_simple(it, tpl, extra={"{{E_BADGE}}": esc(it.get("tipo_badge", ""))}),
    )
    template = fill_email_section(
        template, "ulsasi", email["ulsasi"], None,
        lambda it, tpl: row_simple(it, tpl),
    )
    template = fill_email_section(
        template, "events", email["events"], None,
        lambda it, tpl: tpl.replace("{{E_SUBJ}}", esc(it.get("titulo", ""))).replace(
            "{{E_SUMMARY}}",
            esc(" · ".join(x for x in [it.get("status"), it.get("date_label"), it.get("time")] if x)),
        ),
    )
    # ruido — secção especial (contagem, sem linhas por item)
    inner, template = extract_block(template, "EMAIL_SECTION:ruido")
    if inner is not None:
        ruido = email["ruido"]
        if not ruido:
            template = put_block(template, "EMAIL_SECTION:ruido", "")
        else:
            filled = inner.replace("{{RUIDO_COUNT}}", str(len(ruido)))
            template = put_block(template, "EMAIL_SECTION:ruido", filled)

    # 10) Tempo — tabela 7 dias + janelas
    w_row_tpl, template = extract_block(template, "WEATHER_ROW")
    if w_row_tpl is None:
        print("ERRO: template.html não contém o bloco <!--WEATHER_ROW-->...<!--/WEATHER_ROW-->")
        sys.exit(3)
    rows = []
    for w in tempo["tabela_7dias"]:
        row = w_row_tpl
        row = row.replace("{{W_DIA}}", esc(w.get("date", "")))
        row = row.replace("{{W_ICONE}}", esc(w.get("icone", "")))
        row = row.replace("{{W_MAXMIN}}", f"{esc(w.get('max',''))}°/{esc(w.get('min',''))}°")
        row = row.replace("{{W_CHUVA}}", str(w.get("chuva_pct", 0)))
        rows.append(row)
    template = put_block(template, "WEATHER_ROW", "".join(rows))

    win_row_tpl, template = extract_block(template, "WINDOW_ROW")
    if win_row_tpl is None:
        print("ERRO: template.html não contém o bloco <!--WINDOW_ROW-->...<!--/WINDOW_ROW-->")
        sys.exit(3)
    win_rows = []
    for j in tempo["janelas"]:
        row = win_row_tpl
        row = row.replace("{{WIN_HORA}}", esc(j.get("hora", "")))
        nota = f" — {j.get('nota')}" if j.get("nota") else ""
        row = row.replace("{{WIN_TEXTO}}", esc(f"{j.get('actividade','')}{nota}"))
        win_rows.append(row)
    template = put_block(template, "WINDOW_ROW", "".join(win_rows))

    # 11) Rotina — 3 janelas fixas por id
    janelas_by_id = {j.get("id"): j for j in rotina["janelas"]}
    matinal = janelas_by_id["matinal"]
    processamento = janelas_by_id["processamento"]
    descompressao = janelas_by_id["descompressao"]
    template = template.replace("{{ROT_MATINAL_HORA}}", esc(matinal.get("hora", "")))
    template = template.replace(
        "{{ROT_MATINAL_CONFERIR}}", esc("; ".join(matinal.get("conferir") or []))
    )
    habito = matinal.get("habito_dia") or ""
    sugestao = matinal.get("sugestao") or ""
    template = template.replace(
        "{{ROT_MATINAL_HABITO}}", esc(f"{habito} ·" if habito else "")
    )
    template = template.replace("{{ROT_MATINAL_SUGESTAO}}", esc(sugestao))
    template = template.replace("{{ROT_PROC_HORA}}", esc(processamento.get("hora", "")))
    template = template.replace("{{ROT_PROC_SUGESTAO}}", esc(processamento.get("sugestao", "")))
    template = template.replace("{{ROT_DESC_HORA}}", esc(descompressao.get("hora", "")))
    template = template.replace("{{ROT_DESC_SUGESTAO}}", esc(descompressao.get("sugestao", "")))

    # 12) Rodapé
    gerado_hora = ""
    if meta.get("generated_at"):
        gerado_hora = meta["generated_at"][11:16]
    template = template.replace("{{GERADO_HORA}}", esc(gerado_hora))

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(template)

    print(f"OK: briefing modo {meta['mode']} renderizado -> {output_path}")


if __name__ == "__main__":
    main()
