---
name: artigos
description: Use quando o Rafa pedir "artigos científicos", "gera os artigos", "triagem de artigos", "/artigos" ou variantes — ou quando disparado pelo Dashboard por a última publicação ter mais de 7 dias. Gera a página de triagem semanal de artigos científicos recebidos por e-mail (tag Gmail "Paediatric Surgery/Artigos para ler").
---

# Artigos Científicos

## Passos

1. **Ler `agendas/CLAUDE.md`** (não o `CLAUDE.md` da raiz do repo — esse é de outro projecto, o AII), se ainda não estiver em contexto nesta sessão.
2. **Ler o `SYSTEM_PROMPT` mais recente do projecto Agenda** — pasta Drive `15Ge84lmsAeoUgSXDWFpcW26X-UCixrbg` (procurar por `SYSTEM_PROMPT`, usar a cópia de `createdTime` mais recente).
3. Na mesma pasta Drive, procurar **`INSTRUCOES_ARTIGOS`** pelo nome (usar a cópia mais recente por `createdTime` se houver duplicados — a v1.0 está lá). Descarregar e seguir a rotina na íntegra — não resumir nem saltar etapas.
4. Seguir a rotina tal como descrita lá. Não inventar passos — o documento é a fonte de verdade, este skill é só o ponteiro para ele.

## Notas específicas a ter em atenção (não substituem o documento — só orientação)

- A extração de e-mails/PDF **já foi feita fora do LLM**, por um script Python local (`scripts/gmail_articles_briefing/` neste repo) que corre antes desta rotina — esta skill só lê o JSON já pronto na pasta Drive `Gmail_artigos`, sintetiza, e publica. Nunca tentar aceder ao Gmail diretamente nesta rotina.
- Usar sempre o ficheiro `Gmail_artigos_<data>.json` mais recente dessa pasta — nunca um de uma corrida anterior.
- A página é HTML estático: os botões "guardar"/"excluir"/"já lido" não tocam no Gmail na hora — isso só acontece na próxima corrida do script Python, depois de o Rafa exportar e largar o ficheiro de decisões. Não tentar "implementar" essa ligação em tempo real.
- O Dashboard nunca escreve o HTML inteiro nem faz push directo — produz apenas o JSON canónico e entrega à Rotina de Publicação. Os caminhos exactos de template/render/GitHub vivem em `ROTINA_PUBLICACAO` (mesma pasta Drive das instruções) e podem mudar — ir sempre lá, não assumir os valores actuais.
- Confirmar ao Rafa no fim com 1-2 frases + link (`https://personal-system-hs5.pages.dev/agendas/artigos/`) — sem bloco de código extenso na resposta.
