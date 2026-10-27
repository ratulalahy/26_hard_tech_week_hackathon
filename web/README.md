# GridPilot dashboard

Offline. Run it on the Mac:

```sh
cd web
npm ci && npm run build && npm run preview
```

Then open http://127.0.0.1:4173/ in Chrome.

Node ≥ 22 recommended (`node --version`). The build is checked with `npm ci` on Node 22. Node 20 is the minimum (`engines` in package.json).
