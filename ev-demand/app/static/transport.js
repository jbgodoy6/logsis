/** All browser traffic stays on the controller's origin. No credential storage. */
export class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.status = status;
  }
}

export async function request(path, body, method = 'POST') {
  if (!/^\/[A-Za-z0-9_/%:.-]+$/.test(path) || path.includes('//') ||
      path.split('/').some((part) => part === '.' || part === '..')) {
    throw new Error('Caminho de API inválido');
  }
  const target = new URL(`/api${path}`, window.location.origin);
  if (target.origin !== window.location.origin || !target.pathname.startsWith('/api/')) {
    throw new Error('Destino de API inválido');
  }
  const response = await fetch(target, {
    method: body === undefined ? 'GET' : method,
    credentials: 'same-origin',
    cache: 'no-store',
    redirect: 'error',
    headers: {'Content-Type': 'application/json'},
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  let data;
  try {
    data = await response.json();
  } catch {
    throw new ApiError('Resposta inesperada do controlador', response.status);
  }
  if (!response.ok) {
    const detail = Array.isArray(data.detail)
      ? data.detail.map((item) => `${item.loc.slice(1).join('.')}: ${item.msg}`).join('; ')
      : data.detail;
    throw new ApiError(detail || 'Não foi possível concluir', response.status);
  }
  return data;
}

export function liveSocket() {
  const target = new URL('/ws/live', window.location.origin);
  target.protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  return new WebSocket(target);
}
