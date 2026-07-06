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

## Fases futuras (não implementadas ainda)

- Abrir os links dos emails que só trazem link (sem reportagem no corpo) e
  extrair o texto do artigo, preenchendo `article_text` (hoje sempre `null`).
- Agregar notícias repetidas entre fontes diferentes numa única entrada,
  listando as fontes que mencionaram.
