/** UI primitives. Values become text nodes; no HTML strings are interpreted. */
const HTML_TAGS = new Set([
  'article', 'b', 'button', 'div', 'h3', 'i', 'input', 'label', 'option', 'p',
  'select', 'small', 'span', 'strong', 'table', 'tbody', 'td', 'th', 'thead', 'tr',
]);
const SVG_TAGS = new Set(['svg', 'line', 'polyline', 'polygon', 'text']);

export const $ = (selector) => document.querySelector(selector);
export const $$ = (selector) => Array.from(document.querySelectorAll(selector));

function childrenOf(values) {
  return values.flat(Infinity).filter((value) => value !== null && value !== undefined && value !== false)
    .map((value) => value instanceof Node ? value : document.createTextNode(String(value)));
}

function attributes(node, values) {
  for (const [name, value] of Object.entries(values)) {
    if (/^on/i.test(name) || ['src', 'href', 'srcdoc', 'style'].includes(name.toLowerCase())) {
      throw new Error('Atributo não permitido no componente');
    }
    if (value === null || value === undefined || value === false) continue;
    node.setAttribute(name, value === true ? '' : String(value));
  }
  return node;
}

export function el(tag, attrs = {}, ...children) {
  if (!HTML_TAGS.has(tag)) throw new Error('Componente HTML não permitido');
  const node = attributes(document.createElement(tag), attrs);
  node.append(...childrenOf(children));
  return node;
}

export function svg(tag, attrs = {}, ...children) {
  if (!SVG_TAGS.has(tag)) throw new Error('Componente SVG não permitido');
  const node = attributes(document.createElementNS('http://www.w3.org/2000/svg', tag), attrs);
  node.append(...childrenOf(children));
  return node;
}

export function replace(target, ...children) {
  const node = typeof target === 'string' ? $(target) : target;
  node.replaceChildren(...childrenOf(children));
}

export function button(label, attrs = {}) {
  return el('button', {type: 'button', class: 'secondary', ...attrs}, label);
}

export function field(label, name, value = '', type = 'text', attrs = {}) {
  const input = el('input', {name, type, ...attrs});
  input.value = value ?? '';
  return el('label', {}, label, input);
}

export function selectField(label, name, options, selected) {
  const select = el('select', {name}, options.map(([value, title]) => option(value, title)));
  select.value = selected ?? '';
  return el('label', {}, label, select);
}

export function option(value, title) {
  return el('option', {value}, title);
}

export function check(label, name, checked) {
  return el('label', {class: 'checkbox-label'}, el('input', {name, type: 'checkbox', checked}), label);
}

export function empty(title, text) {
  return el('div', {class: 'empty-state'}, el('strong', {}, title), text);
}

export function table(headers, rows) {
  return el('div', {class: 'table-wrap'}, el('table', {},
    el('thead', {}, el('tr', {}, headers.map((title) => el('th', {}, title)))),
    el('tbody', {}, rows.map((cells) => el('tr', {}, cells.map((cell) => el('td', {}, cell)))))));
}

export function number(value, digits = 1) {
  const safe = Number(value);
  return (Number.isFinite(safe) ? safe : 0).toLocaleString('pt-BR', {maximumFractionDigits: digits});
}

export function percentage(value) {
  const numeric = Number(value);
  return `${Number.isFinite(numeric) ? Math.max(0, Math.min(100, numeric)) : 0}%`;
}
