# Deploy the GPT-2-in-CSS demo to a Cloudflare Worker (workers.dev)

This is option A1 from HOSTING.md. The result is `https://gpt2-css.<your-subdomain>.workers.dev/`.

- 286 small files are served as Workers static assets. These requests are free, have no request limit, and never run the Worker.
- 2 files are larger than the 25 MiB static-asset limit. They are stored in the R2 bucket `gpt2-css-large`, and `src/worker.js` serves them. The Worker runs on Cloudflare's servers, not in the browser, so the page still has zero client JavaScript.

| path | size | served by | Cache-Control |
|---|---|---|---|
| `/` (index.html) | 7.4 MB | static assets | `public, max-age=300` |
| `/runtime.css` | 53,621,749 B | Worker + R2 | `public, max-age=300` |
| `/fonts/embedding-lookup.woff2` | 56,853,724 B | Worker + R2 | `public, max-age=86400` (immutable if requested with `?v=`) |
| `/fonts/*?v=<sha>` and fonts with a hash in the name | | static assets | `public, max-age=31536000, immutable` |
| 9 fonts with no `?v=` and no hash (`score-*`, `gumbel-noise.ttf`, `gpt2-token-id-*`) | | static assets | `public, max-age=86400` |

After these times, the browser revalidates with ETag and gets a cheap 304 if nothing changed. All responses also carry `Content-Security-Policy: script-src 'none'; object-src 'none'`. This is the same header that `tools/launch_browser_gpt2.py` sends, and the page also has it as a `<meta>` tag.

Files in this folder:
- `wrangler.jsonc`: the Worker config. It sets the assets dir, `run_worker_first` for the 2 large paths only, and the R2 binding `LARGE` to `gpt2-css-large`.
- `src/worker.js`: serves the 2 large files from R2. It supports GET/HEAD, Range (206) and If-None-Match (304).
- `_headers`: CSP, nosniff and cache rules for the static files. `stage.sh` copies it into `public/`.
- `stage.sh`: builds `public/` and runs the checks.
- `.gitignore`: ignores `public/`, `.wrangler/` and `node_modules/`.

## 1. Commands, in order

Run these from this folder:

```sh
cd /Users/shubhampatil/Documents/programming/gpt2-css/deploy/cloudflare-worker
M=/Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19/R8D/out/model

# 0. Wrangler. The installed one is 4.115.0; npx always gets the newest.
npx wrangler@latest --version        # or: npm i -g wrangler@latest  (then drop "npx ... @latest" below)

# 1. Log in. This opens the browser for OAuth.
npx wrangler@latest login
npx wrangler@latest whoami

# 2. Create the R2 bucket. The first time, R2 must be enabled in the dashboard:
#    R2 > "Purchase R2 Plan". The free tier still asks for a payment method.
npx wrangler@latest r2 bucket create gpt2-css-large

# 3. Upload the 2 large files. The object key is the bare file name. --remote is required.
npx wrangler@latest r2 object put gpt2-css-large/runtime.css \
  --file "$M/runtime.css" --content-type 'text/css; charset=utf-8' --remote
npx wrangler@latest r2 object put gpt2-css-large/embedding-lookup.woff2 \
  --file "$M/fonts/embedding-lookup.woff2" --content-type font/woff2 --remote

# 4. Stage the static assets. Expect: 286 files, all checks ok, "STAGE OK".
./stage.sh

# 5. Optional: validate the config without uploading anything.
npx wrangler@latest deploy --dry-run

# 6. Deploy. On the first deploy, Wrangler may ask you to pick a workers.dev subdomain.
npx wrangler@latest deploy
```

Wrangler prints the URL: `https://gpt2-css.<your-subdomain>.workers.dev/`. The first deploy uploads about 193 MB of assets. Later deploys upload only the files that changed.

## 2. Turn off Cloudflare features that inject JavaScript

The page must contain no `<script>`. The CSP would block injected scripts anyway, but they would still weaken the "no JS" claim.

- A plain `*.workers.dev` URL has no zone, so zone features do not apply to it. Still, check that these are off. They must stay off if you later add a custom domain (Workers > gpt2-css > Settings > Domains & Routes):
  - **Rocket Loader**: Speed > Optimization > Content Optimization > Rocket Loader: Off.
  - **Email Address Obfuscation**: Scrape Shield: Off.
  - **Web Analytics automatic setup / RUM beacon**: Analytics & Logs > Web Analytics. Do not enable it for this site or hostname. If it was enabled, choose "Disable automatic setup" or "Manage site > Delete".
  - **Zaraz**: Off, and no other HTML-rewriting Snippets or Workers on the route.
- Do not turn on Workers "observability" for traces that inject anything. The current Workers Logs do not touch the HTML, and the config sets `observability.enabled: false`.

Check with: `curl -s $U/ | grep -ci '<script'`. It must print `0`.

## 3. Post-deploy checks

```sh
U=https://gpt2-css.<your-subdomain>.workers.dev

curl -sI $U/ | grep -iE '^HTTP|content-type|cache-control|content-security'
#   200, text/html; charset=utf-8, public, max-age=300, script-src 'none'; object-src 'none'

curl -sI -H 'Accept-Encoding: br, gzip' $U/runtime.css | grep -iE '^HTTP|content-type|content-encoding|cache-control|etag'
#   200, text/css; charset=utf-8, public, max-age=300, content-encoding br or gzip (expected from the edge)

curl -sI $U/fonts/embedding-lookup.woff2 | grep -iE '^HTTP|content-type|content-length|cache-control|accept-ranges'
#   200, font/woff2, 56853724, public, max-age=86400, bytes

curl -sI "$U/fonts/qkv-rowbase-s0.woff2?v=47ff61dfc293" | grep -iE '^HTTP|content-type|cache-control'
#   200, font/woff2, public, max-age=31536000, immutable

curl -s -o /dev/null -w '%{http_code}\n' -H 'Range: bytes=0-99' $U/fonts/embedding-lookup.woff2   # 206
curl -s $U/ | grep -ci '<script'                                                                   # 0
curl -s $U/runtime.css | shasum -a 256 | cut -c1-16                                                # 2085a056bf054f7c
curl -s $U/fonts/embedding-lookup.woff2 | shasum -a 256 | cut -c1-16                               # 8d76543127d8c438
```

If `runtime.css` comes back without `content-encoding`, the browser downloads the full 51 MiB instead of about 2 MB. It still works, but it is slower. In that case, check that no Configuration/Compression Rule disables compression. This could not be tested locally, because `wrangler dev` does not compress.

Then open `$U/` in desktop Chrome or Edge 139+. Open DevTools > Network and check:
- 288 requests, no 404s.
- `runtime.css` and `embedding-lookup.woff2` show 200 with the types above.
- The status line at the top right says "Ready" after the download, which is about 243 MB on a cold visit.
- A short run with the "Hello" prompt works.

The machine needs about 16 GB of RAM: the tab uses about 2 GB after loading and up to about 6 GB while generating. Say this next to the blog link ("Chrome 139+, desktop, ~250 MB download, 16 GB RAM").

## 4. Costs and quotas (Workers Free + R2 free tier)

- **Static assets** (286 files, including all of index.html): requests are free and unlimited, and do not count as Worker invocations.
- **Worker invocations**: 2 per cold visit (runtime.css + the embedding font). The free plan allows 100,000 per day, so about 50,000 cold visits per day. Revalidations (304) also count.
  - Above the limit, those 2 files fail with error 1027 until 00:00 UTC, and the page breaks.
  - Workers Paid ($5/month) gives 10 M requests/month, then $0.30 per million.
  - CPU time is very small, because the Worker only streams the R2 body.
- **R2**:
  - Storage: about 105 MB, which is inside the 10 GB-month free tier.
  - Reads: 2 Class B ops per cold visit. The free tier is 10 M/month, so about 5 M visits/month.
  - Writes: Class A ops for the uploads only.
  - **Egress is free.**
- **Limits**: 25 MiB per static file, 20,000 asset files on the free plan (this site uses 286), 100 `_headers` rules (this file uses 13), 100 `run_worker_first` entries (this config uses 2).
- **Bandwidth**: about 243 MB per cold visit, and Cloudflare does not bill it.

## 5. Update

When the bundle changes:
1. Rebuild the bundle with `work/2026-09-19/R8D/prepare_upload.sh`.
2. Re-run `./stage.sh <new bundle dir>`. It warns if a new unversioned font needs a `_headers` rule.
3. Upload R2 objects first, then deploy the static assets:

```sh
npx wrangler@latest r2 object put gpt2-css-large/embedding-lookup.woff2 --file <new>/fonts/embedding-lookup.woff2 --content-type font/woff2 --remote   # only if changed
npx wrangler@latest r2 object put gpt2-css-large/runtime.css --file <new>/runtime.css --content-type 'text/css; charset=utf-8' --remote
npx wrangler@latest deploy
```

- There is a mixed-version window of a few seconds between the R2 upload and the deploy. A visitor who loads the page in that window can get the new `runtime.css` with the old fonts. Deploy at a quiet time, and do the two steps back to back.
- Browsers keep `index.html` and `runtime.css` for up to 5 minutes, and the unversioned fonts for up to 1 day.
- Changed fonts with `?v=` get new URLs, so they are never stale.

## 6. Rollback

```sh
npx wrangler@latest deployments list            # shows the version IDs
npx wrangler@latest rollback <version-id>       # restores the Worker code + static assets of that version
```

- `wrangler rollback` does **not** roll back R2 objects. Before you overwrite them, keep a copy of the current `runtime.css` and `embedding-lookup.woff2`. For example, keep the old bundle folder, or download them with `npx wrangler@latest r2 object get gpt2-css-large/runtime.css --file old-runtime.css --remote`. Then re-upload the copies with the `r2 object put` commands above.
- To take the demo offline:
  - `npx wrangler@latest delete` removes the Worker.
  - `npx wrangler@latest r2 object delete gpt2-css-large/<key> --remote` and then `r2 bucket delete gpt2-css-large` remove the bucket.
  - You can also turn off the workers.dev route under Workers > gpt2-css > Settings > Domains & Routes.

## 7. Local test, which needs no account

```sh
./stage.sh
npx wrangler@latest r2 object put gpt2-css-large/runtime.css --file "$M/runtime.css" --content-type 'text/css; charset=utf-8' --local
npx wrangler@latest r2 object put gpt2-css-large/embedding-lookup.woff2 --file "$M/fonts/embedding-lookup.woff2" --content-type font/woff2 --local
npx wrangler@latest dev --local --port 8799     # open http://127.0.0.1:8799/
rm -rf .wrangler                                  # afterwards: removes the ~105 MB local R2 copy
```
