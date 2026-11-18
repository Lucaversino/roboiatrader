// Proxy para contornar CORS da Binance na Vercel
// Usa API Key da Binance se configurada (para limites maiores e futuros endpoints autenticados)
export default async function handler(req, res) {
  const { symbol = 'BTCUSDT', interval = '15m', limit = '200' } = req.query;

  try {
    const url = `https://api.binance.com/api/v3/klines?symbol=${symbol}&interval=${interval}&limit=${limit}`;

    // Headers opcionais com credenciais da Binance (se configuradas)
    const headers = {};
    if (process.env.BINANCE_API_KEY) {
      headers['X-MBX-APIKEY'] = process.env.BINANCE_API_KEY;
    }

    const response = await fetch(url, { headers });

    if (!response.ok) {
      throw new Error(`Binance API error: ${response.status}`);
    }

    const data = await response.json();

    // Transformar formato da Binance para Lightweight Charts
    const candles = data.map(d => ({
      time: Math.floor(d[0] / 1000),
      open: parseFloat(d[1]),
      high: parseFloat(d[2]),
      low: parseFloat(d[3]),
      close: parseFloat(d[4]),
    }));

    res.setHeader('Cache-Control', 'no-cache');
    res.status(200).json({ candles });
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
}