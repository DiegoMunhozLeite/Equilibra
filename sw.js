// Guarda em cache só arquivos estáticos. Páginas com dados de pacientes nunca ficam salvas no aparelho.
const VERSAO = 'equilibra-v5';
const ESTATICOS = ['/static/style.css?v=5', '/static/icon-192.png', '/offline'];

self.addEventListener('install', e => {
  e.waitUntil(caches.open(VERSAO).then(c => c.addAll(ESTATICOS)).then(() => self.skipWaiting()));
});
self.addEventListener('activate', e => {
  e.waitUntil(caches.keys().then(ks => Promise.all(ks.filter(k => k !== VERSAO).map(k => caches.delete(k)))).then(() => self.clients.claim()));
});
self.addEventListener('fetch', e => {
  const req = e.request;
  if (req.method !== 'GET') return;
  const url = new URL(req.url);
  if (req.mode === 'navigate') {
    e.respondWith(fetch(req).catch(() => caches.match('/offline')));
    return;
  }
  if (url.pathname.startsWith('/static/') || url.hostname.includes('fonts.g')) {
    e.respondWith(caches.match(req).then(r => r || fetch(req).then(resp => {
      const copia = resp.clone(); caches.open(VERSAO).then(c => c.put(req, copia)); return resp;
    })));
  }
});
