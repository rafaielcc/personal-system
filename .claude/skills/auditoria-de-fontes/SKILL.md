---
name: auditoria-de-fontes
description: Executa a rotina "Auditoria de Fontes" do projeto AII (agrega e apresenta a relevância histórica de cada fonte de notícias — Email, Telegram, Web Search — alimentada pela rotina Notícias do Dia). Use quando o Rafa pedir "auditoria de fontes", "qualidade das fontes" ou variante equivalente, no contexto do projeto AII/carteira de investimentos.
---

# Skill: Auditoria de Fontes (AII)

Este skill é um PONTEIRO — nunca contém a rotina em si, só a instrução de a ir buscar. A rotina é editada com frequência; executar uma cópia guardada aqui seria executar regras desatualizadas.

Esta rotina é distinta da Notícias do Dia (skill `noticias-do-dia`): não faz pesquisa nova, não gera relatório `AII_0_` diário — só lê e agrega dados já recolhidos pelas execuções da Notícias do Dia.

## Passos

1. Se `CLAUDE.md` deste repositório ainda não estiver em contexto, lê-lo primeiro (tem os IDs das pastas do Drive e a convenção do projeto AII).
2. Procurar no Google Drive, na pasta de instruções (ID `1ivd9atfgH5Xmf0wP6Q0BMcZoDByTpqLI`), o ficheiro com título `AII_Z_Auditoria_de_Fontes.md`. Pode haver mais do que um resultado (cópias antigas, o Drive não edita in-place) — usar sempre o de `createdTime` mais recente.
3. Descarregar e ler o ficheiro por completo. Seguir as instruções na íntegra: obter os dados agregados (caminho normal via `Log_fontes_integrado.json`, ou fallback ad hoc a partir dos fragmentos em `Log_fontes` quando o agregado estiver ausente ou desactualizado — nunca apagar fragmentos nesse caminho de fallback, isso é exclusivo do script Python `merge_log_fontes.py`), agregar por fonte, e apresentar a tabela de relevância + candidatos a poda.
4. Ler também `AII_Z_SYSTEM_PROMPT_REVISTO.md` (mesma pasta) para o perfil do investidor e o contexto geral do projeto — ver nota em `CLAUDE.md` sobre isto ser sempre necessário no Code.
5. Esta rotina nunca apaga nem desactiva nenhuma fonte automaticamente — é só leitura/recomendação; a decisão de poda é sempre do Rafa.
