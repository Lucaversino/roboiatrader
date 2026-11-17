import { NextResponse } from 'next/server';

export function middleware(request) {
  const expectedUser = process.env.ADMIN_USER;
  const expectedPassword = process.env.ADMIN_PASSWORD;
  if (!expectedUser || !expectedPassword) {
    return new NextResponse('Configure ADMIN_USER e ADMIN_PASSWORD na Vercel.', {status:503});
  }
  const auth = request.headers.get('authorization') || '';
  let user = '', password = '';
  try {
    if (auth.startsWith('Basic ')) {
      const pair = atob(auth.slice(6));
      const i = pair.indexOf(':');
      if (i !== -1) { user = pair.slice(0,i); password = pair.slice(i+1); }
    }
  } catch (_) { /* invalid header */ }
  if (user === expectedUser && password === expectedPassword) return NextResponse.next();
  return new NextResponse('Acesso restrito. Entre com as credenciais do Trader IA PRO.', {
    status:401,
    headers:{'WWW-Authenticate':'Basic realm="Trader IA PRO", charset="UTF-8"','Cache-Control':'no-store'}
  });
}
export const config = { matcher: ['/((?!_next/static|_next/image|favicon.ico).*)'] };
