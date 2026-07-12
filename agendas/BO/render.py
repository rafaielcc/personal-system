#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
render.py — Render Layer da Lista BO (Modulo 4 / Rotina de Publicação)

Le o MESMO JSON canonico do Painel HFF (schema Seccao 11 de
INSTRUCOES_PAINEL_HFF_v5.0.md) + template.html (estatico, sem logica de
negocio) e produz o index.html final por substituicao mecanica de texto.
Apenas stdlib do Python — mesmo padrao do render.py do Briefing/Lazer/HFF.

Diferenca chave vs. o render do Painel HFF (pessoal): esta pagina e
PUBLICA / FACE A EQUIPA. Nunca inclui tarefas pessoais, calendario pessoal
nem a escala de Prevencao (Secao 9 das instrucoes). Motivo de ausencia:
mostra "Ferias" so se for ferias, caso contrario "Ausente" generico.

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
# Validacao (mesmo schema do Painel HFF — so usa cirurgias + equipa daqui)
# --------------------------------------------------------------------------
def validate_canonical(data):
    errors = []
    meta = data.get("meta")
    if not isinstance(meta, dict) or not meta.get("date"):
        errors.append("meta.date em falta.")
    if not isinstance(data.get("cirurgias"), dict) or not isinstance(data["cirurgias"].get("sessoes"), list):
        errors.append("cirurgias.sessoes em falta (lista).")
    if not isinstance(data.get("equipa"), dict):
        errors.append("'equipa' em falta (objecto).")
    return errors


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------
def esc(text):
    return html_lib.escape(str(text) if text is not None else "", quote=True)


def parse_date(s):
    return datetime.strptime(s, "%Y-%m-%d").date()


def fmt_date_short(date_str):
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    return f"{dt.day} {MESES_ABR[dt.month]}"


def weekday_pt(date_str):
    return DIAS_SEMANA_PT[datetime.strptime(date_str, "%Y-%m-%d").weekday()]


def fmt_full_label(date_str):
    return f"{weekday_pt(date_str).capitalize()}, {fmt_date_short(date_str)}"


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
    cirurgias = data["cirurgias"]
    equipa = data["equipa"]

    with open(template_path, "r", encoding="utf-8") as f:
        template = f.read()

    gerado_hora = meta.get("generated_at", "")[11:16] if meta.get("generated_at") else ""
    template = template.replace("{{GERADO_HORA}}", esc(gerado_hora))
    template = template.replace("{{GERADO_LABEL}}", esc(f"{fmt_full_label(meta['date'])} · {gerado_hora}"))

    # ---- Agrupar sessoes por data, depois por semana ISO ----
    by_date = {}
    for s in cirurgias.get("sessoes", []):
        by_date.setdefault(s["date"], {"M": [], "S": []})
        periodo = s.get("periodo")
        by_date[s["date"]][periodo if periodo in ("M", "S") else "M"].extend(s.get("doentes") or [])

    weeks = {}
    for d in by_date:
        iso = parse_date(d).isocalendar()
        weeks.setdefault((iso[0], iso[1]), []).append(d)

    # ---- Ausencias da equipa (mesmo dado do Painel HFF; motivo so mostrado se Ferias) ----
    confirmadas = {a["cir"]: a for a in equipa.get("ausencias_confirmadas") or []}

    # ---- Templates dos blocos repetiveis ----
    btn_tpl, template = require_block(template, "WEEK_TAB_BTN")
    panel_tpl, template = require_block(template, "WEEK_TAB_PANEL")
    pill_tpl, panel_tpl_body = require_block(panel_tpl, "WTP_TEAM_PILL")
    sem_sessoes_inner, panel_tpl_body = require_block(panel_tpl_body, "WTP_SEM_SESSOES")
    session_tpl, panel_tpl_body = require_block(panel_tpl_body, "WTP_SESSION")
    m_row_tpl, session_tpl_body = require_block(session_tpl, "SESSAO_DOENTE_M")
    sem_manha_inner, session_tpl_body = require_block(session_tpl_body, "SESSAO_SEM_MANHA")
    tarde_tpl, session_tpl_body = require_block(session_tpl_body, "SESSAO_TARDE")
    s_row_tpl, tarde_tpl_body = require_block(tarde_tpl, "SESSAO_DOENTE_S")

    btns_html = ""
    panels_html = ""
    for i, (_, dates) in enumerate(sorted(weeks.items())):
        dates_sorted = sorted(dates)
        week_id = f"semana{i+1}"
        week_label = f"Semana {fmt_date_short(dates_sorted[0])} – {fmt_date_short(dates_sorted[-1])}"
        active = "active" if i == 0 else ""

        btn = btn_tpl.replace("{{WTB_ACTIVE}}", active)
        btn = btn.replace("{{WTB_ID}}", week_id)
        btn = btn.replace("{{WTB_LABEL}}", esc(week_label))
        btns_html += btn

        # Equipa (mesmo estado para toda a pagina — o schema nao segmenta por semana)
        pills_html = ""
        for cir, (nome, dot) in EQUIPA_REF.items():
            pill = pill_tpl
            pill = pill.replace("{{TP_DOT_CLASS}}", dot)
            pill = pill.replace("{{TP_NOME}}", esc(nome))
            if cir in confirmadas:
                motivo = confirmadas[cir].get("motivo", "")
                suffix = " — Férias" if motivo.lower() == "férias" else " — Ausente"
                pill = pill.replace("{{TP_AWAY_CLASS}}", "away")
                pill = pill.replace("{{TP_STATUS_SUFFIX}}", esc(suffix))
            else:
                pill = pill.replace("{{TP_AWAY_CLASS}}", "")
                pill = pill.replace("{{TP_STATUS_SUFFIX}}", "")
            pills_html += pill

        sessions_html = ""
        for d in dates_sorted:
            m_doentes = sorted(by_date[d]["M"], key=lambda x: x.get("idade_raw", 0))
            s_doentes = sorted(by_date[d]["S"], key=lambda x: x.get("idade_raw", 0))
            sess = session_tpl_body
            sess = sess.replace("{{SESSAO_LABEL}}", esc(fmt_full_label(d)))
            if m_doentes:
                rows = "".join(
                    fill_doente_row(m_row_tpl, x, "{{SM_FDR_CLASS}}", "{{SM_PROCESSO}}", "{{SM_IDADE}}",
                                    "{{SM_NOME}}", "{{SM_PROCEDIMENTO}}", "{{SM_OBS}}")
                    for x in m_doentes
                )
                sess = put_block(sess, "SESSAO_DOENTE_M", rows)
                sess = put_block(sess, "SESSAO_SEM_MANHA", "")
            else:
                sess = put_block(sess, "SESSAO_DOENTE_M", "")
                sess = put_block(sess, "SESSAO_SEM_MANHA", sem_manha_inner)

            sess = sess.replace("{{SESSAO_TARDE_DISPLAY}}", "flex" if s_doentes else "none")
            if s_doentes:
                rows = "".join(
                    fill_doente_row(s_row_tpl, x, "{{SS_FDR_CLASS}}", "{{SS_PROCESSO}}", "{{SS_IDADE}}",
                                    "{{SS_NOME}}", "{{SS_PROCEDIMENTO}}")
                    for x in s_doentes
                )
                resumo_procs = ", ".join(x.get("procedimento", "") for x in s_doentes[:3])
                tarde_filled = tarde_tpl_body.replace("{{SESSAO_N_SIGIC}}", str(len(s_doentes)))
                tarde_filled = tarde_filled.replace("{{SESSAO_SIGIC_RESUMO}}", esc(resumo_procs))
                tarde_filled = put_block(tarde_filled, "SESSAO_DOENTE_S", rows)
                sess = put_block(sess, "SESSAO_TARDE", tarde_filled)
            else:
                sess = put_block(sess, "SESSAO_TARDE", "")
            sessions_html += sess

        panel = panel_tpl_body
        panel = panel.replace("{{WTP_ID}}", week_id)
        panel = panel.replace("{{WTP_ACTIVE}}", active)
        panel = put_block(panel, "WTP_TEAM_PILL", pills_html)
        if sessions_html:
            panel = put_block(panel, "WTP_SESSION", sessions_html)
            panel = put_block(panel, "WTP_SEM_SESSOES", "")
        else:
            panel = put_block(panel, "WTP_SESSION", "")
            panel = put_block(panel, "WTP_SEM_SESSOES", sem_sessoes_inner)
        panels_html += panel

    template = put_block(template, "WEEK_TAB_BTN", btns_html)
    template = put_block(template, "WEEK_TAB_PANEL", panels_html)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(template)

    print(f"OK: lista BO renderizada -> {output_path}")


if __name__ == "__main__":
    main()
