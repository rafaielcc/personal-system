---
name: testme
description: Use quando o Rafa pedir "atualizar testme", "atualiza o testme", "test me", "simulado cirurgia pediátrica", "pergunta do dia (cirurgia pediátrica)" ou variantes. Faz o housekeeping da pergunta do dia e do simulado do módulo TestMe (preparação para o exame de Assistente Graduado em Cirurgia Pediátrica) e republica a página.
---

# TestMe (preparação Assistente Graduado — Cirurgia Pediátrica)

## Passos

1. **Ler `agendas/CLAUDE.md`** (não o `CLAUDE.md` da raiz do repo — esse é de outro projecto, o AII), se ainda não estiver em contexto nesta sessão.
2. **Ler `SYSTEM_PROMPT_v6.1_FINAL.md`** — pasta Drive `15Ge84lmsAeoUgSXDWFpcW26X-UCixrbg` (procurar pelo nome; usar a cópia de `createdTime` mais recente se houver duplicados). Obrigatório mesmo que o documento abaixo pareça auto-suficiente.
3. Na mesma pasta Drive, procurar **`TESTME.md`** pelo nome exacto — ao contrário da maioria das rotinas, este ficheiro **não usa sufixo de versão no nome** (a versão vive dentro do documento, não no título — ver nota interna "v0.1..."). Descarregar e seguir o contrato na íntegra — não resumir nem saltar secções.
4. Seguir a rotina tal como descrita lá. Não inventar passos nem assumir o processo de cor — o documento é a fonte de verdade, este skill é só o ponteiro para ele.

## Notas específicas a ter em atenção (não substituem o documento — só orientação)

- **Nome canónico do módulo: `testme`** (sem hífen). Evitar a variante `test-me` em paths, IDs ou ficheiros novos — se aparecer em notas antigas, tratar como legado e normalizar.
- **Este módulo foi desenhado primeiro para execução local** (scripts `preflight_testme.py`/`postflight_testme.py` em `G:\My Drive\Claude_PRJ\Agenda\...`, no desktop do Rafa) — o `TESTME.md` assume isso por omissão (`mode_recommendation: local`). Numa sessão de Code na nuvem (como esta, sem acesso a esse `G:\`), o equivalente funcional tem de ser feito por conectores Drive/Sheets: ler `TESTME.md` + o template/render da pasta Drive `Templates/testme` (`1J31IEd8cpuUvEBVuWWE8DQgknTQph441`), ler/escrever o estado na Google Sheet **`Espelho_testme`** (ID `1umzy0T45iQlN2Fv52OV73PzRpWmgF5GWHUUMBO0Y7wo`) em vez do ficheiro local, e publicar directamente neste repositório (`git commit`/`push`) em vez de copiar para o `G:\` local. Não assumir que os caminhos `G:\...` existem nesta sessão.
- **A Sheet `Espelho_testme` é a fonte única de estado** — é para lá que o Apps Script do site estático (`apps_script_testme.gs`, já publicado pelo Rafa) escreve as respostas do simulado em tempo real, e é de lá que este módulo lê para saber o que fazer. Nunca inferir estado a partir do HTML publicado — ele pode estar desactualizado face à Sheet.
- **Taxonomia fixa de tópicos** (cada pergunta tem exactamente um): Upper GI, Lower GI, Hepatobiliar/Pancreático, Neonatologia, Tórax, Oncologia, Urologia, Trauma, Outros. **Formato** (cada pergunta tem exactamente um): `mcq` ou `discursiva`, com mistura entre 60/40 e 80/20 `mcq`/`discursiva` em qualquer conjunto gerado.
- **Nível de dificuldade obrigatório: assistente graduado**, não licenciatura/internato básico — ver critérios detalhados na Secção 2.1 do `TESTME.md` (evitar perguntas de reconhecimento directo óbvio; preferir decisões clínico-cirúrgicas com trade-offs reais).
- **Duas portas de entrada para a correcção do simulado, ambas válidas e independentes**: (a) o Rafa exporta as respostas do site e cola-as directamente numa conversa — o texto colado é auto-explicativo, corrigir nessa mesma sessão; (b) este trigger corre e encontra, na Sheet, um simulado com estado `terminado` — corrige-o já nesse momento (não é preciso esperar por um export explícito).
- As perguntas são **geradas a partir de conhecimento clínico geral do LLM + pesquisa**, nunca apresentadas como reprodução de perguntas de exames reais, salvo fonte explicitamente fornecida pelo Rafa.
- Publica em `agendas/personal-development/testme/index.html` (+ `agendas/personal-development/testme/data/estado-atual.json`, consumido client-side pelo cartão do Dashboard, no mesmo padrão do cartão Carnegie — não gerado pelo LLM a cada corrida do Dashboard, só lido).
- Confirmar ao Rafa no fim com 1-2 frases + link (`https://personal-system-hs5.pages.dev/personal-development/testme/`) — sem bloco de código extenso na resposta.
