---
name: noticias-do-dia
description: Executa a rotina "Notícias do Dia" do projeto AII (briefing diário de notícias, painel de mercado, gatilhos, portfolio). Use quando o Rafa pedir "notícias do dia", "notícias", "briefing diário", "resumo do dia" ou variantes, no contexto do projeto AII/carteira de investimentos.
---

# Skill: Notícias do Dia (AII)

Este skill é um PONTEIRO — nunca contém a rotina em si, só a instrução de a ir buscar. A rotina é editada com frequência (já vai na v5.9); executar uma cópia guardada aqui seria executar regras desatualizadas.

## Passos

1. Se `CLAUDE.md` deste repositório ainda não estiver em contexto, lê-lo primeiro (tem os IDs das pastas do Drive e a convenção do projeto AII).
2. Procurar no Google Drive, na pasta de instruções (ID `1ivd9atfgH5Xmf0wP6Q0BMcZoDByTpqLI`), o ficheiro com título `AII_Z_Noticias_do_dia.md`. Pode haver mais do que um resultado (cópias antigas, o Drive não edita in-place) — usar sempre o de `createdTime` mais recente.
3. Descarregar e ler o ficheiro por completo. Seguir as instruções na íntegra, sem resumir nem pular etapas (Etapa 0 a Etapa 4, incluindo a checklist de fecho bloqueante da Etapa 4.0 e a tabela de custo de processamento no fim).
4. Ler também `AII_Z_Orientacoes_Gerais.md` (mesma pasta) para o perfil do investidor — ver nota em `CLAUDE.md` sobre isto ser sempre necessário no Code, mesmo quando a rotina diz que a "ativação direta" dispensa este passo.
5. Modalidade por defeito: FULL com fontes + página HTML, salvo se o Rafa pedir explicitamente "short", "sem fontes" ou "sem html"/"sem página"/"só markdown" — seguir exatamente a lógica de ativação descrita na secção ACTIVACAO da própria rotina.
6. Publicar sempre no GitHub quando a rotina o pedir (Etapa 4B) — isto já falhou várias vezes em sessões de claude.ai Project; no Code não há motivo para pular este passo.
