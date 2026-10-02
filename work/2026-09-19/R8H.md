# R8H — where to host the demo-c32 bundle (research only, 2026-10-02; all prices "as of 2026-10-02", sources in Appendix)

## 0. Answer
**Top choice: Cloudflare R2 bucket behind a custom domain (Cloudflare-proxied).** $0 egress, $0 at 1k/10k/50k visitors (storage 0.25 GB < 10 GB free;
worst-case ops ≈ $1.60), per-object limit 5 GB (largest file 57 MB), cached at the edge (512 MB cacheable cap on Free), and — the key point — Cloudflare's
current terms (updated 2026-09-28) only restrict large non-HTML files on the CDN when they are *not* served via a Developer Platform service; R2 is one
(Cloudflare's 2023-05-16 ToS post names R2 explicitly). Needs a domain whose DNS is on Cloudflare (~$10/yr). No bundle change needed.
**Simplest:** GitHub Pages (push `model/`, no domain, no account setup) — but only ≈ 320–400 first visits/month fit its 100 GB *soft* cap; fine for a
private link, wrong for HN. **Robust no-Cloudflare alternative:** CloudFront flat-rate **Pro $15/month** (50 TB, no overage; first 3× spike tolerated) or
**Bunny** ($0.01/GB NA/EU ≈ $125 per 50k visitors). **Fallback (always ship):** GitHub Release asset `gpt2-css-demo.zip` (≈ 300 MB; 2 GiB/asset, no
bandwidth limit) + `tools/launch_browser_gpt2.py` — survives any hosting outage or throttling.

## 1. Bytes per first visit (measured locally on demo-c32)
raw 311.8 MB = index.html 7.45 + runtime.css 53.63 + 283 woff2 239.11 + 3 TTF 11.61 (noise 8.33, token-id 1.66 + 1.62). Compressed: br-11 html 0.54 /
css 2.05 / TTFs 4.79 → **≈ 246.5 MB**; on-the-fly at CDN levels (zstd-3/br-4..5: css 3.5–5.3, html ≈ 1.5, TTFs ≈ 6) → **≈ 250–252 MB**; gzip-9 → 253.5 MB.
The woff2 (239 MB = 96 %) are incompressible, so "precompress" only moves 312 → ~250 MB; the choice of host matters far more than br vs gzip.
Only files > 25 MiB: `embedding-lookup.woff2` 56,853,724 B and `runtime.css` 53.6 MB; head faces are 16.4 MB.

## 2. Comparison (monthly; costs for 1k / 10k / 50k first visits at 312 MB → 250 MB; NA/EU rates)
| option | per-file / site limit | egress price, free tier | precompressed .br/.gz? on-the-fly? | headers | 1k | 10k | 50k | effort |
|---|---|---|---|---|---|---|---|---|
| **R2 + custom domain** | 5 GB/object (S3 multipart); no site cap | **$0 egress**; 10 GB storage, 10 M class-B reads free | br objects reportedly mis-served via custom domain (gzip OK); CF compresses on the fly (Free default zstd; Compression Rules on Free) | per-object Content-Type/Cache-Control metadata; Rules | $0 | $0 | $0 (≤$1.6 ops) | medium (domain on CF, 2 rules) |
| R2 via `r2.dev` | same | $0 | as above, no CF cache/rules | object metadata | — | — | — | **not for launch: "rate-limited… development only"** |
| CF Workers static assets / Pages | **25 MiB/file**; 20k files (Free) | $0, asset requests free & unlimited | CF on the fly | `_headers` (100 rules) | $0 | $0 | $0 | **blocked**: needs CSS split (≥3 sheets, mechanical) + embedding font split (≥3 faces, emitter change, §4) |
| GitHub Pages | 100 MB/file push, 1 GB site | free; **100 GB/mo soft**, 429 rate-limiting | gzip on the fly only, no .br | none (fixed ~10 min cache) | ~at cap (3× over at 312) | ToS-soft violation | throttling likely | **lowest** |
| Netlify | ~10 MB/file recommended | 20 credits/GB; Free 300 cr = 15 GB → **site paused**; Pro $20 = 150 GB, +1500 cr/$10 (≈$0.133/GB) | on the fly | `_headers` | $42 / $33 | $416 / $333 | $2,080 / $1,666 (+≈$19 requests) | low |
| Vercel | Hobby 100 MB upload (unusable, non-commercial); Pro 1 GB | Pro $20 incl. 1 TB, then $0.15/GB | on the fly | `vercel.json` | $20 | $338 / $245 | $2,210 / $1,745 | low |
| B2 + Cloudflare CDN | 10 TB/file | B2 egress free to CF; storage free < 10 GB | CF on the fly | B2 bucket info headers | $0 | $0 | $0 | medium; **ToS risk**: large non-HTML files on CDN not hosted on CF dev platform |
| Bunny storage + CDN | no practical cap | $0.01/GB NA/EU (Asia/LatAm higher), Volume net $0.005; $1 min; storage $0.01/GB | compresses .css/.html on the fly (no cap documented) | Edge Rules | $3.1 / $2.5 | $31 / $25 | $156 / $125 | low–medium |
| S3 + CloudFront PAYG | 5 TB/object | 1 TB + 10 M req/mo always free, then $0.085/GB | **on the fly only 1 KB–10 MB** → upload `runtime.css` as br with `Content-Encoding: br` (passed through) | S3 metadata / response-header policy | $0 | $180 / $128 | ≈$1,220 / $970 | medium–high |
| **CloudFront flat-rate** | same | Free $0 = 100 GB; **Pro $15 = 50 TB**, no overage, 1st spike ≤3× tolerated, then "delivery adjusted" | same 10 MB rule | S3 metadata (custom header policies only Business+) | $0 (Free, within 3×) | $15 | $15 | medium–high |
| HF static Space | 1 GB repo (LFS > 10 MB) | free, bandwidth undocumented | unknown | none | $0? | ? | ? | low, **unpredictable** |
| Fly.io (nginx) | disk | $0.02/GB + ~$2 machine | nginx `brotli_static` | full | $8 / $7 | $64 / $52 | $314 / $252 | medium |
| Render static | — | Hobby 5 GB, then $0.15/GB (Apr 2026) | on the fly | `_headers`-like | $46 / $37 | $467 / $374 | $2.3k / $1.9k | low |
| Hetzner CX23 + nginx | disk 40 GB | €5.49 incl. 20 TB (EU), €1/TB | `brotli_static`/`gzip_static` exact | full | €5.5 | €5.5 | €5.5 | medium; **throughput cap ≈ 300–500 Mbit/s** = ~15–25k visitors/day if perfectly spread; a spike of 100 concurrent → ~8 min downloads |

No provider found that throttles *per file size*; the throttles are volume-based (GitHub Pages soft cap/429, r2.dev rate limit, CloudFront flat-rate
"adjusted delivery", Netlify/Render suspension when credits/allowance end on free tiers). CF's 512 MB cacheable-file cap is far above 57 MB.

## 3. Deployment recipe — R2 + custom domain
1. Domain on Cloudflare DNS. R2 → create bucket `gpt2-css` → Settings → Custom Domains → `demo.<domain>` (keep r2.dev **disabled**).
2. Pack **without** `--br` (CF compresses; br objects are a known R2 pitfall): `R6X/pack_demo.sh demo-c32 /tmp/gpt2-css-demo` →
   `model/{index.html,runtime.css,fonts/(286)}`. **Do not upload `model/BUILD.md` / `model/manifest.json`** — both contain `/Users/…` paths.
3. Bucket layout = `model/` at bucket root: `/index.html`, `/runtime.css`, `/fonts/<name>.woff2|.ttf` (CSS already says `url("fonts/<name>?v=<sha>")`,
   relative — keep relative). Upload with an R2 S3 token (`R2=https://<ACCOUNT_ID>.r2.cloudflarestorage.com`; if aws-cli ≥ 2.23 complains about
   checksums set `AWS_REQUEST_CHECKSUM_CALCULATION=when_required`), fonts first, `index.html` last:
   ```sh
   M=/tmp/gpt2-css-demo/model; S3="aws s3 cp --endpoint-url $R2"; IMM='public, max-age=31536000, immutable'
   $S3 $M/fonts s3://gpt2-css/fonts --recursive --exclude '*' --include '*.woff2' --content-type font/woff2 --cache-control "$IMM"
   $S3 $M/fonts s3://gpt2-css/fonts --recursive --exclude '*' --include '*.ttf'   --content-type font/ttf   --cache-control "$IMM"
   $S3 $M/runtime.css s3://gpt2-css/runtime.css --content-type 'text/css; charset=utf-8'  --cache-control 'public, max-age=300'
   $S3 $M/index.html  s3://gpt2-css/index.html  --content-type 'text/html; charset=utf-8' --cache-control 'public, max-age=300'
   ```
   (`text/css` is mandatory — Chrome drops mistyped sheets; both text files contain non-ASCII, so state `charset=utf-8`. `font/ttf` lets CF compress the
   8.3 MB noise font to ≈ 4.8 MB.)
4. Zone rules (all Free): **Transform → URL rewrite** `http.request.uri.path eq "/"` → path `/index.html` (R2 has no index document);
   **Cache Rule** host `demo.<domain>` → eligible for cache, Edge TTL "use origin Cache-Control" (css/woff2/ttf are cached by default; this also caches
   index.html for 5 min). Query string stays in the cache key (default), so `?v=` digests make fonts version-safe at the edge. Optional Compression Rule
   (`text/css`, `text/html`, `font/ttf` → brotli, zstd, gzip). Turn off Rocket Loader / Email Obfuscation (they inject scripts; the page's CSP is `script-src 'none'`).
5. Verify: `curl -sI https://demo.<domain>/` (200, text/html); `curl -s -o /dev/null -w '%{size_download}\n' -H 'Accept-Encoding: br, zstd, gzip'
   https://demo.<domain>/runtime.css` (expect ≈ 2–5 MB); repeat a font HEAD twice → `cf-cache-status: HIT`, `cache-control: … immutable`, `content-type: font/woff2`.
   Then open in Chrome ≥ 139 and watch for "Ready".

## 4. Bundle changes
- **Required for R2 / CloudFront / Bunny / nginx / GitHub Pages: none.** Same-origin relative URLs → no CORS. Root `/` handled by a rewrite (R2),
  default root object (CloudFront) or natively (Pages/nginx).
- Recommended (pack step only): exclude BUILD.md/manifest.json from `model/`; name the sheet `runtime.<sha8>.css` (and font keys `<name>.<sha8>.woff2`)
  so everything except index.html is immutable and redeploys are atomic; fix pack_bundle.py's stale README text (says 283 fonts / 239 MB; now 286 / 251 MB).
- Only for Cloudflare Pages/Workers (not recommended): split `runtime.css` into ≥ 3 sheets < 25 MiB (mechanical: cut at top-level rule boundaries, ordered
  `<link>`s preserve the cascade) **and** split `embedding-lookup.woff2` into ≥ 3 faces (~19 MB each). The embedding font is a *variable* font addressed by
  axes `GRUP` = token/256 and `LOCL` = token mod 256, not by codepoint, so `unicode-range` cannot split it; the emitter would have to partition the GRUP
  range into 3 fonts and the CSS pick the family from `--fq-token-group` — a model-path change needing full Chrome re-verification. Not worth it vs R2.
- For CloudFront/nginx only: keep `--br` (`runtime.css.br`/`index.html.br`) and serve with `Content-Encoding: br` (CloudFront will not compress > 10 MB).

## 5. Monthly cost scenarios (top 3)
| visitors/month | R2 + domain | CloudFront flat Pro | Bunny (NA/EU) | GitHub Pages |
|---|---|---|---|---|
| 1k (250–312 GB) | $0 (+$10/yr domain) | $15 (or Free plan $0) | $2.5–3 | over soft cap |
| 10k (2.5–3.1 TB) | $0 | $15 | $25–31 | not acceptable |
| 50k (12.5–15.6 TB) | $0–1.6 | $15 | $125–156 | not acceptable |

Caveats: R2 brotli-object behaviour and CF's on-the-fly compression size handling for the 53.6 MB sheet come from community reports/docs, not tested here
(no publishing) — step 5's curl check settles both in a minute. Visitors still need Chrome/Edge ≥ 139 and 16 GB RAM; say so on the landing link.

## Appendix — sources (accessed 2026-10-02)
- Cloudflare R2 pricing: https://developers.cloudflare.com/r2/pricing/ · public buckets / r2.dev rate-limit: https://developers.cloudflare.com/r2/buckets/public-buckets/
- CF service-specific terms (CDN large-file clause, last updated 2026-09-28): https://www.cloudflare.com/service-specific-terms-application-services/
- CF "Goodbye section 2.8" (2023-05-16, large files OK if hosted on Stream/Images/R2): https://blog.cloudflare.com/updated-tos/
- CF default cache behaviour (extensions, 512 MB): https://developers.cloudflare.com/cache/concepts/default-cache-behavior/ · R2 cache: https://developers.cloudflare.com/cache/interaction-cloudflare-products/r2/
- CF compression (origin encoding respected, zstd Free default): https://developers.cloudflare.com/speed/optimization/content/compression/ · Compression Rules: https://developers.cloudflare.com/rules/compression-rules/
- R2 br objects via custom domain: https://community.cloudflare.com/t/r2-bindings-and-compressed-content-without-content-encoding-or-content-length/782040 , https://community.cloudflare.com/t/serve-pre-compressed-brotli-content/536731
- R2 has no index document / Transform Rules: https://blog.iany.me/2025/10/hosting-static-site-on-cloudflare-r2/ , https://community.cloudflare.com/t/index-html-as-root-object-for-spa/581177
- Workers static assets limits (25 MiB, 20k/100k): https://developers.cloudflare.com/changelog/post/2025-09-02-increased-static-asset-limits/ · billing: https://developers.cloudflare.com/workers/static-assets/billing-and-limitations/ · Pages limits: https://developers.cloudflare.com/pages/platform/limits/
- GitHub Pages limits: https://docs.github.com/en/pages/getting-started-with-github-pages/github-pages-limits · gzip only: https://github.com/orgs/community/discussions/21655 · Releases (2 GiB/asset, no bandwidth limit): https://docs.github.com/en/repositories/releasing-projects-on-github/about-releases
- Netlify pricing: https://www.netlify.com/pricing/ · credits: https://docs.netlify.com/manage/accounts-and-billing/billing/billing-for-credit-based-plans/how-credits-work/ · file size: https://answers.netlify.com/t/what-is-the-maximum-allowed-object-size/145182
- Vercel pricing: https://vercel.com/pricing · limits (static upload 100 MB Hobby / 1 GB Pro; page dated 2026-09-16): https://vercel.com/docs/limits
- Backblaze B2: https://www.backblaze.com/cloud-storage/pricing · Bunny: https://bunny.net/pricing/ , https://docs.bunny.net/storage/pricing , https://bunny.net/docs/cdn/frequently-asked-questions/mime-compression
- CloudFront pricing: https://aws.amazon.com/cloudfront/pricing/ · flat-rate plans: https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/flat-rate-pricing-plan.html · compression (1 KB–10 MB): https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/ServingCompressedFiles.html · PAYG $0.085/GB: https://egresscost.com/aws/cloudfront-pricing/ · 1 TB always-free: https://spot.rackspace.com/blog/aws-free-tier
- HF static Spaces: https://huggingface.co/docs/hub/spaces-sdks-static · 1 GB Space repo cap: https://discuss.huggingface.co/t/1gb-storage-limit-in-spaces/170196
- Render free/bandwidth: https://render.com/docs/free , https://bex.co/blog/2026/07/09/render-april-2026-repricing-egress-cut-self-hosting-cost · Fly: https://docs.fly.io/about/pricing
- Hetzner CX23 (prices 2026-09-05): https://costgoat.com/pricing/hetzner · per-server 300–500 Mbit/s: https://bestusavps.com/benchmarks/hetzner/
