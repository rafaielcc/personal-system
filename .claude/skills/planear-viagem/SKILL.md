---
name: planear-viagem
description: Executa a criação/planeamento de uma nova viagem no projeto Viagens (Travel OS) — questionário pré-viagem, pesquisa web extensiva e geração do ficheiro .md + guia HTML da viagem. Use quando o Rafa já tiver destino definido e pedir para planear uma viagem, disser "planear nova viagem", "criar viagem para X", "trip a X" com datas, ou equivalente.
---

# Skill: Planear Viagem (Viagens)

Este skill é um PONTEIRO — nunca contém a rotina em si, só a instrução de a ir buscar. A rotina muda de versão; executar uma cópia guardada aqui seria executar regras desatualizadas.

## Passos

1. Se [`viagens/CLAUDE.md`](../../../viagens/CLAUDE.md) deste repositório ainda não estiver em contexto, lê-lo primeiro (tem os IDs das pastas/ficheiros do Drive, a convenção de nomes e a nota sobre publicação em `trips/`).
2. Ler `System_prompt_Viagens.md.md` (Drive ID `1ZAThYJFFGNT5BIDa4lUohR1ZeabJyhhO`) — obrigatório mesmo que pareça redundante; tem a lógica do questionário pré-viagem (Trigger 2) e a estrutura base do ficheiro `.md` de viagem, que não estão repetidas num documento de instruções separado.
3. Carregar `questionario_pre_viagem.jsx` (Drive ID `1SaMtH3IneRstUcr8vcc_bO124L7XgSEB`) como artifact e correr o questionário de forma conversacional. Não repetir perguntas cujas respostas já vieram do módulo de sugestão de destinos ou do perfil do Rafa.
4. Procurar no Drive, pasta Viagens (ID `1yO5iz4mAc9CHkz5JOZ9kGSTnFTeJLkTd`), o ficheiro `INSTRUCOES_HTML_VIAGEM.md` (se houver mais do que uma cópia, usar a de `createdTime` mais recente). Ler na íntegra e seguir a pesquisa web obrigatória (restaurantes, atrações, praias/natureza, nightlife, logística local, alojamento, contexto local) antes de escrever o guia — mínimo 8-10 restaurantes e 10-15 atrações com detalhes completos.
5. Criar o ficheiro `.md` da viagem (parentId `1yO5iz4mAc9CHkz5JOZ9kGSTnFTeJLkTd`, nome `trip_[destino]_[YYYY-MM].md`) e o guia `.html` seguindo a estrutura e as regras de design descritas em `INSTRUCOES_HTML_VIAGEM.md`. Nunca sobrescrever um ficheiro existente — criar nova versão (`_v2`, `_v3`, ...) e avisar o Rafa para apagar a anterior.
6. Perguntar ao Rafa se quer publicar também o guia neste repo, em `trips/<Destino>/index.html` (mesma pasta do destino, capitalizada — ver exemplo em `trips/Aljezur/`), com uma cópia da app genérica "Travel Log" em `trips/<Destino>/feedback/index.html`. Publicar (commit/push) só com confirmação explícita, por ser uma acção visível no repo partilhado.
