# Hosting plan: Cloudflare R2 + custom domain (fallback: GitHub Release)
Placeholders: `DOMAIN`, bucket `gpt2-css`, `ACCT` = Cloudflare account id. Work dir `W=work/2026-09-19`.

**1. One-time Cloudflare setup**
1. Put DOMAIN on Cloudflare DNS (add site, switch nameservers at registrar; ~$10/yr if buying new).
2. R2 -> Create bucket `gpt2-css`. Settings -> Custom Domains -> add `demo.DOMAIN`. Keep the r2.dev URL disabled.
3. R2 -> Manage API tokens -> Create token, permission "Object Read & Write", scoped to this bucket. Put the keys in your shell only: `export AWS_ACCESS_KEY_ID=... AWS_SECRET_ACCESS_KEY=...` (never in a file).
4. Zone -> Speed -> Optimization: turn off Rocket Loader. Scrape Shield: turn off Email Obfuscation (both inject `<script>`; page CSP is `script-src 'none'`).
5. Rules -> Transform Rules -> URL Rewrite: `http.request.uri.path eq "/"` -> rewrite path to `/index.html` (R2 has no index document).
6. Rules -> Cache Rules: host `demo.DOMAIN` -> Eligible for cache, Edge TTL "Use cache-control header if present". Keep default query-string handling (the `?v=<sha>` digests then version fonts at the edge).

**2. Build the upload folder** (no `.br`; Cloudflare compresses at the edge)
`$W/R8D/prepare_upload.sh /tmp/gpt2-up` -> `/tmp/gpt2-up/model` (288 files, 312 MB), `/tmp/gpt2-up-zip/gpt2-in-css.zip` (253 MB). Strips BUILD.md/manifest.json/font-witnesses.json, greps for `/Users/`, checks every `url()` resolves in `fonts/`, runs the launcher `--check`.

**3. Upload** (needs aws-cli)
`$W/R8D/deploy_r2.sh --dry-run /tmp/gpt2-up/model gpt2-css ACCT` (inspect), then the same without `--dry-run`. Order: fonts (`font/woff2`, `font/ttf`, `immutable` 1 yr), runtime.css (`text/css; charset=utf-8`, max-age=300), README, index.html last (`text/html; charset=utf-8`, max-age=300).

**4. Verify**
```sh
U=https://demo.DOMAIN
curl -sI $U/ | grep -iE 'HTTP|content-type'                       # 200, text/html; charset=utf-8
curl -sI -H 'Accept-Encoding: br, gzip' $U/runtime.css | grep -iE 'content-type|content-encoding'   # text/css, br or gzip
F=$(grep -o 'fonts/[^"?)]*\.woff2' /tmp/gpt2-up/model/runtime.css | head -1)
curl -sI "$U/$F" >/dev/null; curl -sI "$U/$F" | grep -iE 'cf-cache-status|cache-control|content-type'  # HIT, immutable, font/woff2
curl -s $U/ | grep -ci '<script'                                   # 0 (nothing injected)
```
Then open in Chrome >= 139 and wait for "Ready".

**5. Fallback: GitHub Release zip**
`gh release create v1 /tmp/gpt2-up-zip/gpt2-in-css.zip --title "GPT-2 in CSS demo" --notes "Unzip, then: python3 tools/launch_browser_gpt2.py --directory model"` (253 MB, under the 2 GiB asset limit).

**6. Costs and page/README requirements**
- Cost: $0 egress on R2; free tier covers storage (0.3 GB < 10 GB). 1k-50k visitors: request fees <= ~$2; plus ~$10/yr domain.
- State: desktop Chrome/Chromium >= 139 only (no JS, stock browser), about 6 GB RAM free, ~300 MB first download (cached after), 15+ minutes for 32 tokens, tab must stay open.

**7. Updating**: rebuild with prepare_upload.sh and re-run deploy_r2.sh. Fonts are immutable-cached under digest-versioned URLs; index.html/runtime.css revalidate within 5 min. Purge the cache for `/` and `/runtime.css` if you need it instant.
