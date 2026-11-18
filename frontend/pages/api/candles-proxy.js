// Proxy para contornar CORS da Binance na Vercel
// Retorna candles + volumes separados para o Lightweight Charts
export default async function handler(req, res) {
 const { symbol = 'BTCUSDT', interval = '15m', limit = '300' } = req.query;

 try {
 const url = `https://api.binance.com/api/v3/klines?symbol=${symbol}&interval=${interval}&limit=${limit}`;

 const headers = {};
 if (process.env.BINANCE_API_KEY) {
 headers['X-MBX-APIKEY'] = process.env.BINANCE_API_KEY;
 }

 const response = await fetch(url, { headers });

 if (!response.ok) {
 throw new Error(`Binance API error: ${response.status}`);
 }

 const data = await response.json();

 // Binance format: [openTime, open, high, low, close, volume, ...]
 const candles = data.map(d => ({
 time: Math.floor(d[0] / 1000),
 open: parseFloat(d[1]),
 high: parseFloat(d[2]),
 low: parseFloat(d[3]),
 close: parseFloat(d[4]),
 }));

 const volumes = data.map(d => parseFloat(d[5]));

 res.setHeader('Cache-Control', 'no-cache');
 res.status(200).json({ candles, volumes });
 } catch (error) {
 res.status(500).json({ error: error.message });
 }
}