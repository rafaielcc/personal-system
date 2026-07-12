#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
render.py — Render Layer do Painel HFF standalone (Modulo 4 / Rotina de Publicação)

Le o JSON canonico (produzido pela LLM, schema Seccao 11 de
INSTRUCOES_PAINEL_HFF_v5.0.md) + template.html (estatico, sem logica de
negocio) e produz o index.html final por substituicao mecanica de texto.
Apenas stdlib do Python — mesmo padrao do render.py do Briefing/Lazer.

A LLM nunca volta a escrever HTML livremente: a unica camada onde a LLM
exerce juizo e o JSON canonico. Este script e puramente mecanico e deve
produzir o mesmo HTML sempre que receber o mesmo JSON + template.

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

MESES_ABR = {
    1: "Jan", 2: "Fev", 3: "Mar", 4: "Abr", 5: "Mai", 6: "Jun",
    7: "Jul", 8: "Ago", 9: "Set", 10: "Out", 11: "Nov", 12: "Dez",
}

DIAS_SEMANA_PT = {0: "segunda", 1: "terça", 2: "quarta", 3: "quinta", 4: "sexta", 5: "sábado", 6: "domingo"}

EQUIPA_REF = {
    "IF": ("Isabel Franca", "dot-isabel"),
    "RC": ("Rafael Correia", "dot-rafael"),
    "RR": ("Rodrigo Roquette", "dot-rodrigo"),
    "A": ("Afonso", "dot-afonso"),
}


# --------------------------------------------------------------------------
# Validacao
# --------------------------------------------------------------------------
def validate_canonical(data):
    errors = []
    meta = data.get("meta")
    if not isinstance(meta, dict):
        errors.append("Falta o objecto 'meta'.")
        return errors
    for field in ("date", "weekday", "day_type"):
        if not meta.get(field):
            errors.append(f"meta.{field} em falta.")

    for key in ("resumo", "tarefas_hff", "cirurgias", "prevencao", "sigic", "equipa"):
        if not isinstance(data.get(key), dict):
            errors.append(f"'{key}' em falta (objecto).")

    if isinstance(data.get("cirurgias"), dict) and not isinstance(data["cirurgias"].get("sessoes"), list):
        errors.append("cirurgias.sessoes em falta (lista).")
    if isinstance(data.get("prevencao"), dict) and not isinstance(data["prevencao"].get("semanas"), list):
        errors.append("prevencao.semanas em falta (lista).")
    if isinstance(data.get("sigic"), dict) and not isinstance(data["sigic"].get("listas"), list):
        errors.append("sigic.listas em falta (lista).")
    if isinstance(data.get("tarefas_hff"), dict) and not isinstance(data["tarefas_hff"].get("itens"), list):
        errors.append("tarefas_hff.itens em falta (lista).")

    return errors


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------
def esc(text):
    return html_lib.escape(str(text) if text is not None else "", quote=True)


def fmt_data_label(date_str, weekday):
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    if weekday:
        return f"{weekday.capitalize()}, {dt.day} {MESES_ABR[dt.month]}"
    return fmt_date_short(date_str)


def fmt_date_short(date_str):
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    return f"{dt.day} {MESES_ABR[dt.month]}"


def weekday_pt(date_str):
    return DIAS_SEMANA_PT[datetime.strptime(date_str, "%Y-%m-%d").weekday()]


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


def require_block(template, marker):
    inner, template = extract_block(template, marker)
    if inner is None:
        print(f"ERRO: template.html não contém o bloco <!--{marker}-->...<!--/{marker}-->")
        sys.exit(3)
    return inner, template


def doente_row(d, fields_tpl_map):
    """fields_tpl_map: dict token->campo. Devolve a linha preenchida a partir do dict campo->token."""
    pass


def fill_doente_row(row_tpl, d, fdr_token, proc_token, idade_token, nome_token, proc_desc_token, obs_token=None):
    row = row_tpl
    row = row.replace(fdr_token, "fdr-row" if d.get("fdr") else "")
    row = row.replace(proc_token, esc(d.get("processo", "")))
    row = row.replace(idade_token, esc(d.get("idade_fmt", "")))
    row = row.replace(nome_token, esc(d.get("nome", "")))
    row = row.replace(proc_desc_token, esc(d.get("procedimento", "")))
    if obs_token:
        row = row.replace(obs_token, esc(d.get("obs", "")))
    return row


def parse_date(s):
    return datetime.strptime(s, "%Y-%m-%d").date()


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
    resumo = data["resumo"]
    tarefas_hff = data["tarefas_hff"]
    cirurgias = data["cirurgias"]
    prevencao = data["prevencao"]
    sigic = data["sigic"]
    equipa = data["equipa"]
    today_str = meta["date"]
    weekday = meta["weekday"]

    with open(template_path, "r", encoding="utf-8") as f:
        template = f.read()

    data_label = fmt_data_label(today_str, weekday)
    template = template.replace("{{DATA_LABEL}}", esc(data_label))
    template = template.replace("{{TIPO_DIA}}", esc(meta["day_type"]))

    # ---- Resumo: banner ----
    alertas = resumo.get("alertas") or []
    if alertas:
        banner_class, banner_icon = "banner-alert", "⚠️"
        banner_texto = esc("; ".join(alertas))
    else:
        banner_class, banner_icon = "", "ℹ️"
        banner_texto = esc(resumo.get("tipo_dia") or "Sem alertas")
    template = template.replace("{{BANNER_CLASS}}", banner_class)
    template = template.replace("{{BANNER_ICON}}", banner_icon)
    template = template.replace("{{BANNER_TEXTO}}", banner_texto)

    template = template.replace("{{TIPO_DIA_COMPLETO}}", esc(resumo.get("tipo_dia", "")))
    if weekday.lower() in ("segunda", "quarta"):
        regra = f"Hoje é {weekday} → BO confirmado (Segunda/Quarta)."
    else:
        regra = f"Hoje é {weekday} → sem BO (só Segunda/Quarta)."
    template = template.replace("{{TIPO_DIA_REGRA}}", esc(regra))

    template = template.replace(
        "{{ONCALL_NOME}}", esc(prevencao.get("semana_actual", {}).get("cirurgiao") or "—")
    )

    ausencias_txt = []
    for a in equipa.get("ausencias_confirmadas") or []:
        ausencias_txt.append(f"{a.get('cir','?')} ({a.get('motivo','?')})")
    for a in equipa.get("ausencias_provaveis") or []:
        if a.get("dia") == today_str:
            ausencias_txt.append(f"{a.get('cir','?')} (provável)")
    template = template.replace(
        "{{AUSENCIAS_RELEVANTES}}", esc("; ".join(ausencias_txt) if ausencias_txt else "Nenhuma")
    )

    # ---- Resumo: FDR box (0+ pacientes FDR de hoje) ----
    fdr_inner, template = require_block(template, "FDR_RESUMO_BOX")
    today_sessoes = [s for s in cirurgias.get("sessoes", []) if s.get("date") == today_str]
    fdr_hoje = [d for s in today_sessoes for d in (s.get("doentes") or []) if d.get("fdr")]
    fdr_html = ""
    for d in fdr_hoje:
        box = fdr_inner
        box = box.replace("{{FDR_NOME}}", esc(d.get("nome", "")))
        box = box.replace("{{FDR_NOTA}}", esc(d.get("obs") or "sem nota adicional"))
        fdr_html += box
    template = put_block(template, "FDR_RESUMO_BOX", fdr_html)

    # ---- Resumo: Tarefas HFF ----
    tarefas_box_inner, template = require_block(template, "TAREFAS_HFF_BOX")
    item_inner, tarefas_box_inner_body = require_block(tarefas_box_inner, "TAREFA_HFF_ITEM")
    vazio_inner, template = require_block(template, "TAREFAS_HFF_VAZIO")
    itens = tarefas_hff.get("itens") or []
    if itens:
        cls = "tb-red" if any(i.get("prioridade") == "alta" for i in itens) else "tb-yellow"
        items_html = "".join(item_inner.replace("{{TAREFA_TEXTO}}", esc(i.get("texto", ""))) for i in itens)
        box_html = tarefas_box_inner_body.replace("{{TAREFAS_CLASS}}", cls)
        box_html = put_block(box_html, "TAREFA_HFF_ITEM", items_html)
        template = put_block(template, "TAREFAS_HFF_BOX", box_html)
        template = put_block(template, "TAREFAS_HFF_VAZIO", "")
    else:
        template = put_block(template, "TAREFAS_HFF_BOX", "")
        template = put_block(template, "TAREFAS_HFF_VAZIO", vazio_inner)

    proximo_bo = resumo.get("proximo_bo")
    if proximo_bo:
        template = template.replace(
            "{{PROX_BO_DATA}}", esc(fmt_data_label(proximo_bo["date"], proximo_bo.get("weekday", "")))
        )
        template = template.replace("{{PROX_BO_N}}", str(proximo_bo.get("n_cirurgias", 0)))
    else:
        template = template.replace("{{PROX_BO_DATA}}", "—")
        template = template.replace("{{PROX_BO_N}}", "0")

    # ---- Cirurgias: agrupar sessoes por data ----
    by_date = {}
    for s in cirurgias.get("sessoes", []):
        by_date.setdefault(s["date"], {"M": [], "S": []})
        periodo = s.get("periodo")
        by_date[s["date"]][periodo if periodo in ("M", "S") else "M"].extend(s.get("doentes") or [])

    hoje_bloco_inner, template = require_block(template, "CIRURGIAS_HOJE_BLOCO")
    sem_bo_inner, template = require_block(template, "CIRURGIAS_SEM_BO_HOJE")

    if today_str in by_date:
        bloco = hoje_bloco_inner
        m_doentes = sorted(by_date[today_str]["M"], key=lambda d: d.get("idade_raw", 0))
        s_doentes = sorted(by_date[today_str]["S"], key=lambda d: d.get("idade_raw", 0))

        m_row_tpl, bloco = require_block(bloco, "HOJE_DOENTE_M")
        sem_m_inner, bloco = require_block(bloco, "HOJE_SEM_MANHA")
        if m_doentes:
            rows = "".join(
                fill_doente_row(m_row_tpl, d, "{{DM_FDR_CLASS}}", "{{DM_PROCESSO}}", "{{DM_IDADE}}",
                                "{{DM_NOME}}", "{{DM_PROCEDIMENTO}}", "{{DM_OBS}}")
                for d in m_doentes
            )
            bloco = put_block(bloco, "HOJE_DOENTE_M", rows)
            bloco = put_block(bloco, "HOJE_SEM_MANHA", "")
        else:
            bloco = put_block(bloco, "HOJE_DOENTE_M", "")
            bloco = put_block(bloco, "HOJE_SEM_MANHA", sem_m_inner)

        tarde_inner, bloco = require_block(bloco, "HOJE_TARDE_BLOCO")
        sem_tarde_inner, bloco = require_block(bloco, "HOJE_SEM_TARDE")
        if s_doentes:
            s_row_tpl, tarde_inner_body = require_block(tarde_inner, "HOJE_DOENTE_S")
            rows = "".join(
                fill_doente_row(s_row_tpl, d, "{{DS_FDR_CLASS}}", "{{DS_PROCESSO}}", "{{DS_IDADE}}",
                                "{{DS_NOME}}", "{{DS_PROCEDIMENTO}}")
                for d in s_doentes
            )
            resumo_procs = ", ".join(d.get("procedimento", "") for d in s_doentes[:3])
            tarde_filled = tarde_inner_body.replace("{{HOJE_N_SIGIC}}", str(len(s_doentes)))
            tarde_filled = tarde_filled.replace("{{HOJE_SIGIC_RESUMO}}", esc(resumo_procs))
            tarde_filled = put_block(tarde_filled, "HOJE_DOENTE_S", rows)
            bloco = put_block(bloco, "HOJE_TARDE_BLOCO", tarde_filled)
            bloco = put_block(bloco, "HOJE_SEM_TARDE", "")
        else:
            bloco = put_block(bloco, "HOJE_TARDE_BLOCO", "")
            bloco = put_block(bloco, "HOJE_SEM_TARDE", sem_tarde_inner)

        template = put_block(template, "CIRURGIAS_HOJE_BLOCO", bloco)
        template = put_block(template, "CIRURGIAS_SEM_BO_HOJE", "")
    else:
        template = put_block(template, "CIRURGIAS_HOJE_BLOCO", "")
        prox_txt = fmt_data_label(proximo_bo["date"], proximo_bo.get("weekday", "")) if proximo_bo else "—"
        template = put_block(
            template, "CIRURGIAS_SEM_BO_HOJE", sem_bo_inner.replace("{{PROX_BO_DATA}}", esc(prox_txt))
        )

    # ---- Cirurgias: Próximos BOs, agrupados por semana ISO ----
    sem_prox_inner, template = require_block(template, "SEM_PROXIMOS_BOS")
    week_block_tpl, template = require_block(template, "WEEK_BLOCK")
    day_tpl, week_block_body = require_block(week_block_tpl, "WEEK_DAY")
    dm_row_tpl, day_tpl_body = require_block(day_tpl, "WD_DOENTE_M")
    ds_row_tpl, day_tpl_body2 = require_block(day_tpl_body, "WD_DOENTE_S")

    future_dates = sorted(d for d in by_date if d != today_str and parse_date(d) > parse_date(today_str))
    if not future_dates:
        template = put_block(template, "SEM_PROXIMOS_BOS", sem_prox_inner)
        template = put_block(template, "WEEK_BLOCK", "")
    else:
        template = put_block(template, "SEM_PROXIMOS_BOS", "")
        weeks = {}
        for d in future_dates:
            iso = parse_date(d).isocalendar()
            weeks.setdefault((iso[0], iso[1]), []).append(d)

        weeks_html = ""
        for (_, _), dates in sorted(weeks.items()):
            dates_sorted = sorted(dates)
            week_label = f"Semana de {fmt_data_label(dates_sorted[0], '')} a {fmt_data_label(dates_sorted[-1], '')}"
            days_html = ""
            for d in dates_sorted:
                m_doentes = sorted(by_date[d]["M"], key=lambda x: x.get("idade_raw", 0))
                s_doentes = sorted(by_date[d]["S"], key=lambda x: x.get("idade_raw", 0))
                day_html = day_tpl_body2
                day_html = day_html.replace("{{WD_LABEL}}", esc(fmt_data_label(d, weekday_pt(d))))
                resumo_dia = f"{len(m_doentes)} cirurgias manhã"
                if s_doentes:
                    resumo_dia += f" + {len(s_doentes)} SIGIC tarde"
                day_html = day_html.replace("{{WD_RESUMO}}", esc(resumo_dia))
                m_rows = "".join(
                    fill_doente_row(dm_row_tpl, x, "{{WDM_FDR_CLASS}}", "{{WDM_PROCESSO}}", "{{WDM_IDADE}}",
                                    "{{WDM_NOME}}", "{{WDM_PROCEDIMENTO}}")
                    for x in m_doentes
                )
                day_html = put_block(day_html, "WD_DOENTE_M", m_rows)
                s_rows = "".join(
                    fill_doente_row(ds_row_tpl, x, "{{WDS_FDR_CLASS}}", "{{WDS_PROCESSO}}", "{{WDS_IDADE}}",
                                    "{{WDS_NOME}}", "{{WDS_PROCEDIMENTO}}")
                    for x in s_doentes
                )
                day_html = put_block(day_html, "WD_DOENTE_S", s_rows)
                day_html = day_html.replace("{{WD_TARDE_DISPLAY}}", "flex" if s_doentes else "none")
                days_html += day_html
            week_html = week_block_body.replace("{{WEEK_LABEL}}", esc(week_label))
            week_html = put_block(week_html, "WEEK_DAY", days_html)
            weeks_html += week_html
        template = put_block(template, "WEEK_BLOCK", weeks_html)

    # ---- Prevenção ----
    row_tpl, template = require_block(template, "PREVENCAO_ROW")
    rows = []
    for semana in prevencao.get("semanas", []):
        row = row_tpl
        cirurgiao = semana.get("cirurgiao") or ""
        is_current = parse_date(semana["inicio"]) <= parse_date(today_str) <= parse_date(semana["fim"])
        is_rafa = "rafael" in cirurgiao.lower()
        row = row.replace("{{PREV_CURRENT_CLASS}}", "current" if is_current else "")
        row = row.replace("{{PREV_RAFA_CLASS}}", "is-rafa" if is_rafa else "")
        row = row.replace("{{PREV_INICIO}}", esc(fmt_data_label(semana["inicio"], "")))
        row = row.replace("{{PREV_FIM}}", esc(fmt_data_label(semana["fim"], "")))
        obs_parts = [x for x in [semana.get("madeira"), semana.get("ferias"), semana.get("obs")] if x]
        row = row.replace("{{PREV_OBS}}", esc("; ".join(obs_parts)))
        if not cirurgiao:
            row = row.replace("{{PREV_BADGE_CLASS}}", "badge-empty")
            row = row.replace("{{PREV_BADGE_TEXTO}}", "Não atribuído")
        elif is_rafa:
            row = row.replace("{{PREV_BADGE_CLASS}}", "badge-oncall")
            row = row.replace("{{PREV_BADGE_TEXTO}}", esc(f"ON CALL · {cirurgiao}"))
        else:
            row = row.replace("{{PREV_BADGE_CLASS}}", "badge-neutral")
            row = row.replace("{{PREV_BADGE_TEXTO}}", esc(cirurgiao))
        rows.append(row)
    template = put_block(template, "PREVENCAO_ROW", "".join(rows))

    # ---- SIGIC ----
    sem_listas_inner, template = require_block(template, "SIGIC_SEM_LISTAS")
    lista_tpl, template = require_block(template, "SIGIC_LISTA")
    doente_tpl, lista_tpl_body = require_block(lista_tpl, "SIGIC_DOENTE")
    listas = sigic.get("listas", [])
    if not listas:
        template = put_block(template, "SIGIC_SEM_LISTAS", sem_listas_inner)
        template = put_block(template, "SIGIC_LISTA", "")
    else:
        template = put_block(template, "SIGIC_SEM_LISTAS", "")
        listas_html = ""
        for lst in listas:
            doentes = lst.get("cirurgias") or []
            rows = "".join(
                doente_tpl.replace("{{SD_PROCESSO}}", esc(d.get("processo", "")))
                .replace("{{SD_IDADE}}", esc(d.get("idade_fmt", "")))
                .replace("{{SD_NOME}}", esc(d.get("nome", "")))
                .replace("{{SD_PROCEDIMENTO}}", esc(d.get("procedimento", "")))
                for d in doentes
            )
            item = lista_tpl_body
            item = item.replace("{{SIGIC_DATA}}", esc(fmt_data_label(lst["date"], weekday_pt(lst["date"]))))
            item = item.replace(
                "{{SIGIC_CIRURGIOES}}", esc(f"{lst.get('cirurgiao1','')} · {lst.get('cirurgiao2','')}")
            )
            item = item.replace("{{SIGIC_N}}", str(len(doentes)))
            item = put_block(item, "SIGIC_DOENTE", rows)
            listas_html += item
        template = put_block(template, "SIGIC_LISTA", listas_html)

    # ---- Equipa ----
    eq_row_tpl, template = require_block(template, "EQUIPA_ROW")
    confirmadas = {a["cir"]: a for a in equipa.get("ausencias_confirmadas") or []}
    provaveis_hoje = {a["cir"] for a in (equipa.get("ausencias_provaveis") or []) if a.get("dia") == today_str}
    rows = []
    for cir, (nome, dot) in EQUIPA_REF.items():
        row = eq_row_tpl
        row = row.replace("{{EQ_DOT_CLASS}}", dot)
        row = row.replace("{{EQ_NOME}}", esc(nome))
        if cir in confirmadas:
            motivo = confirmadas[cir].get("motivo", "")
            status_txt = "Férias" if motivo.lower() == "férias" else "Ausente"
            row = row.replace("{{EQ_STATUS_CLASS}}", "away")
            row = row.replace("{{EQ_STATUS_TEXTO}}", esc(f"Ausente ({status_txt})" if status_txt != "Férias" else "Ausente (Férias)"))
        elif cir in provaveis_hoje:
            row = row.replace("{{EQ_STATUS_CLASS}}", "away")
            row = row.replace("{{EQ_STATUS_TEXTO}}", "Provável ausente")
        else:
            row = row.replace("{{EQ_STATUS_CLASS}}", "")
            row = row.replace("{{EQ_STATUS_TEXTO}}", "Presente")
        rows.append(row)
    template = put_block(template, "EQUIPA_ROW", "".join(rows))

    if confirmadas:
        proximas_txt = "; ".join(
            f"{EQUIPA_REF.get(cir, (cir, ''))[0]} — {a.get('motivo','')} ({a.get('datas','')})"
            for cir, a in confirmadas.items()
        )
    else:
        proximas_txt = "Sem ausências futuras previstas."
    template = template.replace("{{EQUIPA_PROXIMAS}}", esc(proximas_txt))

    gerado_hora = ""
    if meta.get("generated_at"):
        gerado_hora = meta["generated_at"][11:16]
    template = template.replace("{{GERADO_HORA}}", esc(gerado_hora))

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(template)

    print(f"OK: painel HFF renderizado -> {output_path}")


if __name__ == "__main__":
    main()
