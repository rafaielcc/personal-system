/* Personal Development OS — lógica partilhada das páginas de semana (Camada 2).
   Recolhe os campos marcados com [data-field-label] e oferece dois caminhos:
   "Copiar" (clipboard, para colar numa conversa e discutir ao vivo) e
   "Gravar" (POST silencioso para um endpoint — Apps Script ou Zapier — que
   grava um ficheiro em Inputs/ no Drive, processado no próximo fecho de
   semana). */
(function(){
  function today(){
    return new Date().toISOString().slice(0,10);
  }

  function initScales(){
    document.querySelectorAll('[data-scale-group]').forEach(function(group){
      group.querySelectorAll('button').forEach(function(btn){
        btn.addEventListener('click', function(){
          group.querySelectorAll('button').forEach(function(b){ b.classList.remove('sel'); });
          btn.classList.add('sel');
          group.dataset.value = btn.dataset.val;
        });
      });
    });
  }

  function initDateDefault(){
    var d = document.getElementById('entry-date');
    if (d && !d.value) d.value = today();
  }

  function collectFields(){
    var out = [];
    document.querySelectorAll('[data-field-label]').forEach(function(el){
      var label = el.getAttribute('data-field-label');
      var val;
      if (el.hasAttribute('data-scale-group')){
        val = el.dataset.value ? (el.dataset.value + ' / 5') : '(não respondido)';
      } else {
        val = el.value && el.value.trim() ? el.value.trim() : '(não respondido)';
      }
      out.push({label: label, value: val});
    });
    return out;
  }

  function currentDate(){
    var dateEl = document.getElementById('entry-date');
    return (dateEl && dateEl.value) ? dateEl.value : today();
  }

  function buildTextBlock(){
    var date = currentDate();
    var week = document.body.getAttribute('data-week');
    var title = document.body.getAttribute('data-title');
    var lines = [];
    lines.push('[INPUT DIÁRIO]');
    lines.push('Data: ' + date);
    lines.push('Semana ' + week + ' — ' + title);
    lines.push('');
    collectFields().forEach(function(f){
      lines.push(f.label + ': ' + f.value);
    });
    return lines.join('\n');
  }

  function buildPayload(){
    var fields = {};
    collectFields().forEach(function(f){ fields[f.label] = f.value; });
    return {
      marker: 'INPUT_SEMANA',
      date: currentDate(),
      week: document.body.getAttribute('data-week'),
      title: document.body.getAttribute('data-title'),
      fields: fields,
      source: 'personal_development_semana_html',
      origin: { platform: 'Personal Development OS', method: 'gravar_button' }
    };
  }

  function showFeedback(id, text){
    var fb = document.getElementById(id);
    if (fb){
      fb.textContent = text;
      fb.classList.add('show');
      setTimeout(function(){ fb.classList.remove('show'); }, 2600);
    }
  }

  window.PDOS = {
    copiar: function(){
      navigator.clipboard.writeText(buildTextBlock()).then(function(){
        showFeedback('fb-copiar', 'Copiado!');
      }).catch(function(){
        showFeedback('fb-copiar', 'Não foi possível copiar — copia manualmente.');
      });
    },
    gravar: function(){
      var url = window.PDOS_WEBHOOK_URL;
      if (!url){
        showFeedback('fb-gravar', 'Webhook ainda não configurado.');
        return;
      }
      var btn = document.getElementById('btn-gravar');
      if (btn){ btn.disabled = true; }
      /* mode:'no-cors' porque o recetor (Apps Script ou Zapier) não devolve
         cabeçalhos CORS — sem isto o fetch rejeitava mesmo quando o registo
         era gravado com sucesso do lado do servidor. Content-Type text/plain
         mantém o pedido como "simples", sem preflight. */
      fetch(url, {
        method: 'POST',
        mode: 'no-cors',
        headers: {'Content-Type': 'text/plain'},
        body: JSON.stringify(buildPayload())
      }).then(function(){
        showFeedback('fb-gravar', 'Guardado!');
        if (btn){ btn.disabled = false; }
      }).catch(function(){
        showFeedback('fb-gravar', 'Erro — tenta de novo.');
        if (btn){ btn.disabled = false; }
      });
    }
  };

  document.addEventListener('DOMContentLoaded', function(){
    initScales();
    initDateDefault();
  });
})();
