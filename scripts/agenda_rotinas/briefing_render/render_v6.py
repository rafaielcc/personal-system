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
  - tarefas.cards[]: {"dia": str, "tarefas": [{"texto": str, "feito": bool}],
      "eventos": [{"texto": str, "feito": bool}],
      "extras": [{"texto": str, "feito": bool, "tipo": "habito"|"sugestao"|"desporto"}]}
      (box "Eventos" e independente de calendario.dias — a LLM garante que o
      mesmo item nao aparece em ambos)

Uso:
    python3 render.py <input.json> <template.html> <output.html>

Codigo de saida 0 = sucesso. Qualquer falha de validacao do JSON aborta
com mensagem clara (nao tenta "adivinhar" campos em falta).

v2 -- 19 Jul 2026: removido build_board_cols() (board panorama eliminado);
build_task_days() substituido por build_task_boxes() -- 3 boxes de cor
fixa por dia (Tarefas/Eventos/Extras) em vez de 1 card com cor dinamica
por progresso; build_cal_detail() substituido por build_cal_day_panels()
-- gera um painel por dia (nao so o de hoje), permitindo a navegacao real
por dia no calendario via JS (antes so existia o painel do dia actual).

v3 -- 21 Jul 2026 (ronda de correcoes pos-publicacao, feedback do Rafa):
build_cal_cells() -- token novo {{CAL_SELECTED_CLASS}}, separado de
{{CAL_TODAY_CLASS}} (o "hoje" e o "seleccionado" sao classes distintas,
a seleccionada move-se via JS no template); build_cal_day_panels() --
reescrito para gerar 3 boxes (Tarefas/Eventos/Extras, reaproveitando os
mesmos item_tpl_t/e/x do TASK_DAY) em vez de duas linhas de prosa; os
itens habito/sugestao/desporto sao alinhados por posicao aos primeiros
dias de tarefas.cards (nao inventados para os restantes dias da janela
de 15 dias); build_routine_items() -- nova, gera bullets <li> a partir
de conferir[] + habito_dia + sugestao (antes so a sugestao aparecia para
Processamento/Descompressao -- bug corrigido, o campo conferir existia
no JSON mas era descartado no render).

v4 -- 21 Jul 2026 (segunda ronda de correcoes no mesmo dia, feedback do
Rafa apos rever a v3 publicada): build_cal_cells() -- insere celulas
vazias (.cal-cell.cal-empty) no inicio da grelha, na quantidade do dia
da semana real (segunda=0) do primeiro dia de calendario.dias[], para a
grelha ser um calendario verdadeiro (1a coluna sempre segunda, ultima
sempre domingo) -- antes o primeiro dia ia sempre para a 1a coluna
independentemente do seu dia da semana real, desalinhando tudo.

v5 -- 22 Jul 2026 (pedido do Rafa -- janela de 3 dias, BRIEFING_DIARIO
v13.0): hoje e rotina deixam de ser um bloco unico do dia da corrida --
passam a hoje.dias[]/rotina.dias[] com 3 entradas (Hoje/Amanha/Depois de
amanha), renderizadas como 3 paineis <details> expansiveis cada uma (tab
Hoje e tab Rotina). build_banner()/build_routine_items() sao reaproveitadas
por dia; build_day3_cards() e o token DAY3_CARD foram removidos (a antiga
pre-visualizacao "proximos 3 dias" deixa de fazer sentido -- os 3 paineis
ja mostram o detalhe completo de cada dia). Cada painel Hoje tem o seu
proprio botao/audio (audio-btn-N / audio-script-text-N), 3 audios distintos
na aba. validate_canonical() atualizada para o novo schema.
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
DIAS_SEMANA_PT = ["segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo"]

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
    hoje_dias = hoje.get("dias") if isinstance(hoje, dict) else None
    if not isinstance(hoje_dias, list) or len(hoje_dias) != 3:
        errors.append("hoje.dias em falta ou não tem exactamente 3 entradas (Hoje/Amanhã/Depois de amanhã).")
    else:
        for i, d in enumerate(hoje_dias):
            if not isinstance(d, dict) or not d.get("audio_script"):
                errors.append(f"hoje.dias[{i}].audio_script em falta.")
            if not isinstance(d, dict) or not d.get("date"):
                errors.append(f"hoje.dias[{i}].date em falta.")

    tarefas = data.get("tarefas")
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
    rotina_dias = rotina.get("dias") if isinstance(rotina, dict) else None
    if not isinstance(rotina_dias, list) or len(rotina_dias) != 3:
        errors.append("rotina.dias em falta ou não tem exactamente 3 entradas (Hoje/Amanhã/Depois de amanhã).")
    else:
        for i, d in enumerate(rotina_dias):
            janelas = d.get("janelas") if isinstance(d, dict) else None
            if not isinstance(janelas, list):
                errors.append(f"rotina.dias[{i}].janelas em falta (lista).")
            else:
                ids_presentes = {j.get("id") for j in janelas}
                for req_id in ("matinal", "processamento", "descompressao"):
                    if req_id not in ids_presentes:
                        errors.append(f"rotina.dias[{i}].janelas sem janela id={req_id!r}.")

    if mode == "A" and not isinstance(data.get("hff"), dict):
        errors.append("meta.mode=='A' mas 'hff' em falta ou nao e objecto.")
    if mode == "B" and data.get("hff") is not None:
        errors.append("meta.mode=='B' mas 'hff' nao e null (deve omitir a tab).")

    diagnostico = data.get("diagnostico")
    if not isinstance(diagnostico, dict):
        errors.append("diagnostico em falta (objecto).")
    else:
        if not isinstance(diagnostico.get("fontes"), dict):
            errors.append("diagnostico.fontes em falta (objecto).")
        for key in ("avisos", "erros", "notas_llm"):
            if not isinstance(diagnostico.get(key), list):
                errors.append(f"diagnostico.{key} em falta (lista).")
        if not isinstance(diagnostico.get("tem_alertas"), bool):
            errors.append("diagnostico.tem_alertas em falta (bool).")

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
    # O esquema pede {"nivel", "texto"} por alerta, mas uma string simples ja
    # escapou ao LLM numa corrida real -- normaliza em vez de rebentar o render.
    alertas = [a if isinstance(a, dict) else {"nivel": "info", "texto": str(a)} for a in (hoje.get("alertas") or [])]
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


def day_data_label(day):
    """Label tipo 'Ter, 22 Jul' para um dia de hoje.dias[]/rotina.dias[] -- usa
    weekday se vier no JSON, senão calcula a partir da date."""
    date_str = day.get("date", "")
    weekday = day.get("weekday")
    if not weekday:
        try:
            weekday = DIAS_SEMANA_PT[datetime.strptime(date_str, "%Y-%m-%d").weekday()]
        except ValueError:
            weekday = ""
    try:
        return fmt_data_label(date_str, weekday)
    except ValueError:
        return date_str


def build_hoje_panel_tokens(day, idx):
    """Tokens {{HOJE_D<idx>_...}} para o painel expansível de um dia da aba Hoje."""
    banner_class, banner_icon, banner_texto = build_banner(day)
    proximo = day.get("proximo_evento")
    if proximo:
        prox_display = "block"
        prox_titulo = esc(proximo.get("titulo", ""))
        meta_line = " · ".join(x for x in [proximo.get("date_label"), proximo.get("time")] if x)
        prox_meta = esc(meta_line)
    else:
        prox_display = "none"
        prox_titulo = ""
        prox_meta = ""
    return {
        f"{{{{HOJE_D{idx}_DIA}}}}": esc(day.get("dia", "")),
        f"{{{{HOJE_D{idx}_DATA_LABEL}}}}": esc(day_data_label(day)),
        f"{{{{HOJE_D{idx}_OPEN}}}}": "open" if idx == 0 else "",
        f"{{{{HOJE_D{idx}_AUDIO_SCRIPT}}}}": esc(day.get("audio_script", "")),
        f"{{{{HOJE_D{idx}_BANNER_CLASS}}}}": banner_class,
        f"{{{{HOJE_D{idx}_BANNER_ICON}}}}": banner_icon,
        f"{{{{HOJE_D{idx}_BANNER_TEXTO}}}}": banner_texto,
        f"{{{{HOJE_D{idx}_PROXIMO_DISPLAY}}}}": prox_display,
        f"{{{{HOJE_D{idx}_PROXIMO_TITULO}}}}": prox_titulo,
        f"{{{{HOJE_D{idx}_PROXIMO_META}}}}": prox_meta,
    }


def build_rotina_panel_tokens(day, idx):
    """Tokens {{ROT_D<idx>_...}} para o painel expansível de um dia da aba Rotina."""
    janelas_by_id = {j.get("id"): j for j in (day.get("janelas") or [])}
    matinal = janelas_by_id.get("matinal", {})
    processamento = janelas_by_id.get("processamento", {})
    descompressao = janelas_by_id.get("descompressao", {})
    return {
        f"{{{{ROT_D{idx}_DIA}}}}": esc(day.get("dia", "")),
        f"{{{{ROT_D{idx}_DATA_LABEL}}}}": esc(day_data_label(day)),
        f"{{{{ROT_D{idx}_OPEN}}}}": "open" if idx == 0 else "",
        f"{{{{ROT_D{idx}_MATINAL_HORA}}}}": esc(matinal.get("hora", "")),
        f"{{{{ROT_D{idx}_MATINAL_ITEMS}}}}": build_routine_items(matinal),
        f"{{{{ROT_D{idx}_PROC_HORA}}}}": esc(processamento.get("hora", "")),
        f"{{{{ROT_D{idx}_PROC_ITEMS}}}}": build_routine_items(processamento),
        f"{{{{ROT_D{idx}_DESC_HORA}}}}": esc(descompressao.get("hora", "")),
        f"{{{{ROT_D{idx}_DESC_ITEMS}}}}": build_routine_items(descompressao),
    }


def build_item_rows(items, item_tpl, checked_token, texto_token, done_token, class_token=None):
    if not items:
        return '          <p class="muted" style="font-size:12px;">Nada por agora.</p>\n'
    rows = []
    for it in items:
        row = item_tpl
        if class_token:
            row = row.replace(class_token, TASK_TYPE_CLASS.get(it.get("tipo"), ""))
        row = row.replace(checked_token, "checked" if it.get("feito") else "")
        row = row.replace(done_token, "done" if it.get("feito") else "")
        row = row.replace(texto_token, esc(it.get("texto", "")))
        rows.append(row)
    return "".join(rows)


def build_task_boxes(cards, item_tpl_t, item_tpl_e, item_tpl_x):
    parts = []
    for c in cards:
        tarefas_html = build_item_rows(c.get("tarefas") or [], item_tpl_t, "{{TI_T_CHECKED}}", "{{TI_T_TEXTO}}", "{{TI_T_DONE}}")
        eventos_html = build_item_rows(c.get("eventos") or [], item_tpl_e, "{{TI_E_CHECKED}}", "{{TI_E_TEXTO}}", "{{TI_E_DONE}}")
        extras_html = build_item_rows(c.get("extras") or [], item_tpl_x, "{{TI_X_CHECKED}}", "{{TI_X_TEXTO}}", "{{TI_X_DONE}}", "{{TI_X_CLASS}}")
        parts.append(
            f"\n        <div class=\"task-section-label\">{esc(c.get('dia',''))}</div>\n"
            "\n        <div class=\"task-card tc-tarefas\">\n"
            "          <div class=\"task-card-title\">✅ Tarefas</div>\n"
            + tarefas_html +
            "        </div>\n"
            "\n        <div class=\"task-card tc-eventos\">\n"
            "          <div class=\"task-card-title\">📅 Eventos</div>\n"
            + eventos_html +
            "        </div>\n"
            "\n        <div class=\"task-card tc-extras\">\n"
            "          <div class=\"task-card-title\">🌿 Hábitos · 💡 Sugestão · 🏃 Desporto</div>\n"
            + extras_html +
            "        </div>\n"
        )
    return "".join(parts)


def build_cal_cells(dias, today_str, cell_tpl):
    parts = []
    if dias:
        try:
            leading = datetime.strptime(dias[0].get("date", ""), "%Y-%m-%d").weekday()  # segunda=0
        except ValueError:
            leading = 0
        parts.extend(['<div class="cal-cell cal-empty"></div>\n'] * leading)
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
        cell = cell.replace("{{CAL_SELECTED_CLASS}}", "cal-selected" if date_str == today_str else "")
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


def build_cal_day_panels(dias, today_str, panel_tpl, item_tpl_t, item_tpl_e, item_tpl_x, tarefas_cards=None):
    """Painel de detalhe por dia do calendário — mesma estrutura de 3 boxes (Tarefas/
    Eventos/Extras) da aba Tarefas. Os itens habito/sugestao/desporto só existem em
    tarefas.cards (hoje + 2 dias) — aqui são alinhados por posição aos primeiros dias
    de `dias` (mesmas datas), não inventados para os restantes dias da janela."""
    visible_date = today_str if any(d.get("date") == today_str for d in dias) else (dias[0].get("date") if dias else None)
    extras_by_date = {}
    for idx, card in enumerate(tarefas_cards or []):
        if idx < len(dias):
            extras_by_date[dias[idx].get("date")] = card.get("extras") or []
    parts = []
    for d in dias:
        date_str = d.get("date", "")
        try:
            wd = DIAS_SEMANA_PT[datetime.strptime(date_str, "%Y-%m-%d").weekday()]
            titulo = fmt_data_label(date_str, wd)
        except ValueError:
            titulo = date_str
        itens = d.get("itens") or []
        eventos = [{"texto": i.get("titulo", ""), "feito": False} for i in itens if i.get("tipo") == "evento"]
        tarefas = [{"texto": i.get("titulo", ""), "feito": False} for i in itens if i.get("tipo") == "tarefa"]
        extras = extras_by_date.get(date_str, [])
        panel = panel_tpl
        panel = panel.replace("{{CAL_PANEL_DATE}}", esc(date_str))
        panel = panel.replace("{{CAL_PANEL_DISPLAY}}", "block" if date_str == visible_date else "none")
        panel = panel.replace("{{CAL_PANEL_TITULO}}", esc(titulo))
        panel = panel.replace(
            "{{CAL_PANEL_TAREFAS_HTML}}",
            build_item_rows(tarefas, item_tpl_t, "{{TI_T_CHECKED}}", "{{TI_T_TEXTO}}", "{{TI_T_DONE}}"),
        )
        panel = panel.replace(
            "{{CAL_PANEL_EVENTOS_HTML}}",
            build_item_rows(eventos, item_tpl_e, "{{TI_E_CHECKED}}", "{{TI_E_TEXTO}}", "{{TI_E_DONE}}"),
        )
        panel = panel.replace(
            "{{CAL_PANEL_EXTRAS_HTML}}",
            build_item_rows(extras, item_tpl_x, "{{TI_X_CHECKED}}", "{{TI_X_TEXTO}}", "{{TI_X_DONE}}", "{{TI_X_CLASS}}"),
        )
        parts.append(panel)
    return "".join(parts)


def build_routine_items(janela):
    items = list(janela.get("conferir") or [])
    habito = janela.get("habito_dia")
    if habito:
        items.append(f"🌿 {habito}")
    sugestao = janela.get("sugestao")
    if sugestao:
        items.append(f"💡 {sugestao}")
    if not items:
        return '                <li class="muted">Nada por agora.</li>\n'
    return "".join(f"                <li>{esc(it)}</li>\n" for it in items)


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
# Diagnostico (v8) — le canonical_draft.diagnostico tal como o pre o deixou;
# o LLM so acrescenta a notas_llm, o resto (fontes/avisos/erros) chega pronto.
# --------------------------------------------------------------------------
FONTE_LABELS = {
    "calendario": "Calendário",
    "gmail": "Gmail",
    "todoist": "Todoist",
    "tempo": "Tempo",
    "espelho_hff": "Espelho HFF",
}


def diag_fonte_label(key):
    return FONTE_LABELS.get(key, key.replace("_", " ").capitalize())


# Campos que aparecem em quase todas as fontes mas nunca ajudam a ler o
# diagnostico de relance (identificadores fixos, nao informacao da corrida).
# Descoberto testando contra uma corrida real: sem isto, "Espelho HFF" mostrava
# o spreadsheet_id (uma string enorme e sempre igual) em vez de "sessoes: 7".
DIAG_DETALHE_SKIP_KEYS = {"spreadsheet_id", "abas"}


def diag_fonte_detalhe(fonte):
    """Uma linha curta e generica: se falhou, mostra o erro; senao, ate 3
    campos escalares (ignora sub-objectos/listas e identificadores fixos)."""
    if not isinstance(fonte, dict):
        return esc(str(fonte))
    if fonte.get("erro"):
        return esc(str(fonte["erro"]))
    pares = [
        f"{k}: {v}" for k, v in fonte.items()
        if k not in ("ok", "erro") and k not in DIAG_DETALHE_SKIP_KEYS
        and not isinstance(v, (dict, list))
    ]
    return esc(" · ".join(pares[:3])) if pares else ""


def build_diag_fonte_rows(fontes, row_tpl):
    if not fontes:
        return '          <p class="muted" style="font-size:12px;">Nenhuma fonte registada.</p>\n'
    rows = []
    for key, fonte in fontes.items():
        ok = isinstance(fonte, dict) and fonte.get("ok") is True
        row = row_tpl
        row = row.replace("{{DIAG_FONTE_ROW_CLASS}}", "diag-ok" if ok else "diag-erro")
        row = row.replace("{{DIAG_FONTE_NOME}}", esc(diag_fonte_label(key)))
        row = row.replace("{{DIAG_FONTE_STATUS}}", "✅ ok" if ok else "❌ falhou")
        row = row.replace("{{DIAG_FONTE_DETALHE}}", diag_fonte_detalhe(fonte))
        rows.append(row)
    return "".join(rows)


def fill_diag_section(template, key, items):
    """Mesma mecanica de fill_email_section, generica para qualquer lista de
    texto simples (avisos/erros/notas_llm) — remove a secção inteira se vazia."""
    inner, template = extract_block(template, f"DIAG_SECTION:{key}")
    if inner is None:
        return template
    if not items:
        return put_block(template, f"DIAG_SECTION:{key}", "")
    row_inner, section_stripped = extract_block(inner, f"DIAG_ROW:{key}")
    if row_inner is None:
        rows_html = ""
    else:
        rows_html = "".join(row_inner.replace("{{DIAG_TEXTO}}", esc(str(texto))) for texto in items)
        section_stripped = put_block(section_stripped, f"DIAG_ROW:{key}", rows_html)
    return put_block(template, f"DIAG_SECTION:{key}", section_stripped)


def build_diag_banner(diagnostico):
    if diagnostico.get("erros"):
        return "banner-alert", "🚨", f"{len(diagnostico['erros'])} erro(s) nesta corrida — ver abaixo."
    if diagnostico.get("tem_alertas"):
        return "banner-warn", "⚠️", "Há avisos ou uma fonte falhou nesta corrida — ver abaixo."
    return "", "✅", "Todas as fontes ok, sem avisos nem erros."


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
    diagnostico = data["diagnostico"]

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
            # hff.resumo/cirurgias_resumo tem de ser texto (o LLM escreve-os a
            # partir de hff.resumo_dados) -- se por engano vier outra coisa
            # (ex. o dict cru), mostra vazio em vez do repr do Python.
            hff_resumo = hff.get("resumo", "")
            hff_cirurgias_resumo = hff.get("cirurgias_resumo", "")
            filled = filled.replace("{{HFF_TIPO_DIA}}", esc(hff.get("tipo_dia", "")))
            filled = filled.replace("{{HFF_RESUMO}}", esc(hff_resumo if isinstance(hff_resumo, str) else ""))
            filled = filled.replace("{{HFF_CIRURGIAS_RESUMO}}", esc(hff_cirurgias_resumo if isinstance(hff_cirurgias_resumo, str) else ""))
            template = put_block(template, marker, filled)
        else:
            template = put_block(template, marker, "")

    # 3) Hoje — 3 painéis expansíveis (Hoje/Amanhã/Depois de amanhã)
    hoje_dias = hoje["dias"]
    if len(hoje_dias) != 3:
        print("ERRO: hoje.dias não tem exactamente 3 entradas.")
        sys.exit(3)
    for idx, day in enumerate(hoje_dias):
        for token, value in build_hoje_panel_tokens(day, idx).items():
            template = template.replace(token, value)

    # 6) Cards de tarefas por dia (3 boxes de cor fixa: Tarefas/Eventos/Extras)
    taskday_inner, template = extract_block(template, "TASK_DAY")
    if taskday_inner is None:
        print("ERRO: template.html não contém o bloco <!--TASK_DAY-->...<!--/TASK_DAY-->")
        sys.exit(3)
    item_tpl_t, taskday_body = extract_block(taskday_inner, "TASK_ITEM_T")
    if item_tpl_t is None:
        print("ERRO: template.html não contém o bloco <!--TASK_ITEM_T-->...<!--/TASK_ITEM_T-->")
        sys.exit(3)
    item_tpl_e, taskday_body = extract_block(taskday_body, "TASK_ITEM_E")
    if item_tpl_e is None:
        print("ERRO: template.html não contém o bloco <!--TASK_ITEM_E-->...<!--/TASK_ITEM_E-->")
        sys.exit(3)
    item_tpl_x, taskday_body = extract_block(taskday_body, "TASK_ITEM_X")
    if item_tpl_x is None:
        print("ERRO: template.html não contém o bloco <!--TASK_ITEM_X-->...<!--/TASK_ITEM_X-->")
        sys.exit(3)
    template = put_block(template, "TASK_DAY", build_task_boxes(tarefas["cards"], item_tpl_t, item_tpl_e, item_tpl_x))

    # 7) Calendário
    template = template.replace("{{CAL_MES_ANO}}", esc(fmt_mes_ano(calendario["mes"])))
    cell_tpl, template = extract_block(template, "CAL_CELL")
    if cell_tpl is None:
        print("ERRO: template.html não contém o bloco <!--CAL_CELL-->...<!--/CAL_CELL-->")
        sys.exit(3)
    template = put_block(template, "CAL_CELL", build_cal_cells(calendario["dias"], meta["date"], cell_tpl))
    panel_tpl, template = extract_block(template, "CAL_DAY_PANEL")
    if panel_tpl is None:
        print("ERRO: template.html não contém o bloco <!--CAL_DAY_PANEL-->...<!--/CAL_DAY_PANEL-->")
        sys.exit(3)
    template = put_block(
        template, "CAL_DAY_PANEL",
        build_cal_day_panels(
            calendario["dias"], meta["date"], panel_tpl,
            item_tpl_t, item_tpl_e, item_tpl_x, tarefas["cards"],
        ),
    )

    # 8) Email — secções
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

    # 9) Tempo — tabela 7 dias + janelas
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

    # 10) Rotina — 3 painéis expansíveis (Hoje/Amanhã/Depois de amanhã)
    rotina_dias = rotina["dias"]
    if len(rotina_dias) != 3:
        print("ERRO: rotina.dias não tem exactamente 3 entradas.")
        sys.exit(3)
    for idx, day in enumerate(rotina_dias):
        for token, value in build_rotina_panel_tokens(day, idx).items():
            template = template.replace(token, value)

    # 10b) Diagnóstico (v8) — sempre presente, Modo A e B
    template = template.replace(
        "{{DIAG_TAB_BADGE}}", "⚠️" if diagnostico.get("tem_alertas") else ""
    )
    banner_class, banner_icon, banner_texto = build_diag_banner(diagnostico)
    template = template.replace("{{DIAG_BANNER_CLASS}}", banner_class)
    template = template.replace("{{DIAG_BANNER_ICON}}", banner_icon)
    template = template.replace("{{DIAG_BANNER_TEXTO}}", esc(banner_texto))
    fonte_row_tpl, template = extract_block(template, "DIAG_FONTE_ROW")
    if fonte_row_tpl is None:
        print("ERRO: template.html não contém o bloco <!--DIAG_FONTE_ROW-->...<!--/DIAG_FONTE_ROW-->")
        sys.exit(3)
    template = put_block(template, "DIAG_FONTE_ROW", build_diag_fonte_rows(diagnostico.get("fontes", {}), fonte_row_tpl))
    for key in ("avisos", "erros", "notas_llm"):
        template = fill_diag_section(template, key, diagnostico.get(key) or [])

    # 11) Rodapé
    gerado_hora = ""
    if meta.get("generated_at"):
        gerado_hora = meta["generated_at"][11:16]
    template = template.replace("{{GERADO_HORA}}", esc(gerado_hora))

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(template)

    print(f"OK: briefing modo {meta['mode']} renderizado -> {output_path}")


if __name__ == "__main__":
    main()
