// Cache only the generic recovery screen. Never cache accounts, records or uploads.
const CACHE='portal-recovery-v1';
const ASSETS=['/offline.html','/error.css','/error.js','/theme.css','/theme.js'];
self.addEventListener('install',event=>event.waitUntil(caches.open(CACHE).then(cache=>cache.addAll(ASSETS)).then(()=>self.skipWaiting())));
self.addEventListener('activate',event=>event.waitUntil(caches.keys().then(keys=>Promise.all(keys.filter(key=>key.startsWith('portal-recovery-')&&key!==CACHE).map(key=>caches.delete(key)))).then(()=>self.clients.claim())));
self.addEventListener('fetch',event=>{
 const url=new URL(event.request.url);
 if(url.origin!==self.location.origin||event.request.method!=='GET')return;
 if(event.request.mode==='navigate'&&!url.pathname.startsWith('/api/')&&!url.pathname.startsWith('/auth/')){
  event.respondWith(fetch(event.request).then(async response=>response.status>=500?(await caches.match('/offline.html')||response):response).catch(()=>caches.match('/offline.html')));
 }else if(ASSETS.includes(url.pathname))event.respondWith(fetch(event.request).catch(()=>caches.match(url.pathname)));
});
