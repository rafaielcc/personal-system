import imaplib
import email
import os
import re
import json
import hashlib
from email.header import decode_header
from email.utils import parsedate_to_datetime
from datetime import datetime, timedelta

from dotenv import load_dotenv
from bs4 import BeautifulSoup

# =========================
# BASE PATH
# =========================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

load_dotenv(os.path.join(BASE_DIR, ".env"))

GMAIL_ADDRESS = os.getenv("GMAIL_ADDRESS")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")

# =========================
# CONFIG
# =========================
LABEL = "finance briefing"
WINDOW_DAYS = 7

OUTPUT = r"G:\My Drive\Claude_PRJ\Relatorios\Sources\Gmail_finance_briefing"
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
    "usd_brl": [r"d[oó]lar", r"usd\s*/?\s*brl"],
    "eur_brl": [r"euro", r"eur\s*/?\s*brl"],
    "gbp_brl": [r"libra(?:\s+esterlina)?", r"gbp\s*/?\s*brl"],
    "brent_oil": [r"petr[oó]leo(?:\s+bruto)?", r"\bbrent\b"],
    "iron_ore": [r"min[eé]rio de ferro", r"iron\s*ore"],
    "gold": [r"\bouro\b"],
    "soybean": [r"\bsoja\b"],
    "cotton": [r"algod[aã]o"],
}

NUM_PATTERN = re.compile(
    r"(?:R\$|US\$|U\$|\$|€|£)?\s?-?\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{1,4})?\s?%?"
)

LINK_PATTERN = re.compile(r"https?://\S+")
LINK_IGNORE_KEYWORDS = [
    "unsubscribe", "descadastr", "list-manage", "optout", "opt-out",
    "preferences", "mailto:",
]


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


def extrair_links(texto: str) -> list:
    encontrados = []
    vistos = set()

    for url in LINK_PATTERN.findall(texto):
        url = url.rstrip(").,;>\"'")

        if any(k in url.lower() for k in LINK_IGNORE_KEYWORDS):
            continue

        if url in vistos:
            continue

        vistos.add(url)
        encontrados.append({"url": url, "article_text": None})

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


def extrair_indices(texto: str) -> dict:
    achados = {}
    linhas = texto.splitlines()

    for chave, padroes in INDICE_PATTERNS.items():
        for linha in linhas:
            if not any(re.search(p, linha, flags=re.IGNORECASE) for p in padroes):
                continue

            num_match = NUM_PATTERN.search(linha)
            if not num_match:
                continue

            achados[chave] = {
                "raw": linha.strip(),
                "value": normalizar_numero(num_match.group()),
            }
            break

    return achados


def montar_query_gmail(label: str, dias: int) -> str:
    query = f'label:"{label}" newer_than:{dias}d'
    return '"' + query.replace('"', '\\"') + '"'


def export():
    print("BASE_DIR:", BASE_DIR)

    agora = datetime.now()
    inicio = agora - timedelta(days=WINDOW_DAYS)

    imap = imaplib.IMAP4_SSL("imap.gmail.com")
    imap.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
    imap.select('"[Gmail]/All Mail"', readonly=True)

    criterio = montar_query_gmail(LABEL, WINDOW_DAYS)
    status, dados = imap.search(None, "X-GM-RAW", criterio)

    if status != "OK":
        raise RuntimeError(f"Busca IMAP falhou: {status}")

    ids = dados[0].split()

    vistos = set()
    emails_out = []
    indices_por_dia = {}

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

        texto = extrair_corpo(msg)
        texto = remover_rodape(texto)
        texto = limpar_texto(texto)

        if ignorar_texto(texto):
            continue

        chave = hashlib.sha1(texto.lower().encode("utf-8")).hexdigest()
        if chave in vistos:
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
            "links": extrair_links(texto),
        })

    imap.logout()

    emails_out.sort(key=lambda e: e["date"])

    resultado = {
        "generated_at": agora.strftime("%Y-%m-%dT%H:%M:%S"),
        "period": {
            "start": inicio.strftime("%Y-%m-%d"),
            "end": agora.strftime("%Y-%m-%d"),
        },
        "indices": indices_por_dia,
        "emails": emails_out,
    }

    ficheiro = os.path.join(
        OUTPUT,
        f"Gmail_finance_briefing_{inicio.strftime('%Y-%m-%d')}_a_{agora.strftime('%Y-%m-%d')}.json"
    )

    with open(ficheiro, "w", encoding="utf8") as f:
        json.dump(resultado, f, ensure_ascii=False, indent=2)

    print("Concluído:", ficheiro)


if __name__ == "__main__":
    export()
