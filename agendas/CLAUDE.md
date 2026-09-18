# Projecto Agenda — contexto para Claude Code

Este repositório (`rafaielcc/personal-system`) é onde o projecto **Agenda** publica as suas páginas. A Agenda é um sistema pessoal de rotinas do Rafa (Briefing diário, Painel de trabalho no Hospital Fernando Fonseca, Agenda de Lazer, Dashboard) que corre normalmente via Claude Projects (claude.ai) e cujo output final — HTML estático — é publicado neste repo (pasta `agendas/`) e servido pelo Cloudflare Pages. As rotinas de cada módulo (o "como fazer") vivem como documentos de instrução no Google Drive, não neste repo — este repo só recebe os outputs publicados e os scripts de render.

**Porque correr também via Claude Code:** as sessões de claude.ai (app normal) têm cortado rotinas longas a meio por limite de tokens por mensagem, sobretudo nas rotinas que geram HTML. O Code tem-se mostrado mais fiável a completar rotinas inteiras e a publicar no GitHub sem cortar etapas. Mas uma sessão nova do Code, ao contrário de uma conversa em claude.ai, **não tem nenhum contexto deste projecto por omissão** — não sabe o que é a Agenda, onde ficam as instruções, nem a convenção de nomes. Este ficheiro existe para resolver isso.

## ⚠️ Leitura obrigatória antes de qualquer rotina

O Code não tem o system prompt do projecto Agenda em claude.ai carregado em contexto (isso só existe dentro da conversa em claude.ai, não é replicável automaticamente aqui). Por isso, **antes de correr qualquer rotina a partir do Code, é obrigatório ler primeiro** o ficheiro de perfil/contexto geral do projecto:

> **`SYSTEM_PROMPT_FINAL.md`** — pasta Drive `15Ge84lmsAeoUgSXDWFpcW26X-UCixrbg` (procurar pelo nome, usar a cópia de `createdTime` mais recente se houver mais do que uma; o ficheiro já não leva número de versão no nome, deixou de ser incrementado dessa forma).

Isto aplica-se **mesmo que o documento de instruções da própria rotina diga que não é preciso** ler mais nada antes de activar — essa instrução assume que já estás numa conversa em claude.ai com o system prompt do projecto já carregado, o que nunca é verdade numa sessão nova do Code. O `SYSTEM_PROMPT_FINAL.md` tem a arquitectura do projecto (onde vivem as instruções vs. onde vivem os dados), a Rotina de Publicação partilhada, a Leitura de Calendário partilhada, e um resumo de cada módulo — é o que dá ao Code o mesmo chão que uma conversa em claude.ai já tem.

## Pasta Drive das instruções

Todos os documentos de instrução dos módulos da Agenda (e o `SYSTEM_PROMPT_FINAL.md`) vivem directamente na raiz desta pasta — **não em subpastas**:

> `15Ge84lmsAeoUgSXDWFpcW26X-UCixrbg`

(A pasta-mãe de todos os projectos do Rafa, `1KAVv-gCiCGGlZNvxgVLvx3SuKRRZ-hzC`, é onde ficam ficheiros partilhados entre projectos como `Rafa_profile.md` e `Feedback_log.json` — os IDs exactos desses ficheiros já estão documentados dentro de cada rotina/no system prompt; não precisas de os procurar à parte.)

## Convenção de nomes dos ficheiros de instrução

- Padrão: `NOME_DA_ROTINA_v<X.Y>.md`, maiúsculas com underscores, direto na raiz da pasta acima.
- **O Drive não edita ficheiros in-place** — uma actualização cria sempre um ficheiro novo (nova versão ou o mesmo nome outra vez), sem apagar automaticamente o antigo. Por isso, ao procurar o ficheiro de uma rotina, **pode haver mais do que uma cópia com títulos parecidos** (mesma versão, versões diferentes, ou por vezes até "(conflict ...)" no nome de um conflito de sincronização do Drive). **Usar sempre a cópia com `createdTime` mais recente**, salvo indicação em contrário abaixo.
- Excepções actuais, ficheiros mantidos deliberadamente sem sufixo de versão no nome (o Rafa apaga as versões antigas conforme avança em vez de incrementar o número): **Agenda de Lazer** (`AGENDA_LAZER_INSTRUCOES*.md` — ainda leva sufixo `_vX.Y`, mas o padrão pode mudar; usar sempre o mais recente por `createdTime`) e **Painel HFF**, cujo ficheiro de instruções já não leva nenhum número — é só `INSTRUCOES_PAINEL_HFF.md`. Não assumir um nome fixo com número de versão para nenhum destes dois módulos; procurar por título e usar o mais recente.
- Vários módulos têm agora também uma cópia `_LOCAL` do documento de instruções (ex: `BRIEFING_DIARIO_v13.0_LOCAL.md`, `INSTRUCOES_DASHBOARD_v11.4_LOCAL.md`, `AGENDA_LAZER_INSTRUCOES_v5.5_LOCAL.md`) — descreve a variante da rotina com preflight/postflight Python mecânico (ver secção "Duas formas de correr" abaixo). A versão sem `_LOCAL` é a rotina "pura", pensada para correr inteira dentro de uma conversa (claude.ai ou Code interactivo); não depende dos scripts locais.

## Comandos disponíveis (skills)

| Pedido do Rafa (exemplos) | Skill | Rotina no Drive | Publica em |
|---|---|---|---|
| "dashboard", "gera o dashboard", "atualiza o dashboard", "home" | `dashboard` | `INSTRUCOES_DASHBOARD_v11.4.md` (ou mais recente) | `agendas/index.html` |
| "bom dia", "briefing", "gera o briefing", "briefing para amanhã" | `briefing` | `BRIEFING_DIARIO_v13.0.md` (ou mais recente) — via Code/claude.ai interactivo; ver nota sobre o caminho automatizado (Agendador de Tarefas) abaixo | `agendas/briefing/index.html` |
| "agenda de lazer", "eventos em Lisboa", "o que há para fazer" | `agenda-de-lazer` | `AGENDA_LAZER_INSTRUCOES*` (mais recente, sem sufixo fixo — ver nota acima) | `agendas/lazer/index.html` |
| "painel hff", "agenda de trabalho", "cirurgias hoje", "lista bo" | `agenda-de-trabalho` | `INSTRUCOES_PAINEL_HFF.md` (sem sufixo de versão — ver nota acima) — via Code/claude.ai interactivo; ver nota sobre o caminho automatizado abaixo | `agendas/Hff/index.html` + `agendas/BO/index.html` |
| "artigos científicos", "gera os artigos", "/artigos" | `artigos` | `INSTRUCOES_ARTIGOS_v1.3.md` (ou mais recente) | `agendas/artigos/index.html` |
| "atualizar testme", "test me", "simulado cirurgia pediátrica" | `testme` | `TESTME.md` (sem sufixo de versão no nome) | `agendas/personal-development/testme/index.html` |
| "$notificacoes", "notificacoes", "triagem de notificacoes", "espelho notificacoes" | `notificacoes` | `instrucoes_notificacoes.md` (sem sufixo de versão no nome) | `agendas/notificacoes/index.html` + `agendas/agendas/notificacoes/index.html` (espelho, exigido pelo `destination_dir=agendas` do Cloudflare Pages) |

## Padrão de publicação (todos os módulos)

Nenhum módulo escreve HTML directamente. Cada um produz **apenas um JSON canónico** (o esquema está na Secção 7/11 do respectivo documento de instruções); um `render.py` (stdlib Python, sem dependências) lê esse JSON + um `template.html` e gera o HTML final por substituição mecânica de texto. Os templates e scripts de render vivem no Drive, pasta `Templates` (subpasta por módulo: `Briefing/`, `hff/`, `bo/`, `dashboard/`, `agenda_lazer/`). O que acontece depois do render (commit/push) está descrito em **`ROTINA_PUBLICACAO.md`** (mesma pasta de instruções, sem sufixo de versão no nome — o número de versão vive só no changelog dentro do próprio ficheiro, actualmente na v1.12; tem o mapa completo módulo → IDs de template/render/caminho GitHub) — **não replicar esses detalhes aqui nem nos skills**, esse documento é a única fonte de verdade e pode mudar sem aviso. Não grava cópia no Drive do HTML publicado — só o GitHub, desde a v1.6.

Este padrão existe precisamente para evitar o problema que motivou correr via Code: a LLM nunca escreve o HTML inteiro de uma figura só, o que era a causa directa de rotinas a cortar a meio por tecto de tokens.

## Duas formas de correr: interactivo vs. Agendador de Tarefas

Até aqui, tudo assume uma conversa (claude.ai ou Code) a correr a rotina inteira, do pedido do Rafa até à publicação, com o LLM a fazer tanto a recolha de dados como a redacção. **Briefing e Painel HFF têm, além disso, um segundo caminho, automatizado pelo Agendador de Tarefas do Windows**, que separa a recolha (mecânica, sem LLM) da interpretação (só LLM, sem recolha):

1. **`go_X_briefing_pre.bat`** (06:00, seg-sex) → corre `X_briefing_pre.py`: recolhe Calendar/Gmail/Todoist/Espelho HFF/meteorologia e grava um JSON em `X_Outputs`. Puramente mecânico — não julga, não escreve texto, não publica.
2. **`go_briefing_llm.bat`** (06:30, seg-sex, ~15-20 min depois) → chama `claude -p` (não-interactivo, `--model claude-sonnet-5`, `--permission-mode dontAsk`): lê esse JSON, classifica os emails e escreve `audio_script`/alertas/sugestões, produzindo o JSON canónico final. Depois chama `X_briefing_pos.py` (valida + renderiza + publica o Briefing) e, se o modo for A, também `X_hff_pos.py` (idem para `agendas/Hff/` e `agendas/BO/`) — o LLM nunca escreve HTML nem faz o push directamente, isso é sempre o Python destes dois scripts.

Ambos os `.bat` sincronizam primeiro com `origin/main` (`git fetch` + `git merge --ff-only`, abortando se não conseguirem avançar de forma linear) antes de invocar `claude -p` — sem isto, um checkout local desactualizado nega ferramentas recém-autorizadas em `.claude/settings.json` e faz o commit de publicação divergir do `origin/main`.

**Duas cópias de cada script, propositadamente:** a cópia **versionada** (a fonte de verdade, com diff/histórico) vive neste repo em `scripts/agenda_rotinas/` (`X_briefing_pre.py`, `X_hff_pos.py`, `briefing_render/X_briefing_pos.py`, `briefing_render/postflight_briefing.py`, `briefing_render/render_v5.py`/`render_v6.py`, `painel_hff/preflight_hff.py`, `painel_hff/postflight_hff.py`); a cópia **de execução**, que é a que o Agendador de Tarefas e os `.bat` acima realmente correm, vive no Drive em `G:\My Drive\Claude_PRJ\Agenda\X_Rotinas_Python\` (mesmo motivo que `scripts/gmail_articles_briefing/` — o Drive não edita in-place). Regra: **editar sempre aqui primeiro, testar, só depois copiar para o Drive** (substituindo a cópia lá; ver `scripts/agenda_rotinas/README.md`).

## Estrutura publicada neste repo

```
agendas/
  index.html          ← Dashboard (Módulo 5, raiz)
  briefing/index.html ← Briefing Diário (Módulo 1)
  Hff/index.html       ← Painel HFF pessoal (Módulo 4)
  BO/index.html         ← Lista cirúrgica da equipa (Módulo 4, face pública)
  lazer/index.html     ← Agenda de Lazer (Módulo 2)
  noticiasB3/          ← gerado por outro projecto, só verificado aqui
  artigos/index.html   ← Artigos Científicos (trigger próprio, ver nota abaixo)
  personal-development/testme/index.html ← TestMe, prep. Assist. Graduado (trigger próprio, skill `testme`)
  notificacoes/index.html ← Triagem de Notificações WhatsApp (trigger próprio, skill `notificacoes`)
  agendas/notificacoes/index.html ← espelho do mesmo HTML, exigido pelo destination_dir do Cloudflare Pages
```
Nomes de pastas em maiúscula/minúscula têm de respeitar exactamente o que está acima (`Hff`, `BO` maiúsculas; `briefing`, `lazer` minúsculas) — o Cloudflare serve tudo case-insensitive, mas o GitHub não, e uma caixa errada cria pasta duplicada.

## Módulo Artigos Científicos

Mesmo padrão de accionamento dos outros módulos (frase-gatilho na skill `artigos`, ou o Dashboard aciona a rotina directamente dentro do seu próprio ciclo, tal como já faz com a Notícias do Dia): o Dashboard, na sua orquestração de frescura, verifica se `agendas/artigos/index.html` foi publicado há mais de 7 dias — se sim, acciona a rotina Artigos nesse mesmo ciclo (sem perguntar ao Rafa, tal como as outras regras de janela expirada); se não, não faz nada. A extração de e-mails/PDF é feita por um script Python fora do LLM (`scripts/gmail_articles_briefing/` neste repo, com cópia de execução em Drive — ver `INSTRUCOES_ARTIGOS` secção 4, versão mais recente). Detalhe completo da rotina: skill `artigos`.
