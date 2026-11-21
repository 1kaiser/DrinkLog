#!/usr/bin/env node
/**
 * Zero-dependency local HTTP static server for the DrinkLog Three.js 3D viewer.
 * Rewrites CDN Three.js importmap URLs to /vendor/three/ from local node_modules
 * so the scene runs 100% offline.
 */

import fs from 'node:fs';
import http from 'node:http';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

const MIME = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'application/javascript; charset=utf-8',
  '.mjs': 'application/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.png': 'image/png',
  '.glb': 'model/gltf-binary',
  '.svg': 'image/svg+xml',
};

export function resolveThreeRoot() {
  const candidates = [
    path.join(__dirname, 'node_modules/three'),
    '/home/kaiser/projects/hong-kong-winter-threejs/node_modules/three',
  ];
  for (const c of candidates) {
    if (fs.existsSync(path.join(c, 'build/three.module.js'))) return c;
  }
  throw new Error('Could not locate Three.js package directory.');
}

export function startDrinkLogServer(port = 8080) {
  const threeRoot = resolveThreeRoot();
  return new Promise((resolve) => {
    const server = http.createServer((req, res) => {
      const reqUrl = new URL(req.url, 'http://127.0.0.1');
      let rel = decodeURIComponent(reqUrl.pathname);
      if (rel === '/favicon.ico') {
        res.writeHead(204);
        res.end();
        return;
      }
      if (rel === '/') rel = '/index.html';

      let filePath;
      let rootDir;
      if (rel.startsWith('/vendor/three/')) {
        rootDir = threeRoot;
        filePath = path.normalize(path.join(threeRoot, rel.slice('/vendor/three/'.length)));
      } else {
        rootDir = __dirname;
        filePath = path.normalize(path.join(__dirname, rel));
      }

      if (!filePath.startsWith(rootDir)) {
        res.writeHead(403);
        res.end('Forbidden');
        return;
      }

      fs.readFile(filePath, (err, data) => {
        if (err) {
          res.writeHead(404);
          res.end('Not Found');
          return;
        }
        const ext = path.extname(filePath).toLowerCase();
        if (rel === '/index.html') {
          let html = data.toString('utf8');
          html = html
            .replace('https://cdn.jsdelivr.net/npm/three@0.175.0/build/three.module.js', '/vendor/three/build/three.module.js')
            .replace('https://cdn.jsdelivr.net/npm/three@0.175.0/examples/jsm/', '/vendor/three/examples/jsm/');
          res.writeHead(200, { 'Content-Type': MIME['.html'] });
          res.end(html);
          return;
        }
        res.writeHead(200, { 'Content-Type': MIME[ext] || 'application/octet-stream' });
        res.end(data);
      });
    });

    server.listen(port, '127.0.0.1', () => {
      const addr = server.address();
      resolve({ server, port: addr.port, url: `http://127.0.0.1:${addr.port}` });
    });
  });
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const portArg = process.argv.includes('--port')
    ? Number(process.argv[process.argv.indexOf('--port') + 1])
    : 8080;
  const { url } = await startDrinkLogServer(portArg);
  console.log(`DrinkLog 3D Three.js server listening at ${url}`);
}
