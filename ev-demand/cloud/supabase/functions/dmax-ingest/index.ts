// Deploy with verify_jwt=false: Authorization is a per-controller random token,
// validated inside one PostgreSQL transaction; never a shared public API key.
Deno.serve(async (request: Request) => {
  if (request.method !== 'POST') return new Response('Method not allowed', {status: 405});
  const auth = request.headers.get('Authorization') ?? '';
  if (!/^Bearer [A-Za-z0-9_-]{32,512}$/.test(auth)) return new Response('Unauthorized', {status: 401});
  try {
    const reader = request.body?.getReader();
    if (!reader) return new Response('Invalid body', {status: 400});
    const chunks: Uint8Array[] = []; let size = 0;
    while (true) {
      const {done, value} = await reader.read();
      if (done) break;
      size += value.byteLength;
      if (size > 1_500_000) { await reader.cancel(); return new Response('Body too large', {status: 413}); }
      chunks.push(value);
    }
    const bytes = new Uint8Array(size); let offset = 0;
    for (const chunk of chunks) { bytes.set(chunk, offset); offset += chunk.length; }
    const data = JSON.parse(new TextDecoder().decode(bytes));
    if (typeof data.controller_id !== 'string' || !Array.isArray(data.records) || data.records.length > 200)
      return new Response('Invalid batch', {status: 400});
    const url = Deno.env.get('SUPABASE_URL');
    const key = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY');
    if (!url || !key) return new Response('Service unavailable', {status: 503});
    const result = await fetch(url + '/rest/v1/rpc/dmax_ingest', {
      method: 'POST', headers: {'Content-Type': 'application/json', apikey: key, Authorization: 'Bearer ' + key},
      body: JSON.stringify({p_controller: data.controller_id, p_token: auth.slice(7), p_records: data.records}),
      signal: AbortSignal.timeout(15000),
    });
    if (!result.ok) return new Response('Batch not accepted', {status: result.status === 400 ? 400 : 403});
    return new Response(await result.text(), {headers: {'Content-Type': 'application/json', 'Cache-Control': 'no-store'}});
  } catch {
    return new Response('Request not processed', {status: 400});
  }
});
