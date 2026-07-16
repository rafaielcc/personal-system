---
name: organizar-setor
description: Executa a rotina "Organizar Setor" do projeto AII (reorganiza o ficheiro de análise fundamentalista de um setor, gera JSON companheiro). Use quando o Rafa pedir "organizar setor", "reorganizar [nome do setor]" ou variantes, no contexto do projeto AII/carteira de investimentos.
---

# Skill: Organizar Setor (AII)

Este skill é um PONTEIRO — nunca contém a rotina em si, só a instrução de a ir buscar. A rotina muda de versão; executar uma cópia guardada aqui seria executar regras desatualizadas.

## Passos

1. Se `CLAUDE.md` deste repositório ainda não estiver em contexto, lê-lo primeiro (tem os IDs das pastas do Drive e a convenção do projeto AII).
2. Procurar no Google Drive, na pasta de instruções (ID `1ivd9atfgH5Xmf0wP6Q0BMcZoDByTpqLI`), o ficheiro com título `AII_Z_Organizar_Setor.md`. Pode haver mais do que um resultado (cópias antigas) — usar sempre o de `createdTime` mais recente.
3. Descarregar e ler o ficheiro por completo. Seguir as instruções na íntegra.
4. Ler também `AII_Z_Orientacoes_Gerais.md` (mesma pasta) para o perfil do investidor — ver nota em `CLAUDE.md` sobre isto ser sempre necessário no Code.
5. São 10 setores no projeto (Agro, Bancos, Commodities, Logística e Infraestrutura, Indústria, Seguros, Telecom, Utilities, Varejo, Outros) — confirmar qual antes de agir, a menos que o Rafa já o tenha indicado ou anexado o ficheiro diretamente. A comparação de nome de ficheiro por setor é insensível a maiúsculas/minúsculas.
6. Conteúdo de decisão de carteira encontrado dentro do ficheiro setorial vai para uma secção final "Notas Fora de Escopo", nunca apagado nem misturado com a avaliação fundamental.
