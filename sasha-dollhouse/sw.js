/* Sasha's Dollhouse — offline cache.
   Cache-first for the app shell, fonts and all recorded voice lines,
   so it works on a plane, in a waiting room, anywhere without signal. */
importScripts('audio-map.js');

const CACHE = 'sasha-dollhouse-v4';
const SHELL = ['./', './index.html', './manifest.webmanifest', './icon.svg',
               './icon-180.png', './icon-512.png', './audio-map.js'];

self.addEventListener('install', e => {
  e.waitUntil(
    caches.open(CACHE).then(c =>
      c.addAll(SHELL).then(() => {
        // Voice lines: best-effort, one failure must not sink the install
        const clips = [...Object.values(AUDIO_MAP.en), ...Object.values(AUDIO_MAP.es)];
        return Promise.allSettled(clips.map(u => c.add(u)));
      })
    )
  );
  self.skipWaiting();
});

self.addEventListener('activate', e => {
  e.waitUntil(
    caches.keys().then(ks => Promise.all(ks.filter(k => k !== CACHE).map(k => caches.delete(k))))
  );
  self.clients.claim();
});

/* The app shell must pick up new deploys: network-first, cache as offline
   fallback. Audio clips, fonts and icons never change once published:
   cache-first. Getting this backwards pins every device to a stale build. */
function isShell(req){
  return req.mode === 'navigate' ||
    /(?:index\.html|audio-map\.js|manifest\.webmanifest)(?:\?|$)|\/$/.test(req.url);
}

self.addEventListener('fetch', e => {
  if (e.request.method !== 'GET') return;
  if (isShell(e.request)) {
    e.respondWith(
      fetch(e.request).then(res => {
        if (res.ok) {
          const copy = res.clone();
          caches.open(CACHE).then(c => c.put(e.request, copy));
        }
        return res;
      }).catch(() => caches.match(e.request).then(hit => hit || caches.match('./index.html')))
    );
    return;
  }
  e.respondWith(
    caches.match(e.request).then(hit => hit || fetch(e.request).then(res => {
      const cacheable = res.ok && (
        e.request.url.startsWith(self.location.origin) ||
        /fonts\.(googleapis|gstatic)\.com/.test(e.request.url)
      );
      if (cacheable) {
        const copy = res.clone();
        caches.open(CACHE).then(c => c.put(e.request, copy));
      }
      return res;
    }).catch(() => caches.match('./index.html')))
  );
});
