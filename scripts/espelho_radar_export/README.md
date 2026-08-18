# Espelho Radar export

Roda 100% local (fora do Claude, sem consumir tokens). Lê a aba "Main" da
planilha Espelho Radar via Google Sheets API e devolve/grava um JSON já
separado em `carteira` e `vigiar` pela linha-marcador ("vigiar", detectado
de forma tolerante a variações de formatação — ver `MARKER_RE` no script).

## Setup (uma vez só)

1. `pip install -r requirements.txt`
2. Confirma que `credentials.json` e `token.json` (OAuth "installed app",
   scope `spreadsheets.readonly`) existem na pasta SSOT. Por defeito o script
   procura em `G:\My Drive\Claude_PRJ\SSOT\` — ajusta `DEFAULT_SSOT_DIR` no
   script, ou passa `--credentials`/`--token` explícitos, se o teu caminho for
   outro.
3. `token.json` já contém `client_id`/`client_secret`/`refresh_token`, por
   isso o script consegue renovar o `access_token` sozinho quando expira —
   `credentials.json` só é necessário se algum dia for preciso refazer o
   consentimento interativo do zero (fora deste script).

## Rodar

```
python espelho_radar_export.py
```

Imprime o JSON em stdout. Para gravar em ficheiro:

```
python espelho_radar_export.py --out espelho_radar.json
```

## Saída

```json
{
  "generated_at": "2026-08-18T09:00:00",
  "spreadsheet_id": "1g7JBnpEkaYZQl2SBGYmooZhOBYqOa0ER2o3F1yPkSnA",
  "range": "Main",
  "marker_found": true,
  "header": ["Ticker", "Atual", "Peso %", "..."],
  "carteira": [{"Ticker": "BBAS3", "Atual": "18,00", "...": "..."}],
  "vigiar": [{"Ticker": "ITSA4", "Atual": "...", "...": "..."}]
}
```

Cada linha da aba vira um dicionário chaveado pelos cabeçalhos reais da
planilha (linha 1) — o script não assume nomes de coluna fixos, só a posição
da linha-marcador para separar Carteira de Vigiar. Se `marker_found` vier
`false`, todas as linhas caem em `carteira` e `vigiar` fica vazio — sinal de
que o marcador não foi encontrado (não assumir uma divisão por adivinhação;
ver Etapa 4.0, item 1 da rotina Notícias do Dia).

## Uso pelo preflight/postflight da Notícias do Dia

Este script substitui a leitura interativa da Espelho Radar pelo conector
Drive/Sheets do Claude (Etapa 1A) por uma leitura determinística, sem custo
de tokens de LLM — chamado a partir do preflight (`AII_X_preflight_noticias_do_dia.py`)
ou directamente antes de montar o `data_noticias.json`.
