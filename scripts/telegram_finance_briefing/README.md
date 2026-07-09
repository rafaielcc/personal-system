# Telegram finance briefing export

Roda 100% local (fora do Claude, sem consumir tokens). Extrai as mensagens
dos canais acompanhados dos últimos 7 dias e gera um JSON estruturado para
a rotina do Claude Project ler — mesmo padrão do `gmail_export.py`.

## Setup (uma vez só)

1. Crie uma app em https://my.telegram.org/apps para obter `TELEGRAM_API_ID`
   e `TELEGRAM_API_HASH`.
2. `pip install -r requirements.txt`
3. Copie `.env.example` para `.env` e preencha `TELEGRAM_API_ID`/`TELEGRAM_API_HASH`.
4. Ajuste a constante `OUTPUT` em `telegram_export.py` se a sua pasta do
   Google Drive estiver noutro caminho.
5. Na primeira execução, o Telethon vai pedir para autenticar (código enviado
   pelo Telegram); a sessão fica guardada em `sessions/telegram.session`,
   não é preciso repetir depois.

## Rodar

```
python telegram_export.py
```

Gera `Telegram_<inicio>_a_<fim>.json` na pasta `OUTPUT`.

## Filtros aplicados (fora do LLM, deterministicos)

- **Ruído/promoção**: mensagens com palavras-chave de propaganda, cadastro,
  convite ou grupo pago (`RUIDO_KEYWORDS`) são descartadas antes de chegar
  ao JSON — nunca chegam a ser vistas pela rotina do Claude.
- **Vídeo sem conteúdo**: mensagens que são só um link do YouTube (com no
  máximo uma linha de título antes) são descartadas inteiramente — nunca
  processadas, nunca abertas.
- **Áudio**: só transcrito (via faster-whisper) quando o autor é
  "Daniel Nigri"; os demais áudios são ignorados.
- **Duplicados**: mensagens com o mesmo texto (normalizado) dentro da mesma
  execução são descartadas na segunda ocorrência.

## Extração de link (Fase 2)

Cada mensagem de texto costuma trazer no máximo um link. Quando existe (e
não é vídeo nem convite `t.me/`), o script tenta abri-lo e extrair o texto
do artigo via `trafilatura`, preenchendo `article_text`. Isto:

- Nunca é bloqueante — qualquer falha (timeout, paywall, erro de rede)
  devolve `article_text: null` e a mensagem continua a ser exportada
  normalmente, só sem o texto do artigo.
- Timeout de 8 segundos por link.
- Fica registado em `link_stats` (nível do ficheiro): quantos links foram
  encontrados, quantos foram abertos com sucesso (HTTP 200) e quantos
  produziram texto de artigo utilizável.

## Sobre `tickers_mentioned`

Cada mensagem (texto ou áudio transcrito) já vem com uma lista de tickers
detectados por correspondência de padrão fixo (`scripts/common/tickers.py`,
partilhado com o `gmail_export.py`) — sem LLM nenhum, só regex. Serve para
a rotina localizar rapidamente o que é relevante para a carteira/Vigiar sem
ter de ler mensagem a mensagem.

## Fases futuras (não implementadas ainda)

- Agregar notícias repetidas entre canais/fontes diferentes numa única
  entrada, listando as fontes que mencionaram.
