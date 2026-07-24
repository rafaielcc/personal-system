import imaplib
import email
import os
import re
import sys
import json
import socket
import glob
import shutil
import tempfile
from email.header import decode_header
from email.utils import parsedate_to_datetime, parseaddr
from datetime import datetime, timedelta

from dotenv import load_dotenv
import fitz  # pymupdf

# =========================
# BASE PATH
# =========================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

load_dotenv(os.path.join(BASE_DIR, ".env"))

GMAIL_ADDRESS = os.getenv("GMAIL_ADDRESS")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")
# Remetente prioritário (o próprio Rafa) — por omissão, a própria conta que faz
# login, já que os artigos mais importantes são os que ele reenvia para si mesmo.
OWNER_EMAIL = (os.getenv("OWNER_EMAIL") or GMAIL_ADDRESS or "").lower()

# =========================
# CONFIG
# =========================
# Labels aninhadas do Gmail (pai "Paediatric Surgery", duas sub-labels). O
# IMAP do Gmail trata o "/" como parte literal do nome da label — não é uma
# hierarquia de pastas real, só de apresentação.
LABEL_PARA_LER = "Paediatric Surgery/Artigos para ler"
LABEL_LIDOS = "Paediatric Surgery/Artigos Lidos"

BATCH_SIZE = 10

# Pasta Drive sincronizada localmente onde o JSON semanal é gravado e onde o
# botão "Exportar decisões da semana" da página HTML deixa o ficheiro de
# decisões para este script recolher no arranque da próxima corrida.
OUTPUT = r"G:\My Drive\Claude_PRJ\Relatorios\Sources\Gmail_artigos"
PROCESSADAS_DIR = os.path.join(OUTPUT, "decisoes_processadas")
os.makedirs(OUTPUT, exist_ok=True)
os.makedirs(PROCESSADAS_DIR, exist_ok=True)

IMAP_TIMEOUT_SECONDS = 30
MIN_ABSTRACT_CHARS = 80

# marcadores onde cortamos o rodape do corpo do e-mail (assinatura,
# unsubscribe, disclaimers legais de instituição, etc.)
RODAPE_MARCADORES = [
    "unsubscribe", "descadastre-se", "cancelar inscri",
    "view in browser", "ver no navegador",
    "this email was sent to", "confidentiality notice",
    "click here to unsubscribe",
]

# heurística de fim de secção do abstract: primeiro heading destes que
# aparecer depois do "Abstract" fecha a secção.
ABSTRACT_FIM_HEADINGS = [
    r"key\s*words", r"keywords", r"introduction", r"background",
    r"1\.\s+introduction", r"1\s+introduction", r"©", r"doi\s*:",
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
        from bs4 import BeautifulSoup
        return BeautifulSoup(texto_html, "html.parser").get_text(separator="\n")

    return ""


def extrair_pdf_anexo(msg):
    """Devolve (nome_ficheiro, bytes) do primeiro anexo PDF encontrado, ou
    (None, None) se não houver nenhum."""
    if not msg.is_multipart():
        return None, None

    for parte in msg.walk():
        disposicao = str(parte.get("Content-Disposition") or "")
        content_type = parte.get_content_type()
        nome = parte.get_filename()

        e_pdf = content_type == "application/pdf" or (nome and nome.lower().endswith(".pdf"))
        if not e_pdf:
            continue
        if "attachment" not in disposicao and not nome:
            continue

        try:
            payload = parte.get_payload(decode=True)
        except Exception:
            continue
        if not payload:
            continue

        nome_decodificado = decodificar_assunto(nome) if nome else "artigo.pdf"
        return nome_decodificado, payload

    return None, None


def extrair_texto_pdf(pdf_bytes: bytes) -> str:
    """Extrai o texto completo do PDF via pymupdf. Nunca bloqueante — qualquer
    falha de parsing (PDF corrompido, digitalizado sem OCR, etc.) devolve
    string vazia em vez de rebentar a corrida inteira."""
    try:
        with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
            partes = [pagina.get_text() for pagina in doc]
        return limpar_texto("\n".join(partes))
    except Exception as e:
        print(f"  [aviso] falha ao extrair texto do PDF: {e}")
        return ""


def isolar_abstract(texto_completo: str) -> str:
    """Heurística: encontra o heading 'Abstract' e devolve o texto até ao
    próximo heading de secção (Keywords/Introduction/etc.) ou até
    MAX_ABSTRACT_CHARS se nenhum heading for encontrado depois."""
    if not texto_completo:
        return ""

    match_inicio = re.search(r"\babstract\b\s*:?\s*\n?", texto_completo, flags=re.IGNORECASE)
    if not match_inicio:
        return ""

    resto = texto_completo[match_inicio.end():]

    fim = len(resto)
    for padrao in ABSTRACT_FIM_HEADINGS:
        m = re.search(padrao, resto, flags=re.IGNORECASE)
        if m:
            fim = min(fim, m.start())

    # sem heading de fim encontrado: corta num tamanho razoável para nao
    # trazer o artigo inteiro como "abstract" por engano.
    fim = min(fim, 3000)

    candidato = resto[:fim].strip()
    if len(candidato) < MIN_ABSTRACT_CHARS:
        return ""
    return limpar_texto(candidato)


def encontrar_pasta_label(imap, texto_procura: str) -> str:
    """Encontra o nome exacto (tal como o IMAP do Gmail o reporta) da pasta/
    label que contém `texto_procura`. Evita depender da sintaxe de busca
    label:"..." do Gmail (cujo escape de espaços/hierarquia em labels
    aninhadas via X-GM-RAW nunca foi 100% fiável em testes) — em vez disso,
    seleciona directamente a pasta IMAP correspondente à label, que o Gmail
    expõe como uma mailbox navegável como qualquer outra."""
    status, pastas = imap.list()
    if status != "OK":
        raise RuntimeError("Não foi possível listar as pastas da conta (comando LIST falhou).")

    candidatos = []
    for pasta in pastas:
        linha = pasta.decode("utf-8", errors="replace") if isinstance(pasta, bytes) else pasta
        match = re.search(r'"([^"]+)"\s*$', linha)
        nome = match.group(1) if match else linha.split()[-1]
        if texto_procura.lower() in nome.lower():
            candidatos.append(nome)

    if not candidatos:
        raise RuntimeError(
            f"Não encontrei nenhuma pasta/label contendo '{texto_procura}'. "
            "Confirme o nome exacto da label no Gmail (maiúsculas/minúsculas, "
            "espaços) — o script imprime todas as pastas encontradas acima "
            "deste erro para ajudar a comparar."
        )

    # a correspondência mais curta é a mais específica (evita apanhar a
    # label-pai "Paediatric Surgery" quando se procura a sub-label).
    candidatos.sort(key=len)
    return candidatos[0]


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


def encontrar_pasta_trash(imap) -> str:
    status, pastas = imap.list()
    if status != "OK":
        raise RuntimeError("Não foi possível listar as pastas da conta (comando LIST falhou).")

    for pasta in pastas:
        linha = pasta.decode("utf-8", errors="replace") if isinstance(pasta, bytes) else pasta
        if "\\Trash" not in linha:
            continue
        match = re.search(r'"([^"]+)"\s*$', linha)
        return match.group(1) if match else linha.split()[-1]

    raise RuntimeError("Não encontrei a pasta de lixo (Trash) na conta.")


def _x_gm_labels_literal(labels: list) -> str:
    partes = " ".join(f'"{l}"' for l in labels)
    return f"({partes})"


def aplicar_decisao(imap, pasta_all: str, pasta_trash: str, message_id: str, acao: str) -> bool:
    """Aplica uma decisão (guardar/excluir) a uma mensagem, localizada pelo
    X-GM-MSGID estável (não o UID, que só é válido dentro de uma pasta).
    Devolve True se aplicada com sucesso."""
    imap.select(f'"{pasta_all}"', readonly=False)

    status, dados = imap.uid("SEARCH", None, "X-GM-MSGID", message_id)
    if status != "OK" or not dados[0]:
        print(f"  [aviso] mensagem X-GM-MSGID={message_id} não encontrada — decisão '{acao}' ignorada.")
        return False

    uid = dados[0].split()[0]

    if acao == "guardar":
        imap.uid("STORE", uid, "+X-GM-LABELS", _x_gm_labels_literal([LABEL_LIDOS]))
        imap.uid("STORE", uid, "-X-GM-LABELS", _x_gm_labels_literal([LABEL_PARA_LER]))
        return True

    if acao == "excluir":
        # copia para o Lixo (recuperável 30 dias) e só depois remove da
        # label de origem + expunge em All Mail (equivalente a "apagar" no
        # modelo de labels do Gmail).
        imap.uid("COPY", uid, f'"{pasta_trash}"')
        imap.uid("STORE", uid, "-X-GM-LABELS", _x_gm_labels_literal([LABEL_PARA_LER]))
        imap.uid("STORE", uid, "+FLAGS", "(\\Deleted)")
        imap.expunge()
        return True

    print(f"  [aviso] ação desconhecida '{acao}' para {message_id} — ignorada.")
    return False


def processar_decisoes_pendentes(imap, pasta_all: str, pasta_trash: str) -> dict:
    stats = {"guardados": 0, "excluidos": 0, "falhas": 0}
    ficheiros = sorted(glob.glob(os.path.join(OUTPUT, "decisoes_*.json")))

    for caminho in ficheiros:
        print(f"A processar ficheiro de decisões: {os.path.basename(caminho)}")
        try:
            with open(caminho, "r", encoding="utf-8") as f:
                decisoes = json.load(f)
        except Exception as e:
            print(f"  [aviso] não consegui ler {caminho}: {e}")
            continue

        for entrada in decisoes:
            message_id = str(entrada.get("message_id", "")).strip()
            acao = str(entrada.get("acao", "")).strip().lower()
            if not message_id or acao not in ("guardar", "excluir"):
                continue

            ok = aplicar_decisao(imap, pasta_all, pasta_trash, message_id, acao)
            if ok:
                stats["guardados" if acao == "guardar" else "excluidos"] += 1
            else:
                stats["falhas"] += 1

        shutil.move(caminho, os.path.join(PROCESSADAS_DIR, os.path.basename(caminho)))

    return stats


def extrair_novos_artigos(imap) -> list:
    pasta_label = encontrar_pasta_label(imap, "Artigos para ler")
    print(f"  [info] label resolvida para a pasta IMAP: {pasta_label}")

    status, dados = imap.select(f'"{pasta_label}"', readonly=True)
    if status != "OK":
        raise RuntimeError(f"Não consegui abrir a pasta '{pasta_label}' (status: {status}).")

    status, dados = imap.search(None, "ALL")
    if status != "OK":
        raise RuntimeError(f"Busca IMAP falhou: {status}")

    ids = dados[0].split()
    candidatos = []

    for msg_id in ids:
        status, msg_data = imap.fetch(msg_id, "(RFC822 X-GM-MSGID)")
        if status != "OK":
            continue

        # X-GM-MSGID vem na mesma resposta do FETCH, num item separado.
        gm_msgid = None
        for item in msg_data:
            if isinstance(item, tuple):
                continue
            texto_item = item.decode("utf-8", errors="replace") if isinstance(item, bytes) else str(item)
            m = re.search(r"X-GM-MSGID\s+(\d+)", texto_item)
            if m:
                gm_msgid = m.group(1)

        raw = next((item[1] for item in msg_data if isinstance(item, tuple)), None)
        if raw is None or gm_msgid is None:
            continue

        msg = email.message_from_bytes(raw)

        try:
            data_email = parsedate_to_datetime(msg.get("Date"))
            if data_email.tzinfo:
                data_email = data_email.replace(tzinfo=None)
        except Exception:
            continue

        nome_remetente, email_remetente = parseaddr(msg.get("From", ""))
        email_remetente = (email_remetente or "").lower()

        candidatos.append({
            "message_id": gm_msgid,
            "sender_name": nome_remetente or email_remetente,
            "sender_email": email_remetente,
            "sender_is_owner": email_remetente == OWNER_EMAIL,
            "date": data_email,
            "subject": decodificar_assunto(msg.get("Subject", "")),
            "msg": msg,
        })

    # prioridade: o próprio Rafa primeiro, depois os restantes — dentro de
    # cada grupo, mais recente primeiro.
    candidatos.sort(key=lambda c: (not c["sender_is_owner"], -c["date"].timestamp()))
    escolhidos = candidatos[:BATCH_SIZE]

    artigos = []
    for c in escolhidos:
        msg = c["msg"]
        corpo = limpar_texto(remover_rodape(extrair_corpo(msg)))

        pdf_nome, pdf_bytes = extrair_pdf_anexo(msg)
        texto_completo = extrair_texto_pdf(pdf_bytes) if pdf_bytes else ""
        abstract = isolar_abstract(texto_completo)

        gm_msgid_hex = format(int(c["message_id"]), "x")

        artigos.append({
            "message_id": c["message_id"],
            "gmail_web_link": f"https://mail.google.com/mail/u/0/#all/{gm_msgid_hex}",
            "sender_name": c["sender_name"],
            "sender_email": c["sender_email"],
            "sender_is_owner": c["sender_is_owner"],
            "date": c["date"].strftime("%Y-%m-%dT%H:%M:%S"),
            "subject": c["subject"],
            "email_body_text": corpo,
            "pdf_filename": pdf_nome,
            "abstract_text": abstract,
            "full_text": texto_completo,
        })

    return artigos


def export():
    print("BASE_DIR:", BASE_DIR)

    try:
        imap = imaplib.IMAP4_SSL("imap.gmail.com", timeout=IMAP_TIMEOUT_SECONDS)
    except (socket.timeout, OSError) as e:
        raise RuntimeError(
            f"Nao foi possivel ligar a imap.gmail.com em {IMAP_TIMEOUT_SECONDS}s ({e}). "
            "Provavel bloqueio de rede (firewall/antivirus/VPN) na porta 993."
        )
    imap.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)

    pasta_all = encontrar_pasta_todos_emails(imap)
    pasta_trash = encontrar_pasta_trash(imap)

    print("A aplicar decisões pendentes (guardar/excluir) da semana anterior...")
    stats_decisoes = processar_decisoes_pendentes(imap, pasta_all, pasta_trash)

    print("A extrair novos artigos da label 'Artigos para ler'...")
    artigos = extrair_novos_artigos(imap)

    imap.logout()

    resultado = {
        "generated_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        "label_origem": LABEL_PARA_LER,
        "batch_size": BATCH_SIZE,
        "decisoes_aplicadas": stats_decisoes,
        "articles": artigos,
    }

    ficheiro = os.path.join(
        OUTPUT,
        f"Gmail_artigos_{datetime.now().strftime('%Y-%m-%d')}.json"
    )

    fd, caminho_temp = tempfile.mkstemp(suffix=".json")
    with os.fdopen(fd, "w", encoding="utf8") as f:
        json.dump(resultado, f, ensure_ascii=False, indent=2)
    shutil.move(caminho_temp, ficheiro)

    print()
    print("=" * 56)
    print("RELATORIO DA EXECUCAO")
    print("=" * 56)
    print(f"Decisões aplicadas — guardados: {stats_decisoes['guardados']}, "
          f"excluídos: {stats_decisoes['excluidos']}, falhas: {stats_decisoes['falhas']}")
    print(f"Artigos novos extraídos: {len(artigos)}")
    print(f"  - com PDF/abstract encontrado: {sum(1 for a in artigos if a['abstract_text'])}")
    print(f"  - do próprio Rafa (prioridade 1): {sum(1 for a in artigos if a['sender_is_owner'])}")
    print("=" * 56)
    print("Ficheiro gravado em:", ficheiro)
    print("=" * 56)


if __name__ == "__main__":
    export()
