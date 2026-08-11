(function(){
  const container = document.getElementById('toast-container');
  if(!container) return;

  function createToast({title='Notification', body='', type='info', timeout=6000}){
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

    const close = document.createElement('button'); close.className='close'; close.innerHTML='✕';
    close.addEventListener('click', ()=> hide());

    el.appendChild(icon); el.appendChild(bodyWrap); el.appendChild(close);

    let timeoutId;
    function hide(){
      el.classList.remove('show');
      setTimeout(()=> el.remove(),300);
      if(timeoutId) clearTimeout(timeoutId);
    }

    el.addEventListener('mouseenter', ()=> { if(timeoutId) clearTimeout(timeoutId); });
    el.addEventListener('mouseleave', ()=> { timeoutId = setTimeout(hide, 3000); });

    container.appendChild(el);
    // force reflow for animation
    requestAnimationFrame(()=> el.classList.add('show'));

    timeoutId = setTimeout(hide, timeout);
  }

  window.showToast = createToast;

  function initFromServer(){
    try{
      const notifs = window.notifications || [];
      if(!Array.isArray(notifs)) return;
      notifs.forEach(n => {
        createToast({title: n.title || 'Notification', body: n.body || n.message || '', type: n.type || 'info', timeout: n.timeout || 6000});
      });
    }catch(e){ console.error('init notifications', e); }
  }

  // small API for adding notifications from other scripts
  window.notify = function(title, body, type){ createToast({title,body,type}); };

  // init on DOM ready
  if(document.readyState === 'loading') document.addEventListener('DOMContentLoaded', initFromServer); else initFromServer();
})();
