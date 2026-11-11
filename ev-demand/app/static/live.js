/* D-Max: update existing text/SVG nodes; never reload a document or parse HTML. */
'use strict';
(() => {
  const root = document.querySelector('[data-live-page]');
  if (!root) return;
  const status = document.querySelector('[data-live-status]');
  const page = root.dataset.livePage;
  if (!['overview', 'monitor'].includes(page)) return;
  const svgNS = 'http://www.w3.org/2000/svg';
  const tags = new Set('section article div span p b strong em small h2 h3 h4 a svg g path rect circle ellipse line polyline text title i'.split(' '));
  const attrs = new Set('class id role aria-label data-live-key data-curve-value tabindex viewbox x y x1 x2 y1 y2 cx cy r rx ry width height d points fill stroke stroke-width stroke-opacity fill-opacity stroke-linecap stroke-linejoin stroke-dasharray text-anchor font-size opacity transform href target'.split(' '));
  const key = item => typeof item === 'string' ? null : item.attrs?.['data-live-key'];
  let pendingChart=null, curveRevision=Number(root.dataset.curveRevision || 0);
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
        if(id==='chart'&&matches)pendingChart={node,children:description.children,ns};
        else if(id!=='curve-controls'||!matches)reconcile(node, description.children, ns);
      }
      retained.add(node);
      if (parent.childNodes[index] !== node) parent.insertBefore(node, parent.childNodes[index] || null);
    });
    for (const node of Array.from(parent.childNodes)) if (!retained.has(node)) parent.removeChild(node);
  }
  let stopped = false, timer, controller, push, inFlight=false;
  async function update() {
    if(stopped||inFlight)return;
    inFlight=true;clearTimeout(timer);
    controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 8000);
    try {
      const response = await fetch('/ui-data/' + page + window.location.search, {credentials: 'same-origin', cache: 'no-store', redirect: 'error', headers: {'Accept': 'application/json'}, signal: controller.signal});
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
      if (curveRevision !== undefined && data.curve_revision !== curveRevision && pendingChart) {
        const {node,children,ns}=pendingChart;pendingChart=null;
        if(node.isConnected)reconcile(node,children,ns);
      }
      curveRevision=data.curve_revision;
      if(data.curve_push&&!push){
        push=new EventSource('/api/curve/events');
        push.onmessage=()=>update();
      }
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
      inFlight=false;clearTimeout(timeout);
      if (!stopped) timer = setTimeout(update, 2000);
    }
  }
  const chartTimer=setInterval(()=>{
    if(!stopped&&pendingChart){const {node,children,ns}=pendingChart;pendingChart=null;if(node.isConnected)reconcile(node,children,ns);}
  },5000);
  window.addEventListener('pagehide', () => { stopped = true; push?.close(); clearTimeout(timer); clearInterval(chartTimer); pendingChart=null; controller?.abort(); });
  timer = setTimeout(update, 1000);
  const tooltip=document.createElement('div');tooltip.className='curve-tooltip';tooltip.setAttribute('role','status');tooltip.hidden=true;document.body.appendChild(tooltip);
  function show(text,x,y){tooltip.textContent=text;tooltip.hidden=false;tooltip.style.left=Math.max(8,Math.min(x+12,window.innerWidth-tooltip.offsetWidth-8))+'px';tooltip.style.top=Math.max(8,Math.min(y+12,window.innerHeight-tooltip.offsetHeight-8))+'px';}
  function inspectCurve(event){
    const svg=event.target.closest?.('.curve-chart');
    if(!svg){tooltip.hidden=true;return;}
    const matrix=svg.getScreenCTM();if(!matrix)return;
    const x=new DOMPoint(event.clientX,event.clientY).matrixTransform(matrix.inverse()).x;
    let nearest,distance=Infinity;
    svg.querySelectorAll('[data-curve-value]').forEach(p=>{const delta=Math.abs(Number(p.getAttribute('cx'))-x);if(delta<distance){distance=delta;nearest=p;}});
    if(nearest)show(nearest.dataset.curveValue.split(' | ').join('\n'),event.clientX,event.clientY);
  }
  document.addEventListener('pointermove',inspectCurve);
  document.addEventListener('pointerdown',inspectCurve);
  document.addEventListener('focusin',event=>{const p=event.target.closest?.('[data-curve-value]');if(p){const box=p.getBoundingClientRect();show(p.dataset.curveValue.split(' | ').join('\n'),box.x,box.y);}});
  document.addEventListener('focusout',()=>{tooltip.hidden=true;});
})();
