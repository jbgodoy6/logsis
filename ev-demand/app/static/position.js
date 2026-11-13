/* Preserve viewport across form POST/redirect and refresh, per browser tab. */
(() => {
  'use strict';
  const key = 'dmax:pending-position';
  if ('scrollRestoration' in history) history.scrollRestoration = 'manual';
  let clickPosition = null;
  document.addEventListener('pointerdown', () => { clickPosition = {x: scrollX, y: scrollY, at: Date.now()}; }, true);
  function save(path) {
    const position = clickPosition && Date.now() - clickPosition.at < 1500 ? clickPosition : {x: scrollX, y: scrollY};
    try { sessionStorage.setItem(key, JSON.stringify({path, x: position.x, y: position.y, at: Date.now()})); } catch (_) {}
  }
  window.addEventListener('pagehide', () => {
    try { if (!sessionStorage.getItem(key)) { clickPosition = null; save(location.pathname); } } catch (_) {}
  });
  document.addEventListener('submit', event => {
    const form = event.target;
    if (form.querySelector('[name="_action"][value="logout"]')) {
      try { sessionStorage.removeItem(key); } catch (_) {}
      return;
    }
    const page = form.querySelector('[name="_page"]')?.value;
    save(page ? '/ui/' + page : location.pathname);
  }, true);
  document.addEventListener('click', event => {
    const link = event.target.closest('a[href]');
    if (!link || link.target === '_blank') return;
    const url = new URL(link.href, location.href);
    if (url.origin === location.origin) save(url.pathname);
  }, true);
  try {
    const raw = sessionStorage.getItem(key);
    sessionStorage.removeItem(key);
    const position = raw && JSON.parse(raw);
    if (position && position.path === location.pathname && Date.now() - position.at < 60000) {
      const restore = () => scrollTo({left: position.x, top: position.y, behavior: 'instant'});
      requestAnimationFrame(restore);
      window.addEventListener('load', restore, {once: true});
    }
  } catch (_) {}
})();
