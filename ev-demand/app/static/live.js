/* D-Max: update existing text/SVG nodes; never reload a document or parse HTML. */
'use strict';
(() => {
  const root = document.querySelector('[data-live-page]');
  if (!root) return;
  const status = document.querySelector('[data-live-status]');
  const page = root.dataset.livePage;
  if (!['overview', 'monitor'].includes(page)) return;
  const svgNS = 'http://www.w3.org/2000/svg';
  const tags = new Set('section article div span p b strong em small h2 h3 h4 a svg g path rect circle ellipse line polyline text i'.split(' '));
  const attrs = new Set('class id role aria-label data-live-key viewbox x y x1 x2 y1 y2 cx cy r rx ry width height d points fill stroke stroke-width stroke-opacity fill-opacity stroke-linecap stroke-linejoin stroke-dasharray text-anchor font-size opacity transform href target'.split(' '));
  const key = item => typeof item === 'string' ? null : item.attrs?.['data-live-key'];
  const nodeKey = node => node.nodeType === 1 ? node.getAttribute('data-live-key') : null;
  function reconcile(parent, descriptions, inSVG = false) {
    const old = Array.from(parent.childNodes), retained = new Set();
    descriptions.forEach((description, index) => {
      const text = typeof description === 'string';
      if (!text && (!tags.has(description.tag) || !Array.isArray(description.children))) throw new Error('Invalid view');
      const id = key(description), ns = !text && (inSVG || description.tag === 'svg');
      let node = id ? old.find(n => nodeKey(n) === id) : old[index];
      const matches = node && !retained.has(node) && (!id ? !nodeKey(node) : true) &&
        (text ? node.nodeType === 3 : node.nodeType === 1 && node.localName === description.tag && (node.namespaceURI === svgNS) === Boolean(ns));
      if (!matches) node = text ? document.createTextNode('') : ns ? document.createElementNS(svgNS, description.tag) : document.createElement(description.tag);
      if (text) {
        if (node.nodeValue !== description) node.nodeValue = description;
      } else {
        const desired = description.attrs || {};
        for (const attribute of Array.from(node.attributes)) {
          if (!Object.hasOwn(desired, attribute.name.toLowerCase())) node.removeAttribute(attribute.name);
        }
        for (const [name, value] of Object.entries(desired)) {
          if (!attrs.has(name) || typeof value !== 'string') throw new Error('Invalid attribute');
          if (name === 'href' && !/^\/ui\/[a-z]+(?:\?[^\s]*)?$/.test(value)) throw new Error('Invalid link');
          const actual = name === 'viewbox' ? 'viewBox' : name;
          if (node.getAttribute(actual) !== value) node.setAttribute(actual, value);
        }
        reconcile(node, description.children, ns);
      }
      retained.add(node);
      if (parent.childNodes[index] !== node) parent.insertBefore(node, parent.childNodes[index] || null);
    });
    for (const node of Array.from(parent.childNodes)) if (!retained.has(node)) parent.removeChild(node);
  }
  let stopped = false, timer, controller;
  async function update() {
    controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 8000);
    try {
      const response = await fetch('/ui-data/' + page, {credentials: 'same-origin', cache: 'no-store', redirect: 'error', headers: {'Accept': 'application/json'}, signal: controller.signal});
      if (response.status === 401 || response.status === 403) {
        stopped = true;
        status.textContent = 'Sessão encerrada ou acesso revogado. Entre novamente.';
        status.dataset.stale = 'true';
        return;
      }
      if (!response.ok) throw new Error('Unavailable');
      const data = await response.json();
      if (data.schema_version !== 1 || !Array.isArray(data.nodes)) throw new Error('Invalid data');
      reconcile(root, data.nodes);
      const banner = document.getElementById('subscription-banner');
      if (banner && Array.isArray(data.subscription_nodes) && data.subscription_nodes[0]?.tag === 'div') reconcile(banner, data.subscription_nodes[0].children);
      for (const name of ['charging', 'connected', 'alarm', 'disconnected', 'communication']) {
        const color = data.colors?.[name];
        if (typeof color === 'string' && /^#[0-9a-f]{6}$/i.test(color) && document.documentElement.style.getPropertyValue('--plant-' + name) !== color) document.documentElement.style.setProperty('--plant-' + name, color);
      }
      document.querySelectorAll('[data-dmax-version]').forEach(n => { n.textContent = 'v' + data.version; });
      if (typeof data.site_name === 'string') document.querySelectorAll('[data-live-site]').forEach(n => { if (n.textContent !== data.site_name) n.textContent = data.site_name; });
      const message = 'Atualizado às ' + new Date(data.observed_at * 1000).toLocaleTimeString('pt-BR');
      status.textContent = message;
      status.dataset.stale = 'false';
    } catch {
      status.textContent = 'Dados desatualizados · sem confirmação de atualização. Tentando reconectar…';
      status.dataset.stale = 'true';
    } finally {
      clearTimeout(timeout);
      if (!stopped) timer = setTimeout(update, 2000);
    }
  }
  window.addEventListener('pagehide', () => { stopped = true; clearTimeout(timer); controller?.abort(); });
  timer = setTimeout(update, 1000);
})();
