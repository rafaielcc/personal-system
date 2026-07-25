/* Personal Development OS — lógica partilhada das páginas de semana (Camada 2).
   Recolhe os campos marcados com [data-field-label], monta o bloco de texto
   e copia para a área de transferência via navigator.clipboard.writeText. */
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

  function buildBlock(marker, extraLines){
    var dateEl = document.getElementById('entry-date');
    var date = (dateEl && dateEl.value) ? dateEl.value : today();
    var week = document.body.getAttribute('data-week');
    var title = document.body.getAttribute('data-title');
    var lines = [];
    lines.push('[' + marker + ']');
    lines.push('Data: ' + date);
    lines.push('Semana ' + week + ' — ' + title);
    if (extraLines) extraLines.forEach(function(l){ lines.push(l); });
    lines.push('');
    collectFields().forEach(function(f){
      lines.push(f.label + ': ' + f.value);
    });
    return lines.join('\n');
  }

  function copyToClipboard(text, feedbackId){
    navigator.clipboard.writeText(text).then(function(){
      var fb = document.getElementById(feedbackId);
      if (fb){
        fb.textContent = 'Copiado!';
        fb.classList.add('show');
        setTimeout(function(){ fb.classList.remove('show'); }, 2400);
      }
    }).catch(function(){
      var fb = document.getElementById(feedbackId);
      if (fb){
        fb.textContent = 'Não foi possível copiar — copia manualmente.';
        fb.classList.add('show');
      }
    });
  }

  window.PDOS = {
    guardarInputDia: function(){
      copyToClipboard(buildBlock('INPUT DIÁRIO'), 'fb-guardar');
    },
    fecharSemana: function(){
      copyToClipboard(buildBlock('FECHO DE SEMANA', ['Estado: semana concluída — avançar para a próxima']), 'fb-fechar');
    }
  };

  document.addEventListener('DOMContentLoaded', function(){
    initScales();
    initDateDefault();
  });
})();
