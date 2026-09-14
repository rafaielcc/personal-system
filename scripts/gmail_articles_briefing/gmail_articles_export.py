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
import argparse
from email.header import decode_header
from email.utils import parsedate_to_datetime, parseaddr
from datetime import datetime, timedelta
from pathlib import Path

from dotenv import load_dotenv
import fitz  # pymupdf

# =========================
# BASE PATH
# =========================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LEGACY_ENV = r"G:\My Drive\Claude_PRJ\Relatorios\Sources\System\gmail_artigos_briefing\.env"

if not load_dotenv(os.path.join(BASE_DIR, ".env")) and os.path.exists(LEGACY_ENV):
    load_dotenv(LEGACY_ENV)

GMAIL_ADDRESS = os.getenv("GMAIL_ADDRESS")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")
# Remetente prioritário (o próprio Rafa) — por omissão, a própria conta que faz
# login, já que os artigos mais importantes são os que ele reenvia para si mesmo.
OWNER_EMAIL = (os.getenv("OWNER_EMAIL") or GMAIL_ADDRESS or "").lower()

# Espelho_artigos: fonte normal das decisoes Guardar/Excluir feitas na pagina
# estatica. Ausencia de decisao nao escreve nada aqui e, portanto, deixa o
# artigo pendente na label atual ate uma decisao real ser tomada.
ARTIGOS_SHEET_ID = os.getenv("ARTIGOS_SHEET_ID", "1Sl67SXLz--uOaYlbo6tT97pXUu_O3qNvVCVAVDDZBp0")
GOOGLE_TOKEN_PATH = Path(os.getenv("GOOGLE_TOKEN_PATH", r"G:\My Drive\Claude_PRJ\token.json"))
GOOGLE_CREDENTIALS_PATH = Path(os.getenv("GOOGLE_CREDENTIALS_PATH", r"G:\My Drive\Claude_PRJ\credentials.json"))
SHEETS_SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

# =========================
# CONFIG
# =========================
# Labels aninhadas do Gmail (pai "Paediatric Surgery", três sub-labels sem
# espaço no nome — evita ambiguidade de escaping). O IMAP do Gmail trata o
# "/" como parte literal do nome da label — não é uma hierarquia de pastas
# real, só de apresentação. Estas três constantes são a ÚNICA fonte de
# verdade dos nomes — o texto de busca usado para localizar cada pasta IMAP
# é sempre derivado delas (nunca duplicado à parte), para uma renomeação de
# tag no Gmail só exigir mudar aqui.
LABEL_PARA_LER = "Paediatric Surgery/Artigos-ParaLer"
LABEL_LIDOS = "Paediatric Surgery/Artigos-Lidos"
# terceira label: equivalente a "guardar", mas os artigos aqui continuam a
# ser reexpostos em todas as corridas (secção própria "em leitura"), em vez
# de saírem de circulação — pensada para artigos longos/de leitura
# recorrente que levam semanas.
LABEL_EM_LEITURA = "Paediatric Surgery/Artigos-EmLeitura"

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

def _padrao_letras_espacadas(palavra: str) -> str:
    """Gera um padrão regex tolerante a letras separadas por espaço —
    artefacto comum da extração de PDF quando o heading usa versalete/
    letter-spacing (ex.: 'Abstract' costuma extrair como 'a b s t r a c t')."""
    return r"\s*".join(re.escape(c) for c in palavra)


PADRAO_ABSTRACT = re.compile(
    r"\b" + _padrao_letras_espacadas("abstract") + r"\b", re.IGNORECASE
)

# heurística de fim de secção do abstract: primeiro heading destes que
# aparecer depois do "Abstract" fecha a secção. Tolerante a letras
# espaçadas, pelo mesmo motivo do heading do abstract acima.
ABSTRACT_FIM_HEADINGS = [
    _padrao_letras_espacadas("keywords"),
    _padrao_letras_espacadas("key words"),
    _padrao_letras_espacadas("introduction"),
    _padrao_letras_espacadas("background"),
    r"1\.\s+introduction", r"1\s+introduction", r"©", r"doi\s*:",
]


def limpar_texto(texto: str) -> str:
    texto = re.sub(r"\n{3,}", "\n\n", texto)
    # PDFs com colunas estreitas geram uma quebra de linha por linha (por
    # vezes por palavra) — junta essas quebras simples num espaço, mas
    # preserva quebras duplas (\n\n) como separador real de parágrafo.
    texto = re.sub(r"(?<!\n)\n(?!\n)", " ", texto)
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

    match_inicio = PADRAO_ABSTRACT.search(texto_completo)
    if not match_inicio:
        return ""

    resto = texto_completo[match_inicio.end():].lstrip(" :\n")

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
    """Aplica uma decisão (guardar/excluir/manter-em-leitura) a uma mensagem,
    localizada pelo X-GM-MSGID estável (não o UID, que só é válido dentro de
    uma pasta). Devolve True se aplicada com sucesso.

    Remove sempre as duas labels de origem possíveis (para_ler e
    em_leitura) antes de aplicar o destino — cobre tanto um artigo novo
    (vindo de "para ler") como um artigo que já estava "em leitura" há
    semanas e agora finalmente é guardado/excluído."""
    imap.select(f'"{pasta_all}"', readonly=False)

    status, dados = imap.uid("SEARCH", None, "X-GM-MSGID", message_id)
    if status != "OK" or not dados[0]:
        print(f"  [aviso] mensagem X-GM-MSGID={message_id} não encontrada — decisão '{acao}' ignorada.")
        return False

    uid = dados[0].split()[0]

    if acao == "guardar":
        imap.uid("STORE", uid, "+X-GM-LABELS", _x_gm_labels_literal([LABEL_LIDOS]))
        imap.uid("STORE", uid, "-X-GM-LABELS", _x_gm_labels_literal([LABEL_PARA_LER, LABEL_EM_LEITURA]))
        return True

    if acao == "manter":
        imap.uid("STORE", uid, "+X-GM-LABELS", _x_gm_labels_literal([LABEL_EM_LEITURA]))
        imap.uid("STORE", uid, "-X-GM-LABELS", _x_gm_labels_literal([LABEL_PARA_LER]))
        return True

    if acao == "excluir":
        # copia para o Lixo (recuperável 30 dias) e só depois remove das
        # labels de origem + expunge em All Mail (equivalente a "apagar" no
        # modelo de labels do Gmail).
        imap.uid("COPY", uid, f'"{pasta_trash}"')
        imap.uid("STORE", uid, "-X-GM-LABELS", _x_gm_labels_literal([LABEL_PARA_LER, LABEL_EM_LEITURA]))
        imap.uid("STORE", uid, "+FLAGS", "(\\Deleted)")
        imap.expunge()
        return True

    print(f"  [aviso] ação desconhecida '{acao}' para {message_id} — ignorada.")
    return False


def _bool_sheet(valor) -> bool:
    if isinstance(valor, bool):
        return valor
    return str(valor).strip().lower() in {"true", "1", "sim", "yes", "y"}


def _rows_to_dicts(rows: list) -> list:
    if not rows:
        return []
    headers = [str(c).strip() for c in rows[0]]
    parsed = []
    for row_number, row in enumerate(rows[1:], start=2):
        if not any(str(c).strip() for c in row):
            continue
        padded = list(row) + [""] * max(0, len(headers) - len(row))
        item = {headers[i]: padded[i] for i in range(len(headers))}
        item["_row_number"] = row_number
        parsed.append(item)
    return parsed


def renovar_google_token():
    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError as exc:
        raise RuntimeError("google-auth-oauthlib nao esta instalado") from exc

    if not GOOGLE_CREDENTIALS_PATH.exists():
        raise RuntimeError(f"credentials.json nao encontrado: {GOOGLE_CREDENTIALS_PATH}")
    flow = InstalledAppFlow.from_client_secrets_file(str(GOOGLE_CREDENTIALS_PATH), SHEETS_SCOPES)
    creds = flow.run_local_server(port=0)
    GOOGLE_TOKEN_PATH.write_text(creds.to_json(), encoding="utf-8")
    return creds


def carregar_sheets_service(force_refresh: bool = False):
    """Cria cliente Sheets com permissao de leitura/escrita.

    Se o token local tiver sido renovado apenas com escopo readonly, a rotina
    ignora a Sheet e preserva o fallback legacy por ficheiro exportado.
    """
    if not ARTIGOS_SHEET_ID:
        raise RuntimeError("ARTIGOS_SHEET_ID vazio")
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build
    except ImportError as exc:
        raise RuntimeError(
            "Bibliotecas Google API ausentes. Instale google-api-python-client, "
            "google-auth e google-auth-oauthlib."
        ) from exc

    if not GOOGLE_TOKEN_PATH.exists():
        if force_refresh:
            creds = renovar_google_token()
            return build("sheets", "v4", credentials=creds)
        raise RuntimeError(f"token.json nao encontrado: {GOOGLE_TOKEN_PATH}")

    creds = Credentials.from_authorized_user_file(str(GOOGLE_TOKEN_PATH), SHEETS_SCOPES)
    if not creds.has_scopes(SHEETS_SCOPES):
        if force_refresh:
            creds = renovar_google_token()
            return build("sheets", "v4", credentials=creds)
        raise RuntimeError(
            "token.json nao tem escopo de escrita em Sheets. Renove OAuth com "
            "https://www.googleapis.com/auth/spreadsheets."
        )
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        GOOGLE_TOKEN_PATH.write_text(creds.to_json(), encoding="utf-8")

    return build("sheets", "v4", credentials=creds)


def ler_decisoes_sheet(service) -> list:
    result = (
        service.spreadsheets()
        .values()
        .get(spreadsheetId=ARTIGOS_SHEET_ID, range="decisoes_artigos!A1:N10000")
        .execute()
    )
    return _rows_to_dicts(result.get("values", []))


def selecionar_decisoes_pendentes(rows: list) -> tuple[list, list]:
    """Devolve (acoes_efetivas, linhas_a_marcar).

    A Sheet e append-only. Para cada message_id, a linha mais recente ainda
    pendente manda. Se active=false, isso significa "sem decisao" e nao ha
    acao no Gmail; a linha e marcada como ignored para nao reaparecer.
    """
    pendentes = []
    for row in rows:
        status = str(row.get("status", "")).strip().lower()
        decision = str(row.get("decision", "")).strip().lower()
        message_id = str(row.get("message_id", "")).strip()
        if status in {"processed", "ignored", "seed", "failed"}:
            continue
        if not message_id or decision not in {"guardar", "excluir"}:
            continue
        pendentes.append(row)

    por_msg = {}
    linhas_por_msg = {}
    for row in pendentes:
        message_id = str(row.get("message_id", "")).strip()
        por_msg[message_id] = row
        linhas_por_msg.setdefault(message_id, []).append(row["_row_number"])

    acoes = []
    linhas = []
    for message_id, latest in por_msg.items():
        row_numbers = linhas_por_msg.get(message_id, [])
        decision = str(latest.get("decision", "")).strip().lower()
        active = _bool_sheet(latest.get("active"))
        if active:
            acoes.append({
                "message_id": message_id,
                "acao": decision,
                "row_numbers": row_numbers,
                "article_title": latest.get("article_title", ""),
            })
        else:
            linhas.append({
                "row_numbers": row_numbers,
                "status": "ignored",
                "notes": "Decisao desativada no site; artigo permanece pendente.",
            })
    return acoes, linhas


def marcar_linhas_sheet(service, updates: list, run_id: str) -> None:
    if not updates:
        return
    now = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    data = []
    for update in updates:
        for row_number in update.get("row_numbers", []):
            data.append({
                "range": f"decisoes_artigos!K{row_number}:N{row_number}",
                "values": [[
                    now,
                    run_id,
                    update.get("status", ""),
                    update.get("notes", ""),
                ]],
            })
    if not data:
        return
    service.spreadsheets().values().batchUpdate(
        spreadsheetId=ARTIGOS_SHEET_ID,
        body={"valueInputOption": "USER_ENTERED", "data": data},
    ).execute()


def processar_decisoes_sheet_pendentes(imap, pasta_all: str, pasta_trash: str, run_id: str, force_refresh: bool = False) -> dict:
    stats = {"guardados": 0, "excluidos": 0, "mantidos_em_leitura": 0, "ignorados": 0, "falhas": 0}
    chave_stats = {"guardar": "guardados", "excluir": "excluidos"}

    try:
        service = carregar_sheets_service(force_refresh=force_refresh)
        rows = ler_decisoes_sheet(service)
        acoes, status_updates = selecionar_decisoes_pendentes(rows)
    except Exception as exc:
        print(f"  [aviso] nao consegui ler Espelho_artigos; usando fallback por ficheiro: {exc}")
        return stats

    if not acoes and not status_updates:
        print("  [info] Espelho_artigos sem decisões pendentes.")
        return stats

    print(f"A processar decisões do Espelho_artigos: {len(acoes)} acao(oes), {len(status_updates)} noop(s)")
    for acao in acoes:
        ok = aplicar_decisao(imap, pasta_all, pasta_trash, acao["message_id"], acao["acao"])
        if ok:
            stats[chave_stats[acao["acao"]]] += 1
            status_updates.append({
                "row_numbers": acao["row_numbers"],
                "status": "processed",
                "notes": f"Aplicado no Gmail: {acao['acao']}",
            })
        else:
            stats["falhas"] += 1
            status_updates.append({
                "row_numbers": acao["row_numbers"],
                "status": "failed",
                "notes": f"Falha ao aplicar no Gmail: {acao['acao']}",
            })

    stats["ignorados"] += sum(1 for item in status_updates if item.get("status") == "ignored")
    try:
        marcar_linhas_sheet(service, status_updates, run_id)
    except Exception as exc:
        print(f"  [aviso] decisoes aplicadas, mas falhou marcar linhas na Sheet: {exc}")

    return stats


def somar_stats(*items: dict) -> dict:
    result = {"guardados": 0, "excluidos": 0, "mantidos_em_leitura": 0, "ignorados": 0, "falhas": 0}
    for item in items:
        for key, value in item.items():
            result[key] = result.get(key, 0) + int(value or 0)
    return result


def processar_decisoes_pendentes(imap, pasta_all: str, pasta_trash: str) -> dict:
    stats = {"guardados": 0, "excluidos": 0, "mantidos_em_leitura": 0, "ignorados": 0, "falhas": 0}
    ficheiros = sorted(glob.glob(os.path.join(OUTPUT, "decisoes_*.json")))

    chave_stats = {"guardar": "guardados", "excluir": "excluidos", "manter": "mantidos_em_leitura"}

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
            if not message_id or acao not in chave_stats:
                continue

            ok = aplicar_decisao(imap, pasta_all, pasta_trash, message_id, acao)
            if ok:
                stats[chave_stats[acao]] += 1
            else:
                stats["falhas"] += 1

        shutil.move(caminho, os.path.join(PROCESSADAS_DIR, os.path.basename(caminho)))

    return stats


def buscar_candidatos_da_label(imap, texto_procura: str) -> list:
    """Localiza a pasta IMAP da label e devolve os metadados brutos (sem
    processar PDF/corpo ainda) de todas as mensagens lá dentro."""
    pasta_label = encontrar_pasta_label(imap, texto_procura)
    print(f"  [info] label resolvida para a pasta IMAP: {pasta_label}")

    # STATUS é independente do estado de selecção — dá uma contagem
    # autoritativa de mensagens na pasta sem depender do SELECT/SEARCH
    # seguintes. Serve para isolar se o problema está na visibilidade da
    # label no IMAP (ex.: opção "Mostrar no IMAP" desligada no Gmail) ou
    # noutro sítio.
    status, status_dados = imap.status(f'"{pasta_label}"', "(MESSAGES)")
    print(f"  [info] STATUS da pasta (contagem independente): {status} {status_dados}")

    status, dados = imap.select(f'"{pasta_label}"', readonly=True)
    print(f"  [info] SELECT devolveu (contagem EXISTS): {dados}")
    if status != "OK":
        raise RuntimeError(f"Não consegui abrir a pasta '{pasta_label}' (status: {status}).")

    status, dados = imap.search(None, "ALL")
    if status != "OK":
        raise RuntimeError(f"Busca IMAP falhou: {status}")

    ids = dados[0].split()
    print(f"  [info] SEARCH ALL devolveu {len(ids)} mensagem(ns)")
    candidatos = []

    for msg_id in ids:
        status, msg_data = imap.fetch(msg_id, "(RFC822 X-GM-MSGID)")
        if status != "OK":
            continue

        # X-GM-MSGID vem no descritor do FETCH — que é o PRIMEIRO elemento
        # do tuple (ex.: (b'1 (X-GM-MSGID 123... RFC822 {1234}', b'<bytes>')),
        # não um item à parte. A versão anterior ignorava tuples por
        # completo ao procurar o X-GM-MSGID, por isso nunca o encontrava —
        # e todas as mensagens eram silenciosamente descartadas.
        gm_msgid = None
        for item in msg_data:
            descritor = item[0] if isinstance(item, tuple) else item
            texto_item = descritor.decode("utf-8", errors="replace") if isinstance(descritor, bytes) else str(descritor)
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

    print(f"  [info] candidatos processados com sucesso: {len(candidatos)}/{len(ids)}")
    return candidatos


def montar_artigo(c: dict) -> dict:
    """Processa um candidato bruto (extrai corpo, PDF, abstract) e monta a
    entrada final do artigo para o JSON."""
    msg = c["msg"]
    corpo = limpar_texto(remover_rodape(extrair_corpo(msg)))

    pdf_nome, pdf_bytes = extrair_pdf_anexo(msg)
    texto_completo = extrair_texto_pdf(pdf_bytes) if pdf_bytes else ""
    abstract = isolar_abstract(texto_completo)

    gm_msgid_hex = format(int(c["message_id"]), "x")

    return {
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
    }


def extrair_novos_artigos(imap) -> list:
    """Até BATCH_SIZE e-mails novos da label 'para ler', priorizando o
    próprio Rafa e depois os mais recentes."""
    candidatos = buscar_candidatos_da_label(imap, LABEL_PARA_LER.split("/")[-1])

    candidatos.sort(key=lambda c: (not c["sender_is_owner"], -c["date"].timestamp()))
    escolhidos = candidatos[:BATCH_SIZE]

    return [montar_artigo(c) for c in escolhidos]


def extrair_em_leitura(imap) -> list:
    """Todos os e-mails actualmente na label 'em leitura' — sem limite de
    lote, porque é uma lista já curada pelo próprio Rafa (artigos longos/
    recorrentes que ele escolheu manter em aberto). Se a label ainda não
    existir ou estiver vazia, devolve lista vazia em vez de rebentar a
    corrida."""
    try:
        candidatos = buscar_candidatos_da_label(imap, LABEL_EM_LEITURA.split("/")[-1])
    except RuntimeError as e:
        print(f"  [aviso] label 'em leitura' não encontrada/vazia: {e}")
        return []

    candidatos.sort(key=lambda c: -c["date"].timestamp())
    return [montar_artigo(c) for c in candidatos]


def export(force_refresh: bool = False):
    print("BASE_DIR:", BASE_DIR)
    run_id = f"artigos_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

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

    print("A aplicar decisões pendentes do Espelho_artigos (guardar/excluir)...")
    stats_sheet = processar_decisoes_sheet_pendentes(imap, pasta_all, pasta_trash, run_id, force_refresh=force_refresh)

    print("A aplicar decisões pendentes legacy por ficheiro JSON, se existirem...")
    stats_legacy = processar_decisoes_pendentes(imap, pasta_all, pasta_trash)
    stats_decisoes = somar_stats(stats_sheet, stats_legacy)

    print("A extrair novos artigos da label 'Artigos para ler'...")
    artigos = extrair_novos_artigos(imap)

    print("A extrair artigos da label 'Artigos em Leitura'...")
    artigos_em_leitura = extrair_em_leitura(imap)

    imap.logout()

    resultado = {
        "generated_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        "run_id": run_id,
        "label_origem": LABEL_PARA_LER,
        "label_em_leitura": LABEL_EM_LEITURA,
        "artigos_sheet_id": ARTIGOS_SHEET_ID,
        "artigos_sheet_url": f"https://docs.google.com/spreadsheets/d/{ARTIGOS_SHEET_ID}",
        "batch_size": BATCH_SIZE,
        "decisoes_aplicadas": stats_decisoes,
        "articles": artigos,
        "articles_em_leitura": artigos_em_leitura,
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
          f"excluídos: {stats_decisoes['excluidos']}, "
          f"mantidos em leitura: {stats_decisoes['mantidos_em_leitura']}, "
          f"ignorados/noop: {stats_decisoes['ignorados']}, "
          f"falhas: {stats_decisoes['falhas']}")
    print(f"Artigos novos extraídos: {len(artigos)}")
    print(f"  - com PDF/abstract encontrado: {sum(1 for a in artigos if a['abstract_text'])}")
    print(f"  - do próprio Rafa (prioridade 1): {sum(1 for a in artigos if a['sender_is_owner'])}")
    print(f"Artigos em leitura (sempre reexpostos): {len(artigos_em_leitura)}")
    print("=" * 56)
    print("Ficheiro gravado em:", ficheiro)
    print("=" * 56)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--force-refresh",
        action="store_true",
        help="Renova token Google local com escopo de escrita em Sheets antes de ler decisoes.",
    )
    parser.add_argument(
        "--refresh-token-only",
        action="store_true",
        help="Apenas renova o token Google local e termina, sem tocar no Gmail.",
    )
    args = parser.parse_args()
    if args.refresh_token_only:
        renovar_google_token()
        print(f"Token Google renovado em: {GOOGLE_TOKEN_PATH}")
        raise SystemExit(0)
    export(force_refresh=args.force_refresh)
