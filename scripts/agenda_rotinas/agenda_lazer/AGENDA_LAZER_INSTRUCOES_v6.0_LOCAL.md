# 🗺️ Agenda Lisboa — Instruções de Geração
*Versão LOCAL 6.0 · Pré mecânico diário + LLM periódica + publicação automática · 24 Set 2026*
*Esta versão substitui a v5.5 LOCAL na máquina do Rafa. `X_lazer_pre.py`, na raiz de `X_Rotinas_Python`, incorpora as quatro extrações do antigo `Go_All_events.bat`, recolhe as restantes fontes e produz um único handoff. A LLM usa exclusivamente esse JSON, escreve diretamente o JSON canónico final e nunca consulta fontes nem cria scripts auxiliares. `go_lazer_llm.bat` corre um postflight sem publicação e, se estiver limpo, publica sempre automaticamente — autorização permanente do Rafa, sem pedido de confirmação. A rotina de nuvem `AGENDA_LAZER_INSTRUCOES_v5.5.md` permanece separada e intacta.*

## CONTRATO LOCAL 6.0 — AUTORITATIVO

Em caso de conflito com texto histórico abaixo, este contrato prevalece.

1. **Pré diário, sem LLM:** `G:\My Drive\Claude_PRJ\Agenda\X_Rotinas_Python\X_lazer_pre.py` é executado diariamente por `go_X_lazer_pre.bat`. Ele chama diretamente os exportadores de Gmail Events, Cinema, Livros e Streaming antes agrupados em `Go_All_events.bat`; lê Calendar, `espelho_lazer`, `Rafa_profile.md`, `Feedback_log.json`, `travel_log`, `Lista_Sazonal.json`, meteorologia, MotelX e fontes públicas; e produz `X_Outputs\lazer\<run_id>_lazer_pre.json` + draft.
2. **Fonte única da LLM:** o ficheiro `*_lazer_pre.json` é a única entrada. O texto integral do perfil e todas as entradas/catálogos/regras do feedback estão em `canonical_draft.sources.profile.context` e `canonical_draft.sources.feedback.context`. A LLM não volta a consultar Gmail, Calendar, Sheets, Drive, web ou ficheiros locais.
3. **Limite de escrita da LLM:** a LLM altera apenas os caminhos listados em `_llm_handoff.editable_paths` e grava `*_lazer_final.json` diretamente com a ferramenta Write. É proibido criar ou executar `.tmp_build_*.py` ou qualquer script intermédio.
4. **Nunca inventar:** uma falha de fonte permanece explícita. O antigo fallback de “eventos prováveis” fica abolido. Threshold abaixo do mínimo é documentado, nunca preenchido com data, sessão, canal, preço, link ou disponibilidade inferidos.
5. **Itens evergreen:** livros, streaming, restaurantes e escapadinhas podem ter `date: null`; o render não os coloca no calendário. É proibido atribuir uma data-placeholder apenas para satisfazer o schema.
6. **Publicação automática:** `go_lazer_llm.bat` valida/renderiza primeiro sem publicação. Se o postflight terminar com código 0, chama imediatamente `postflight_lazer.py --publish`. Não pede autorização ao Rafa. Falha de preflight, JSON ou postflight aborta sem publicar.
7. **Duas cópias obrigatórias:** editar primeiro a cópia versionada em `C:\Users\rafai\Documents\github\personal-system\scripts\agenda_rotinas\`; depois copiar para `G:\My Drive\Claude_PRJ\Agenda\X_Rotinas_Python\`. As duas devem ter conteúdo idêntico.

*Base histórica · 28 Ago 2026 · Esta nota descreve a variante que antecedeu o contrato LOCAL 6.0 acima. As antigas leituras/fallbacks ao vivo pela LLM estão revogadas: toda a recolha pertence agora a `X_lazer_pre.py` e a LLM recebe apenas o JSON pré.*
*Update LOCAL · 28 Ago 2026 · O botão antigo "Salvar" / Zapier fica aposentado nos renders futuros. "Guardar para o futuro" continua ativo via `espelho_lazer`. Os botões de curadoria passam a funcionar como toggle: clicar de novo no botão ativo grava `limpo` e desfaz a marcação. `merge_feedback.py` pergunta, para cada `consumido`, se deve guardar no Feedback_log e qual nota atribuir; também pode preparar um CSV limpo mantendo apenas `elevar` e `guardado_futuro`.*
*Versão 5.5 · Reversão: score deixa de ser pedido no browser, passa para rotina Python local · 22 Ago 2026*
*O Rafa esclareceu que o pedido de nota/pontuação da v5.4 nunca era para acontecer no browser: a ideia dele desde o início era essa pergunta viver numa rotina Python LOCAL (`merge_feedback.py`, mesmo espírito do `preflight_hff.py`/`postflight_hff.py` — sem API Google, sem sessão Claude, corre na máquina do Rafa) que ele próprio corre quando quiser processar feedback pendente. O ícone ✅ "já experimentei" volta a só marcar `consumido` no clique, sem pedir nada — a coluna `nota` da `espelho_lazer` fica sempre vazia. Consequência importante para esta rotina: a LLM DEIXA de escrever no Feedback_log.json a partir de linhas `consumido` (Secção 8.1, passo 4) — essa conversão passou a ser exclusiva do `merge_feedback.py`, para não haver duas escritas independentes a criar entradas duplicadas. A LLM continua só a evitar re-sugerir um item já marcado `consumido`. Ver Secções 0.5 e 8.1 abaixo — nenhum threshold, fonte ou filtro de perfil pré-existente foi alterado.*
*Versão 5.4 · Feedback pós-teste real: calendário alinhado à semana + botão "já experimentei" · 22 Ago 2026*
*Pedido do Rafa, depois de ver a primeira geração real de ponta a ponta publicada ("gera a agenda de lazer"): (1) o calendário expansível (Secção 11.4) começava sempre no dia de hoje/periodo_inicio em vez de respeitar o padrão de grelha já usado no Briefing (1ª coluna sempre segunda, última domingo) — corrigido inteiramente no render.py/template.html (v7/v8), nenhuma mudança do lado da LLM/JSON canónico. (2) faltava um botão "já vi/já fui/já experimentei" em cada card (só existia no bloco "Guardado para o futuro") para fechar o ciclo de feedback de restaurantes/lugares/filmes sem depender só do botão Salvar — reaproveita a acção `consumido` já existente na `espelho_lazer` (Secção 0.5), agora também disponível em qualquer card, com nota/pontuação pedida no momento do clique. Ver Secções 0.5 e 8.1 abaixo — nenhum threshold, fonte ou filtro de perfil pré-existente foi alterado.*
*Versão 5.3 · Curadoria (remover/elevar/guardar para o futuro) + calendário expansível · 22 Ago 2026*
*Pedido do Rafa (sessão "ícones de curadoria"): Highlights não estava a acertar bem no perfil dele — em vez de só melhorar a selecção, ganhou mecanismo para o próprio Rafa curar directamente na página (✕ remover · ⬆ elevar · 🕒 guardar para o futuro), gravado numa sheet nova (`espelho_lazer`) via Apps Script. Ganhou também um bloco de calendário expansível na aba Highlights. Ver Secções 0.5, 8.1 e 17-A abaixo — nenhuma regra pré-existente (thresholds, fontes, filtros de perfil) foi alterada.*
*Versão 5.2 · Expansion Architecture · 22 Jul 2026*
*Pedido do Rafa: fim da cópia do HTML no Drive — a publicação (Secção 12) passa a terminar no GitHub, alinhada com a Rotina de Publicação v1.6. Nenhum threshold, trigger ou ID de dados foi alterado.*
*Auditoria de forma (sessão Lazer, v5.0): calendário delegado ao documento partilhado "Leitura de Calendário"; publicação delegada à Rotina de Publicação; token GitHub removido deste ficheiro; regras de desporto TV actualizadas às preferências reais; histórico comprimido no Registo de Alterações.*

---

## 0. PRIMEIROS PASSOS OBRIGATÓRIOS

Antes de gerar qualquer agenda, ler sempre DOIS ficheiros da pasta SSoT:

> ⚠️ **FONTE ÚNICA DE VERDADE — Pasta SSoT no Google Drive**
> 📁 https://drive.google.com/drive/folders/1KAVv-gCiCGGlZNvxgVLvx3SuKRRZ-hzC
> Os ficheiros de perfil e feedback NÃO estão no projecto. Estão APENAS nesta pasta.
> Nunca usar memória local ou cópias antigas. Ir sempre ao Drive, sempre por ID (nunca pesquisar por nome — existem duplicados).

### 0.1 — `Rafa_profile.md`
**ID: `1ewoFcKK0JPp2_fseW9GDi7Kl96zYDKq_`**

Estrutura modular com índice — ler apenas as secções relevantes:
- Secção 1: Identidade base — ler sempre
- Secção 6: Desporto & Actividade Física — para agenda desporto (grupos, horários, links Luma — ver Secção 4.2/4.4 deste ficheiro)
- Secção 8: Desportos na TV — para eventos TV (futebol, ténis, etc.)
- Secção 11: Gastronomia — preferências e restrições (sem sushi, sem chinês)
- Secção 16: Logística Carnide — distâncias, transporte, parking
- Secção 17: Vanessa — sugestões a dois

### 0.2 — `Feedback_log.json` ⚠️ OBRIGATÓRIO para gastronomia e lazer
**ID: `1HgrEZUakKW1JrIQFrB7tOrlUI10gKEqH`**

Ficheiro único e canónico — aceder directamente por este ID.

Contém: locais excluídos (❌ nunca sugerir), aprovados (✅), favoritos, recomendações de terceiros por testar, parques preferidos, eventos sazonais favoritos. Inclui exclusões a nível de prato específico — ex: um restaurante pode estar "approved" no geral mas ter um prato em `dish_blacklist`.

> **Regra crítica:** Verificar sempre a secção ❌ EXCLUÍDOS (status `excluded`, flag `never_again: true`) e qualquer `dish_blacklist` antes de sugerir qualquer restaurante, prato, parque ou actividade. Atenção a variantes de nome do mesmo local (ex: "Taberna Soão" pode aparecer listado como "Soão — Taberna Asiática" noutra fonte — é o mesmo local excluído).

### 0.3 — Pasta `Guardados da Agenda` (legado do botão antigo "Salvar")
**ID: `1SsDDXwmzbhYMEKbZOjJ2RmNWV5t_R6j5`** (dentro da pasta SSoT)

Fluxo legado. O botão "Salvar" / Zapier foi aposentado na rotina LOCAL porque duplicava a função de "Guardar para o futuro" e gerava payloads vazios. Não usar esta pasta como fonte primária das próximas gerações. Manter apenas para leitura histórica/última ingestão manual via `merge_feedback.py --guardados-dir`, se o Rafa pedir ou se houver ficheiros antigos com payload válido. A fonte ativa para guardar itens é `espelho_lazer` com `acao=guardado_futuro`.

### 0.4 — `Lista_Sazonal.json` (eventos/actividades anuais recorrentes)
**ID: `1K307L5u7Ftl0fRRnX11FGA245kFzUzgQ`** (aceder sempre por este ID directo — o Rafa move este ficheiro de pasta livremente, o ID não muda)

Regista eventos/actividades que se repetem todos os anos na mesma época (feiras, desporto, festas), para o Rafa não se esquecer deles — sobretudo os que têm reserva antecipada de bilhete (já perdeu o prazo do Estoril Open uma vez). Schema de cada entrada em `entries[]`:

| Campo | Tipo | Descrição |
|---|---|---|
| `id` | string | `"saz_NNN"` sequencial |
| `nome` | string | Nome do evento/actividade |
| `categoria` | string | livre curto (ex.: `desporto`, `festa popular`) |
| `epoca` | string | mês ou estação em que ocorre (ex.: `Julho`) |
| `reserva_antecipada` | boolean | se exige comprar bilhete com antecedência |
| `aviso_ideal` | string | quando/como agir, se `reserva_antecipada: true` |
| `observacoes` | string | texto livre |
| `link` | string\|null | opcional |
| `ultima_confirmacao` | string | `YYYY-MM-DD` da última confirmação/criação |

**Skill "incluir sazonal"** (gatilho: "sazonal:", "incluir sazonal", ou o Rafa mencionar um evento anual que quer lembrar): descarregar o ficheiro pelo ID acima, pré-preencher os campos possíveis a partir do que o Rafa disser, perguntar SÓ os que faltarem (nunca a lista toda). Gerar o `id` sequencial seguinte e `ultima_confirmacao` = hoje. Como o Drive não edita in-place, gravar como ficheiro novo com o mesmo título `Lista_Sazonal.json`, na mesma pasta da cópia actual — update directo, sem aprovação prévia (mesma regra do `Feedback_log.json`, Secção 0.2).

**Skill "consultar sazonal"** (gatilho: "consultar sazonal", fora de gerar a agenda completa): ler o ficheiro, filtrar `epoca` do mês actual + mês seguinte, responder directamente no chat — não gerar agenda nem publicar nada.

### 0.5 — `espelho_lazer` (curadoria do Rafa: remover / elevar / guardar para o futuro) — NOVO v5.3
**ID: `15Y75AwcqV4l2GtuGI5kFfSftv6T3kpexKUmfDyBEp5I`** (Google Sheet, pasta SSoT)

Sheet dedicada só à curadoria da Agenda de Lazer (não misturar com Espelho HFF — é sobre trabalho/hospital — nem com Espelho Radar — é sobre acções/bolsa). Colunas: `timestamp` · `dedup_key` (`titulo.strip().casefold() + "::" + categoria`, calculado mecanicamente pelo `render.py` — a LLM nunca o inventa) · `titulo` · `categoria` · `acao` (`removido`\|`elevar`\|`guardado_futuro`\|`consumido`\|`limpo`) · `data_evento` · `expira_em` · `nota` (coluna existe desde v5.4, mas fica sempre vazia desde v5.5 — ver nota abaixo; auto-reparada no cabeçalho pelo Apps Script se a sheet ainda não tiver esta 8ª coluna).

**Como as linhas chegam lá:** quatro ícones em todos os cards (✕ remover · ⬆ elevar · 🕒 guardar para o futuro · ✅ já experimentei/já vi/já fui — antes só existia no bloco "Guardado para o futuro") fazem `fetch()` directo da página publicada para um Apps Script bound a esta sheet (código-fonte de referência: `apps_script_espelho_lazer.gs`, mesma pasta Templates/agenda_lazer do Drive) — grava sempre uma linha nova (append-only, nunca reescreve linhas antigas). O deploy do Apps Script é feito pelo Rafa sempre que este ficheiro muda (ver comentário no topo do próprio `.gs`); depois disso o registo é 100% automático por clique, sem qualquer intervenção manual. Na rotina LOCAL, isto substitui o botão antigo "Salvar"/Zapier.

**NOVO v5.5/LOCAL — nota/pontuação NÃO se pede no browser:** o clique no ícone ✅ grava `consumido` de imediato, sem perguntar nada. Quem pergunta é a rotina Python LOCAL `merge_feedback.py` (mesma pasta Templates/agenda_lazer), que o Rafa corre na própria máquina, fora de qualquer sessão Claude. Para cada `consumido` ainda sem entrada correspondente no Feedback_log.json, ela pergunta primeiro se deve guardar esse consumo no Feedback_log; só se a resposta for sim é que pede nota 0-5 e comentário opcional. Se a resposta for não, o item é ignorado para feedback e pode sair do CSV limpo da sheet. **Por causa disto, a LLM NUNCA escreve no Feedback_log.json a partir de uma linha `consumido`** (ver Secção 8.1, passo 4, revisto).

**Como a próxima geração lê esta sheet** (passo obrigatório na Filter Layer, ver Secção 8.1 abaixo): na rotina LOCAL, exportar a sheet como CSV e entregar ao preflight com `--espelho-lazer-csv`. Para cada `dedup_key`, só a linha de `timestamp` mais recente conta.

**Semântica de cada `acao`** (definida na sessão de desenho com o Rafa — ver histórico completo no Registo de Alterações se precisares do raciocínio):
- **`removido`** — exclui esse item exacto (`dedup_key`) quando o preflight lê a sheet. Não entra automaticamente no Feedback_log. Se o CSV limpo posterior apagar esta linha da sheet, a exclusão deixa de persistir; para transformar algo em "nunca mais sugerir", criar entrada `excluded`/`never_again` no Feedback_log por decisão explícita do Rafa.
- **`elevar`** — força `highlight:true` nesse item na próxima geração. Expira sozinho: se o item tem `date`/`date_inicio`/`date_fim`, expira na própria data (`expira_em` = essa data, calculado pelo Apps Script); se não tem data, expira 14 dias depois do clique (`expira_em` = timestamp + 14 dias). Um novo clique em "elevar" no mesmo item reinicia a janela de 14 dias.
- **`guardado_futuro`** — NÃO escreve na pasta "Guardados da Agenda" (Secção 0.3) nem no Feedback_log.json directamente. Fica só nesta sheet, como estado temporário, e entra no bloco "🕒 Guardado para o futuro" (fim da secção Highlights) em todas as gerações seguintes, até ser removido ou consumido.
- **`consumido`** — clicado pelo Rafa: no botão ✓ do bloco "Guardado para o futuro" quando finalmente vê/faz um item guardado, **ou** no ícone ✅ "já experimentei/já vi/já fui" de qualquer card normal (útil sobretudo para restaurantes/lugares que ele já conhecia e nunca tinham passado pelo bloco "Guardado"). O clique não pede nada — grava logo (Secção 0.5, NOVO v5.5). Deixa de ser gatilho de escrita no Feedback_log.json pela LLM (isso passou a ser exclusivo do `merge_feedback.py`, rotina local — ver Secção 0.5 e 8.1 passo 4); o efeito para esta rotina é apenas: não voltar a sugerir esse `dedup_key` enquanto a linha `consumido` continuar a ser a mais recente. Quando veio do bloco "Guardado para o futuro" o item sai desse bloco na próxima geração.
- **`limpo`** — desfaz clique acidental. É gravado quando o Rafa clica de novo num botão ativo no HTML. Como só a linha mais recente por `dedup_key` vale, `limpo` neutraliza `removido`/`elevar`/`guardado_futuro`/`consumido` anterior.

**Manutenção local da sheet:** `merge_feedback.py --espelho-lazer-clean-out <ficheiro.csv>` prepara um CSV limpo com apenas as linhas atuais `elevar` e `guardado_futuro` ainda úteis. `removido`, `consumido`, `limpo` e `elevar` expirado saem desse artefacto. O script não atualiza a Sheet real automaticamente.

**Sequência local recomendada:**
1. Antes da próxima geração: exportar `espelho_lazer` como CSV e correr `preflight_lazer.py --espelho-lazer-csv <csv>`. É aqui que `removido`, `consumido`, `elevar`, `guardado_futuro` e `limpo` influenciam a agenda nova.
2. Quando o Rafa quiser fechar feedback: correr `Templates/agenda_lazer/merge_feedback.py --feedback-log <Feedback_log.json> --espelho-lazer-csv <csv> --espelho-lazer-clean-out <csv_limpo>`. Para cada `consumido`, responder se vai para o Feedback_log; se sim, atribuir nota/comentário.
3. Só depois de confirmar que a geração/merge consumiu as marcações, usar o CSV limpo para arrumar a Sheet real. O script local prepara o ficheiro, mas não altera a Sheet automaticamente.

---

## 1. QUANDO GERAR A AGENDA

### Frases que activam a geração
- "Agenda da semana" / "agenda de lazer" / "agenda completa"
- "Eventos próximos" / "eventos em Lisboa" / "o que há para fazer"
- "Roteiro de fim de semana" / "o que posso fazer este fim de semana"
- "Faz-me a agenda" / "gera a agenda" / "mostra-me a agenda"
- "Próximos 15 dias" / "próximas duas semanas"
- "Há alguma coisa interessante esta semana?"

### Período por defeito
**15 dias a partir de hoje.** Usar sempre a data real actual (confirmar via `user_time_v0` ou equivalente — nunca assumir).

---

## 2. PRINCÍPIO FUNDAMENTAL DA ARQUITETURA

> ⚠️ **NUNCA FILTRAR ANTES DE EXPANDIR.**

A causa raiz da agenda pobre nas versões antigas foi selecção precoce: o sistema decidia "o que interessa" ao mesmo tempo que pesquisava, reduzindo volume e diversidade antes de qualquer comparação justa ser possível. Ter a regra escrita não substitui confirmar, no fim, que ela foi cumprida — ver Secção 17 (Checklist).

### Pipeline global

```text
RAW SOURCES
↓
EXPANSION LAYER
↓
INITIAL CANDIDATES
↓
MINIMUM THRESHOLD CHECK
↓
FALLBACK EXPANSION (se necessário)
↓
NORMALIZATION
↓
FILTER LAYER (SSoT + Feedback_log.json)
↓
LIGHT SCORING (ordenação, não exclusão)
↓
JSON OUTPUT (CANÓNICO)
↓
DEBUG VIEW
↓
CHECKLIST DE AUTO-VERIFICAÇÃO (Secção 17) — obrigatório antes de publicar
↓
ROTINA DE PUBLICAÇÃO (render → GitHub)
```

---

## 3. VERIFICAÇÃO DO CALENDÁRIO (entrada da Expansion Layer)

O procedimento de leitura do calendário (ferramenta, calendários, formato de datas, hora de Lisboa, retries, correcção de timezone do Todoist) vive no documento partilhado **"Leitura de Calendário" v1.0** — **ID: `1UIH2nUdz5867satNKiWUq0KyLYQHWWlm`** — comum ao Briefing, Lazer e Painel HFF. Segui-lo integralmente.

Específico da Lazer:
- **Janela:** os 15 dias do período da agenda.
- Linha defensiva: usar sempre `Google Calendar:list_events` — `event_search_v0` está banida (devolve vazios silenciosos); o seu uso é, por si só, falha a registar no Debug View.

**Flags de disponibilidade:**
- `"Sigic"` = tarde bloqueada (~15h30–21h) — não sugerir actividades nessa tarde
- `"Prevenção"` = sem viagens longas, disponibilidade limitada
- Viagem marcada = sugerir actividades no destino, não em Lisboa

Esta verificação alimenta a Expansion Layer como contexto de disponibilidade — não filtra eventos nesta fase, apenas marca-os.

**NOVO v5.3 — captura para o calendário do Highlights:** além das flags de disponibilidade acima, registar TODOS os compromissos reais do período (título curto + hora, sem detalhe) por dia, para popular `meta.calendario_pessoal[]` (Secção 10.1) — é o que alimenta a coluna "Compromissos" do bloco de calendário expansível. Não filtrar por relevância aqui: qualquer evento real do calendário do Rafa no período conta, mesmo que não tenha nada a ver com lazer (ex.: Sigic, consultas, compromissos pessoais) — o objectivo é ele conseguir cruzar "o que tenho marcado" com "o que a agenda sugere" ao clicar num dia.

---

## 4. EXPANSION LAYER (núcleo do sistema)

**Objetivo: gerar o máximo de candidatos possíveis antes de qualquer filtro.**

### 4.1 Calendar
- Eventos, bloqueios, contexto de disponibilidade (ver Secção 3)

### 4.2 Gmail ⚠️ OBRIGATÓRIO — NUNCA PULAR ESTA SECÇÃO

> 🚨 **Regra crítica:** a agenda NÃO PODE ser gerada sem consultar o Gmail (via MODO 1 ou MODO 2 abaixo).

**MODO 1 — ficheiro JSON pronto (verificar SEMPRE primeiro, é o caminho normal):**

1. Procurar na pasta do Drive "Gmail_events" (ID `1PTSoHKaUhTnaYJmNFsY52ZxaJhfS4y65`) o ficheiro mais recente (`Gmail_events_<inicio>_a_<fim>.json`).
2. Se existir um ficheiro cujo campo `period.end` esteja dentro dos últimos 5 dias: usar este MODO. Ler o JSON e:
   - **Procedimento de leitura:** Descarregar o ficheiro via ferramenta de download. Se no resultado vier com aviso de tamanho excedido e um caminho de ficheiro local, usar esse caminho directamente. Ler os itens de `emails[]` um a um.
   - `emails[]` alimenta a Expansion Layer (Secção 4). Cada item já vem limpo (sender, subject, date, body_text) — extrair todos os eventos relevantes ao perfil (desporto, cultura, música, gastro) com data, hora e local a partir do `body_text`.
   - `event_hints{}` (`date_guess`/`time_guess`/`location_guess`) é um atalho best-effort, não autoritativo — útil sobretudo para confirmações Luma/Meetup (data/hora/local já vêm limpos ali); para newsletters/digests com vários eventos, confiar no `body_text`, não só nas pistas.
   - `links[].article_text`, quando preenchido, é o texto extraído da página do evento (Luma/Fever/TimeOut/etc.) — normalmente mais completo que o teaser do email; quando `null` (falha, JS obrigatório, paywall), tratar o link apenas como referência, não abrir manualmente.
   - Registar no Debug View os números de `stats` e `link_stats` do ficheiro.
3. Registar no Debug View qual modo foi usado e a data/período do ficheiro JSON consultado.

**MODO 2 — fallback, sem ficheiro fresco (excepção, não o caminho normal):**

Se NÃO existir nenhum ficheiro `Gmail_events_*.json` com `period.end` dentro dos últimos 5 dias (export local não foi executado): seguir os passos originais desta secção —
1. `Gmail:search_threads` com `query: "label:events newer_than:15d"` — cobre newsletters Luma, Fever, TimeOut, Gulbenkian, MEO Kalorama e confirmações de eventos.
2. `Gmail:search_threads` com `query: "from:luma-mail.com OR from:meetup.com newer_than:14d"` — cobre especificamente confirmações de grupos (ActiveHive, Clube 7 Colinas, etc.).
3. Para qualquer thread relevante encontrado, usar `Gmail:get_thread` para ler o corpo completo (a pesquisa só devolve snippet, que não basta).
4. Extrair todos os eventos relevantes ao perfil com data, hora e local, e adicioná-los como candidatos no Expansion Layer.

Sinalizar no Debug View que o modo fallback foi usado, e o motivo (ficheiro ausente/desactualizado).

**Nota sobre ActiveHive/Luma (ligado à Secção 4.4):**
os eventos de desporto do Rafa (voleibol relva, beach tennis, etc.) vivem nas páginas de calendário Luma específicas dos grupos (ver Secção 4.4) e Meetup; a confirmação do Rafa a estes eventos ou a sua entrada em lista de espera geram e-mails individuais — o Gmail é complementar, não substituto, da consulta directa a essas páginas.


### 4.3 Web Events
Observar sempre:

- Lisboa Secreta: https://lisboasecreta.co/
- AgendaLX: https://www.agendalx.pt/
- Time Out Lisboa: https://www.timeout.pt/lisboa/
- Fever Lisboa: https://feverup.com/lisbon
- Camara Lisboa: https://informacao.lisboa.pt/agenda
- Blueticket: https://blueticket.pt · Ticketline: https://ticketline.sapo.pt · LiveNation Portugal: https://www.livenation.pt

Expandir para: cultura, música, eventos gratuitos, eventos temporários, eventos outdoors. Não fazer pesquisa superficial: pesquisar dentro dos links, nas subpáginas, verificar com precisão e dedicação o que realmente está a ocorrer na cidade nesses próximos 15 dias.

### 4.4 Desporto (Meetup + Luma) ⚠️ OBRIGATÓRIO — NUNCA PULAR ESTA SECÇÃO

> 🚨 **Regra crítica:** a agenda NÃO PODE ser gerada sem pelo menos uma tentativa de sessão de desporto real, com data e horário concretos quando disponíveis. "Não consegui confirmar o calendário Luma" é uma resposta aceitável APENAS depois de ter tentado o passo 2 abaixo; nunca é aceitável omitir a secção de Desporto sem essa tentativa documentada no Debug View.

**Fontes concretas (do perfil do Rafa, Secção 6 de `Rafa_profile.md`):**
- ActiveHive — calendário principal: https://lu.ma/activehive (cobre voleibol relva Algés/Olivais/Campo Grande, meditação, beach tennis, game night)
- Calendário do Rafa na plataforma Luma: https://luma.com/rafaielcc
- GBS — voleibol indoor INATEL (sextas/segundas) + voleibol de praia Carcavelos (sábados)
- Grupos WhatsApp (SSL, PowerRangels, Lisbora ciclismo) — não acessíveis via ferramenta; mencionar como recorrentes conhecidos pelo perfil, sem inventar datas específicas
- `meetup.com/lisbonhikingmeetup/events` para hiking

**Passos obrigatórios:**
1. `web_fetch` em `https://lu.ma/activehive` — mesmo que a página seja dinâmica e não devolva a lista completa de datas em texto, confirma a existência de eventos activos e dá pelo menos 1-2 nomes de sessões a colocar como candidatos (ex: "Grass Volleyball at Marvila").
2. Se o `web_fetch` não devolver datas suficientes, complementar com `web_search` por "ActiveHive Lisboa [modalidade] [mês] lu.ma" — aceitar resultados de fontes secundárias (ex: federações desportivas, câmaras municipais) para eventos paralelos relevantes (ex: torneios oficiais de voleibol de praia em Carcavelos).
3. Se mesmo assim não for possível confirmar datas exactas de sessões recorrentes, incluir na secção Desporto os horários fixos conhecidos do perfil (ex: "Voleibol relva ActiveHive — Terças 18h, Ribeirinho Algés (recorrente; confirmar lugar disponível em lu.ma/activehive)") em vez de omitir a secção.
4. Registar no Debug View qual dos passos 1-3 foi necessário e porquê.

Expandir: eventos próximos 15 dias, eventos similares, eventos paralelos, eventos recorrentes, eventos de grupos relacionados.

### 4.5 Cinema (CRÍTICO — indoor e outdoor têm regras de expansão diferentes)

**MODO 1 — ficheiro JSON pronto (verificar SEMPRE primeiro — cobre Cinecartaz indoor + CineConchas + Black Cat):**

1. Procurar na pasta do Drive "websearch_cinema" (ID `1WnWE-rNGokSJNlF5qumuvucGGjMRHk6J`) o ficheiro mais recente (`Cinema_Lisboa_<data>.json`).
2. Se existir um ficheiro cujo campo `generated_at` esteja dentro dos últimos 7 dias: usar este MODO para as fontes que ele cobre:
   - `indoor.cinecartaz[]` — cada filme já vem com título, sinopse, género, duração, ano, país, e `showings[]` (uma entrada por sala — Cinemas Nos Colombo / UCI Cinemas - El Corte Inglés — com realizador, elenco, classificação e `sessions_raw`, o texto de horários tal como o site apresenta, em português, com abreviaturas de dia da semana: `5ª`=quinta, `6ª`=sexta, `Sab.`=sábado, `Dom.`=domingo, `2ª`-`4ª`=segunda a quarta). Expandir TODOS os filmes de ambas as salas — o filtro de perfil aplica-se só na Filter Layer (Secção 8), nunca aqui.
   - `open_air.cineconchas[]` — sessão a sessão, já com sinopse completa, género, duração, classificação.
   - `open_air.black_cat[]` — título/data/local; **sem sinopse** (a fonte não a disponibiliza) — apresentar mesmo assim, sem inventar sinopse.
3. Registar no Debug View qual modo foi usado e a data do ficheiro JSON consultado.

**MODO 2 — fallback, sem ficheiro fresco (excepção, não o caminho normal, só para as fontes cobertas pelo MODO 1):**

Se NÃO existir nenhum ficheiro `Cinema_Lisboa_*.json` com `generated_at` dentro dos últimos 7 dias:
- Indoor: `web_fetch` em `https://cinecartaz.publico.pt/cinema/zon-lusomundo-colombo-17538` (NOS Colombo) e `https://cinecartaz.publico.pt/cinema/uci-cinemas---el-corte-ingles-54418` (UCI El Corte Inglés), mais a página individual de cada filme relevante (`https://cinecartaz.publico.pt/filme/[slug]-[id]`) para sinopse/elenco/horários. As páginas `https://www.cinemas.nos.pt/filmes` e `https://www.ucicinemas.pt` são dinâmicas via JS e NÃO devolvem dados úteis — não usar.
- CineConchas / Black Cat: `web_fetch` directo em `https://www.cineconchas.pt/2026/` e `https://www.theblackcatcinema.com/pt`.

Sinalizar no Debug View que o modo fallback foi usado, e o motivo.

**MotelX — fonte local estruturada quando sazonalmente relevante:**
- Antes da curadoria, correr localmente `X_Rotinas_Python/Agenda_Lazer/extract_motelx.py` contra `https://www.motelx.org/programa-e-horarios` e entregar o JSON ao preflight com `--motelx-json`.
- O output normalizado entra como fonte `motelx`; sessões de filmes entram por defeito em `cinema_indoor`, eventos paralelos entram em `culture`, e itens fora da janela principal podem ser usados como `radar`.
- A LLM não deve fazer scraping manual repetitivo do MotelX quando este export fresco existir; deve apenas avaliar alinhamento com o perfil, priorizar e redigir.

**Ao ar livre — restantes locais (sempre ao vivo via pesquisa/web_fetch, não cobertos por MODO 1/2 — sem fonte estruturada fiável):**
- Cinema Rooftop Capitólio (Parque Meyer) — o AgendaLX não dá sessão a sessão de forma fiável (testado); usar pesquisa web pontual se relevante.
- Cine Society (Carmo Rooftop / Doca da Marinha) — site confirmado dinâmico via JS, sem dados por scraping simples; usar pesquisa web pontual se relevante.
- Cinemateca Portuguesa (Cine-Gastro Bar 39 Degraus)
- Counting Stars Cinema (Jardins do Bombarda): até setembro


> A expansão de cinema ao ar livre é sempre pela **programação completa do período** — todos os locais, todas as datas, todas as sessões, **cada uma com sinopse de pelo menos 1-2 frases quando disponível** (Black Cat é excepção conhecida — a fonte não disponibiliza sinopse). Não se aplica aqui o minimum threshold como corte.

**Indoor — minimum threshold de 4 candidatos, COM SINOPSE + HORÁRIOS REAIS + ELENCO:**
- NOS Cinemas — NOS Colombo a 5 min a pé de casa (prioritário)
- UCI Cinemas — UCI El Corte Inglés (a UCI de referência do Rafa em Lisboa)

Cada card de filme dentro do perfil DEVE incluir: título, realizador, elenco principal, classificação etária, sinopse (1-3 frases), horários de sessão do dia/período, botões de partilha. Nunca apresentar um filme indoor sem sinopse (Black Cat ao ar livre é a única excepção conhecida) — pedido explícito do Rafa, cumprir sempre.


### 4.6 TV + Streaming

**TV:**
- Futebol, competições relevantes, eventos desportivos importantes (regras detalhadas na Secção 9.2)
- ⚠️ **Torneios majors em curso (Mundial, Euro, Olimpíadas, Grand Slam, fases finais da Champions):** confirmar SEMPRE a fase actual e as datas exactas da fase via `web_search` antes de gerar a secção TV — nunca assumir só pela memória; as datas mudam a cada edição.

**Streaming — restrito às subscrições reais do Rafa (Netflix, Prime Video, HBO Max, Disney+):**

**MODO 1 — ficheiro JSON pronto (verificar SEMPRE primeiro, é o caminho normal):**
1. Procurar na pasta do Drive "websearch_streaming" (ID `1zuf8HVq2-xmfDq1LFW_GyjhCt1yscSv2`) o ficheiro mais recente (`Streaming_<data>.json`).
2. Se existir um ficheiro cujo campo `generated_at` esteja dentro dos últimos 7 dias: usar este MODO.
   - `movies[]` e `series[]` já vêm com sinopse completa (`overview`; `overview_em_ingles:true` sinaliza quando caiu para inglês por falta de tradução), género, avaliação (`vote_average`), e `platforms[]` com a(s) plataforma(s) exacta(s) do Rafa onde o título está disponível.
   - Aplicar o perfil do Rafa (`Rafa_profile.md`, `movies_preferences`/`series_preferences`) para escolher os destaques dentro deste conjunto já pré-filtrado pelas plataformas certas — a curadoria continua a ser da LLM, só a descoberta do catálogo é que já vem pronta.
3. Registar no Debug View qual modo foi usado e a data do ficheiro consultado.

**MODO 2 — fallback, sem ficheiro fresco (excepção, não o caminho normal):**
Se NÃO existir nenhum ficheiro `Streaming_*.json` com `generated_at` dentro dos últimos 7 dias: usar `web_search`/`web_fetch` para identificar títulos recentes/populares nas 4 plataformas, catálogo Portugal, tal como antes.

- ❌ Não incluir outras plataformas (ex: Apple TV+) salvo pedido explícito do Rafa

### 4.7 Books

**MODO 1 — ficheiro JSON pronto (verificar SEMPRE primeiro, é o caminho normal):**
1. Procurar na pasta do Drive "websearch_livros" (ID `1pMA_WeJymblsy7gYV9SsOOVSTeBvZAtQ`) o ficheiro mais recente (`Livros_<data>.json`).
2. Se existir um ficheiro cujo campo `generated_at` esteja dentro dos últimos 7 dias: usar este MODO.
   - `books[]` já vem com sinopse completa (`description`), autores, categorias, data de publicação e link.
   - Aplicar o perfil do Rafa (`books_preferences`) para escolher os candidatos mais alinhados dentro deste conjunto.
3. Registar no Debug View qual modo foi usado e a data do ficheiro consultado.

**MODO 2 — fallback, sem ficheiro fresco (excepção, não o caminho normal):**
Se NÃO existir nenhum ficheiro `Livros_*.json` com `generated_at` dentro dos últimos 7 dias: expandir via `web_search` — lançamentos recentes, bestsellers, recomendações personalizadas. Áreas: história, economia, biografias, psicologia, ciência.

### 4.8 Gastro
- TheFork Lisboa: https://www.thefork.pt/restaurantes/lisboa-c665920
- LX Factory (mercado domingos): https://lxfactory.com/eventos/lx-market/
- Feiras gastronómicas e street food do período
- Novos restaurantes
- `Feedback_log.json` secção "Recomendações de Terceiros" → incluir com atribuição (exclusão só na Filter Layer)

### 4.9 Escapes
- Natureza, praia, cidades próximas, eventos locais
- Verão (Mai–Set): Sesimbra + Arrábida · Comporta · Caparica · Algarve
- Qualquer época: Sintra · Cascais · Guincho · Ericeira
- Consultar também `Lista_Sazonal.json` (Secção 0.4) — qualquer item sazonal com `epoca` no período gerado conta como candidato aqui (regra de inclusão completa na Secção 14).

### 4.10 Previsão do tempo
- IPMA: https://www.ipma.pt (contexto para Plano A/B e Escapes, não filtra eventos)

---

## 5. MINIMUM THRESHOLDS (obrigatório)

> 🚨 **Regra crítica:** estes números são um chão, não uma meta a aproximar. Um output com 2 restaurantes ou 3 conteúdos de streaming é uma FALHA DE EXECUÇÃO, mesmo que o resto da agenda esteja bem feito. Se um mínimo não for atingido após Fallback Expansion (Secção 6), isso tem de aparecer explicitamente no Debug View com o motivo — nunca apresentar silenciosamente um número abaixo do mínimo como se fosse o resultado normal.

```json
{
  "desporto": "pelo menos 1 sessão real ou recorrente confirmada (ver Secção 4.4) — nunca omitir a categoria",
  "meetup": 8,
  "cinema": {
    "indoor": 4,
    "outdoor": "programação completa — sem mínimo numérico, listar todas as sessões do período, com sinopse completa de cada filme"
  },
  "web_events": 12,
  "gastro": "5, além de todas as sugestões de terceiros do feedback_log",
  "tv_streaming": 10,
  "books": 5,
  "escapes": 6
}
```

> 📊 **Nota de eficiência (pós-auditoria, 2 Jul 2026):** os mínimos mantêm-se em vigor, mas estão **em observação de custo**. Nas primeiras execuções pós-auditoria — sobretudo quando a Lazer for orquestrada pelo Dashboard junto com os restantes módulos, dentro da janela de tokens de 5 horas — avaliar o custo real via tabela de custo/diagnóstico (regra global do System Prompt v6.1). Candidatos a ajuste se o custo se revelar inviável: profundidade do scraping da Secção 4.3, Fallback Level 3, e eventualmente um modo económico quando invocada pelo Dashboard. Qualquer ajuste é decisão do Rafa — não antecipar.

---

## 6. FALLBACK EXPANSION SYSTEM

Ativado sempre que os mínimos da Secção 5 não forem atingidos numa categoria (cinema outdoor está isento);

**LEVEL 1 — Expansão directa**
Ampliar scraping · incluir eventos menos relevantes · incluir sessões adicionais · incluir horários alternativos

**LEVEL 2 — Cross-source expansion**
Meetup ↔ Web Events · Cinema ↔ Streaming · Escapes ↔ Web + Weather · Gastro ↔ Feedback + Web + TheFork

**LEVEL 3 — Catálogo factual/evergreen (último recurso)**
Usar apenas itens reais já presentes no perfil, feedback, lista sazonal ou exports estruturados. Nunca criar eventos prováveis, datas inferidas, sessões implícitas ou sugestões factualmente não suportadas.

> 🚨 **Regra crítica:** nunca permitir output final abaixo dos mínimos sem ter passado pelos 3 níveis de fallback E registado isso no Debug View.

---

## 7. NORMALIZATION LAYER
- Remover duplicados · Normalizar datas · Padronizar locais · Consolidar sessões (cinema mantém sessão a sessão)

---

## 8. FILTER LAYER (SSoT + Feedback_log.json)

> ⚠️ O filtro não deve reduzir agressivamente. Aplica regras de exclusão claras (SSoT, feedback, calendário), não preferências de gosto vagas — isso é trabalho da Light Scoring (Secção 9).

**Aplicar:** SSoT (`Rafa_profile.md`) · `Feedback_log.json` (exclusões obrigatórias) · Calendário (bloqueios reais) · Restrições pessoais

**Regras de exclusão específicas:**
1. **Nunca sugerir:** corridas a pé · sushi · comida chinesa · funk brasileiro · sertanejo · meetups online · eventos infantis
2. **Ténis:** apenas masculino. Nunca feminino.
3. **Cinema (filtro de perfil):** ✅ drama histórico, biopic, thriller psicológico, ficção científica séria, produção britânica, baseado em factos reais · ❌ ação pura sem substância, comédia leviana, animação infantil
   > **Filmes fora do perfil:** nunca omitir por completo — listar resumidamente (título + cinema, sem sessões/sinopse/botões) por baixo dos filmes detalhados.
4. **Streaming:** excluir qualquer plataforma fora de Netflix/Prime Video/HBO Max/Disney+
5. **Gastro:** excluir ❌ do Feedback_log.json (restaurante e prato) antes de qualquer sugestão
6. **Dog-friendly:** verificar antes de sugerir locais com Pub e Dexter
7. **Viagem activa:** sugerir actividades no destino, não em Lisboa
8. **Torneios que o Rafa acompanha (ver Secção 9.2):** jogos de Portugal e Brasil nunca são excluídos; durante um Mundial de futebol, nenhum jogo do torneio é excluído (acompanha-se por inteiro).

### 8.1 — Curadoria do Rafa via `espelho_lazer` — NOVO v5.3, passo obrigatório

Antes do LLM fechar o `events[]` final, o preflight local deve ler `espelho_lazer` via `--espelho-lazer-csv` (Secção 0.5) e aplicar, por `dedup_key` (usando só a linha mais recente de cada), na seguinte ordem:

1. **`removido`**: excluir esse candidato por completo nesta geração. Regista-se no Debug View quantos foram excluídos por esta via, separado da contagem normal de `Feedback_log.json`. Não escrever nada no Feedback_log por este motivo.
2. **`elevar`** (e ainda dentro do prazo — comparar `expira_em` com a data de hoje): se o candidato correspondente ainda existir nesta geração, forçar `highlight: true`, `elevado: true` e preencher `elevado_expira_label` (ex.: `"até 27 Ago"` se expira numa data conhecida, `"14 dias"` caso contrário) — nunca inventar a data, usar sempre o `expira_em` da sheet.
3. **`guardado_futuro`** (e ainda não `consumido` nem `removido` numa linha mais recente): incluir no campo top-level `futuro_guardado[]` (Secção 10.1) com `title`/`category`/`data_guardado` (= `data_evento` da sheet, ou a data do `timestamp` se vazia) — estes itens NÃO entram em `events[]`, são renderizados à parte no bloco "Guardado para o futuro".
4. **`consumido`** (REVISTO v5.5 — NUNCA escrever no Feedback_log.json a partir daqui): excluir o candidato correspondente de `events[]` (não voltar a sugeri-lo, mesmo espírito do `removido` mas sem ser permanente — uma linha mais recente do mesmo `dedup_key` substitui esta). A conversão para uma entrada do Feedback_log.json é feita EXCLUSIVAMENTE pela rotina Python local `merge_feedback.py` (Secção 0.5), que o Rafa corre na própria máquina; a LLM nunca duplica esse trabalho aqui — duas escritas independentes do mesmo `dedup_key` criariam entradas repetidas. Registar no Debug View quantos `consumido` foram excluídos desta forma.
5. **`limpo`**: não aplicar efeito nenhum; a marcação anterior está desfeita.

Nenhum destes passos altera os `minimum thresholds` da Secção 5 — se uma exclusão por `removido` deixar uma categoria abaixo do mínimo, aplica-se o Fallback Expansion (Secção 6) normalmente.

---

## 9. LIGHT SCORING (ordenação apenas — não exclui)

Ordenar por: compatibilidade com perfil · proximidade · timing · relevância/urgência · contexto social · preferência de plataforma (Netflix/Prime/HBO antes de Disney+)

### 9.1 Taxonomia de categorias

| Ícone | Categoria | Exemplos |
|---|---|---|
| 🏃 | Desporto | Voleibol, beach tennis, hiking, bowling |
| 📺 | TV | Futebol (PT/BR/torneios), ténis masc. Grand Slam |
| 🎭🎵🎉 | Cultura · Música · Festas | Concertos, arraiais, festas populares, museus, fado |
| 🎬 | Cinema | Ao ar livre (programação completa) + NOS/UCI indoor |
| 🍽️ | Gastro | TheFork + recomendações de amigos |
| 🚗 | Escapadinha | Fora de Lisboa, roteiros fim de semana |
| 📡 | Radar | Shows futuros, bilhetes à venda, estreias TV, Grand Slams |
| 📺🎞️ | Streaming | Netflix, Prime Video, HBO Max, Disney+ |
| 📚 | Books | Lançamentos, bestsellers, recomendações |

*Cultura, Música e Festas são apresentadas numa única secção — não separar.*

### 9.2 TV Desportivo — regras por modalidade

**Futebol:** Portugal: TODOS os jogos · Brasil: TODOS os jogos · Mundial de futebol (a cada 4 anos): o torneio acompanha-se POR INTEIRO, todas as fases e todas as selecções · Champions League: apenas playoffs, semi-finais e final. Canais: Sport TV · LiveModeTV YouTube · RTP/SIC/TVI.

**Ténis:** Roland Garros / Wimbledon / US Open / Australian Open: quartas-de-final em diante, masculino apenas. Canais: Eurosport (Sport TV) · HBO Max.

**Olimpíadas:** evento de grande interesse — cobertura alargada: abertura, fases finais e provas em destaque do período.

Fora destes, o Rafa não acompanha outras modalidades regularmente (fonte das preferências: `Rafa_profile.md`, Secção 8). Quando nenhum destes torneios está a decorrer, a secção TV desportivo reduz-se naturalmente aos jogos de Portugal/Brasil.

Para cada evento TV: hora exacta em Lisboa, canal(is) em Portugal, sports bar sugerido.

### 9.3 Com quem (etiquetar sempre)
🏃 Solo/amigos · 👑 Com Vanessa · 🧒 Com Clara · 🐕 Com Pub e Dexter (dog-friendly obrigatório)

### 9.4 Avaliação · Preço · Urgência · Plataforma
⭐⭐⭐/⭐⭐/⭐ · 🟢 Grátis/🟡 Barato/🔴 Caro mas vale · ✅ Confirmado/🔶 Pendente/🕓 Waiting List/⏰ Prazo curto · Streaming: Netflix/Prime/HBO antes de Disney+

---

## 10. JSON OUTPUT (CANÓNICO)

```json
{
  "meta": {},
  "sources": {},
  "event_candidates": [],
  "events": [],
  "futuro_guardado": [],
  "summary": {},
  "validation": {}
}
```

`futuro_guardado[]` é novo na v5.3 — ver schema próprio no fim desta secção.

### 10.1 Schema de cada objecto em `events[]`

```json
{
  "id": "ev001",
  "category": "tv",
  "title": "Final da Champions League",
  "date": "2026-06-27",
  "date_inicio": null,
  "date_fim": null,
  "date_label": "Sáb 27 Jun",
  "time": "20:00",
  "location": null,
  "description": "Transmissão da final, com pré-jogo a partir das 19h.",
  "with_tags": [],
  "rating": null,
  "price_badge": null,
  "status_badge": "Destaque",
  "platform": null,
  "channel": "RTP1",
  "logistics": {"distance_min": 8, "via": "Av. Lusíada", "parking_status": "facil"},
  "link": null,
  "highlight": false,
  "confirmed": false,
  "saved": false,
  "elevado": false,
  "elevado_expira_label": null
}
```

**Campos obrigatórios (`REQUIRED_EVENT_FIELDS`):** `id`, `category`, `title`, `date_label`, `description`, mais a presença explícita da chave `date`. Para `streaming`, `books`, `gastro` e `escape` evergreen, `date` pode ser `null`; esses itens ficam fora do calendário. Nas restantes categorias, a data factual continua obrigatória. Nunca usar data-placeholder.

**Campos opcionais (v2–v5 — Jul/2026):** `highlight` (booleano; marca o evento para também aparecer na aba "Highlights"); `confirmed` (booleano; presença confirmada no calendário — destaque no topo de Meetup/Cultura); `saved` (booleano; item lido da pasta "Guardados da Agenda", Secção 0.3 — destaque no topo de Livros/Escapadinhas/Streaming).

**Campos opcionais novos (v5.3 — Ago/2026, ver Secção 8.1 e 0.5):**
- `date_inicio` / `date_fim` (string `YYYY-MM-DD`\|null) — só preencher quando o evento ocupa vários dias seguidos (ex.: uma feira de 3 dias); nesse caso aparece no calendário expansível em TODOS os dias do intervalo. Deixar `null`/omitir para eventos de um dia só (o calendário usa `date` como fallback).
- `elevado` (booleano) / `elevado_expira_label` (string\|null) — preenchidos pela LLM quando o Filter Layer (Secção 8.1) encontra uma linha `elevar` válida na `espelho_lazer` para este item. Nunca definir manualmente fora desse fluxo.

**Categorias válidas:** `tv`, `streaming`, `cinema_indoor`, `cinema_outdoor`, `meetup`, `culture`, `books`, `gastro`, `escape`, `radar`.

### 10.2 — `meta` (campos novos v5.3, para o calendário expansível)

| Campo | Tipo | Descrição |
|---|---|---|
| `periodo_inicio` | string `YYYY-MM-DD` | primeiro dia do período gerado (Secção 1) |
| `periodo_fim` | string `YYYY-MM-DD` | último dia do período gerado |
| `hoje` | string `YYYY-MM-DD` | data real de hoje (Passo Zero) — usada só para destacar o dia actual no calendário |
| `calendario_pessoal` | `[{"date": "YYYY-MM-DD", "compromissos": ["texto curto", ...]}]` | compromissos reais do Rafa por dia, capturados na Secção 3 |

Sem `periodo_inicio`/`periodo_fim`, o Render Layer simplesmente omite o bloco de calendário (nunca falha nem inventa datas) — só preencher quando tiveres a certeza das duas datas.

### 10.3 — `futuro_guardado[]` (novo v5.3)

```json
{
  "title": "O Regresso",
  "category": "streaming",
  "data_guardado": "2026-08-15",
  "nota": "Netflix"
}
```

Um objecto por linha `guardado_futuro` ainda activa na `espelho_lazer` (Secção 8.1, passo 3) — nunca um evento novo desta geração. `nota` é opcional, texto livre curto (ex. a plataforma). Omitir o campo `dedup_key` — o Render Layer recalcula-o a partir de `title`+`category`.

---

## 11. VIEW TEMPLATE (camada intermédia — render model)

```json
{
  "layout": {"sections": ["tv", "cinema", "meetup", "culture", "gastro", "escape", "books", "streaming", "radar"]},
  "render_rules": {"group_by_type": true, "show_logistics": true, "show_with": true, "show_source": false},
  "ui": {"density": "high", "sorting": "score_desc"}
}
```

### 11.1 Logística
Cada evento presencial inclui linha de transporte: `🚗 [X] min via [Via] | [emoji] Parking: [estado]`. Base: Carnide. ✅ fácil/gratuito · 🟡 pago/difícil · 🔴 muito difícil — sugerir uber/metro/bicicleta. Bicicleta: nunca para o hospital; sugerir para destinos difíceis de estacionar se bom tempo.

### 11.2 Botões de partilha
"Mais info →" (navy outline) · "💬 Partilhar" (verde WhatsApp) · "📧 Email" (azul outline). Cards de gastronomia aparecem APENAS na secção Gastro.

### 11.3 Estilo
Fontes: Fraunces (títulos) + DM Sans (corpo). Paleta: creme `#F5F0E8` · navy `#1A3D52` · terracota `#C75A2C`. Mobile-first · JavaScript puro · Stripe de cor 4px no topo por categoria.

### 11.4 Estrutura HTML obrigatória (ordem)
1. Header fixo sticky 2. Banner urgente 3. Filtros sticky (inclui aba "Highlights") 4. Banner de viagem 5. Cards de eventos por secção 6. Secção Gastro 7. Secção Escapadinhas 8. Secção Radar

**NOVO v5.3 — dentro da secção Highlights especificamente:** bloco de calendário expansível logo a seguir ao título da secção (antes do grid de cards) e bloco "Guardado para o futuro" no fim da secção (depois do grid de cards) — ambos mecânicos, construídos pelo `render.py` a partir de `meta.periodo_inicio`/`periodo_fim`/`calendario_pessoal` e `futuro_guardado[]` respectivamente; nenhum dos dois é escrito pela LLM. Todos os cards (todas as secções, não só Highlights) ganham também quatro ícones de curadoria (✕ remover · ⬆ elevar · 🕒 guardar para o futuro · ✅ já experimentei — NOVO v5.4) numa linha própria por baixo dos botões existentes — ver `apps_script_espelho_lazer.gs` e Secção 0.5 para o mecanismo de gravação.

**NOVO v5.4 — alinhamento do calendário:** a grelha do calendário expansível segue o MESMO padrão já usado no calendário do Briefing — 1ª coluna sempre segunda-feira, última sempre domingo, com células vazias (invisíveis, só ocupam espaço) a preencher os dias antes de `meta.periodo_inicio` conforme o seu dia da semana real. Isto é inteiramente mecânico no `render.py` (`build_calendario_dias`) — a LLM não precisa de fazer nada de diferente ao preencher `meta.periodo_inicio`/`periodo_fim`/`calendario_pessoal`, só não deve assumir que o calendário renderizado começa visualmente no primeiro dia do período.

---

## 12. PUBLICAÇÃO — via Rotina de Publicação (partilhada)

A LLM produz **apenas o JSON canónico** (Secção 10) — única camada de julgamento. Todo o resto (render determinístico com o template e render.py da Lazer, escrita no GitHub em `agendas/lazer/index.html`, confirmação com o link Cloudflare) é executado pela **Rotina de Publicação v1.6** — **ID: `14Jo-H5fVsMBCk2jv447ck8nfH54jWZGB`** — invocada com `modulo: lazer` + a data confirmada no início da corrida. Os IDs de template/render e caminhos vivem exclusivamente no mapa da Rotina — não os duplicar aqui. O token GitHub é tratado exclusivamente pela Rotina (lido de `github_token.md`); este ficheiro não contém nem referencia segredos. ⚠️ Desde a v1.6 (22 Jul 2026) já não se grava cópia do HTML em Relatorios/Agenda — a rotina termina no GitHub.

**Regras locais da Lazer (não cobertas pela Rotina):**
1. Na rotina LOCAL 6.0, a publicação automática está permanentemente autorizada pelo Rafa. Depois de um postflight sem publicação com código 0, `go_lazer_llm.bat` deve chamar o postflight com `--publish`, sem pedir confirmação.
2. Falha de validação, render ou GitHub aborta a publicação e fica registada no log. Nunca contornar o postflight nem publicar HTML incompleto.

---

## 13. DEBUG VIEW (obrigatório, sempre gerado)

```text
FONTES
- calendar / gmail / web / meetup-luma / cinema / streaming / books / gastro / escapes

CALENDÁRIO (procedimento: doc "Leitura de Calendário" v1.0)
- ferramenta usada: Google Calendar:list_events (nunca event_search_v0)
- calendários consultados (IDs/nomes)
- resultado final: verificado com sucesso / sem eventos confirmado / falha de leitura

GMAIL (obrigatório registar mesmo se vazio)
- queries executadas (label:events 15d · luma/meetup 14d)
- threads relevantes encontrados: X
- eventos extraídos para candidatos: X

DESPORTO (obrigatório registar mesmo se inconclusivo)
- fontes tentadas (lu.ma/activehive, web_search, etc.)
- sessões confirmadas vs. recorrentes inferidas do perfil
- nunca "secção omitida" sem justificação aqui

EXPANSION
- meetup: X candidatos
- cinema indoor: X candidatos (com sinopse: sim/não)
- cinema outdoor: X sessões (programação completa, com sinopse: sim/não)
- web: X eventos
- streaming: X conteúdos (por plataforma)
- books: X livros
- gastro: X candidatos
- escapes: X candidatos

FALLBACK (se ativado)
- nível 1/2/3 — por categoria, com motivo

FILTER
- removidos: X, razão de cada remoção
- cinema indoor fora do perfil: X títulos (resumidos, não descartados)

RESULTADO FINAL
- eventos por categoria
- densidade final (vs. minimum thresholds da Secção 5) — sinalizar QUALQUER categoria abaixo do mínimo em maiúsculas
```

---

## 14. SECÇÃO RADAR

Eventos FUTUROS (fora das próximas 2 semanas) que não se podem perder: bilhetes já comprados · estreias de séries importantes · shows/festivais com bilhetes à venda · torneios majors em fase decisiva (Mundial de futebol, Grand Slams quartas+ masculino, fases finais da Champions, Olimpíadas) · NOS Alive, Cool Jazz, outros festivais de verão.

**Lista Sazonal (`Lista_Sazonal.json`, Secção 0.4):** incluir no Radar qualquer entrada cuja `epoca` caia dentro dos próximos 60 dias a partir de hoje. Para as que tiverem `reserva_antecipada: true`, destacar o `aviso_ideal` como o ponto principal do item (ex.: "bilhetes abrem em Maio — não perder o prazo, como aconteceu em 2026"), não uma nota lateral. Para as `reserva_antecipada: false`, apresentar normalmente (época + `observacoes`, se houver).

---

## 15. SECÇÃO ESCAPADINHAS

Incluir sempre o mínimo de 6 da Secção 5. Cada uma com: destino · distância · actividades · com quem · clima ideal · logística · link.

---

## 16. REGRAS TRANSVERSAIS

- Fonte dos perfis: SEMPRE ir à pasta SSoT no Drive (`1KAVv-gCiCGGlZNvxgVLvx3SuKRRZ-hzC`) — NUNCA usar memória local. IDs na Secção 0.
- **Princípio fundamental (Secção 2):** nunca filtrar antes de expandir
- **Minimum thresholds (Secção 5):** chão obrigatório — nunca sair abaixo deles sem registar no Debug View (nota de eficiência: em observação de custo pós-auditoria)
- **JSON canónico é a única camada de julgamento** (Secção 10) — render e publicação são mecânicos, via Rotina de Publicação (Secção 12)
- **Calendário (Secção 3):** procedimento no doc partilhado "Leitura de Calendário"; sempre `Google Calendar:list_events`
- **Gmail (Secção 4.2) e Desporto (Secção 4.4):** OBRIGATÓRIOS, nunca pular
- **Cinema indoor (Secção 4.5):** sempre com sinopse, elenco e horários reais via cinecartaz.publico.pt
- **Streaming:** só Netflix/Prime Video/HBO Max/Disney+
- **Curadoria do Rafa (Secção 8.1, v5.3/LOCAL):** consultar `espelho_lazer` no preflight via CSV antes de fechar `events[]` — remover/elevar/incluir em `futuro_guardado[]`/excluir consumidos; nunca gravar consumidos no Feedback_log pela LLM

---

## 17. ✅ CHECKLIST DE AUTO-VERIFICAÇÃO OBRIGATÓRIA

> 🚨 Antes de apresentar QUALQUER output ao Rafa, confirmar item a item esta lista, explicitamente, no Debug View. Não é suficiente "ter seguido" as instruções de memória — cada item tem de ser verificado contra o JSON canónico já produzido. Se algum item falhar, voltar ao Fallback Expansion (Secção 6) antes de apresentar.

1. [ ] Calendário consultado segundo o doc "Leitura de Calendário" (via `Google Calendar:list_events`, nunca `event_search_v0`) — resultado registado no Debug View
2. [ ] Gmail consultado (Secção 4.2) — pelo menos as 2 queries obrigatórias executadas, resultado registado
3. [ ] Desporto: pelo menos 1 evento/sessão na categoria, com fonte registada (Secção 4.4) — categoria NUNCA vazia
4. [ ] Cinema indoor: ≥4 candidatos, TODOS com sinopse + elenco + horários reais (não inventados)
5. [ ] Cinema outdoor: programação completa do período, TODOS com sinopse
6. [ ] Gastro: ≥5 candidatos + todas as recomendações de terceiros do feedback_log
7. [ ] TV+Streaming: ≥10 no total combinado
8. [ ] Escapadinhas: ≥6
9. [ ] Meetup/Web events: ≥8 / ≥12 respectivamente
10. [ ] Nenhum local com `status: excluded` ou `never_again: true` presente (verificar variantes de nome)
11. [ ] Nenhum filme indoor fora do perfil foi omitido — todos aparecem na lista resumida
12. [ ] Publicação delegada à Rotina de Publicação — nenhum segredo (token) em texto plano em qualquer output ou ficheiro
13. [ ] Cada categoria abaixo do mínimo (se houver) está sinalizada em maiúsculas no Debug View, com motivo
14. [ ] `espelho_lazer` consultada pelo preflight — removidos excluídos, elevados com `highlight`/`elevado` forçados e ainda dentro do prazo, `futuro_guardado[]` reflecte as linhas `guardado_futuro` activas, `consumido` excluído de `events[]`, `limpo` neutralizado (NUNCA gravar consumidos no Feedback_log pela LLM — isso é exclusivo do `merge_feedback.py` local)
15. [ ] **(v5.3)** Se `meta.periodo_inicio`/`periodo_fim` forem preenchidos, `meta.calendario_pessoal` também está — nunca um sem o outro

---

## Registo de Alterações

| Versão | Data | Alteração |
|---|---|---|
| LOCAL 5.5a | 28 Ago 2026 | **Consolidação da curadoria via sheet.** Botão antigo "Salvar" / Zapier aposentado nos renders futuros; "Guardar para o futuro" continua via `espelho_lazer`. HTML passa a permitir desfazer clique acidental: clicar de novo no botão ativo grava `limpo`, e o preflight trata `limpo` como estado neutro. `preflight_lazer.py` passa a aceitar `--espelho-lazer-csv`, aplicar `removido`/`consumido`, elevar itens e montar `futuro_guardado[]`. `merge_feedback.py` passa a perguntar, para cada `consumido`, se deve guardar no Feedback_log e qual nota usar; também prepara CSV limpo mantendo só `elevar` e `guardado_futuro`. Nenhuma publicação/commit/push nesta alteração. |
| 5.5 | 22 Ago 2026 | **Reversão: nota/pontuação deixa de ser pedida no browser.** O Rafa esclareceu que a v5.4 (pedido de nota via `window.prompt` no clique do ícone ✅) não era o desenho pretendido — a pergunta devia sempre ter sido feita numa rotina Python LOCAL, fora de qualquer sessão Claude. (1) Secção 0.5: clique em ✅ volta a gravar `consumido` de imediato, sem perguntar nada; coluna `nota` da sheet fica sempre vazia. Novo ficheiro `merge_feedback.py` (mesmo padrão do `preflight_hff.py`/`postflight_hff.py` — sem API Google, só ficheiros locais) que o Rafa corre na própria máquina: varre `consumido` da `espelho_lazer` (export CSV) + pasta "Guardados da Agenda", pergunta nota (0-5, opcional) e comentário (opcional) — sempre pergunta, responder é que é opcional — e grava directo no Feedback_log.json local. (2) Secção 8.1 passo 4 revisto: a LLM NUNCA mais escreve no Feedback_log.json a partir de uma linha `consumido` (evita duplicar o trabalho do `merge_feedback.py`) — só exclui o candidato de `events[]`, não permanente. (3) Checklist item 14 actualizado. Templates promovidos: `template_v9.html`/`render_v8.py`. Nenhum threshold, fonte ou filtro de perfil pré-existente foi alterado. |
| 5.4 | 22 Ago 2026 | **Feedback do Rafa pós-teste real (primeira geração de ponta a ponta, "gera a agenda de lazer").** (1) Calendário expansível (Secção 11.4): grelha corrigida para o mesmo padrão do Briefing — 1ª coluna sempre segunda, última domingo, células vazias a preencher o início conforme o dia da semana real de `periodo_inicio`. Puramente mecânico no `render.py`/`template.html` (v7/v8) — nenhuma mudança no JSON canónico. (2) Secção 0.5: `espelho_lazer` ganha 8ª coluna `nota` (auto-reparada no cabeçalho pelo Apps Script); acção `consumido` passa a estar disponível também num ícone ✅ em qualquer card normal (não só no bloco "Guardado para o futuro"), pedindo sempre nota/pontuação no clique. (3) Secção 8.1 passo 4: ao converter `consumido` em Feedback_log, usar a `nota` da sheet directamente (nunca adivinhar se vier preenchida). Nenhum threshold, fonte ou filtro de perfil pré-existente foi alterado. |
| 5.3 | 22 Ago 2026 | **Curadoria do Rafa + calendário expansível (pedido do Rafa, sessão "ícones de curadoria").** Motivo: selecção de Highlights não estava a acertar bem no perfil dele — em vez de só afinar critérios, ganhou mecanismo para ele curar directamente na página publicada. (1) Nova Secção 0.5: sheet `espelho_lazer` (append-only, mesmo padrão do Espelho HFF), gravada via Apps Script a partir de 3 ícones novos em todos os cards (✕ remover · ⬆ elevar · 🕒 guardar para o futuro) — paralelo ao "Salvar"/Zapier existente, sem lhe mexer. (2) Nova Secção 8.1 (Filter Layer): ler `espelho_lazer` antes de fechar `events[]` — `removido` exclui por `dedup_key` (permanente até apagar a linha), `elevar` força `highlight`/`elevado` até expirar (data própria ou 14 dias), `guardado_futuro` entra em `futuro_guardado[]` (novo campo top-level, não é `events[]`), `consumido` grava directo no Feedback_log.json. (3) Secção 10.1 ganha `date_inicio`/`date_fim` (eventos multi-dia) e `elevado`/`elevado_expira_label`; novas Secções 10.2 (`meta.periodo_inicio`/`periodo_fim`/`hoje`/`calendario_pessoal`) e 10.3 (`futuro_guardado[]`). (4) Secção 3 (calendário) passa também a capturar compromissos reais do período inteiro para `meta.calendario_pessoal`, não só as flags de disponibilidade. (5) Secção 11.4: bloco de calendário expansível (clicar num dia mostra sugestões + compromissos lado a lado, com link para o card) no topo da secção Highlights, bloco "Guardado para o futuro" no fim dela — ambos mecânicos, no `render.py`/`template.html` (v6/v7, ver `ROTINA_PUBLICACAO.md`). (6) Checklist (Secção 17) ganha os itens 14-15. Nenhum threshold, fonte ou regra de filtro de perfil pré-existente foi alterado. |
| 5.2 | 22 Jul 2026 | **Pedido do Rafa: fim da cópia do HTML no Drive.** Secção 12 e o pipeline (Secção 2) deixam de mencionar cópia/Drive — a publicação termina no GitHub, alinhada com a Rotina de Publicação v1.6. Motivo: trabalho duplicado sem uso, o único acesso real às páginas é via Cloudflare. Nenhum threshold, trigger ou ID de dados foi alterado. |
| 1.0–4.6 | Mai–25 Jun 2026 | Histórico anterior: SSoT centralizada; Expansion Architecture; correcções de ID; event_search_v0 → list_events; token GitHub removido do texto (v4.6); reforços de execução (Gmail/Desporto/Cinema obrigatórios) e criação do Checklist após a corrida falhada de 25 Jun/2026 — cuja causa foi ausência de verificação final, não de instrução. |
| 5.0 | 2 Jul 2026 | **Auditoria de forma (sessão Lazer).** (1) Secção 3: procedimento de calendário delegado ao doc partilhado "Leitura de Calendário" v1.0 (`1UIH2nUdz5867satNKiWUq0KyLYQHWWlm`); na Lazer ficam só janela de 15 dias, flags de disponibilidade e linha defensiva anti-`event_search_v0`. (2) Antigas Secções 12+16 colapsadas na nova Secção 12: publicação integral via Rotina de Publicação v1.3 (`14Jo-H5fVsMBCk2jv447ck8nfH54jWZGB`); código Python, IDs de template/render e toda a mecânica do token saem deste ficheiro (antiga Secção 0.3 removida — o token é responsabilidade exclusiva da Rotina). (3) Gmail: query `label:events` passa de 30d para **15d** (decisão do Rafa); query Luma/Meetup mantém 14d. (4) Desporto TV: removidas as referências datadas ao Mundial 2026; nova regra perene de confirmação de fase via web_search para torneios majors; Secção 9.2 corrigida às preferências reais — **Mundial de futebol acompanha-se por inteiro** (não só a partir das eliminatórias) e Olimpíadas com cobertura alargada. (5) Secção 5: nota de observação de eficiência dos thresholds (avaliar custo via tabela de custo/diagnóstico do v6.1 nas execuções orquestradas pelo Dashboard; ajustes são decisão do Rafa). (6) Notas históricas "(v4.6)" comprimidas neste registo; Secção 17 antiga enxugada (agora 16); Checklist renumerado para Secção 17, item 12 reformulado. Nenhum threshold, trigger, fonte ou ID de dados foi alterado além do descrito. |
| 5.1 | 12 Jul 2026 | **Botão "Salvar" + pré-fetch de Streaming/Livros (reconciliação de conflito de sincronização do Drive).** (1) Secção 0.3 reutilizada para a pasta "Guardados da Agenda" (ID `1SsDDXwmzbhYMEKbZOjJ2RmNWV5t_R6j5`) — itens que o Rafa guarda a partir da página publicada entram na próxima geração com `saved:true`. (2) Secção 10.1: schema ganha `highlight`, `confirmed` e `saved` (booleanos); JSON de exemplo corrigido (faltava vírgula). (3) Secção 11: `render_rules` perde `max_description_length` (contradizia o pedido de sinopses completas); Secção 11.4 remove "Dashboard visual" (eliminado) e inclui a aba "Highlights". (4) Secções 4.6/4.7 (Streaming/Books) ganham MODO 1 (ficheiro JSON pré-gerado em `websearch_streaming`/`websearch_livros`) + MODO 2 (fallback `web_search`), mesmo padrão do Gmail/Cinema — elimina a pesquisa ao vivo cara para estas categorias. (5) Corrigidos erros de sincronização introduzidos por edição concorrente no Drive (ficheiro chegou a bifurcar em duas cópias): ID da pasta "websearch_cinema" restaurado para `1WnWE-rNGokSJNlF5qumuvucGGjMRHk6J` (tinha sido corrompido para um `S` a mais nalguma altura); três erros de "música"/pontuação corrigidos; frase de linha defensiva do calendário (Secção 3) restaurada. A cópia duplicada "(conflict ...)" gerada pelo Drive foi descartada — este ficheiro passa a ser a única fonte. Nenhum threshold, trigger ou ID de dados foi alterado além do descrito. |
