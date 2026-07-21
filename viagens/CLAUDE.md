# Projeto Viagens (Travel OS) — contexto para o Claude Code

Este repositório (`rafaielcc/personal-system`) também serve de espaço de execução para o projeto pessoal de viagens do Rafa ("Travel OS"). Tal como o AII ([`CLAUDE.md`](../CLAUDE.md) na raiz) e a Agenda ([`agendas/CLAUDE.md`](../agendas/CLAUDE.md)), **as instruções das rotinas não vivem aqui** — vivem no Google Drive e são lidas em tempo de execução, nunca copiadas para o repo, para não haver duas fontes de verdade desincronizadas. Este ficheiro só dá o contexto que uma sessão de Code precisa para executar essas rotinas correctamente, sem o Rafa ter de reexplicar o projecto a cada nova conversa.

O Travel OS corre normalmente como projecto em claude.ai, com o perfil e as regras gerais embutidos no system prompt do projecto ("Ativação directa"). Uma sessão de Claude Code **não tem esse contexto por omissão** — ver a secção "Regra importante" abaixo.

## Pasta Drive do projecto (IDs fixos)

- **Pasta Viagens** (todos os ficheiros de instrução do projecto, direto na raiz, sem subpastas): `1yO5iz4mAc9CHkz5JOZ9kGSTnFTeJLkTd`
- **Pasta Trips Passadas** (feedback individual de cada viagem já fechada): `1bOvFZXETazARg1eXIU82HtkYIUrBWyFd`
- **Pasta SSoT partilhado entre projectos** (perfil do Rafa e histórico de feedback, partilhados com o AII e a Agenda): `1KAVv-gCiCGGlZNvxgVLvx3SuKRRZ-hzC`
  - `rafa_profile.md` — ID `1EKv0dfaB_N-WZC1yMJpJkP6GckjCgDXb`. Alterações requerem aprovação explícita do Rafa antes de escrever.
  - `feedback_log.md` — ID `1Dkc3C4fsaJc0tRfnQkTCIQdFCLga3He4`. ⚠️ **Inacessível ao Claude** — apresentar sempre a sugestão no chat e aguardar o Rafa copiar manualmente.
- **`travel_log.md`** (registo cronológico de todas as viagens, lido no Obsidian) — ID `1VTiQjl4phrCMpjKktoV-wRa9o4jl6D9_`, na pasta Viagens.

Há também uma pasta `.obsidian` na pasta Viagens (metadata do vault do Obsidian) — ignorar, não é conteúdo do projecto.

## Convenção de nomes e versões

- Os documentos de instrução (`INSTRUCOES_*.md`) e o system prompt vivem directamente na raiz da pasta Viagens, sem sufixo de versão no nome actualmente.
- O Drive não edita ficheiros in-place — uma actualização pode gerar uma cópia nova com o mesmo título. **Se uma busca devolver mais do que um resultado com o mesmo título, usar sempre o de `createdTime` mais recente.**
- Ficheiros de viagem individual seguem o padrão `trip_[destino]_[YYYY-MM].md` / `.html`; iterações da mesma viagem podem gerar sufixo `_v2`, `_v3`, etc. (o Drive não substitui o ficheiro anterior).
- Ficheiros de feedback pós-viagem (pasta Trips Passadas): `trip_[destino]_[YYYY-MM]_feedback.md`.
- **Viagem em preparação (onboarding incremental, jul/2026):** cada viagem ainda por fechar tem uma subpasta própria dentro da pasta Viagens, `[Destino]_[YYYY-MM]` (mesma chave destino+mês/ano que o Rafa usa para identificar as viagens). Dentro dela: `trip_[destino]_[YYYY-MM]_dados.md` (ficheiro-mãe com as respostas acumuladas do Questionário Pré-Viagem, que agora aceita preenchimento parcial/retomável) e `trip_[destino]_[YYYY-MM]_itinerario_preliminar.md` (rascunho leve, gerado a pedido, para discutir com o Rafa antes de fechar a viagem). Os ficheiros finais `.md`/`.html` só nascem quando a viagem é confirmada como fechada — ver `System_prompt_Viagens.md.md`, Trigger 2 e Trigger 2b.

## Regra importante: ler o system prompt do projecto primeiro

As rotinas foram escritas para um projecto do claude.ai onde o perfil e o contexto geral já vêm embutidos no system prompt do projecto. **Uma sessão de Claude Code não tem esse contexto** — por isso, ao executar QUALQUER rotina Viagens a partir daqui, ler sempre primeiro:

> **`System_prompt_Viagens.md.md`** — pasta Viagens, ID `1ZAThYJFFGNT5BIDa4lUohR1ZeabJyhhO`.

(Sim, o título do ficheiro tem `.md.md` — é o nome real no Drive, não um erro de transcrição.)

Isto aplica-se mesmo quando o documento da própria rotina disser que isso "não é preciso" numa activação directa — essa instrução assume uma conversa em claude.ai já com o system prompt carregado, o que nunca é verdade numa sessão nova do Code. Para tudo o resto (apresentar resultados no chat, gerar ficheiros, publicar no GitHub), seguir a activação directa normalmente.

## Rotinas disponíveis (skills)

| Comando | Rotina | Documento de instrução no Drive |
|---|---|---|
| `/sugestao-destinos` | Consultor de destinos — sugere destinos personalizados a partir do perfil + questionário | `INSTRUCOES_SUGESTAO_DESTINOS.md` |
| `/planear-viagem` | Onboarding de viagem — questionário pré-viagem incremental/retomável (Trigger 2), itinerário preliminar a pedido (Trigger 2b) + geração do guia HTML final quando o Rafa fechar a viagem | `INSTRUCOES_HTML_VIAGEM.md` (não há um `INSTRUCOES_PRE_VIAGEM.md` separado — a lógica do questionário pré-viagem está descrita no próprio `System_prompt_Viagens.md.md`, Triggers 2 e 2b) |
| `/pos-viagem` | Feedback pós-viagem — questionário, actualização do `travel_log.md`, ficheiro de feedback individual | `INSTRUCOES_POS_VIAGEM.md` |

Outras acções mencionadas no system prompt ("continuar viagem em curso", "ver viagens passadas") são simples leituras de ficheiro existente — não têm rotina/skill própria, basta localizar e ler o ficheiro certo na pasta Viagens ou Trips Passadas.

## Ficheiros de interface e dados (Project knowledge)

| Ficheiro | Google Drive ID | Descrição |
|---|---|---|
| `questionario_destinos.json` / `.jsx` | `1IjfcrLg9ebUoCFNjc9VqrdbwOlFD4y03` / `1WnLnFfArHIbLIC_D2eG2pkEEouftgZHR` | Perguntas + interface do questionário de sugestão de destinos |
| `questionario_pre_viagem.jsx` | `1SaMtH3IneRstUcr8vcc_bO124L7XgSEB` | Interface do questionário pré-viagem (usado no `/planear-viagem`) |
| `questionario_pos_viagem.json` / `.jsx` | `1hWxb_Lk5iOZX7X6zafaZuedmW6-3l2xe` / `15dFQf2aBG_3EBjcFyFyuTKunZhQytT-7` | Perguntas + interface do questionário pós-viagem |

## Publicação no GitHub — `trips/<Destino>/` (prática actual, não documentada nos ficheiros do Drive)

Além dos ficheiros criados no Google Drive, o guia de cada viagem e a app de Travel Log já são publicados neste repo, na raiz (pasta `trips/`, ao lado de `agendas/` e `AII/`) — confirmado pelo Rafa como o fluxo real, mesmo os documentos do Drive não mencionando isto:

```
trips/
  <Destino>/
    index.html          ← guia da viagem (mesmo conteúdo gerado seguindo INSTRUCOES_HTML_VIAGEM.md)
    feedback/index.html ← app "Travel Log" (genérica, grava localmente via localStorage no telemóvel — sem dados do destino embutidos)
```

Exemplo já publicado: `trips/Aljezur/`. Note-se que `trips/Aljezur/trip_aljezur_2026-06.html` é uma cópia de backup pontual (upload manual) — não é uma convenção a repetir; para novas viagens, o par a publicar é só `index.html` + `feedback/index.html`.

Nome da pasta = nome do destino, capitalizado (ex: `Aljezur`, não `aljezur`) — o GitHub é case-sensitive, ao contrário do Cloudflare/hosting que possa servir o conteúdo.

Publicar aqui (commit/push) é uma acção visível no repo partilhado — confirmar com o Rafa antes de dar push, tal como para qualquer outro módulo.
