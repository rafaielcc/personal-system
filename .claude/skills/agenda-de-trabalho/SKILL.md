---
name: agenda-de-trabalho
description: Use quando o Rafa pedir "painel hff", "painel trabalho", "agenda hff", "work panel", "agenda de trabalho", "work agenda", "o que tenho no hospital", "cirurgias hoje", "resumo hff", "lista cirúrgica", "lista bo" ou "lista para a equipa". Gera o painel operacional do Hospital Fernando Fonseca (cirurgias, Prevenção, SIGIC, ausências) — painel pessoal e/ou lista pública para a equipa do bloco.
---

# Painel HFF / Agenda de Trabalho (Módulo 4)

## Passos

1. **Ler `agendas/CLAUDE.md`** (não o `CLAUDE.md` da raiz do repo — esse é de outro projecto, o AII), se ainda não estiver em contexto nesta sessão.
2. **Ler `SYSTEM_PROMPT_v6.1_FINAL.md`** — pasta Drive `15Ge84lmsAeoUgSXDWFpcW26X-UCixrbg` (procurar pelo nome; usar a cópia de `createdTime` mais recente se houver duplicados). Obrigatório mesmo que a rotina abaixo pareça auto-suficiente.
3. Na mesma pasta Drive, procurar **`INSTRUCOES_PAINEL_HFF`** pelo nome (título actual esperado: `INSTRUCOES_PAINEL_HFF_v5.0.md`) — se houver mais do que uma cópia, usar sempre a de `createdTime` mais recente. Descarregar e seguir a rotina na íntegra — não resumir nem saltar etapas.

## Notas específicas a ter em atenção (não substituem o documento — só orientação)

- Este módulo gera **DOIS outputs a partir do MESMO JSON canónico** (esquema na Secção 11 do documento de instruções — não gerar dois JSONs separados):
  - **Painel pessoal** (`módulo = hff`) — 5 tabs: Resumo, Cirurgias, Prevenção, SIGIC, Equipa. Contém tarefas HFF e é só para o Rafa.
  - **Lista cirúrgica da equipa** (`módulo = bo`) — face pública, partilhada com a equipa do bloco operatório. **Nunca mostra** Prevenção, tarefas pessoais nem calendário pessoal. Motivo de ausência só aparece se for "Férias"; caso contrário mostra "Ausente" genérico.
- **Trigger A** ("painel hff", "agenda de trabalho", etc.) gera sempre os dois outputs juntos. **Trigger C** ("lista cirúrgica", "lista bo") regenera **apenas** o output `bo`.
- **Guarda crítica de dias:** BO (Bloco Operatório) só à Segunda e Quarta — nunca Terça/Quinta/Sexta. SIGIC geralmente à Segunda (confirmar sempre no calendário). Prevenção normalmente a semana inteira, mas há excepções — confirmar na escala e no calendário Google. Mostrar sempre dados da data actual (janela de 15 dias), nunca cirurgias de dias passados.
- Fonte de dados única: **Espelho HFF** (Google Sheet, ID `1culq10MksUxSd05P1_ejqOEzaoQrFLKT-vP0brqp7iU`, 4 abas: Cirurgias · SIGIC · Prevenção · Ausências) — as planilhas-mãe já não são lidas directamente por este módulo.
- Ausências codificadas por texto: maiúscula = motivo (F/C/M), minúsculas = iniciais dos cirurgiões (rc/rr/if) — ex: `Mif`. A aba Ausências é autoritativa; a flag "Previsão ausente" TRUE conta como "provável ausente" mesmo sem confirmação.
- Este módulo nunca escreve o HTML inteiro nem faz push directo — produz o JSON canónico e entrega à Rotina de Publicação (`módulo = hff` e/ou `módulo = bo`), que trata do render (`render.py` + `template.html` nas pastas Drive `Templates/hff/` e `Templates/bo/` — cada output tem o seu próprio template mas partilham o mesmo JSON de entrada), commit/push para `agendas/Hff/index.html` e `agendas/BO/index.html` neste repo, e cópia em `Relatorios/Agenda/hff_<data>.html` / `bo_<data>.html`.
