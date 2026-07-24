# Gmail articles export (rotina Artigos Científicos)

Roda 100% local (fora do Claude, sem consumir tokens). Duas funções por
execução, sempre pela mesma ordem:

1. **Aplica as decisões da semana anterior** — lê qualquer ficheiro
   `decisoes_*.json` na pasta `OUTPUT` (gerado pelo botão "Exportar decisões
   da semana" da página HTML publicada) e aplica no Gmail via IMAP:
   - `guardar` → aplica a label `Paediatric Surgery/Artigos Lidos` e remove
     `Paediatric Surgery/Artigos para ler` e `Paediatric Surgery/Artigos em
     Leitura` (o artigo pode vir de qualquer uma das duas).
   - `excluir` → copia para o Lixo (recuperável 30 dias, nunca apaga
     definitivamente) e remove das mesmas duas labels de origem.
   - `manter` → aplica `Paediatric Surgery/Artigos em Leitura` e remove
     `Paediatric Surgery/Artigos para ler`. Diferença chave para `guardar`:
     o artigo **continua a ser reexposto em todas as corridas seguintes**
     (campo `articles_em_leitura` do JSON, sem limite de lote) em vez de
     sair de circulação — pensado para artigos longos/de leitura recorrente
     que levam semanas a terminar.
   - Ficheiros processados são movidos para `decisoes_processadas/` (nunca
     apagados, para auditoria).
2. **Extrai os próximos artigos** da label `Paediatric Surgery/Artigos para
   ler` — até 10 por corrida (`articles`), priorizando remetente = você
   mesmo (`OWNER_EMAIL`), depois os restantes, mais recentes primeiro.
3. **Extrai todos os artigos "em leitura"** da label `Paediatric Surgery/
   Artigos em Leitura` — sem limite de lote (`articles_em_leitura`), já que
   é uma lista curada manualmente pelo Rafa. Se a label ainda não existir
   ou estiver vazia, o campo vem como lista vazia, sem rebentar a corrida.

## Setup (uma vez só)

1. Ative a verificação em duas etapas na sua conta Google, se ainda não tiver.
2. Gere uma senha de app em https://myaccount.google.com/apppasswords.
3. Confirme que o IMAP está ativado em Gmail > Configurações > Encaminhamento e POP/IMAP.
4. `pip install -r requirements.txt`
5. Copie `.env.example` para `.env` e preencha `GMAIL_ADDRESS` e
   `GMAIL_APP_PASSWORD` (a senha de app). Preencha `OWNER_EMAIL` só se o seu
   endereço prioritário for diferente do `GMAIL_ADDRESS`.
6. Ajuste a constante `OUTPUT` em `gmail_articles_export.py` se a sua pasta
   do Google Drive estiver noutro caminho.

## Rodar

```
python gmail_articles_export.py
```

Gera `Gmail_artigos_<data>.json` na pasta `OUTPUT` — é este ficheiro que a
rotina LLM (trigger "Artigos") lê para gerar a página HTML.

## Sobre a extração de PDF

Cada e-mail com um anexo PDF tem o texto completo extraído via `pymupdf`
(`full_text`) e o abstract isolado por heurística de regex (`abstract_text`
— procura o heading "Abstract" até ao próximo heading de secção conhecido).
Isto nunca bloqueia a corrida: um PDF corrompido ou digitalizado sem OCR
simplesmente devolve texto vazio nesses dois campos, e o e-mail continua a
ser incluído normalmente (só sem abstract/texto completo).

## Sobre as labels aninhadas

`Paediatric Surgery/Artigos para ler`, `Paediatric Surgery/Artigos Lidos` e
`Paediatric Surgery/Artigos em Leitura` são sub-labels do Gmail — o IMAP
trata o `/` como parte literal do nome, não como hierarquia de pastas real.
As três ações (`guardar`/`excluir`/`manter`) usam a extensão `X-GM-LABELS`
do IMAP do Gmail para mover entre elas; "excluir" adicionalmente copia a
mensagem para o Lixo antes de remover as labels de origem, para nunca
apagar nada de forma irrecuperável.

A extração das labels (Secção "extrai" acima) **não usa** o operador de
busca `label:"..."` do Gmail (`X-GM-RAW`) — essa sintaxe não se mostrou
fiável com labels aninhadas com espaços em testes reais. Em vez disso, o
script lista as pastas IMAP da conta (`imap.list()`) e localiza/selecciona
directamente a pasta cujo nome contém o texto da label, que o Gmail expõe
como uma mailbox navegável como qualquer outra.

## Sobre `gmail_web_link`

Cada artigo já vem com o link direto para a mensagem no Gmail
(`https://mail.google.com/mail/u/0/#all/<hex do X-GM-MSGID>`), usado no botão
"Ver no Gmail" da página HTML. O `message_id` gravado no JSON é o mesmo
`X-GM-MSGID` (decimal) — é ele, não o UID do IMAP, que identifica a mensagem
de forma estável entre corridas (o UID só é válido dentro de uma pasta).

## Ficheiro de decisões (gerado pela página HTML)

Formato esperado em `decisoes_<data>.json`:

```json
[
  {"message_id": "1234567890123456789", "acao": "guardar"},
  {"message_id": "9876543210987654321", "acao": "excluir"},
  {"message_id": "1111111111111111111", "acao": "manter"}
]
```

Artigos marcados só como "já lido" na página **não** entram neste ficheiro —
essa marcação é cosmética, vale só para aquela renderização da semana.
