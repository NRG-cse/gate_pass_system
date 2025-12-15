// static/js/service-worker.js (Updated)
const CACHE_NAME = 'gate-pass-v1.0';
const STATIC_CACHE = 'static-v1';
const DYNAMIC_CACHE = 'dynamic-v1';

const urlsToCache = [
    '/',
    '/offline',
    '/static/css/style.css',
    '/static/js/script.js',
    '/static/js/camera.js',
    '/static/js/pwa-install.js',
    '/static/icons/icon-192x192.png',
    '/static/icons/icon-512x512.png',
    '/manifest.json'
];

self.addEventListener('install', event => {
    event.waitUntil(
        caches.open(STATIC_CACHE)
            .then(cache => {
                console.log('Caching static assets');
                return cache.addAll(urlsToCache);
            })
            .then(() => self.skipWaiting())
    );
});

self.addEventListener('activate', event => {
    event.waitUntil(
        caches.keys().then(keys => {
            return Promise.all(
                keys.filter(key => key !== STATIC_CACHE && key !== DYNAMIC_CACHE)
                    .map(key => caches.delete(key))
            );
        })
    );
});

self.addEventListener('fetch', event => {
    event.respondWith(
        caches.match(event.request)
            .then(response => {
                if (response) return response;
                
                return fetch(event.request)
                    .then(res => {
                        return caches.open(DYNAMIC_CACHE)
                            .then(cache => {
                                cache.put(event.request.url, res.clone());
                                return res;
                            });
                    })
                    .catch(() => {
                        // If offline and not cached, show offline page
                        if (event.request.url.includes('/api/')) {
                            return new Response(JSON.stringify({
                                error: 'You are offline'
                            }), {
                                headers: { 'Content-Type': 'application/json' }
                            });
                        }
                        return caches.match('/offline');
                    });
            })
    );
});

// Background sync for offline data
self.addEventListener('sync', event => {
    if (event.tag === 'sync-gatepass') {
        event.waitUntil(syncGatePasses());
    }
});

async function syncGatePasses() {
    // Sync pending gate passes when online
    console.log('Syncing offline data...');
}