---
name: pos-viagem
description: Executa o módulo de Feedback Pós-Viagem do projeto Viagens (Travel OS) — questionário pós-viagem, actualização do travel_log.md, ficheiro de feedback individual e sugestão para o SSoT. Use quando o Rafa disser "acabei de chegar de...", "feedback da viagem", "fechar viagem", "pós-viagem" ou equivalente.
---

# Skill: Feedback Pós-Viagem (Viagens)

Este skill é um PONTEIRO — nunca contém a rotina em si, só a instrução de a ir buscar. A rotina muda de versão; executar uma cópia guardada aqui seria executar regras desatualizadas.

## Passos

1. Se [`viagens/CLAUDE.md`](../../../viagens/CLAUDE.md) deste repositório ainda não estiver em contexto, lê-lo primeiro (tem os IDs das pastas/ficheiros do Drive e o contexto geral do projecto Viagens).
2. Ler `System_prompt_Viagens.md.md` (Drive ID `1ZAThYJFFGNT5BIDa4lUohR1ZeabJyhhO`) — obrigatório mesmo que a rotina diga que não é preciso numa "activação directa".
3. Procurar no Drive, pasta Viagens (ID `1yO5iz4mAc9CHkz5JOZ9kGSTnFTeJLkTd`), o ficheiro `INSTRUCOES_POS_VIAGEM.md` (se houver mais do que uma cópia, usar a de `createdTime` mais recente). Ler na íntegra e seguir o fluxo completo, incluindo:
   - Verificar se há travel log exportado disponível no chat (ou partilhado pelo Rafa a partir da app "Travel Log" publicada em `trips/<Destino>/feedback/` — ver `viagens/CLAUDE.md`).
   - Carregar `questionario_pos_viagem.jsx` (Drive ID `15dFQf2aBG_3EBjcFyFyuTKunZhQytT-7`) como artifact.
   - Consolidar respostas + travel log + ficheiros anexados.
4. Criar nova versão de `travel_log.md` (parentId `1yO5iz4mAc9CHkz5JOZ9kGSTnFTeJLkTd`, ID actual `1VTiQjl4phrCMpjKktoV-wRa9o4jl6D9_`; se já existir, criar `travel_log_vN.md` e avisar o Rafa para apagar a versão anterior). **Atenção ao formato de âncoras Obsidian** descrito no documento — usar headings directamente, nunca `<a id="...">`.
5. Criar o ficheiro de feedback individual (parentId `1bOvFZXETazARg1eXIU82HtkYIUrBWyFd`, pasta Trips Passadas, nome `trip_[destino]_[YYYY-MM]_feedback.md`).
6. Apresentar no chat a sugestão para o `feedback_log.md` do SSoT (formato descrito no documento) e aguardar aprovação explícita do Rafa antes de ele copiar manualmente — o ficheiro (ID `1Dkc3C4fsaJc0tRfnQkTCIQdFCLga3He4`) está inacessível ao Claude. Padrões com 4+ ocorrências → sugerir também promoção ao `rafa_profile.md`.
