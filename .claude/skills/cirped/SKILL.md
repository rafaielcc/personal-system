---
name: cirped
description: Use quando o Rafa pedir "história cirped", "história da cirurgia", "charada cirped" ou variantes. Gera/actualiza o módulo CIRPED (História longa + Charada curta de cirurgia pediátrica e história da medicina) e republica a página, com biblioteca de itens guardados.
---

# CIRPED (História & Charadas de Cirurgia Pediátrica)

## Passos

1. **Ler `agendas/CLAUDE.md`** (não o `CLAUDE.md` da raiz do repo — esse é de outro projecto, o AII), se ainda não estiver em contexto nesta sessão.
2. **Ler `SYSTEM_PROMPT_v6.1_FINAL.md`** — pasta Drive `15Ge84lmsAeoUgSXDWFpcW26X-UCixrbg` (procurar pelo nome; usar a cópia de `createdTime` mais recente se houver duplicados). Obrigatório mesmo que o documento abaixo pareça auto-suficiente.
3. Na mesma pasta Drive, procurar **`INSTRUCOES_CIRPED.md`** pelo nome (ID conhecido `14VZ4cqJQsUhPP3lsBTZuc7vDLmy8jlBY`, mas confirmar sempre pelo nome/`createdTime` caso exista uma versão mais recente). Descarregar e seguir o contrato na íntegra — não resumir nem saltar secções.
4. Seguir a rotina tal como descrita lá. Não inventar passos nem assumir o processo de cor — o documento é a fonte de verdade, este skill é só o ponteiro para ele.

## Notas específicas a ter em atenção (não substituem o documento — só orientação)

- **Duas peças de conteúdo, avaliadas de forma independente**: História (texto longo, ~10 min de leitura, ângulo específico e estreito) e Charada (pergunta curta e factual). Um único gatilho ("história cirped") gera só a(s) trilha(s) sem `estado = pendente` — nunca gerar uma trilha que já tenha algo por decidir.
- **Nunca escrever de memória sem verificação** — pesquisar sempre para confirmar nomes, datas e valores clínicos/anatómicos. Texto sempre original, nunca copiado. Imagens só reais e de domínio público/licença livre (Wikimedia Commons), nunca geradas por IA.
- **Anti-repetição**: a coluna que impede repetir não é o tema amplo (pode repetir-se) — é o ângulo específico (Historias) / a pergunta exacta (Charadas). Ler sempre os valores já usados antes de escolher um novo.
- **Este módulo foi desenhado para o padrão híbrido local/cloud** (mesmo espírito do TestMe): local usa Python (`X_Rotinas_Python/cirped/preflight_cirped.py` + `postflight_cirped.py`, workspace `G:\My Drive\Claude_PRJ\Agenda`) para o trabalho mecânico; numa sessão sem esse workspace (como esta), seguir o fluxo equivalente via Drive/Sheets descrito em `INSTRUCOES_CIRPED.md` Secção 4.
- **A Sheet `Espelho_Cirped`** (ID `1svP-Vydd1oJ_gHxG5UnGS8MrhELvWIXeDqpgeJ4MJs4`, abas `Historias`/`Charadas`) é a fonte única de estado. Se as abas ainda não existirem, correr `create_espelho_cirped.py` uma vez antes de continuar (ver `INSTRUCOES_CIRPED.md` Secção 1).
- **Apps Script dos botões** (Lido/Guardar/Excluir/Desfazer): o URL do Web App implantado tem de ser confirmado sempre a partir de `INSTRUCOES_CIRPED.md` — nunca cachear entre sessões, o deploy é manual e o URL pode ter mudado.
- Pedido manual com uma trilha ainda pendente por decidir: avisar primeiro, só gerar de novo (perdendo a pendente) com confirmação explícita do Rafa.
- Publica em `agendas/cirped/index.html` + espelho `agendas/agendas/cirped/index.html` (exigência do `destination_dir=agendas` do Cloudflare Pages).
- Confirmar ao Rafa no fim com 1-2 frases + link (`https://personal-system-hs5.pages.dev/cirped/`) — sem bloco de código extenso na resposta.
