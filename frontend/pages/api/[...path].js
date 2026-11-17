export const config = { api: { bodyParser: { sizeLimit: '128kb' } } };

export default async function handler(req,res) {
  const backend = process.env.BACKEND_URL;
  const token = process.env.BACKEND_TOKEN;
  if (!backend || !token || !/^https:\/\//i.test(backend)) {
    return res.status(503).json({detail:'Backend não configurado. Configure BACKEND_URL (https) e BACKEND_TOKEN na Vercel.'});
  }
  const parts = req.query.path;
  const path = Array.isArray(parts) ? parts : [parts];
  const allowed = ['status','engine','settings','step','reset','candles'];
  if (path.length !== 1 || !allowed.includes(path[0])) return res.status(404).json({detail:'Rota inválida'});
  const methods = {status:'GET',candles:'GET',engine:'POST',settings:'POST',step:'POST',reset:'POST'};
  if (req.method !== methods[path[0]]) return res.status(405).json({detail:'Método inválido'});
  try {
    const upstream = await fetch(backend.replace(/\/$/,'') + '/api/' + path[0], {
      method:req.method,
      headers:{'Authorization':'Bearer '+token,'Content-Type':'application/json'},
      ...(req.method==='POST' ? {body:JSON.stringify(req.body ?? {})} : {}),
      signal:AbortSignal.timeout(20000)
    });
    const body=await upstream.text();
    res.setHeader('Cache-Control','no-store');
    res.setHeader('Content-Type','application/json; charset=utf-8');
    return res.status(upstream.status).send(body);
  } catch (_) {
    return res.status(502).json({detail:'Backend indisponível ou não respondeu a tempo.'});
  }
}
