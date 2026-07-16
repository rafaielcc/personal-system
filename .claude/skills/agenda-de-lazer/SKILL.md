---
name: agenda-de-lazer
description: Use quando o Rafa pedir "agenda da semana", "agenda de lazer", "agenda completa", "eventos próximos", "eventos em Lisboa", "o que há para fazer", "o que está a acontecer em Lisboa", "roteiro de fim de semana", "faz-me a agenda" ou pedidos equivalentes sobre descobrir/planear actividades e lazer nos próximos dias. Não usar para perguntas sobre o dia de hoje (isso é o briefing) — este módulo descobre e planeia, não acompanha o dia-a-dia.
---

# Agenda de Lazer (Módulo 2)

## Passos

1. **Ler `agendas/CLAUDE.md`** (não o `CLAUDE.md` da raiz do repo — esse é de outro projecto, o AII), se ainda não estiver em contexto nesta sessão.
2. **Ler `SYSTEM_PROMPT_v6.1_FINAL.md`** — pasta Drive `15Ge84lmsAeoUgSXDWFpcW26X-UCixrbg` (procurar pelo nome; usar a cópia de `createdTime` mais recente se houver duplicados). Obrigatório mesmo que a rotina abaixo pareça auto-suficiente.
3. Na mesma pasta Drive, procurar por título a começar por **`AGENDA_LAZER_INSTRUCOES`**. ⚠️ Este módulo está em auditoria/reestruturação activa — o Rafa está deliberadamente a manter o ficheiro sem sufixo de versão fixo no nome, apagando versões antigas conforme avança. **Não assumir um nome de ficheiro fixo com número de versão** (ex: não confiar cegamente em "v5.0" estar no título) — procurar por prefixo e usar sempre a cópia de `createdTime` mais recente entre os resultados. Se houver um ficheiro com "(conflict ...)" no título, ignorá-lo e usar o que não tem esse sufixo, a não ser que o Rafa diga o contrário nessa sessão. Descarregar e seguir a rotina na íntegra — não resumir nem saltar etapas.

## Notas específicas a ter em atenção (não substituem o documento — só orientação)

- Este módulo **descobre** eventos/actividades para os próximos 15 dias (concertos, exposições, restaurantes, desporto, escapadinhas); o Briefing (M1) só **acompanha** o que já foi descoberto. Dúvida entre os dois: pergunta operacional sobre hoje → Briefing; pergunta sobre descobrir/planear → este módulo.
- Arquitectura de expansão ("Expansion Architecture"): pipeline de expandir-antes-de-filtrar, com fallback em 3 níveis, JSON canónico como única camada de julgamento, e uma Debug View obrigatória. Consulta o `Feedback_log.json` (SSoT) na Filter Layer antes de decidir o que mostrar.
- **Esta é a única rotina do sistema Agenda que lê a label Gmail `label:events`** — janela de 15 dias (Luma/Meetup mantém 14). O Briefing nunca toca neste pool; é tratado em exclusivo aqui.
- Calendário via doc partilhado **Leitura de Calendário**; publicação via **Rotina de Publicação** (nunca push directo).
- Este módulo nunca escreve o HTML inteiro nem faz push directo — produz o JSON canónico (`events[]`) e entrega à Rotina de Publicação (`módulo = lazer`), que trata do render (`render.py` + `template.html` na pasta Drive `Templates/agenda_lazer/` — ⚠️ verificar se há uma versão mais recente do render fora dessa subpasta, directamente na raiz de `Templates/`, já que este módulo tem tido iterações rápidas; confirmar com o Rafa se tiveres dúvidas sobre qual usar), commit/push para `agendas/lazer/index.html` neste repo, e cópia em `Relatorios/Agenda/lazer_<data>.html` + markdown de apoio.
