---
name: analise-carteira
description: Executa a rotina "Análise de Carteira" do projeto AII (avalia a carteira atual, decide manter/acumular/reduzir/vender por posição, prioridades de movimentação). Use quando o Rafa pedir "análise de carteira", "analisar carteira", "revisar carteira" ou variantes, no contexto do projeto AII/carteira de investimentos.
---

# Skill: Análise de Carteira (AII)

Este skill é um PONTEIRO — nunca contém a rotina em si, só a instrução de a ir buscar. A rotina muda de versão; executar uma cópia guardada aqui seria executar regras desatualizadas.

## Passos

1. Se `CLAUDE.md` deste repositório ainda não estiver em contexto, lê-lo primeiro (tem os IDs das pastas do Drive e a convenção do projeto AII).
2. Procurar no Google Drive, na pasta de instruções (ID `1ivd9atfgH5Xmf0wP6Q0BMcZoDByTpqLI`), o ficheiro com título `AII_Z_Analise_Carteira.md`. Pode haver mais do que um resultado (cópias antigas) — usar sempre o de `createdTime` mais recente.
3. Descarregar e ler o ficheiro por completo. Seguir as instruções na íntegra, sem resumir nem pular etapas.
4. Ler também `AII_Z_SYSTEM_PROMPT_REVISTO.md` (mesma pasta) para o perfil do investidor e o contexto geral do projeto — ver nota em `CLAUDE.md` sobre isto ser sempre necessário no Code.
5. A fonte de cotações é sempre a coluna "Atual" da planilha Espelho Radar (ID `1g7JBnpEkaYZQl2SBGYmooZhOBYqOa0ER2o3F1yPkSnA`) — nunca verificação web multi-fonte (eliminada do projeto).
6. Gravar o relatório `AII_0_Analise_Carteira_[DDmesANO].md` na pasta de relatórios (ID `19IlmZ5GwFj6iF2OBbMmIvyuDA33s8u04`), exatamente como a rotina descrever.
