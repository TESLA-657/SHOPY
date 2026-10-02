(function(){
  const container = document.getElementById('toast-container');
  if(!container) return;

  function getCSRFToken(){
    const name = 'csrftoken';
    let value = null;
    if(document.cookie && document.cookie !== ''){
      document.cookie.split(';').forEach(c => {
        c = c.trim();
        if(c.substring(0, name.length+1) === (name + '=')){
          value = decodeURIComponent(c.substring(name.length+1));
        }
      });
    }
    return value;
  }

  // Marque la notification comme lue en base : sans cela elle
  // reapparait au prochain chargement de page et au polling.
  function markAsRead(id){
    if(!id) return;
    try{
      fetch(`/api/notifications/${id}/marquer-lue/`, {
        method: 'POST',
        headers: {'X-CSRFToken': getCSRFToken()},
        credentials: 'same-origin'
      }).then(r => r.json()).then(data => {
        if(data && typeof data.nb_non_lues === 'number'){
          // Met a jour le badge immediatement, sans attendre le polling.
          const badge = document.querySelector('.notif-fab-badge');
          if(badge){
            if(data.nb_non_lues > 0){
              badge.textContent = data.nb_non_lues;
              badge.style.display = 'flex';
            } else {
              badge.style.display = 'none';
            }
          }
        }
      }).catch(() => {});
    }catch(e){ /* silencieux : la fermeture visuelle reste prioritaire */ }
  }

  function createToast({id=null, title='Notification', body='', type='info', timeout=6000}){
    const el = document.createElement('div');
    el.className = `toast ${type}`;

    const icon = document.createElement('div');
    icon.className = 'icon';
    icon.textContent = type === 'success' ? '✓' : type === 'error' ? '✕' : 'i';

    const bodyWrap = document.createElement('div');
    bodyWrap.className = 'body';
    const t = document.createElement('div'); t.className='title'; t.textContent = title;
    const m = document.createElement('div'); m.className='msg'; m.textContent = body;
    bodyWrap.appendChild(t); bodyWrap.appendChild(m);

    const close = document.createElement('button');
    close.className='close';
    close.innerHTML='✕';
    close.setAttribute('aria-label','Fermer la notification');
    // Ferme visuellement tout de suite, puis signale a la base.
    // markDismissed DOIT etre appele ici : c'est lui qui empeche
    // la notification de reapparaitre au prochain chargement de page.
    close.addEventListener('click', ()=>{
      markAsRead(id);
      markDismissed();
      hide();
    });

    el.appendChild(icon); el.appendChild(bodyWrap); el.appendChild(close);

    let timeoutId;
    function hide(){
      el.classList.remove('show');
      setTimeout(()=> el.remove(),300);
      if(timeoutId) clearTimeout(timeoutId);
    }

    // Une notification lue (croix deja actionnee) ne doit pas
    // reapparaitre au prochain chargement : on memorise son id.
    function markDismissed(){
      if(!id) return;
      try{
        const key = 'shopy_notif_lues';
        const list = JSON.parse(localStorage.getItem(key) || '[]');
        if(!list.includes(id)){
          list.push(id);
          localStorage.setItem(key, JSON.stringify(list.slice(-100)));
        }
      }catch(e){}
    }

    el.addEventListener('mouseenter', ()=> { if(timeoutId) clearTimeout(timeoutId); });
    el.addEventListener('mouseleave', ()=> { timeoutId = setTimeout(hide, 3000); });

    container.appendChild(el);
    requestAnimationFrame(()=> el.classList.add('show'));

    timeoutId = setTimeout(hide, timeout);

    // Expose la fonction de fermeture (croix du polling).
    el.__markDismissed = markDismissed;
    return el;
  }

  window.showToast = createToast;

  function dismissedIds(){
    try{
      return JSON.parse(localStorage.getItem('shopy_notif_lues') || '[]');
    }catch(e){ return []; }
  }

  function initFromServer(){
    try{
      const notifs = window.notifications || [];
      if(!Array.isArray(notifs)) return;
      const dismisses = dismissedIds();
      notifs.forEach(n => {
        // Ignore les notifications deja fermees par l'utilisateur.
        if(n.id != null && dismisses.includes(n.id)) return;
        createToast({
          id: n.id ?? null,
          title: n.title || 'Notification',
          body: n.body || n.message || '',
          type: n.type || 'info',
          timeout: n.timeout || 6000
        });
      });
    }catch(e){ console.error('init notifications', e); }
  }

  window.notify = function(title, body, type){ createToast({title,body,type}); };
  window.marquerNotificationLue = markAsRead;
  window.notificationsDejaFermees = dismissedIds;

  if(document.readyState === 'loading') document.addEventListener('DOMContentLoaded', initFromServer); else initFromServer();
})();
