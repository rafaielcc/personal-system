---
name: notificacoes
description: Use quando o Rafa pedir "$notificacoes", "notificacoes", "triagem de notificacoes", "espelho notificacoes", "resumo das notificacoes" ou variantes. Executa a triagem das notificações do WhatsApp capturadas via MacroDroid em `Espelho_Notificacoes`, resume por origem e republica a página estática — sem depender de créditos de API OpenAI.
---

# Rotina de Notificações

## Passos

1. **Ler `agendas/CLAUDE.md`** (não o `CLAUDE.md` da raiz do repo — esse é de outro projecto, o AII), se ainda não estiver em contexto nesta sessão.
2. **Ler `SYSTEM_PROMPT_v6.1_FINAL.md`** — pasta Drive `15Ge84lmsAeoUgSXDWFpcW26X-UCixrbg` (procurar pelo nome; usar a cópia de `createdTime` mais recente se houver duplicados). Obrigatório mesmo que o documento abaixo pareça auto-suficiente.
3. Na mesma pasta Drive, procurar **`instrucoes_notificacoes.md`** pelo nome exacto (sem sufixo de versão no título). Se houver mais do que uma cópia, usar sempre a de `createdTime` mais recente. Descarregar e seguir o contrato na íntegra — não resumir nem saltar secções.
4. Confirmar a data real em Lisboa antes de executar (Passo Zero do documento) — governa nomes de ficheiro, filtro de mensagens antigas e o texto `generated_at` da página.

## Notas específicas a ter em atenção (não substituem o documento — só orientação)

- **Rotina híbrida, tal como o TestMe:** em ambiente local/Codex, o `preflight_notificacoes.py` (`X_Rotinas_Python/Notificacoes/`, no `G:\My Drive\Claude_PRJ\Agenda\...` do Rafa) faz o trabalho mecânico — lê a Sheet, normaliza origens, filtra ruído determinístico, agrupa por origem, sincroniza `feedback_notificacoes` para JSON local e monta o manifesto + draft canónico. **Numa sessão de Code na nuvem (como esta), esse caminho `G:\` não existe** — o equivalente funcional é ler a Google Sheet **`Espelho_Notificacoes`** (ID `16yjJdHRvp-seUtjwvmKTvSrwf-On0WaxJLFEaXcdhis`, aba `Página1`) directamente via conector, aplicar a mesma lógica de normalização/agrupamento descrita no documento, e produzir o JSON canónico à mão — nunca inventar o resultado do preflight nem assumir que ele correu.
- **A Sheet é a fonte única de estado** — não inferir estado a partir do HTML publicado, que pode estar desactualizado face à Sheet (mesmo princípio do TestMe/`Espelho_testme`).
- **Vocabulário de `status`:** activos são `novo` (ou vazio, tratado como `novo`), `revisar`, `mantido`; terminal é `lido`. `tratado` e `descartado` são valores antigos mantidos só por compatibilidade — tratar sempre como `lido` em rotinas novas, nunca como categoria própria.
- **Sem dependência de créditos OpenAI:** o resumo/priorização por origem é feito pelo próprio LLM da sessão (Claude), lendo o manifesto/draft — nunca chamar a API da OpenAI nem assumir que ela está disponível.
- **Publicação duplicada, propositada:** o Cloudflare Pages do `personal-system` serve com `destination_dir = agendas`, por isso o HTML final tem de ir para **dois** caminhos — `agendas/notificacoes/index.html` (serve `/notificacoes/`) e `agendas/agendas/notificacoes/index.html` (serve `/agendas/notificacoes/`). Publicar só num dos dois é uma rotina incompleta.
- **Nunca expor no JSON canónico:** códigos de autenticação, segredos ou mensagens pessoais sensíveis verbatim — a Secção 5 do documento é explícita sobre isto; resumir/redigir texto sensível em vez de o citar.
- Botões da página chamam o Apps Script (`espelho_notificacoes_apps_script_v2.js`) com acções fixas: `lido_origem`, `review_origem`, `status_origem`, `feedback_notificacao`, `marcar_antigas_lidas` — não inventar novas acções sem verificar se o Apps Script já publicado as suporta.
- Confirmar ao Rafa no fim com 1-2 frases + link (`https://personal-system-hs5.pages.dev/notificacoes/`) — sem bloco de código extenso na resposta.
