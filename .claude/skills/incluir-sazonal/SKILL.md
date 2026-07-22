---
name: incluir-sazonal
description: Use quando o Rafa disser "sazonal:", "incluir sazonal", "guarda isto na lista sazonal", ou mencionar um evento/actividade que se repete todos os anos na mesma época (feiras, desporto, festas) que quer lembrar para o futuro — sobretudo os que têm prazo de reserva antecipada de bilhete que ele já perdeu antes (ex.: Estoril Open). Não usar para eventos pontuais/não-recorrentes (isso é o Feedback_log normal) nem para pedidos de consulta (isso é o skill consultar-sazonal).
---

# Skill: Incluir Sazonal (Agenda de Lazer)

Este skill é um PONTEIRO — a lógica de preenchimento (o que pré-preencher a partir do que o Rafa disser, o que perguntar quando falta) vive na secção "Lista Sazonal" do documento de instruções da Agenda de Lazer, não aqui.

## Passos

1. Se [`agendas/CLAUDE.md`](../../../agendas/CLAUDE.md) deste repositório ainda não estiver em contexto, lê-lo primeiro.
2. No Drive, na pasta de instruções (ID `15Ge84lmsAeoUgSXDWFpcW26X-UCixrbg`), procurar o ficheiro `AGENDA_LAZER_INSTRUCOES*` mais recente (ver nota em `agenda-de-lazer/SKILL.md` sobre não haver sufixo de versão fixo neste módulo) e ler a secção "Lista Sazonal" — tem o schema completo dos campos e a regra de pré-preencher o que der para inferir, perguntando só o que faltar.
3. O ficheiro de dados é `Lista_Sazonal.json`, Drive ID fixo `1K307L5u7Ftl0fRRnX11FGA245kFzUzgQ`. Usar sempre este ID directamente (`download_file_content` por `fileId`) — nunca procurar por pasta, porque o Rafa move este ficheiro de pasta livremente e o ID não muda.
4. Como o Drive não edita ficheiros in-place, gravar a versão actualizada como um ficheiro novo com o mesmo título `Lista_Sazonal.json`, na mesma pasta onde está a cópia actual (`get_file_metadata` no ID acima para saber onde é). Confirmar ao Rafa em 1 linha o que foi guardado — é update directo, sem aprovação prévia, tal como o `Feedback_log.json`.
