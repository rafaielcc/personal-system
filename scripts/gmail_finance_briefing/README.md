# Gmail finance briefing export

Roda 100% local (fora do Claude, sem consumir tokens). Extrai os emails da
label "finance briefing" dos últimos 7 dias e gera um JSON estruturado para
a rotina do Claude Project ler.

## Setup (uma vez só)

1. Ative a verificação em duas etapas na sua conta Google, se ainda não tiver.
2. Gere uma senha de app em https://myaccount.google.com/apppasswords
   (escolha "Mail" / "Outro" como app).
3. Confirme que o IMAP está ativado em Gmail > Configurações > Encaminhamento e POP/IMAP.
4. `pip install -r requirements.txt`
5. Copie `.env.example` para `.env` e preencha `GMAIL_ADDRESS` e `GMAIL_APP_PASSWORD`
   (a senha de app, não a senha normal da conta).
6. Ajuste a constante `OUTPUT` em `gmail_export.py` se sua pasta do Google Drive
   estiver em outro caminho.

## Rodar

```
python gmail_export.py
```

Gera `Gmail_finance_briefing_<inicio>_a_<fim>.json` na pasta `OUTPUT`.

## Sobre a extração de índices

A seção `indices` do JSON tenta capturar automaticamente, por dia, os valores de:
dólar, euro, libra esterlina (vs. real), petróleo bruto/Brent, minério de ferro,
ouro, soja e algodão — procurando a palavra-chave no texto do email e o número
mais próximo dela.

Isso é uma heurística de primeira versão: como cada newsletter formata os
valores de um jeito, é bem provável que algumas capturas venham erradas ou
faltando na primeira rodada. Recomendado: rodar uma vez, olhar o campo `raw`
de cada índice capturado (ele mostra o trecho de texto de onde tirou o valor)
e ajustar os padrões em `INDICE_PATTERNS`/`NUM_PATTERN` no script conforme o
formato real das suas newsletters.

## Extração de link (Fase 2)

Cada link encontrado no corpo do email (exceto os de descadastro/preferências,
já filtrados) é aberto e tem o texto do artigo extraído via `trafilatura`,
preenchendo `article_text` em `links`. Isto:

- Nunca é bloqueante — qualquer falha (timeout, paywall, erro de rede)
  devolve `article_text: null` e o email continua a ser exportado
  normalmente, só sem o texto do artigo.
- Timeout de 8 segundos por link.
- Fica registado em `link_stats` (nível do ficheiro): quantos links foram
  encontrados, quantos foram abertos com sucesso (HTTP 200) e quantos
  produziram texto de artigo utilizável.

## Sobre `tickers_mentioned`

Cada email já vem com uma lista de tickers detectados por correspondência de
padrão fixo (`scripts/common/tickers.py`, partilhado com o
`telegram_export.py`) — sem LLM nenhum, só regex. Serve para a rotina
localizar rapidamente o que é relevante para a carteira/Vigiar sem ter de
ler email a email.

## Relatório de execução

Ao fim de cada execução, o script imprime um relatório no terminal (e grava
os mesmos números no campo `stats`/`link_stats` do JSON): emails vistos na
janela de 7 dias, quantos foram ignorados por corpo curto/vazio ou por
duplicado, quantos foram incluídos, e quantos links foram encontrados/
abertos/produziram artigo utilizável (com taxa de sucesso em %). Serve para
avaliar, ao longo do tempo, se vale a pena manter a abertura de links.

## Fases futuras (não implementadas ainda)

- Agregar notícias repetidas entre fontes diferentes numa única entrada,
  listando as fontes que mencionaram.
