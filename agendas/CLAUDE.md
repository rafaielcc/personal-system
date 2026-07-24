# Projecto Agenda — contexto para Claude Code

Este repositório (`rafaielcc/personal-system`) é onde o projecto **Agenda** publica as suas páginas. A Agenda é um sistema pessoal de rotinas do Rafa (Briefing diário, Painel de trabalho no Hospital Fernando Fonseca, Agenda de Lazer, Dashboard) que corre normalmente via Claude Projects (claude.ai) e cujo output final — HTML estático — é publicado neste repo (pasta `agendas/`) e servido pelo Cloudflare Pages. As rotinas de cada módulo (o "como fazer") vivem como documentos de instrução no Google Drive, não neste repo — este repo só recebe os outputs publicados e os scripts de render.

**Porque correr também via Claude Code:** as sessões de claude.ai (app normal) têm cortado rotinas longas a meio por limite de tokens por mensagem, sobretudo nas rotinas que geram HTML. O Code tem-se mostrado mais fiável a completar rotinas inteiras e a publicar no GitHub sem cortar etapas. Mas uma sessão nova do Code, ao contrário de uma conversa em claude.ai, **não tem nenhum contexto deste projecto por omissão** — não sabe o que é a Agenda, onde ficam as instruções, nem a convenção de nomes. Este ficheiro existe para resolver isso.

## ⚠️ Leitura obrigatória antes de qualquer rotina

O Code não tem o system prompt do projecto Agenda em claude.ai carregado em contexto (isso só existe dentro da conversa em claude.ai, não é replicável automaticamente aqui). Por isso, **antes de correr qualquer rotina a partir do Code, é obrigatório ler primeiro** o ficheiro de perfil/contexto geral do projecto:

> **`SYSTEM_PROMPT_v6.1_FINAL.md`** — pasta Drive `15Ge84lmsAeoUgSXDWFpcW26X-UCixrbg` (procurar pelo nome, usar a cópia de `createdTime` mais recente se houver mais do que uma).

Isto aplica-se **mesmo que o documento de instruções da própria rotina diga que não é preciso** ler mais nada antes de activar — essa instrução assume que já estás numa conversa em claude.ai com o system prompt do projecto já carregado, o que nunca é verdade numa sessão nova do Code. O `SYSTEM_PROMPT_v6.1_FINAL.md` tem a arquitectura do projecto (onde vivem as instruções vs. onde vivem os dados), a Rotina de Publicação partilhada, a Leitura de Calendário partilhada, e um resumo de cada módulo — é o que dá ao Code o mesmo chão que uma conversa em claude.ai já tem.

## Pasta Drive das instruções

Todos os documentos de instrução dos módulos da Agenda (e o `SYSTEM_PROMPT_v6.1_FINAL.md`) vivem directamente na raiz desta pasta — **não em subpastas**:

> `15Ge84lmsAeoUgSXDWFpcW26X-UCixrbg`

(A pasta-mãe de todos os projectos do Rafa, `1KAVv-gCiCGGlZNvxgVLvx3SuKRRZ-hzC`, é onde ficam ficheiros partilhados entre projectos como `Rafa_profile.md` e `Feedback_log.json` — os IDs exactos desses ficheiros já estão documentados dentro de cada rotina/no system prompt; não precisas de os procurar à parte.)

## Convenção de nomes dos ficheiros de instrução

- Padrão: `NOME_DA_ROTINA_v<X.Y>.md`, maiúsculas com underscores, direto na raiz da pasta acima.
- **O Drive não edita ficheiros in-place** — uma actualização cria sempre um ficheiro novo (nova versão ou o mesmo nome outra vez), sem apagar automaticamente o antigo. Por isso, ao procurar o ficheiro de uma rotina, **pode haver mais do que uma cópia com títulos parecidos** (mesma versão, versões diferentes, ou por vezes até "(conflict ...)" no nome de um conflito de sincronização do Drive). **Usar sempre a cópia com `createdTime` mais recente**, salvo indicação em contrário abaixo.
- Excepção actual: a **Agenda de Lazer** está em auditoria/reestruturação activa e o Rafa está deliberadamente a manter o ficheiro sem sufixo de versão no nome (só `AGENDA_LAZER_INSTRUCOES.md` ou equivalente, apagando as versões antigas conforme avança) — não assumir um nome fixo com número de versão para este módulo, procurar por título a começar por `AGENDA_LAZER_INSTRUCOES` e usar o mais recente.

## Comandos disponíveis (skills)

| Pedido do Rafa (exemplos) | Skill | Rotina no Drive | Publica em |
|---|---|---|---|
| "dashboard", "gera o dashboard", "atualiza o dashboard", "home" | `dashboard` | `INSTRUCOES_DASHBOARD_v10.0.md` | `agendas/index.html` |
| "bom dia", "briefing", "gera o briefing", "briefing para amanhã" | `briefing` | `BRIEFING_DIARIO_v12.1.md` (ou mais recente) | `agendas/briefing/index.html` |
| "agenda de lazer", "eventos em Lisboa", "o que há para fazer" | `agenda-de-lazer` | `AGENDA_LAZER_INSTRUCOES*` (mais recente, sem sufixo fixo — ver nota acima) | `agendas/lazer/index.html` |
| "painel hff", "agenda de trabalho", "cirurgias hoje", "lista bo" | `agenda-de-trabalho` | `INSTRUCOES_PAINEL_HFF_v5.0.md` | `agendas/Hff/index.html` + `agendas/BO/index.html` |
| "artigos científicos", "gera os artigos", "/artigos" | `artigos` | `INSTRUCOES_ARTIGOS_v1.0.md` (ou mais recente) | `agendas/artigos/index.html` |

## Padrão de publicação (todos os módulos)

Nenhum módulo escreve HTML directamente. Cada um produz **apenas um JSON canónico** (o esquema está na Secção 7/11 do respectivo documento de instruções); um `render.py` (stdlib Python, sem dependências) lê esse JSON + um `template.html` e gera o HTML final por substituição mecânica de texto. Os templates e scripts de render vivem no Drive, pasta `Templates` (subpasta por módulo: `Briefing/`, `hff/`, `bo/`, `dashboard/`, `agenda_lazer/`). O que acontece depois do render (commit/push, e se há ou não cópia no Drive) está descrito em **`ROTINA_PUBLICACAO_v1.5.md`** (mesma pasta de instruções, com o mapa completo módulo → IDs de template/render/caminho GitHub) — **não replicar esses detalhes aqui nem nos skills**, esse documento é a única fonte de verdade e pode mudar sem aviso (ex: o Rafa está a considerar deixar de gravar cópia no Drive, já que a publicação no GitHub já se mostrou fiável).

Este padrão existe precisamente para evitar o problema que motivou correr via Code: a LLM nunca escreve o HTML inteiro de uma figura só, o que era a causa directa de rotinas a cortar a meio por tecto de tokens.

## Estrutura publicada neste repo

```
agendas/
  index.html          ← Dashboard (Módulo 5, raiz)
  briefing/index.html ← Briefing Diário (Módulo 1)
  Hff/index.html       ← Painel HFF pessoal (Módulo 4)
  BO/index.html         ← Lista cirúrgica da equipa (Módulo 4, face pública)
  lazer/index.html     ← Agenda de Lazer (Módulo 2)
  noticiasB3/          ← gerado por outro projecto, só verificado aqui
  artigos/index.html   ← Artigos Científicos (trigger próprio, ver nota abaixo)
```
Nomes de pastas em maiúscula/minúscula têm de respeitar exactamente o que está acima (`Hff`, `BO` maiúsculas; `briefing`, `lazer` minúsculas) — o Cloudflare serve tudo case-insensitive, mas o GitHub não, e uma caixa errada cria pasta duplicada.

## Módulo Artigos Científicos

Mesmo padrão de accionamento dos outros módulos (frase-gatilho na skill `artigos`, ou o Dashboard aciona a rotina directamente dentro do seu próprio ciclo, tal como já faz com a Notícias do Dia): o Dashboard, na sua orquestração de frescura, verifica se `agendas/artigos/index.html` foi publicado há mais de 7 dias — se sim, acciona a rotina Artigos nesse mesmo ciclo (sem perguntar ao Rafa, tal como as outras regras de janela expirada); se não, não faz nada. A extração de e-mails/PDF é feita por um script Python fora do LLM (`scripts/gmail_articles_briefing/` neste repo, com cópia de execução em Drive — ver `INSTRUCOES_ARTIGOS` secção 4, versão mais recente). Detalhe completo da rotina: skill `artigos`.
