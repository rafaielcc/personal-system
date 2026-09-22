---
name: dashboard
description: Use quando o Rafa pedir "dashboard", "gera o dashboard", "atualiza o dashboard", "home", "hub" ou "página inicial da agenda". Gera a página raiz do sistema Agenda — hub leve de ícones + badges + tempo — orquestrando a frescura de Briefing/HFF e, via pré-filtro Python, de TestMe/CIRPED/Artigos antes de publicar (Agenda de Lazer/Notícias do Dia/Notificações são sempre atalhos estáticos, nunca orquestrados).
---

# Dashboard (Módulo 5 — Hub leve de atalhos)

## Passos

1. **Ler `agendas/CLAUDE.md`** (não o `CLAUDE.md` da raiz do repo — esse é de outro projecto, o AII), se ainda não estiver em contexto nesta sessão.
2. **Ler `SYSTEM_PROMPT_FINAL.md`** — pasta Drive `15Ge84lmsAeoUgSXDWFpcW26X-UCixrbg` (procurar pelo nome; se houver mais do que uma cópia, usar a de `createdTime` mais recente). Obrigatório mesmo que pareça redundante — dá o contexto de arquitectura, Rotina de Publicação e Leitura de Calendário partilhadas que este documento por si só não repete.
3. Na mesma pasta Drive, procurar por título a começar por **`INSTRUCOES_DASHBOARD`** (última confirmada: `v12.0` — redesign de Set 2026, hub passou a ser só ícones/badges/tempo; usar sempre a cópia mais recente por `createdTime`, não assumir que o número mais alto no título é o mais recente). Descarregar e seguir a rotina na íntegra — não resumir nem saltar etapas.
4. **Em ambiente local** (workspace `G:\My Drive\Claude_PRJ\Agenda` + Python), o Dashboard já tem caminho automatizado próprio: correr `X_dashboard_pre.py` antes de qualquer outra coisa — produz contagens/tempo do hub e o pré-filtro `needs_action` de Artigos/CIRPED/TestMe (ver Secção 4 do documento de instruções). Em ambiente cloud, seguir os mecanismos individuais descritos em cada alínea da Secção 4 (mais caros em tokens, mesmo resultado funcional).
5. Seguir a rotina tal como descrita lá. Não inventar passos nem assumir que sabes o processo de cor — o documento é a fonte de verdade, este skill é só o ponteiro para ele.

## Notas específicas a ter em atenção (não substituem o documento — só orientação)

- O hub é **apenas ícones + badges + tempo** — não há banner de nota do dia, prioridades nem resumo B3 desde a v12.0 (removidos a pedido do Rafa). Não os reintroduzir sem pedido explícito.
- O Dashboard **orquestra** Briefing (M1, com HFF/BO M4 em cascata quando Modo A) e, via pré-filtro, TestMe/CIRPED/Artigos — falhas nestes módulos NUNCA bloqueiam o render dos restantes. **Não orquestra** Agenda de Lazer, Notícias do Dia nem Notificações — os respectivos ícones são sempre atalhos estáticos, publicados ou não, nunca disparam a rotina.
- Aplica sempre o doc partilhado **Leitura de Calendário** apenas em ambiente cloud (ver Secção 3 do documento de instruções) — em ambiente local, contagens vêm de `X_dashboard_pre.py`, que reaproveita o `_briefing.json` já produzido pela corrida separada de `X_briefing_pre.py`, sem repetir a leitura.
- **Modo C do Briefing:** o passo 4a do `SYSTEM_PROMPT_FINAL.md` (lido no passo 2 acima) já cobre a regra de detecção/reencaminhamento — não repetida aqui para não ficar desactualizada; seguir o que lá estiver escrito.
- O Dashboard nunca escreve o HTML inteiro nem faz push directo — produz apenas o JSON canónico (schema reduzido desde a v12.0: `meta`/`counts`/`weather`, sem `banner`/`priorities`/`b3`) e entrega à Rotina de Publicação (`módulo = dashboard`). Os caminhos exactos de template/render/GitHub vivem em `ROTINA_PUBLICACAO.md` (mesma pasta Drive das instruções, sem sufixo de versão no nome) e podem mudar — ir sempre lá, não assumir os valores actuais.
- Confirmar ao Rafa no fim com 1-2 frases + link (`https://personal-system-hs5.pages.dev/`) — sem bloco de código extenso na resposta.
