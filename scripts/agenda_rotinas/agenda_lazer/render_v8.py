#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
render.py — Render Layer da Agenda de Lazer (Modulo 2 / Expansion Architecture)

v2 — feedback do Rafa 11 Jul 2026: removido dashboard de contagens; "Todos"
substituido por "Highlights" (evento marcado com highlight:true no JSON
canonico); descricoes longas ficam expansiveis (<details>) em vez de
truncadas sem alternativa; Meetup agrupado por data em blocos expansiveis;
Meetup e Cultura destacam eventos confirmados (confirmed:true) num bloco
proprio no topo.

v3 — 11 Jul 2026: botao "Salvar" nos cards de Livros e Escapadinhas, que
envia a sugestao para um Zap (Catch Hook -> Google Drive Create File) para
nao se perder quando a proxima geracao da agenda a substituir.

v4 — 11 Jul 2026: Livros/Escapadinhas passam a suportar o campo saved:true
(preenchido pela LLM ao ler a pasta "Guardados da Agenda" antes de gerar o
JSON canonico) — os itens guardados aparecem num bloco proprio no topo da
seccao, separados das sugestoes novas.

v5 — 11 Jul 2026: Streaming ganha o mesmo botao "Salvar" e bloco "Guardados"
de Livros/Escapadinhas (grava como category:other, subcategory:streaming
no Feedback_log).

v8 — 22 Ago 2026 (3a sessao do dia): reversao pedida pelo Rafa — o pedido
de nota/pontuacao no clique (introduzido na v7, no template.html) volta a
sair. A ideia dele desde o inicio era o score ser pedido fora do
browser/LLM, numa rotina Python local (merge_feedback.py, mesmo padrao do
preflight_hff.py/postflight_hff.py) que ele corre na propria maquina.
CURATION_ACOES mantem o 4o botao "consumido"/✅ em todos os cards, so o
texto do tooltip mudou (nao promete mais "registar nota" — o clique so
marca "ja experimentei"). Nenhuma mudanca de logica neste ficheiro alem
disso — o prompt em si nunca esteve aqui, estava no template.html.

Update local — 28 Ago 2026: botao antigo "Salvar" / Zapier aposentado nos
renders futuros. A curadoria passa pela sheet espelho_lazer; o bloco
"Guardado para o futuro" vem de futuro_guardado[] calculado pelo preflight.

v7 — 22 Ago 2026 (2a sessao do dia): feedback do Rafa sobre a v6. (1)
build_calendario_dias() passa a preencher a grelha com celulas vazias
("vazio": true) no inicio, na quantidade de dias entre a ultima segunda-
feira e o periodo_inicio (inicio.weekday(), segunda=0) — mesmo padrao ja
usado no Briefing (build_cal_cells em X_Rotinas_Python), 1a coluna sempre
segunda, ultima domingo. Antes a grelha comecava sempre no dia 1 =
periodo_inicio, desalinhado do resto do projecto quando esse dia nao caia
numa segunda. (2) CURATION_ACOES ganha uma 4a entrada ("consumido", icone
✅) — disponivel em TODOS os cards, nao so no bloco "Guardado para o
futuro" (que ja usava esta mesma accao via build_futuro_block). O prompt
de nota/pontuacao fica inteiramente no template.html (curarItem), nao
aqui — este ficheiro so monta o botao e o payload base.

v6 — 22 Ago 2026: curadoria (pedido do Rafa). Todo card ganha 3 icones novos
(remover / elevar / guardar para o futuro), gravados via Apps Script na sheet
espelho_lazer. Highlights ganha: (a) bloco de calendario expansivel, construido
a partir de meta.periodo_inicio/periodo_fim + date/date_inicio/date_fim de
cada evento + meta.calendario_pessoal (compromissos reais); (b) bloco
"Guardado para o futuro", a partir do novo campo top-level futuro_guardado[].
Tudo aditivo/opcional no schema: um JSON sem estes campos novos renderiza
identico a v5, so sem calendario nem bloco futuro.

Le o JSON canonico (produzido pela LLM) + template.html (estatico, sem logica
de negocio) e produz o index.html final por substituicao mecanica de texto.
Nao usa Jinja2 nem qualquer dependencia externa — apenas a stdlib do Python,
para correr sem instalacao em qualquer sandbox bash.

A LLM nunca volta a escrever HTML livremente: a unica camada onde a LLM
exerce juizo e o JSON canonico (events[], incluindo highlight/confirmed/saved).
Este script e puramente mecanico e deve produzir o mesmo HTML sempre que
receber o mesmo JSON + template.

Uso:
    python3 render.py <input.json> <template.html> <output.html>

Codigo de saida 0 = sucesso. Qualquer falha de validacao do JSON aborta
com mensagem clara (nao tenta "adivinhar" campos em falta).
"""

import sys
import json
import re
import html
from datetime import date, timedelta
from itertools import groupby
from urllib.parse import quote

# ----------------------------------------------------------------------------
# Metadados por categoria (cor da tarja de 4px, fundo do cartao, label, icone)
# "highlights" e uma categoria virtual: nao existe em events[].category, e
# povoada a partir de eventos de qualquer categoria com highlight:true.
# ----------------------------------------------------------------------------
CATEGORY_META = {
    "highlights":     {"stripe": "#D4A017", "bg_class": "bg-highlights", "icon": "✨", "label": "Highlights"},
    "tv":             {"stripe": "#2563EB", "bg_class": "bg-tv",     "icon": "📺", "label": "Televisão"},
    "streaming":      {"stripe": "#0EA5E9", "bg_class": "",          "icon": "🎬", "label": "Streaming"},
    "cinema_indoor":  {"stripe": "#C75A2C", "bg_class": "",          "icon": "🎟️", "label": "Cinema"},
    "cinema_outdoor": {"stripe": "#EA580C", "bg_class": "",          "icon": "🌙", "label": "Cinema ao ar livre"},
    "meetup":         {"stripe": "#1A3D52", "bg_class": "",          "icon": "🤝", "label": "Meetup"},
    "culture":        {"stripe": "#7C3AED", "bg_class": "",          "icon": "🎭", "label": "Cultura"},
    "books":          {"stripe": "#92400E", "bg_class": "",          "icon": "📚", "label": "Livro"},
    "gastro":         {"stripe": "#C75A2C", "bg_class": "",          "icon": "🍽️", "label": "Gastronomia"},
    "escape":         {"stripe": "#16A34A", "bg_class": "bg-escape", "icon": "🧭", "label": "Escapadinha"},
    "radar":          {"stripe": "#6B7280", "bg_class": "",          "icon": "📡", "label": "Radar"},
}

# Ordem de renderizacao das seccoes reais (exclui a virtual "highlights",
# que e tratada em separado por nao ter eventos proprios em events[]).
CATEGORIES_ORDER = [c for c in CATEGORY_META if c != "highlights"]

# Categorias cuja seccao usa layout composto (bloco de confirmados +
# agrupamento por data) em vez do grid simples.
GROUPED_LAYOUT_CATEGORIES = {"meetup", "culture"}

# Comprimento da pre-visualizacao antes de precisar expandir (<details>).
# Acima disto a descricao fica expansivel; textos mais curtos aparecem
# sempre por inteiro sem qualquer interacao.
DESCRIPTION_PREVIEW_LENGTH = 260

REQUIRED_EVENT_FIELDS = ["id", "category", "title", "date_label", "description"]
UNDATED_CATEGORIES = {"streaming", "books", "gastro", "escape"}


# ----------------------------------------------------------------------------
# Validacao
# ----------------------------------------------------------------------------
def validate_canonical(data):
    errors = []
    if "events" not in data or not isinstance(data["events"], list):
        errors.append("Falta o campo 'events' (lista) no JSON canonico.")
        return errors
    for i, ev in enumerate(data["events"]):
        for field in REQUIRED_EVENT_FIELDS:
            if field not in ev or ev[field] in (None, ""):
                errors.append(f"events[{i}] (id={ev.get('id','?')}) falta campo obrigatorio: '{field}'")
        cat = ev.get("category")
        if cat not in CATEGORY_META or cat == "highlights":
            errors.append(f"events[{i}] (id={ev.get('id','?')}) categoria desconhecida ou invalida: '{cat}'")
        if "date" not in ev:
            errors.append(f"events[{i}] (id={ev.get('id','?')}) deve conter a chave 'date'")
        elif ev.get("date") in (None, "") and cat not in UNDATED_CATEGORIES:
            errors.append(f"events[{i}] (id={ev.get('id','?')}) precisa de data factual na categoria '{cat}'")
    return errors


# ----------------------------------------------------------------------------
# Helpers de formatacao (mecanicos, sem juizo de conteudo)
# ----------------------------------------------------------------------------
def truncate(text, max_len=DESCRIPTION_PREVIEW_LENGTH):
    text = text or ""
    if len(text) <= max_len:
        return text
    return text[: max_len - 1].rstrip() + "…"


def esc(text):
    return html.escape(text or "", quote=True)


def build_badges_html(ev):
    badges = []
    if ev.get("confirmed"):
        badges.append('<span class="badge badge-confirmed">✅ Confirmado</span>')
    if ev.get("saved"):
        badges.append('<span class="badge badge-saved">📌 Guardado</span>')
    if ev.get("elevado"):
        expira = ev.get("elevado_expira_label")
        texto = "⬆ Elevado" + (f" · {expira}" if expira else "")
        badges.append(f'<span class="badge badge-elevado">{esc(texto)}</span>')
    if ev.get("status_badge"):
        badges.append(f'<span class="badge">{esc(ev["status_badge"])}</span>')
    if ev.get("price_badge"):
        badges.append(f'<span class="badge">{esc(ev["price_badge"])}</span>')
    if ev.get("rating") is not None:
        badges.append(f'<span class="badge">⭐ {esc(str(ev["rating"]))}</span>')
    if ev.get("platform"):
        badges.append(f'<span class="badge">{esc(ev["platform"])}</span>')
    if ev.get("channel"):
        badges.append(f'<span class="badge">{esc(ev["channel"])}</span>')
    return "".join(badges)


def build_meta_line(ev):
    parts = [esc(ev.get("date_label", ""))]
    if ev.get("time"):
        parts.append(esc(ev["time"]))
    if ev.get("location"):
        parts.append(esc(ev["location"]))
    return " · ".join(p for p in parts if p)


def build_description_block(ev):
    """Descricoes curtas aparecem por inteiro num <div>; descricoes longas
    ficam num <details> com pre-visualizacao + 'ler mais' — nunca cortadas
    sem alternativa (pedido do Rafa: a pagina tem de bastar-se a si mesma,
    sem ter de sair para pesquisar detalhes)."""
    desc = ev.get("description", "") or ""
    if not desc:
        return ""
    if len(desc) <= DESCRIPTION_PREVIEW_LENGTH:
        return f'<div class="card-desc">{esc(desc)}</div>'
    preview = truncate(desc)
    return (
        '<details class="card-desc-details">'
        f'<summary class="card-desc-preview">{esc(preview)}</summary>'
        f'<div class="card-desc-full">{esc(desc)}</div>'
        '</details>'
    )


def build_with_block(ev):
    tags = ev.get("with_tags") or []
    if not tags:
        return ""
    joined = ", ".join(esc(t) for t in tags)
    return f'<div class="card-with">👥 Com: {joined}</div>'


PARKING_EMOJI = {
    "facil": "🟢",
    "dificil": "🟡",
    "pago": "🔵",
    "muito_dificil": "🔴",
}


def build_logistics_block(ev):
    log = ev.get("logistics") or {}
    dist = log.get("distance_min")
    via = log.get("via")
    parking_status = log.get("parking_status")
    if dist is None and not via and not parking_status:
        return ""
    pieces = []
    if dist is not None and via:
        pieces.append(f"🚗 {esc(str(dist))} min via {esc(via)}")
    elif dist is not None:
        pieces.append(f"🚗 {esc(str(dist))} min")
    if parking_status:
        emoji = log.get("parking_emoji") or PARKING_EMOJI.get(parking_status, "⚪")
        pieces.append(f"{emoji} Parking: {esc(parking_status)}")
    if not pieces:
        return ""
    return f'<div class="card-logistica">{" | ".join(pieces)}</div>'


def build_link_button(ev):
    if not ev.get("link"):
        return ""
    return f'<a class="btn btn-mais" href="{esc(ev["link"])}" target="_blank" rel="noopener">Mais info →</a>'


def build_whatsapp_href(ev):
    msg = f'{ev.get("title","")} — {ev.get("date_label","")}'
    if ev.get("location"):
        msg += f' @ {ev["location"]}'
    if ev.get("link"):
        msg += f' {ev["link"]}'
    return "https://wa.me/?text=" + quote(msg)


def build_email_href(ev):
    subject = quote(f'Agenda de Lazer: {ev.get("title","")}')
    body_lines = [ev.get("title", ""), ev.get("date_label", "")]
    if ev.get("location"):
        body_lines.append(ev["location"])
    if ev.get("description"):
        body_lines.append(ev["description"])
    if ev.get("link"):
        body_lines.append(ev["link"])
    body = quote("\n".join(body_lines))
    return f"mailto:?subject={subject}&body={body}"


def build_save_button(ev):
    return ""


# ----------------------------------------------------------------------------
# Curadoria: remover / elevar / guardar para o futuro / consumido em qualquer
# card, tudo gravado na sheet espelho_lazer. O antigo botao Salvar/Zapier foi
# aposentado; a proxima geracao le a sheet no preflight local.
# ----------------------------------------------------------------------------
def build_dedup_key(title, category):
    return (title or "").strip().casefold() + "::" + (category or "")


CURATION_ACOES = [
    ("removido", "icon-remover", "✕", "Remover — não mostrar mais"),
    ("elevar", "icon-elevar", "⬆", "Elevar para Highlights"),
    ("guardado_futuro", "icon-futuro", "🕒", "Guardar para o futuro"),
    # v7 (pedido do Rafa): disponivel em TODOS os cards, nao so no bloco
    # "Guardado para o futuro" — mesma acao "consumido" que ja existia la
    # (build_futuro_block), reaproveitada aqui para restaurantes/lugares/
    # filmes vistos directamente a partir da sugestao. v9: NAO pede nota no
    # clique (isso reverteu-se para o merge_feedback.py, script local do
    # Rafa) — o clique so marca "ja experimentei", sem prompt nenhum.
    ("consumido", "icon-experimentei", "✅", "Já experimentei / já vi / já fui"),
]


def build_curation_buttons(ev):
    dedup_key = build_dedup_key(ev.get("title"), ev.get("category"))
    date_val = ev.get("date") or ev.get("date_inicio") or ""
    buttons = []
    for acao, css_class, icon, title_attr in CURATION_ACOES:
        payload = {
            "dedup_key": dedup_key,
            "title": ev.get("title", ""),
            "category": ev.get("category", ""),
            "date": date_val,
            "acao": acao,
        }
        payload_json = esc(json.dumps(payload, ensure_ascii=False))
        ativo_class = " ativo" if (acao == "elevar" and ev.get("elevado")) else ""
        buttons.append(
            f'<button type="button" class="icon-btn {css_class}{ativo_class}" '
            f'data-payload="{payload_json}" data-acao="{acao}" onclick="curarItem(this)" '
            f'title="{esc(title_attr)}">{icon}</button>'
        )
    return '<div class="icon-acoes">' + "".join(buttons) + "</div>"


def build_futuro_block(futuro_items):
    """Bloco 'Guardado para o futuro' no fim da seccao Highlights — a partir
    do campo top-level futuro_guardado[] (NAO events[]: sao itens que a LLM
    recebeu do pre mecanico a partir da sheet espelho_lazer com
    acao=guardado_futuro, nao sugestoes desta geracao). Botao Consumido fecha
    o ciclo de curadoria; qualquer merge permanente no Feedback_log continua
    exclusivo do merge_feedback.py local."""
    if not futuro_items:
        return ""
    rows = []
    for it in futuro_items:
        dedup_key = it.get("dedup_key") or build_dedup_key(it.get("title"), it.get("category"))
        titulo = esc(it.get("title", ""))
        nota = it.get("nota") or ""
        data_guardado = it.get("data_guardado", "")
        sub = esc(f"Guardado a {data_guardado}" + (f" · {nota}" if nota else ""))
        payload_base = {
            "dedup_key": dedup_key,
            "title": it.get("title", ""),
            "category": it.get("category", ""),
            "date": "",
        }
        payload_consumido = esc(json.dumps({**payload_base, "acao": "consumido"}, ensure_ascii=False))
        payload_remover = esc(json.dumps({**payload_base, "acao": "removido"}, ensure_ascii=False))
        rows.append(
            '<div class="futuro-item">'
            f'<div><strong>{titulo}</strong><span class="sub">{sub}</span></div>'
            '<div class="futuro-acoes">'
            f'<button type="button" class="icon-btn icon-consumido" data-payload="{payload_consumido}" '
            'data-acao="consumido" onclick="curarItem(this)" title="Marcar como consumido">✓</button>'
            f'<button type="button" class="icon-btn icon-remover" data-payload="{payload_remover}" '
            'data-acao="removido" onclick="curarItem(this)" title="Remover">✕</button>'
            '</div></div>'
        )
    return (
        '<div class="futuro-bloco">'
        '<div class="futuro-titulo">🕒 Guardado para o futuro</div>'
        + "".join(rows) +
        '</div>'
    )


# ----------------------------------------------------------------------------
# Calendario expansivel (Highlights) — cruza sugestoes (date/date_inicio/
# date_fim de events[]) com compromissos reais (meta.calendario_pessoal).
# So aparece se o JSON trouxer meta.periodo_inicio + meta.periodo_fim; sem
# isso build_calendario_dias devolve [] e o bloco e simplesmente omitido
# (mesma regra mecanica de "nunca seccao vazia" das restantes seccoes).
# ----------------------------------------------------------------------------
DOW_PT = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]


def parse_iso_date(s):
    y, m, d = s.split("-")
    return date(int(y), int(m), int(d))


def build_calendario_dias(data, events):
    meta = data.get("meta", {})
    inicio_s = meta.get("periodo_inicio")
    fim_s = meta.get("periodo_fim")
    if not inicio_s or not fim_s:
        return []
    try:
        inicio = parse_iso_date(inicio_s)
        fim = parse_iso_date(fim_s)
    except (ValueError, AttributeError):
        return []
    hoje_s = meta.get("hoje")
    hoje = None
    if hoje_s:
        try:
            hoje = parse_iso_date(hoje_s)
        except (ValueError, AttributeError):
            hoje = None

    compromissos_por_dia = {}
    for entrada in meta.get("calendario_pessoal", []) or []:
        chave = entrada.get("date")
        if not chave:
            continue
        compromissos_por_dia.setdefault(chave, []).extend(entrada.get("compromissos", []) or [])

    sugestoes_por_dia = {}
    for ev in events:
        d_ini_s = ev.get("date_inicio") or ev.get("date")
        d_fim_s = ev.get("date_fim") or ev.get("date")
        if not d_ini_s or not d_fim_s or not ev.get("id"):
            continue
        try:
            cursor = parse_iso_date(d_ini_s)
            limite = parse_iso_date(d_fim_s)
        except (ValueError, AttributeError):
            continue
        while cursor <= limite:
            chave = cursor.isoformat()
            sugestoes_por_dia.setdefault(chave, []).append(
                {"t": ev.get("title", ""), "href": "#" + ev["id"], "cat": ev.get("category", "")}
            )
            cursor += timedelta(days=1)

    # Padding no inicio da grelha (mesmo padrao do Briefing, ver
    # agendas/briefing/index.html v6: "1a coluna sempre segunda, ultima
    # domingo" — celulas vazias em quantidade igual ao dia da semana real
    # do primeiro dia do periodo, segunda=0) — nunca a grelha comecar no
    # dia de hoje/periodo_inicio independentemente do seu dia da semana.
    dias = [
        {"d": None, "dow": "", "hoje": False, "sug": [], "comp": [], "vazio": True}
        for _ in range(inicio.weekday())
    ]
    cursor = inicio
    while cursor <= fim:
        chave = cursor.isoformat()
        dias.append({
            "d": cursor.day,
            "dow": DOW_PT[cursor.weekday()],
            "hoje": (cursor == hoje),
            "sug": sugestoes_por_dia.get(chave, []),
            "comp": compromissos_por_dia.get(chave, []),
            "vazio": False,
        })
        cursor += timedelta(days=1)
    return dias


def build_calendario_block(dias):
    if not dias:
        return ""
    return (
        '<details class="cal-bloco">'
        '<summary>📅 Ver calendário do período</summary>'
        '<div class="cal-body">'
        '<div class="cal-grid" id="calGrid"></div>'
        '<div class="cal-detalhe" id="calDetalhe" hidden>'
        '<div class="cal-col"><h4>Sugestões</h4><ul id="calSugestoes"></ul></div>'
        '<div class="cal-col"><h4>Compromissos</h4><ul id="calCompromissos"></ul></div>'
        '</div></div></details>'
    )


def render_card(ev, card_tpl, id_suffix=""):
    """id_suffix distingue a copia de um card na seccao virtual 'highlights'
    (id_suffix='--hl') da copia na sua seccao real — o mesmo evento e
    renderizado duas vezes quando highlight:true, e um id duplicado no HTML
    tornaria as ancoras do calendario ambiguas (document.querySelector devolve
    sempre a primeira ocorrencia, que seria a copia potencialmente escondida).
    O calendario aponta sempre para o id sem sufixo — a copia na seccao real,
    que existe sempre, esteja o evento em highlight ou nao."""
    meta = CATEGORY_META[ev["category"]]
    card_html = card_tpl
    card_html = card_html.replace("{{ID}}", esc(ev.get("id", "")) + id_suffix)
    card_html = card_html.replace("{{CATEGORY}}", ev["category"])
    card_html = card_html.replace("{{CARD_BG_CLASS}}", meta["bg_class"])
    card_html = card_html.replace("{{STRIPE_COLOR}}", meta["stripe"])
    card_html = card_html.replace("{{TITLE}}", esc(ev["title"]))
    card_html = card_html.replace("{{BADGES_HTML}}", build_badges_html(ev))
    card_html = card_html.replace("{{DATE_LABEL}}", build_meta_line(ev))
    card_html = card_html.replace("{{TIME_SUFFIX}}", "")
    card_html = card_html.replace("{{LOCATION_SUFFIX}}", "")
    card_html = card_html.replace("{{DESCRIPTION_BLOCK}}", build_description_block(ev))
    card_html = card_html.replace("{{WITH_BLOCK}}", build_with_block(ev))
    card_html = card_html.replace("{{LOGISTICS_BLOCK}}", build_logistics_block(ev))
    card_html = card_html.replace("{{LINK_BUTTON}}", build_link_button(ev))
    card_html = card_html.replace("{{WHATSAPP_HREF}}", build_whatsapp_href(ev))
    card_html = card_html.replace("{{EMAIL_HREF}}", build_email_href(ev))
    card_html = card_html.replace("{{SAVE_BUTTON}}", build_save_button(ev))
    card_html = card_html.replace("{{CURATION_BUTTONS}}", build_curation_buttons(ev))
    return card_html


def build_simple_grid_html(evs, card_tpl, id_suffix=""):
    return "\n".join(render_card(ev, card_tpl, id_suffix) for ev in evs)


def build_confirmed_block(confirmed_evs, card_tpl):
    if not confirmed_evs:
        return ""
    cards = build_simple_grid_html(confirmed_evs, card_tpl)
    return (
        '<div class="confirmados-bloco">'
        '<div class="confirmados-titulo">✅ Já confirmados</div>'
        f'<div class="grid-cards">{cards}</div>'
        '</div>'
    )


def build_meetup_section_html(evs, card_tpl):
    """Bloco de confirmados no topo + restantes agrupados por data em
    blocos expansiveis (<details open> — visiveis por omissao, mas
    recolhiveis), como pedido pelo Rafa para tornar a seccao mais legivel."""
    confirmed = [e for e in evs if e.get("confirmed")]
    rest = [e for e in evs if not e.get("confirmed")]
    parts = [build_confirmed_block(confirmed, card_tpl)]

    rest_sorted = sorted(rest, key=lambda e: (e.get("date", ""), e.get("time") or ""))
    for (date_val, date_label), group_iter in groupby(
        rest_sorted, key=lambda e: (e.get("date", ""), e.get("date_label", ""))
    ):
        group_evs = list(group_iter)
        cards = build_simple_grid_html(group_evs, card_tpl)
        parts.append(
            '<details class="data-grupo" open>'
            f'<summary class="data-grupo-titulo">{esc(date_label)} '
            f'<span class="data-grupo-count">({len(group_evs)})</span></summary>'
            f'<div class="grid-cards">{cards}</div>'
            '</details>'
        )
    return "\n".join(p for p in parts if p)


def build_culture_section_html(evs, card_tpl):
    """Bloco de confirmados no topo + restantes num grid simples (sem
    agrupamento por data — apenas o Meetup pediu essa granularidade)."""
    confirmed = [e for e in evs if e.get("confirmed")]
    rest = [e for e in evs if not e.get("confirmed")]
    parts = [build_confirmed_block(confirmed, card_tpl)]
    if rest:
        cards = build_simple_grid_html(rest, card_tpl)
        parts.append(f'<div class="grid-cards">{cards}</div>')
    return "\n".join(p for p in parts if p)


def build_saved_block(saved_evs, card_tpl):
    if not saved_evs:
        return ""
    cards = build_simple_grid_html(saved_evs, card_tpl)
    return (
        '<div class="guardado-bloco">'
        '<div class="guardado-titulo">📌 Guardados numa geração anterior</div>'
        f'<div class="grid-cards">{cards}</div>'
        '</div>'
    )


def build_saveable_section_html(evs, card_tpl):
    """Livros/Escapadinhas/Streaming: itens marcados saved:true (lidos da
    pasta 'Guardados da Agenda' pela LLM antes de gerar o JSON canonico)
    aparecem num bloco proprio no topo, separados das sugestoes novas —
    pedido do Rafa para nunca perder uma sugestao entre geracoes."""
    saved = [e for e in evs if e.get("saved")]
    rest = [e for e in evs if not e.get("saved")]
    parts = [build_saved_block(saved, card_tpl)]
    if rest:
        cards = build_simple_grid_html(rest, card_tpl)
        parts.append(f'<div class="grid-cards">{cards}</div>')
    return "\n".join(p for p in parts if p)


# ----------------------------------------------------------------------------
# Extracao de blocos marcados no template (CARD / SECTION / PILL)
# ----------------------------------------------------------------------------
def extract_block(template, marker):
    pattern = re.compile(
        r"<!--" + marker + r"-->(.*?)<!--/" + marker + r"-->", re.DOTALL
    )
    m = pattern.search(template)
    if not m:
        return None, template
    full_match = m.group(0)
    inner = m.group(1)
    stripped = template.replace(full_match, "{{__PLACEHOLDER_" + marker + "__}}", 1)
    return inner, stripped


def remove_block_markers_only(template, marker):
    """Remove os comentarios-marcador mas preserva o conteudo interior."""
    template = template.replace(f"<!--{marker}-->", "")
    template = template.replace(f"<!--/{marker}-->", "")
    return template


def main():
    if len(sys.argv) != 4:
        print("Uso: python3 render.py <input.json> <template.html> <output.html>")
        sys.exit(1)

    input_path, template_path, output_path = sys.argv[1], sys.argv[2], sys.argv[3]

    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    errors = validate_canonical(data)
    if errors:
        print("ERRO: JSON canonico invalido — render abortado.")
        for e in errors:
            print(" -", e)
        sys.exit(2)

    events = data["events"]
    meta = data.get("meta", {})
    summary = data.get("summary", {})
    validation = data.get("validation", {})

    with open(template_path, "r", encoding="utf-8") as f:
        template = f.read()

    # 1) Extrair o snippet de cartao generico (unico, reutilizado por todas
    #    as categorias) e remove-lo do corpo do template.
    card_tpl, template = extract_block(template, "CARD")
    if card_tpl is None:
        print("ERRO: template.html nao contem o bloco <!--CARD--> ... <!--/CARD-->")
        sys.exit(3)
    template = template.replace("{{__PLACEHOLDER_CARD__}}", "")

    # 2) Agrupar eventos por categoria real + popular a categoria virtual
    #    "highlights" com qualquer evento marcado highlight:true (mantendo
    #    a sua categoria/estilo original quando exibido nesse cartao).
    events_by_cat = {cat: [] for cat in CATEGORIES_ORDER}
    highlights = []
    for ev in events:
        cat = ev["category"]
        if cat in events_by_cat:
            events_by_cat[cat].append(ev)
        if ev.get("highlight"):
            highlights.append(ev)
    for cat in events_by_cat:
        events_by_cat[cat].sort(key=lambda e: (e.get("date") or "9999-12-31", e.get("time") or ""))
    highlights.sort(key=lambda e: (e.get("date") or "9999-12-31", e.get("time") or ""))

    all_cats_for_render = ["highlights"] + CATEGORIES_ORDER
    events_by_cat["highlights"] = highlights

    # 3) Para cada categoria: preencher {{CARDS:cat}} (ou o layout composto
    #    para meetup/culture/books/escape/streaming) ou remover a seccao
    #    toda se nao houver eventos (regra mecanica — nunca seccao vazia).
    # Calendario final para a variavel JS do passo 5 — computado uma unica
    # vez quando a seccao "highlights" e processada abaixo.
    calendario_dias_final = []

    for cat in all_cats_for_render:
        evs = events_by_cat[cat]
        section_inner, template = extract_block(template, f"SECTION:{cat}")
        if section_inner is None:
            continue
        # "highlights" nunca e removida por falta de eventos: o bloco de
        # calendario e o de "Guardado para o futuro" podem ter conteudo
        # proprio mesmo sem nenhum evento highlight:true nesta geracao.
        if not evs and cat != "highlights":
            template = template.replace("{{__PLACEHOLDER_SECTION:" + cat + "__}}", "")
            pill_inner, template = extract_block(template, f"PILL:{cat}")
            if pill_inner is not None:
                template = template.replace("{{__PLACEHOLDER_PILL:" + cat + "__}}", "")
            continue
        if cat == "meetup":
            cards_html = build_meetup_section_html(evs, card_tpl)
        elif cat == "culture":
            cards_html = build_culture_section_html(evs, card_tpl)
        elif cat in ("books", "escape", "streaming"):
            cards_html = build_saveable_section_html(evs, card_tpl)
        elif cat == "highlights":
            # '--hl' evita id duplicado com a copia do mesmo evento na sua
            # seccao real (ver docstring de render_card).
            cards_html = build_simple_grid_html(evs, card_tpl, id_suffix="--hl")
        else:
            cards_html = build_simple_grid_html(evs, card_tpl)
        section_filled = section_inner.replace("{{CARDS:" + cat + "}}", cards_html)
        if cat == "highlights":
            calendario_dias_final = build_calendario_dias(data, events)
            section_filled = section_filled.replace(
                "{{CALENDARIO_BLOCK}}", build_calendario_block(calendario_dias_final)
            )
            section_filled = section_filled.replace(
                "{{FUTURO_BLOCK}}", build_futuro_block(data.get("futuro_guardado", []) or [])
            )
        template = template.replace("{{__PLACEHOLDER_SECTION:" + cat + "__}}", section_filled)
        # manter o pill (apenas remover os marcadores de comentario) — a
        # seccao "highlights" nao tem PILL: marcador (o pill dela e fixo
        # no template, sempre presente e activo por omissao).
        template = remove_block_markers_only(template, f"PILL:{cat}")

    # 4) Periodo, banners (urgente / viagem) — vem do summary/validation,
    #    nunca inventados pelo render layer. (Sem dashboard de contagens —
    #    removido a pedido do Rafa: nao lia, so ocupava espaco.)
    periodo_label = meta.get("periodo_label", "")
    template = template.replace("{{PERIODO_LABEL}}", esc(periodo_label))

    urgente_texto = summary.get("alerta_urgente", "")
    template = template.replace("{{URGENTE_CLASS}}", "show" if urgente_texto else "")
    template = template.replace("{{URGENTE_TEXTO}}", esc(urgente_texto))

    viagem_texto = validation.get("aviso_viagem", "")
    template = template.replace("{{VIAGEM_CLASS}}", "show" if viagem_texto else "")
    template = template.replace("{{VIAGEM_TEXTO}}", esc(viagem_texto))

    # 5) Variavel JS — usar json.dumps para evitar bugs de apostrofo/aspas
    safe_events_for_js = [
        {
            "id": e.get("id"),
            "category": e.get("category"),
            "title": e.get("title"),
            "date": e.get("date"),
        }
        for e in events
    ]
    template = template.replace(
        "{{EVENTOS_JSON}}", json.dumps(safe_events_for_js, ensure_ascii=False)
    )
    template = template.replace(
        "{{CALENDARIO_JSON}}", json.dumps(calendario_dias_final, ensure_ascii=False)
    )

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(template)

    print(f"OK: {len(events)} eventos renderizados ({len(highlights)} em highlights) -> {output_path}")


if __name__ == "__main__":
    main()
