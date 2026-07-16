---
name: dashboard
description: Use quando o Rafa pedir "dashboard", "gera o dashboard", "atualiza o dashboard", "home", "hub" ou "página inicial da agenda". Gera a página raiz do sistema Agenda, orquestrando a frescura dos outros módulos (Briefing, Painel HFF, Agenda de Lazer, Notícias/B3) antes de publicar.
---

# Dashboard (Módulo 5 — Hub leve + Orquestrador)

## Passos

1. **Ler `CLAUDE.md`** na raiz deste repo, se ainda não estiver em contexto nesta sessão.
2. **Ler `SYSTEM_PROMPT_v6.1_FINAL.md`** — pasta Drive `15Ge84lmsAeoUgSXDWFpcW26X-UCixrbg` (procurar pelo nome; se houver mais do que uma cópia, usar a de `createdTime` mais recente). Obrigatório mesmo que pareça redundante — dá o contexto de arquitectura, Rotina de Publicação e Leitura de Calendário partilhadas que este documento por si só não repete.
3. Na mesma pasta Drive, procurar **`INSTRUCOES_DASHBOARD_v10.0.md`** pelo nome exacto (usar a cópia mais recente por `createdTime` se houver duplicados). Descarregar e seguir a rotina na íntegra — não resumir nem saltar etapas.
4. Seguir a rotina tal como descrita lá. Não inventar passos nem assumir que sabes o processo de cor — o documento é a fonte de verdade, este skill é só o ponteiro para ele.

## Notas específicas a ter em atenção (não substituem o documento — só orientação)

- O Dashboard **orquestra a frescura** dos outros módulos antes de renderizar (falhas de um módulo NUNCA bloqueiam o render dos restantes): Briefing (M1), Painel HFF (M4 — gera sempre `hff` + `bo` juntos), Agenda de Lazer (M2 — só regenerar se a última publicação em `Relatorios/Agenda` tiver mais de 2 dias), Notícias do Dia/B3 (verificar `Relatorios/AII`, nunca usar ficheiro de dia anterior).
- Aplica sempre o doc partilhado **Leitura de Calendário**: uma única leitura de calendário e uma única leitura da label Gmail `events` (janela 15 dias) por ciclo — os módulos accionados reutilizam esse resultado, não repetem a leitura.
- **Modo C do Briefing:** se o Rafa pedir "dashboard para amanhã" (explícito) ou pedir dashboard depois das 16h00 sem especificar o dia (implícito — confirmar antes de avançar), o Dashboard tem de reencaminhar essa ordem para o sub-passo do Briefing (M1), correndo-o em Modo C. O próprio Dashboard **nunca** gera versões de amanhã de Lazer, Notícias ou Curso — isso fica sempre ancorado a hoje. ⚠️ Verificar se `INSTRUCOES_DASHBOARD_v10.0.md` já reflecte esta regra explicitamente; se não, aplicar mesmo assim (é uma correcção confirmada pelo Rafa, pendente de colar no documento).
- O Dashboard nunca escreve o HTML inteiro nem faz push directo — produz apenas o JSON canónico e entrega à Rotina de Publicação (`módulo = dashboard`), que trata do render (`render.py` + `template.html` na pasta Drive `Templates/dashboard/`), commit/push para `agendas/index.html` neste repo, e cópia em `Relatorios/Agenda/dashboard_<data>.html`.
- Confirmar ao Rafa no fim com 1-2 frases + link (`https://personal-system-hs5.pages.dev/agendas/`) — sem bloco de código extenso na resposta.
