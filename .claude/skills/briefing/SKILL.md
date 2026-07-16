---
name: briefing
description: Use quando o Rafa pedir "bom dia", "good morning", "briefing", "faz o briefing", "gera o briefing", "dá-me o briefing" ou "briefing para amanhã". Gera o briefing diário pessoal (tarefas, calendário, email, tempo, e opcionalmente o Painel HFF) em Modo A (completo), B (sem HFF) ou C (dia seguinte).
---

# Briefing Diário (Módulo 1)

## Passos

1. **Ler `agendas/CLAUDE.md`** (não o `CLAUDE.md` da raiz do repo — esse é de outro projecto, o AII), se ainda não estiver em contexto nesta sessão.
2. **Ler `SYSTEM_PROMPT_v6.1_FINAL.md`** — pasta Drive `15Ge84lmsAeoUgSXDWFpcW26X-UCixrbg` (procurar pelo nome; usar a cópia de `createdTime` mais recente se houver duplicados). Obrigatório mesmo que a rotina abaixo pareça auto-suficiente.
3. Na mesma pasta Drive, procurar **`BRIEFING_DIARIO`** pelo nome (título actual esperado: `BRIEFING_DIARIO_v12.1.md`) — se houver mais do que uma versão, usar sempre a de `createdTime` mais recente, não assumir que o número de versão no nome é o mais alto (o Rafa por vezes demora a apagar a versão anterior). Descarregar e seguir a rotina na íntegra — não resumir nem saltar etapas.

## Notas específicas a ter em atenção (não substituem o documento — só orientação)

- **Passo Zero é sempre o primeiro passo, inalterável:** confirmar a data/hora reais antes de qualquer outra coisa. Nunca assumir a data pela conversa.
- **Três modos:** A (completo, 7 tabs incl. Painel HFF, por omissão antes das 16h00) · B (sem HFF, 6 tabs, por omissão em fins-de-semana/feriados) · C (briefing do dia seguinte — explícito "briefing para amanhã", ou implícito se pedido depois das 16h00 sem dia especificado, caso em que é preciso perguntar ao Rafa antes de avançar).
- **O Briefing nunca lê a label Gmail `label:events`** (nem versão completa nem reduzida) — esse pool grande e arquivado é tratado em exclusivo pela Agenda de Lazer. A única relação com eventos é indirecta: emails com a tag `events` que continuam na Inbox (confirmações, listas de espera) aparecem naturalmente na leitura normal da Inbox.
- **O Briefing nunca dispara a Agenda de Lazer nem as Notícias/B3** — essa orquestração é exclusiva do Dashboard (Módulo 5).
- O Briefing nunca escreve o HTML inteiro nem faz push directo — produz apenas o JSON canónico (esquema na Secção 7 do documento de instruções) e entrega à Rotina de Publicação (`módulo = briefing`), que trata do render (`render.py` + `template.html` na pasta Drive `Templates/Briefing/`, incluindo `weather.py` para a tab Tempo), commit/push para `agendas/briefing/index.html` neste repo, e cópia em `Relatorios/Agenda/briefing_<data>.html`.
- O bloco `hff` do JSON (Modo A) é o mesmo produzido pelo módulo Painel HFF — não gerar dois JSONs separados; se o Rafa também quiser o Painel HFF/Lista BO publicados a sério nesse ciclo, correr o skill `agenda-de-trabalho` à parte.
