---
name: consultar-sazonal
description: Use quando o Rafa pedir "consultar sazonal", "o que tenho sazonal agora", "lista sazonal", ou perguntar directamente no chat (fora de gerar uma Agenda de Lazer completa) que eventos/actividades recorrentes anuais estão próximos. Mostra só os itens relevantes do mês actual + mês seguinte, sem gerar a agenda completa nem publicar HTML.
---

# Skill: Consultar Sazonal (Agenda de Lazer)

## Passos

1. Descarregar `Lista_Sazonal.json` pelo Drive ID fixo `1K307L5u7Ftl0fRRnX11FGA245kFzUzgQ` (`download_file_content` por `fileId` directo — nunca procurar por pasta, o Rafa move este ficheiro livremente).
2. Filtrar as entradas cuja `epoca` cai no mês actual ou no mês seguinte (usar a data de hoje da sessão).
3. Apresentar directamente no chat — nome, época, se precisa de reserva antecipada e, se sim, o `aviso_ideal`; incluir `observacoes` quando forem relevantes. Ordenar por proximidade (mês actual antes do mês seguinte).
4. Se não houver nenhum item nos próximos 2 meses, dizer isso claramente em vez de mostrar uma lista vazia sem contexto.
5. Não correr a rotina completa da Agenda de Lazer nem publicar nada — isto é só uma consulta pontual ao ficheiro.
