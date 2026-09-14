# Gmail articles export (rotina Artigos Científicos)

Roda 100% local (fora do Claude, sem consumir tokens). Duas funções por
execução, sempre pela mesma ordem:

1. **Aplica as decisões pendentes** — lê primeiro `Espelho_artigos`
   (`decisoes_artigos`) via Google Sheets API. O ficheiro `decisoes_*.json`
   na pasta `OUTPUT` fica apenas como fallback legacy/manual. As decisões são
   aplicadas no Gmail via IMAP:
   - `guardar` → aplica a label `Paediatric Surgery/Artigos-Lidos` e remove
     `Paediatric Surgery/Artigos-ParaLer` e `Paediatric Surgery/Artigos-
     EmLeitura` (o artigo pode vir de qualquer uma das duas).
   - `excluir` → copia para o Lixo (recuperável 30 dias, nunca apaga
     definitivamente) e remove das mesmas duas labels de origem.
   - Sem decisão nenhuma → não há linha efetiva na Sheet, o Gmail não é
     alterado e o artigo continua pendente na label atual até uma decisão real
     ser tomada.
   - `manter` permanece aceito apenas para ficheiros legacy antigos; a UI nova
     não oferece esse botão.
   - Ficheiros fallback processados são movidos para `decisoes_processadas/`
     (nunca apagados, para auditoria).
2. **Extrai os próximos artigos** da label `Paediatric Surgery/Artigos-
   ParaLer` — até 10 por corrida (`articles`), priorizando remetente = você
   mesmo (`OWNER_EMAIL`), depois os restantes, mais recentes primeiro.
3. **Extrai todos os artigos "em leitura"** da label `Paediatric Surgery/
   Artigos-EmLeitura` — sem limite de lote (`articles_em_leitura`), já que
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
6. Confirme que `G:\My Drive\Claude_PRJ\token.json` tem escopo de escrita em
   Google Sheets (`https://www.googleapis.com/auth/spreadsheets`). Se o token
   tiver sido criado só com readonly, renove o OAuth antes de usar o espelho.
7. Ajuste a constante `OUTPUT` em `gmail_articles_export.py` se a sua pasta
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

`Paediatric Surgery/Artigos-ParaLer`, `Paediatric Surgery/Artigos-Lidos` e
`Paediatric Surgery/Artigos-EmLeitura` são sub-labels do Gmail — o IMAP
trata o `/` como parte literal do nome, não como hierarquia de pastas real.
Os nomes das sub-labels não têm espaço de propósito (evita ambiguidade de
escaping). As três ações (`guardar`/`excluir`/`manter`) usam a extensão
`X-GM-LABELS` do IMAP do Gmail para mover entre elas; "excluir"
adicionalmente copia a mensagem para o Lixo antes de remover as labels de
origem, para nunca apagar nada de forma irrecuperável.

As três constantes `LABEL_PARA_LER`/`LABEL_LIDOS`/`LABEL_EM_LEITURA` no
topo do script são a **única fonte de verdade** dos nomes das labels — o
texto usado para localizar cada pasta IMAP é sempre derivado delas (nunca
duplicado à parte). Se renomear uma tag no Gmail, basta actualizar a
constante correspondente aqui.

A extração das labels (Secção "extrai" acima) **não usa** o operador de
busca `label:"..."` do Gmail (`X-GM-RAW`) — essa sintaxe não se mostrou
fiável com labels aninhadas em testes reais. Em vez disso, o script lista
as pastas IMAP da conta (`imap.list()`) e localiza/selecciona directamente
a pasta cujo nome contém o texto da label, que o Gmail expõe como uma
mailbox navegável como qualquer outra.

## Sobre `gmail_web_link`

Cada artigo já vem com o link direto para a mensagem no Gmail
(`https://mail.google.com/mail/u/0/#all/<hex do X-GM-MSGID>`), usado no botão
"Ver no Gmail" da página HTML. O `message_id` gravado no JSON é o mesmo
`X-GM-MSGID` (decimal) — é ele, não o UID do IMAP, que identifica a mensagem
de forma estável entre corridas (o UID só é válido dentro de uma pasta).

## Espelho_artigos

Fonte normal das decisões:

https://docs.google.com/spreadsheets/d/1Sl67SXLz--uOaYlbo6tT97pXUu_O3qNvVCVAVDDZBp0

A página HTML envia eventos para o Apps Script, que faz append em
`decisoes_artigos`. A rotina considera a linha pendente mais recente por
`message_id`:

- `decision=guardar`, `active=TRUE` → guardar;
- `decision=excluir`, `active=TRUE` → excluir;
- `active=FALSE` → clique revertido; sem ação no Gmail.

Linhas processadas recebem `processed_at`, `processed_by_run_id` e `status`.

## Ficheiro de decisões fallback

```json
[
  {"message_id": "1234567890123456789", "acao": "guardar"},
  {"message_id": "9876543210987654321", "acao": "excluir"},
  {"message_id": "1111111111111111111", "acao": "manter"}
]
```

Esse ficheiro já não é o fluxo normal. Continua aceite para contingência ou
para decisões antigas exportadas antes da migração para Sheets.
