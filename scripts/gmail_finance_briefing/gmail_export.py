import imaplib
import email
import os
import re
import sys
import json
import socket
import hashlib
import tempfile
import shutil
import requests
import trafilatura
from email.header import decode_header
from email.utils import parsedate_to_datetime
from datetime import datetime, timedelta

from dotenv import load_dotenv
from bs4 import BeautifulSoup

# =========================
# BASE PATH
# =========================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from common.tickers import find_tickers

load_dotenv(os.path.join(BASE_DIR, ".env"))

GMAIL_ADDRESS = os.getenv("GMAIL_ADDRESS")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")

# =========================
# CONFIG
# =========================
LABEL = "finance briefing"
WINDOW_DAYS = 7

# tempo maximo de espera para ligar/autenticar no IMAP antes de desistir com
# erro explicito, em vez de ficar bloqueado indefinidamente (ex.: firewall/
# antivirus/VPN a bloquear a porta 993 em silencio).
IMAP_TIMEOUT_SECONDS = 30

OUTPUT = r"G:\My Drive\Claude_PRJ\Relatorios\Sources\Gmail_finances"
os.makedirs(OUTPUT, exist_ok=True)

MIN_CHARS = 60

# marcadores onde cortamos o rodape (assinatura legal, unsubscribe, etc.)
RODAPE_MARCADORES = [
    "descadastre-se", "cancelar inscri", "unsubscribe",
    "voce esta recebendo este e-mail", "você está recebendo este e-mail",
    "view in browser", "ver no navegador", "copyright ©", "todos os direitos reservados",
]

# grupos de palavras-chave para os indices. cada indice pega o primeiro
# valor numerico encontrado perto de uma das palavras-chave.
INDICE_PATTERNS = {
    "usd_brl": [r"\bd[oó]lar(?:es)?\b", r"usd\s*/?\s*brl"],
    "eur_brl": [r"\beuros?\b", r"eur\s*/?\s*brl"],
    "gbp_brl": [r"\blibras?(?:\s+esterlinas?)?\b", r"gbp\s*/?\s*brl"],
    "brent_oil": [r"\bpetr[oó]leo(?:\s+bruto)?\b", r"\bbrent\b"],
    "iron_ore": [r"\bmin[eé]rio de ferro\b", r"\biron\s*ore\b"],
    "gold": [r"\bouro\b"],
    "soybean": [r"\bsoja\b"],
    "cotton": [r"\balgod[aã]o\b"],
    "ibovespa": [r"\bibovespa\b", r"\bibov\b"],
    "sp500": [r"\bs&p\s*500\b", r"\bsp\s*500\b"],
    "dow_jones": [r"\bdow\s+jones\b", r"\bdow\b"],
}

# numero com simbolo de moeda explicito (preferido: e o que distingue o
# preco real de uma variacao percentual ou de outro numero solto na frase).
# NAO tem exclusoes embutidas no padrao (ver _candidato_valido) — colocar
# lookaheads de rejeicao aqui faz o regex "encolher" o numero so para escapar
# da rejeicao (ex.: rejeitar "R$ 6,7" seguido de "bilhoes" faz o motor
# recuar para "R$ 6", que ja nao e seguido de "bilh" e passa).
NUM_BRL = re.compile(r"R\$\s?-?\d{1,3}(?:\.\d{3})*(?:,\d{1,4})?")
NUM_USD = re.compile(r"(?:US\$|U\$|\$)\s?-?\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{1,4})?")

# numero em pontos, com separador de milhar (ex.: "134.850" do Ibovespa) —
# o que distingue o nivel do indice de uma variacao percentual na mesma frase.
NUM_PONTOS = re.compile(r"\d{1,3}(?:\.\d{3})+(?:,\d{1,2})?")

# numero solto, sem simbolo de moeda: exige que nao esteja colado a uma letra
# (evita pegar digitos de ticker, tipo GOLD11). O lookbehind e seguro aqui
# porque olha para TRAS do inicio do numero — nao ha como o motor recuar
# para escapar dele encolhendo o numero por trás.
NUM_GENERICO = re.compile(r"(?<![A-Za-z0-9])-?\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{1,4})?")

# rejeita o candidato se, logo depois dele, vier: uma percentagem (variacao,
# nao valor); uma barra (fragmento de data, tipo "02/07" ou "26/jun"); ou
# "bilh(ao/oes)"/"milh(ao/oes)"/"trilh(ao/oes)" (quase sempre o tamanho de
# uma transaccao/negocio, nao uma cotacao — ex. "R$ 6,7 bilhoes" no valor de
# uma fusao/aquisicao). Verificado em Python, DEPOIS de achar o numero
# inteiro, para nao sofrer o problema do recuo do regex descrito acima.
SUFIXO_REJEITADO = re.compile(r"\s*(?:%|/|bilh|milh|trilh)")


def _candidato_valido(linha: str, match) -> bool:
    return SUFIXO_REJEITADO.match(linha, match.end()) is None


def _primeiro_valido(padrao, linha: str):
    for match in padrao.finditer(linha):
        if _candidato_valido(linha, match):
            return match.group()
    return None


# hora ("05h00", "11:30") e data numerica ("02/07", "02/07/2026") sao
# removidas da linha antes de procurar o valor: senao a hora/dia vira um
# "valor" falso quando a linha nao tem nenhuma cotacao de verdade (comum em
# entradas de agenda economica, ex. "05h00 - Zona do euro: PMI industrial").
TEMPO_DATA_PATTERN = re.compile(
    r"\d{1,2}h\d{2}\b|\b\d{1,2}:\d{2}\b|\b\d{1,2}/\d{1,2}(?:/\d{2,4})?\b"
)

# indices cuja unidade de referencia esperada e conhecida — usada para
# decidir qual padrao de numero tentar primeiro.
MOEDA_ESPERADA = {
    "usd_brl": NUM_BRL,
    "eur_brl": NUM_BRL,
    "gbp_brl": NUM_BRL,
    "brent_oil": NUM_USD,
    "iron_ore": NUM_USD,
    "gold": NUM_USD,
    "ibovespa": NUM_PONTOS,
    "sp500": NUM_PONTOS,
    "dow_jones": NUM_PONTOS,
}

LINK_PATTERN = re.compile(r"https?://\S+")
LINK_IGNORE_KEYWORDS = [
    "unsubscribe", "descadastr", "list-manage", "optout", "opt-out",
    "preferences", "mailto:",
]

# tempo maximo de espera ao abrir um link (Fase 2 — extraccao de artigo)
LINK_TIMEOUT_SECONDS = 8
LINK_USER_AGENT = "Mozilla/5.0 (compatible; AII-briefing-bot/1.0)"


def limpar_texto(texto: str) -> str:
    texto = re.sub(r"\n{3,}", "\n\n", texto)
    texto = re.sub(r"[ \t]+", " ", texto)
    return texto.strip()


def remover_rodape(texto: str) -> str:
    baixo = texto.lower()
    corte = len(texto)
    for marcador in RODAPE_MARCADORES:
        pos = baixo.find(marcador)
        if pos != -1:
            corte = min(corte, pos)
    return texto[:corte].strip()


def ignorar_texto(texto: str) -> bool:
    return not texto or len(texto.strip()) < MIN_CHARS


def decodificar_assunto(raw_subject: str) -> str:
    partes = decode_header(raw_subject or "")
    resultado = ""
    for texto, encoding in partes:
        if isinstance(texto, bytes):
            resultado += texto.decode(encoding or "utf-8", errors="replace")
        else:
            resultado += texto
    return resultado


def extrair_corpo(msg) -> str:
    texto_plain = ""
    texto_html = ""

    if msg.is_multipart():
        for parte in msg.walk():
            content_type = parte.get_content_type()
            disposicao = str(parte.get("Content-Disposition") or "")

            if "attachment" in disposicao:
                continue

            try:
                payload = parte.get_payload(decode=True)
                if not payload:
                    continue
                charset = parte.get_content_charset() or "utf-8"
                conteudo = payload.decode(charset, errors="replace")
            except Exception:
                continue

            if content_type == "text/plain" and not texto_plain:
                texto_plain = conteudo
            elif content_type == "text/html" and not texto_html:
                texto_html = conteudo
    else:
        try:
            payload = msg.get_payload(decode=True)
            charset = msg.get_content_charset() or "utf-8"
            conteudo = payload.decode(charset, errors="replace") if payload else ""
            if msg.get_content_type() == "text/html":
                texto_html = conteudo
            else:
                texto_plain = conteudo
        except Exception:
            pass

    if texto_plain.strip():
        return texto_plain

    if texto_html.strip():
        return BeautifulSoup(texto_html, "html.parser").get_text(separator="\n")

    return ""


def abrir_link(url: str, stats: dict) -> str | None:
    """Fase 2: abre o link e extrai o texto do artigo. Nunca bloqueante —
    qualquer falha devolve None e regista em stats."""
    stats["encontrados"] += 1
    try:
        resp = requests.get(
            url,
            timeout=LINK_TIMEOUT_SECONDS,
            headers={"User-Agent": LINK_USER_AGENT},
        )
        stats["abertos"] += 1
        if resp.status_code != 200:
            return None
        texto = trafilatura.extract(resp.text, include_comments=False, include_tables=False)
        if texto and len(texto.strip()) >= MIN_CHARS:
            stats["sucesso"] += 1
            return texto.strip()
        return None
    except Exception:
        return None


def extrair_links(texto: str, link_stats: dict) -> list:
    encontrados = []
    vistos = set()

    for url in LINK_PATTERN.findall(texto):
        url = url.rstrip(").,;>\"'")

        if any(k in url.lower() for k in LINK_IGNORE_KEYWORDS):
            continue

        if url in vistos:
            continue

        vistos.add(url)
        encontrados.append({"url": url, "article_text": abrir_link(url, link_stats)})

    return encontrados


def normalizar_numero(token: str):
    token = re.sub(r"[^0-9,.\-]", "", token)
    if not token:
        return None

    ultima_virgula = token.rfind(",")
    ultimo_ponto = token.rfind(".")

    if ultima_virgula == -1 and ultimo_ponto == -1:
        try:
            return float(token)
        except ValueError:
            return None

    if ultima_virgula == -1:
        # so ha pontos: se formar grupos de exactamente 3 digitos (ex.:
        # "134.850"), e separador de milhar (nivel de indice em pontos),
        # nao casa decimal — senao e um preco tipo "82.45".
        if re.fullmatch(r"\d{1,3}(?:\.\d{3})+", token):
            try:
                return float(token.replace(".", ""))
            except ValueError:
                return None
        try:
            return float(token)
        except ValueError:
            return None

    if ultima_virgula > ultimo_ponto:
        inteiro = token[:ultima_virgula].replace(".", "").replace(",", "")
        decimal = token[ultima_virgula + 1:]
    else:
        inteiro = token[:ultimo_ponto].replace(",", "").replace(".", "")
        decimal = token[ultimo_ponto + 1:]

    try:
        return float(f"{inteiro}.{decimal}")
    except ValueError:
        return None


def extrair_numero_da_linha(linha: str, chave: str):
    linha = TEMPO_DATA_PATTERN.sub(" ", linha)
    esperado = MOEDA_ESPERADA.get(chave)

    # se o indice tem um formato esperado (R$ para cambio, separador de
    # milhar para o Ibovespa, etc.) e ele nao aparece na linha, NAO cair
    # para um numero generico qualquer: essas frases costumam citar varios
    # numeros de assuntos diferentes juntos (ex.: "dolar" mencionado de
    # passagem numa frase cujo unico numero "limpo" e o nivel do Nikkei) —
    # e melhor nao capturar nada do que capturar o numero errado.
    if esperado:
        return _primeiro_valido(esperado, linha)

    token = _primeiro_valido(NUM_BRL, linha) or _primeiro_valido(NUM_USD, linha)
    if token:
        return token

    return _primeiro_valido(NUM_GENERICO, linha)


def extrair_indices(texto: str) -> dict:
    achados = {}
    linhas = texto.splitlines()

    for chave, padroes in INDICE_PATTERNS.items():
        for linha in linhas:
            # remove links da linha antes de tudo: um "soja"/"ouro" etc.
            # dentro do slug de uma URL nao e uma mencao real ao indice, e
            # os parametros da URL (utm_*) tem digitos que parecem valores.
            linha_limpa = LINK_PATTERN.sub(" ", linha)

            if not any(re.search(p, linha_limpa, flags=re.IGNORECASE) for p in padroes):
                continue

            token = extrair_numero_da_linha(linha_limpa, chave)
            if not token:
                continue

            achados[chave] = {
                "raw": linha_limpa.strip(),
                "value": normalizar_numero(token),
            }
            break

    return achados


def montar_query_gmail(label: str, dias: int) -> str:
    query = f'label:"{label}" newer_than:{dias}d'
    return '"' + query.replace('"', '\\"') + '"'


def encontrar_pasta_todos_emails(imap) -> str:
    status, pastas = imap.list()
    if status != "OK":
        raise RuntimeError("Não foi possível listar as pastas da conta (comando LIST falhou).")

    for pasta in pastas:
        linha = pasta.decode("utf-8", errors="replace") if isinstance(pasta, bytes) else pasta
        if "\\All" not in linha:
            continue
        match = re.search(r'"([^"]+)"\s*$', linha)
        return match.group(1) if match else linha.split()[-1]

    raise RuntimeError(
        "Não encontrei a pasta 'Todos os e-mails' (All Mail) na conta. "
        "Confirme que o IMAP está ativado nas configurações do Gmail."
    )


def export():
    print("BASE_DIR:", BASE_DIR)

    agora = datetime.now()
    inicio = agora - timedelta(days=WINDOW_DAYS)

    try:
        imap = imaplib.IMAP4_SSL("imap.gmail.com", timeout=IMAP_TIMEOUT_SECONDS)
    except (socket.timeout, OSError) as e:
        raise RuntimeError(
            f"Nao foi possivel ligar a imap.gmail.com em {IMAP_TIMEOUT_SECONDS}s ({e}). "
            "Provavel bloqueio de rede (firewall/antivirus/VPN) na porta 993 — "
            "verificar se ha um pedido de permissao de firewall pendente para o python.exe."
        )
    imap.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)

    pasta_all = encontrar_pasta_todos_emails(imap)
    status, _ = imap.select(f'"{pasta_all}"', readonly=True)
    if status != "OK":
        raise RuntimeError(f"Não consegui abrir a pasta '{pasta_all}' (status: {status}).")

    criterio = montar_query_gmail(LABEL, WINDOW_DAYS)
    status, dados = imap.search(None, "X-GM-RAW", criterio)

    if status != "OK":
        raise RuntimeError(f"Busca IMAP falhou: {status}")

    ids = dados[0].split()

    vistos = set()
    emails_out = []
    indices_por_dia = {}
    link_stats = {"encontrados": 0, "abertos": 0, "sucesso": 0}
    stats = {
        "emails_vistos": 0,
        "ignorados_curto": 0,
        "ignorados_duplicado": 0,
        "incluidos": 0,
    }

    for msg_id in ids:
        status, msg_data = imap.fetch(msg_id, "(RFC822)")
        if status != "OK":
            continue

        msg = email.message_from_bytes(msg_data[0][1])

        try:
            data_email = parsedate_to_datetime(msg.get("Date"))
            if data_email.tzinfo:
                data_email = data_email.replace(tzinfo=None)
        except Exception:
            continue

        if data_email < inicio:
            continue

        stats["emails_vistos"] += 1

        texto = extrair_corpo(msg)
        texto = remover_rodape(texto)
        texto = limpar_texto(texto)

        if ignorar_texto(texto):
            stats["ignorados_curto"] += 1
            continue

        chave = hashlib.sha1(texto.lower().encode("utf-8")).hexdigest()
        if chave in vistos:
            stats["ignorados_duplicado"] += 1
            continue
        vistos.add(chave)

        dia = data_email.strftime("%Y-%m-%d")
        indices_dia = indices_por_dia.setdefault(dia, {})
        for chave_indice, valor in extrair_indices(texto).items():
            indices_dia.setdefault(chave_indice, valor)

        emails_out.append({
            "sender": msg.get("From", ""),
            "subject": decodificar_assunto(msg.get("Subject", "")),
            "date": data_email.strftime("%Y-%m-%dT%H:%M:%S"),
            "body_text": texto,
            "tickers_mentioned": find_tickers(texto),
            "links": extrair_links(texto, link_stats),
        })
        stats["incluidos"] += 1

    imap.logout()

    emails_out.sort(key=lambda e: e["date"])

    resultado = {
        "generated_at": agora.strftime("%Y-%m-%dT%H:%M:%S"),
        "period": {
            "start": inicio.strftime("%Y-%m-%d"),
            "end": agora.strftime("%Y-%m-%d"),
        },
        "indices": indices_por_dia,
        "stats": stats,
        "link_stats": link_stats,
        "emails": emails_out,
    }

    ficheiro = os.path.join(
        OUTPUT,
        f"Gmail_finance_briefing_{inicio.strftime('%Y-%m-%d')}_a_{agora.strftime('%Y-%m-%d')}.json"
    )

    # escreve num arquivo temporario local e so entao move para o Google Drive:
    # gravar direto num drive virtual sincronizado pode falhar com
    # "OSError: [Errno 22] Invalid argument" durante a escrita.
    fd, caminho_temp = tempfile.mkstemp(suffix=".json")
    with os.fdopen(fd, "w", encoding="utf8") as f:
        json.dump(resultado, f, ensure_ascii=False, indent=2)

    shutil.move(caminho_temp, ficheiro)

    taxa_links = (link_stats["sucesso"] / link_stats["encontrados"] * 100) if link_stats["encontrados"] else 0

    print()
    print("=" * 56)
    print("RELATORIO DA EXECUCAO")
    print("=" * 56)
    print(f"Emails vistos (dentro da janela de {WINDOW_DAYS} dias): {stats['emails_vistos']}")
    print(f"  - Ignorados (corpo curto/vazio):     {stats['ignorados_curto']}")
    print(f"  - Ignorados (duplicado):              {stats['ignorados_duplicado']}")
    print(f"  - Incluidos no ficheiro final:        {stats['incluidos']}")
    print("-" * 56)
    print(f"Links encontrados:                {link_stats['encontrados']}")
    print(f"Links abertos (HTTP 200):         {link_stats['abertos']}")
    print(f"Artigos extraidos com sucesso:    {link_stats['sucesso']} ({taxa_links:.1f}%)")
    print("=" * 56)
    print("Ficheiro gravado em:", ficheiro)
    print("=" * 56)


if __name__ == "__main__":
    export()
