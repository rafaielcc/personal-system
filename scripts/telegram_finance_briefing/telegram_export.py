from telethon import TelegramClient
from telethon.tl.types import MessageService

from dotenv import load_dotenv
from faster_whisper import WhisperModel

import os
import re
import sys
import json
import tempfile
import shutil
import requests
import trafilatura
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from common.tickers import find_tickers

# =========================
# BASE PATH
# =========================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

load_dotenv(os.path.join(BASE_DIR, ".env"))

API_ID = int(os.getenv("TELEGRAM_API_ID"))
API_HASH = os.getenv("TELEGRAM_API_HASH")

# =========================
# CONFIG
# =========================
GROUPS = [
    "Dica de Hoje - Notícias 📰 e Atualizações 🌎",
    "Canal Neto Invest",
    "DH - Dica Ações",
    "DH - DicaPrev",
    "XP Investimentos"
]

OUTPUT = r"G:\My Drive\Claude_PRJ\Relatorios\Sources\Telegram_finances"
SESSION = os.path.join(BASE_DIR, "sessions", "telegram")

os.makedirs(OUTPUT, exist_ok=True)
os.makedirs(os.path.dirname(SESSION), exist_ok=True)

# =========================
# WHISPER
# =========================
whisper_model = WhisperModel(
    "base",
    device="cpu",
    compute_type="int8"
)

# =========================
# CLIENT
# =========================
client = TelegramClient(
    SESSION,
    API_ID,
    API_HASH
)

# =========================
# RUIDO (promocoes, cadastros, convites — nunca conteudo relevante)
# =========================
RUIDO_KEYWORDS = [
    "oferta", "promoção", "assinatura", "clique aqui",
    "grupo vip", "plano premium", "cupom",
    "últimas vagas", "cadastre-se", "entre agora",
    "link na bio", "desconto",
    "vagas limitadas", "por tempo limitado", "condição especial", "condições especiais",
    "assine agora", "garanta sua vaga", "inscreva-se", "garanta já",
    "sorteio", "brinde",
    "grupo fechado", "grupo exclusivo",
    "não perca", "aproveite agora",
    "acesse o link", "saiba mais aqui", "clique no link",
    "t.me/",
]

MIN_CHARS = 25

# link de video (nunca abrimos, nunca extraimos artigo)
VIDEO_LINK_PATTERN = re.compile(r"(?:youtube\.com|youtu\.be)/\S+", re.IGNORECASE)
LINK_PATTERN = re.compile(r"https?://\S+")

# tempo maximo de espera ao abrir um link (Etapa "Fase 2" — extraccao de artigo)
LINK_TIMEOUT_SECONDS = 8
LINK_USER_AGENT = "Mozilla/5.0 (compatible; AII-briefing-bot/1.0)"


def limpar_texto(texto: str) -> str:
    texto = re.sub(r"\n{3,}", "\n\n", texto)
    texto = re.sub(r"[ \t]+", " ", texto)
    return texto.strip()


def ignorar_texto(texto: str) -> bool:
    if not texto:
        return True

    t = texto.strip().lower()

    if len(t) < MIN_CHARS:
        return True

    if all(c in "👍👏🔥❤️ " for c in t):
        return True

    if re.fullmatch(r"https?://\S+", t):
        return True

    if any(k in t for k in RUIDO_KEYWORDS):
        return True

    return False


def eh_apenas_video(texto: str) -> bool:
    """Mensagem inteira e so um link de video (com no maximo uma linha de
    titulo antes) — nunca processamos video, so texto/artigo."""
    linhas = [l.strip() for l in texto.strip().splitlines() if l.strip()]
    if not linhas:
        return False
    ultima = linhas[-1]
    if not VIDEO_LINK_PATTERN.search(ultima):
        return False
    # todo o resto (se houver) tem de ser so titulo curto, sem outro link
    resto = " ".join(linhas[:-1])
    return not LINK_PATTERN.search(resto)


def extrair_link(texto: str) -> str | None:
    """Telegram normalmente traz um unico link por mensagem. Ignora links
    de video (nunca abertos) e de convite (t.me, ja cortado como ruido)."""
    for match in LINK_PATTERN.finditer(texto):
        url = match.group()
        if VIDEO_LINK_PATTERN.search(url):
            continue
        if "t.me/" in url:
            continue
        return url
    return None


def abrir_link(url: str, stats: dict) -> str | None:
    """Fase 2: abre o link unico da mensagem e extrai o texto do artigo.
    Nunca bloqueante — qualquer falha devolve None e regista em stats."""
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


def transcrever_audio(path: str) -> str:
    try:
        segments, _ = whisper_model.transcribe(path)
        return " ".join([s.text for s in segments]).strip()
    except Exception as e:
        return f"[ERRO_TRANSCRICAO: {e}]"


# =========================
# PIPELINE
# =========================
async def export():

    print("BASE_DIR:", BASE_DIR)

    await client.start()

    await client.get_dialogs()

    limite = datetime.now() - timedelta(days=7)
    agora = datetime.now()
    inicio = agora - timedelta(days=7)

    ficheiro = os.path.join(
        OUTPUT,
        f"Telegram_{inicio.strftime('%Y-%m-%d')}_a_{agora.strftime('%Y-%m-%d')}.json"
    )

    vistos = set()
    mensagens = []
    link_stats = {"encontrados": 0, "abertos": 0, "sucesso": 0}

    for grupo in GROUPS:

        entidade = await client.get_entity(grupo)

        async for m in client.iter_messages(entidade):

            if not m.date:
                continue

            if m.date.replace(tzinfo=None) < limite:
                break

            if isinstance(m, MessageService):
                continue

            autor = ""
            try:
                if m.sender:
                    autor = getattr(m.sender, "first_name", "")
            except Exception:
                autor = ""

            data = m.date.strftime("%Y-%m-%dT%H:%M:%S")

            # =========================
            # AUDIO (SO DANIEL NIGRI)
            # =========================
            if m.voice or m.audio:

                if autor != "Daniel Nigri":
                    continue

                try:
                    path = await m.download_media()
                    texto_audio = transcrever_audio(path)

                    mensagens.append({
                        "channel": grupo,
                        "time": data,
                        "author": autor,
                        "type": "audio",
                        "content": texto_audio,
                        "tickers_mentioned": find_tickers(texto_audio),
                        "link": None,
                        "article_text": None,
                    })

                except Exception as e:
                    mensagens.append({
                        "channel": grupo,
                        "time": data,
                        "author": autor,
                        "type": "audio",
                        "content": f"[AUDIO_ERROR: {e}]",
                        "tickers_mentioned": [],
                        "link": None,
                        "article_text": None,
                    })

                continue

            # =========================
            # TEXTO
            # =========================
            texto_bruto = m.text or ""

            # video-only nunca e processado (nem sequer entra no JSON)
            if eh_apenas_video(texto_bruto):
                continue

            texto = limpar_texto(texto_bruto)

            if ignorar_texto(texto):
                continue

            chave = texto.lower()

            if chave in vistos:
                continue

            vistos.add(chave)

            link = extrair_link(texto)
            article_text = abrir_link(link, link_stats) if link else None

            mensagens.append({
                "channel": grupo,
                "time": data,
                "author": autor,
                "type": "text",
                "content": texto,
                "tickers_mentioned": find_tickers(texto),
                "link": link,
                "article_text": article_text,
            })

    payload = {
        "generated_at": agora.strftime("%Y-%m-%dT%H:%M:%S"),
        "period": {
            "start": inicio.strftime("%Y-%m-%d"),
            "end": agora.strftime("%Y-%m-%d"),
        },
        "channels": GROUPS,
        "link_stats": link_stats,
        "messages": mensagens,
    }

    # escrita segura em pastas sincronizadas (Google Drive Desktop) — evita
    # OSError [Errno 22] ao escrever directamente no destino final.
    fd, tmp_path = tempfile.mkstemp(suffix=".json", dir=OUTPUT)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    shutil.move(tmp_path, ficheiro)

    print("Concluido:", ficheiro)
    print("Mensagens:", len(mensagens), "| Links:", link_stats)


with client:
    client.loop.run_until_complete(export())
