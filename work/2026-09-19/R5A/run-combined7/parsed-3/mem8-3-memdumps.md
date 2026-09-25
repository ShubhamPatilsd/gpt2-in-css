# memory-infra dumps — R5A/run-combined7/mem8-3-trace.json.gz

renderer pid 99300; 10 renderer dumps; token bounds (s after Run): [(1, 0.0), (2, 0.0), (3, 0.0), (4, 0.0), (5, 0.0), (6, 0.0), (7, 0.0)]

| dump | window | t (s) | level | RSS MB | PrivFoot MB | blink_gc | malloc | blink_objects | web_cache | partition_alloc | v8 | shared_memory | gpu | cc | skia | parkable_strings | site_storage | mojo | parkable_images | discardable | canvas |
|---|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| None | before post-load | 0.0 | light | 0 | 1,440 | 150 | 424 | 0 | 873 | 303 | 4 | 1 | 2 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| None | before post-load | 19.2 | light | 0 | 3,342 | 1,817 | 612 | 0 | 873 | 327 | 4 | 2 | 2 | 1 | 1 | 0 | 0 | 0 | 0 | 0 | 0 |
| None | before post-load | 33.0 | light | 0 | 4,422 | 2,549 | 877 | 0 | 873 | 353 | 4 | 2 | 2 | 1 | 1 | 0 | 0 | 0 | 0 | 0 | 0 |
| post-load | before token-1 | 47.5 | light | 0 | 4,979 | 3,082 | 944 | 0 | 873 | 371 | 4 | 2 | 2 | 1 | 1 | 0 | 0 | 0 | 0 | 0 | 0 |
| token-1 | before token-2 | 62.5 | light | 0 | 5,301 | 3,289 | 1,044 | 0 | 873 | 382 | 4 | 2 | 2 | 1 | 1 | 0 | 0 | 0 | 0 | 0 | 0 |
| token-2 | before token-3 | 79.3 | light | 0 | 5,317 | 3,438 | 1,090 | 0 | 873 | 391 | 4 | 1 | 2 | 1 | 1 | 0 | 0 | 0 | 0 | 0 | 0 |
| token-3 | before token-4 | 100.0 | light | 0 | 5,502 | 3,567 | 961 | 0 | 873 | 388 | 4 | 1 | 2 | 1 | 1 | 0 | 0 | 0 | 0 | 0 | 0 |
| None | before token-4 | 118.3 | light | 0 | 5,749 | 3,695 | 1,066 | 0 | 873 | 402 | 4 | 1 | 2 | 1 | 1 | 0 | 0 | 0 | 0 | 0 | 0 |
| None | before token-4 | 138.8 | light | 0 | 6,240 | 3,903 | 1,356 | 0 | 873 | 402 | 4 | 1 | 2 | 1 | 1 | 0 | 0 | 0 | 0 | 0 | 0 |
| token-4 | after token-4 | 146.6 | detailed | 0 | 5,666 | 2,975 | 834 | 924 | 873 | 344 | 4 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 |

## blink_gc (MB; blink_objects = counts)

| dump | main | main/heap | main/allocated_objects |
|---|---:|---:|---:|
| before post-load | 150.3 | 150.3 | 0.0 |
| before post-load | 1,817.5 | 1,817.5 | 0.0 |
| before post-load | 2,548.6 | 2,548.6 | 0.0 |
| post-load | 3,081.7 | 3,081.7 | 0.0 |
| token-1 | 3,288.8 | 3,288.8 | 0.0 |
| token-2 | 3,437.7 | 3,437.7 | 0.0 |
| token-3 | 3,566.9 | 3,566.9 | 0.0 |
| before token-4 | 3,695.2 | 3,695.2 | 0.0 |
| before token-4 | 3,902.9 | 3,902.9 | 0.0 |
| token-4 | 3,898.7 | 3,898.7 | 924.1 |

## partition_alloc (MB; blink_objects = counts)

| dump | partitions | partitions/buffer | allocated_objects | allocated_objects/<unspecified> | allocated_objects/__17ef71fabd2698da | allocated_objects/__dc8c5ed8d267b604 | allocated_objects/__d373e46d13ddb926 | allocated_objects/__65386bc298a06710 | allocated_objects/__d6185146b7e473e4 | allocated_objects/__de4dbe0ff5aeae48 | allocated_objects/__9528b10e77337b88 | allocated_objects/__9652212c6e15da5c | allocated_objects/__bd86ee93f131cfca | allocated_objects/__b426a0956f37d6f5 | allocated_objects/__bca4761b49fb7729 | allocated_objects/__c49c36003921e443 | allocated_objects/__d43738838c37e413 | allocated_objects/__f93a8e74a83ee592 | allocated_objects/__7d375549694349a4 | allocated_objects/__1c5b4c67612ac9e1 | allocated_objects/__12970e6d9b23dc60 | allocated_objects/__19c9fdcfa0e5a362 | allocated_objects/__979ef5f64ddc98bf | allocated_objects/__bb5cc6918093665b |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| before post-load | 304.5 | 304.5 | 274.8 | 273.5 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| before post-load | 328.3 | 328.3 | 315.7 | 314.4 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| before post-load | 354.0 | 354.0 | 350.2 | 348.9 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| post-load | 371.9 | 371.9 | 369.0 | 367.7 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| token-1 | 383.4 | 383.4 | 377.7 | 376.4 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| token-2 | 392.3 | 392.3 | 374.6 | 373.3 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| token-3 | 389.1 | 389.1 | 353.3 | 352.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| before token-4 | 403.1 | 403.1 | 372.4 | 371.1 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| before token-4 | 403.3 | 403.3 | 355.5 | 354.2 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| token-4 | 345.8 | 345.8 | 316.9 | 315.6 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |

## malloc (MB; blink_objects = counts)

| dump | partitions | allocated_objects |
|---|---:|---:|
| before post-load | 1,296.6 | 1,264.5 |
| before post-load | 1,484.3 | 1,428.8 |
| before post-load | 1,749.3 | 1,720.4 |
| post-load | 1,816.7 | 1,788.8 |
| token-1 | 1,916.7 | 1,893.8 |
| token-2 | 1,962.6 | 1,913.4 |
| token-3 | 1,834.0 | 1,655.2 |
| before token-4 | 1,939.1 | 1,799.8 |
| before token-4 | 2,228.1 | 2,188.1 |
| token-4 | 1,706.3 | 1,526.5 |

## skia (MB; blink_objects = counts)

| dump | sk_glyph_cache | sk_glyph_cache/CSS_Matrix_Variable_13720 | sk_glyph_cache/CSS_Matrix_Variable_13719 | sk_glyph_cache/CSS_Matrix_Variable_13723 | sk_glyph_cache/CSS_Matrix_Variable_13724 | sk_glyph_cache/CSS_Matrix_Variable_13721 | sk_glyph_cache/CSS_Matrix_Variable_13722 | sk_glyph_cache/_AppleSystemUIFont_4 | sk_glyph_cache/_AppleSystemUIFont_3 | sk_glyph_cache/_AppleSystemUIFont_8 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| before post-load | 0.4 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| before post-load | 0.6 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| before post-load | 0.7 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| post-load | 0.7 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| token-1 | 0.8 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| token-2 | 1.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| token-3 | 0.8 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| before token-4 | 0.9 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| before token-4 | 0.7 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| token-4 | 0.7 | 0.3 | 0.2 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |

## blink_objects (MB; blink_objects = counts)

| dump | blink_gc | MediaKeySession | Resource | Node | Document | ContextLifecycleStateObserver | MediaKeys | RTCPeerConnection | AudioHandler | WorkerGlobalScope | ArrayBufferContents | LayoutObject | ResourceFetcher | V8PerContextData | JSEventListener | AudioWorkletProcessor | DetachedScriptState | AdSubframe | Frame | UACSSResource |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| before post-load | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| before post-load | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| before post-load | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| post-load | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| token-1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| token-2 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| token-3 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| before token-4 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| before token-4 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| token-4 | 968,968,280 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |

## v8 (MB; blink_objects = counts)

| dump | main | main/heap | shared/read_only_space | shared | main/malloc | main/global_handles | main/code_stats | main/contexts |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| before post-load | 2.3 | 2.2 | 2.0 | 2.0 | 0.1 | 0.0 | 0.0 | 0.0 |
| before post-load | 2.2 | 2.1 | 2.0 | 2.0 | 0.1 | 0.0 | 0.0 | 0.0 |
| before post-load | 2.2 | 2.1 | 2.0 | 2.0 | 0.1 | 0.0 | 0.0 | 0.0 |
| post-load | 2.2 | 2.1 | 2.0 | 2.0 | 0.1 | 0.0 | 0.0 | 0.0 |
| token-1 | 2.1 | 2.0 | 2.0 | 2.0 | 0.1 | 0.0 | 0.0 | 0.0 |
| token-2 | 2.3 | 2.2 | 2.0 | 2.0 | 0.1 | 0.0 | 0.0 | 0.0 |
| token-3 | 2.3 | 2.2 | 2.0 | 2.0 | 0.1 | 0.0 | 0.0 | 0.0 |
| before token-4 | 2.2 | 2.1 | 2.0 | 2.0 | 0.1 | 0.0 | 0.0 | 0.0 |
| before token-4 | 2.3 | 2.2 | 2.0 | 2.0 | 0.1 | 0.0 | 0.0 | 0.0 |
| token-4 | 2.3 | 2.2 | 2.0 | 2.0 | 0.1 | 0.0 | 0.0 | 0.0 |

## discardable (MB; blink_objects = counts)

| dump | child_0x11400138C00 |
|---|---:|
| before post-load | 0.0 |
| before post-load | 0.0 |
| before post-load | 0.0 |
| post-load | 0.0 |
| token-1 | 0.0 |
| token-2 | 0.0 |
| token-3 | 0.0 |
| before token-4 | 0.0 |
| before token-4 | 0.0 |
| token-4 | 0.0 |

## other processes (RSS MB per dump)

- WebUI Top Renderer: before post-load=0, before post-load=0, before post-load=0, post-load=0, token-1=0, token-2=0, token-3=0, before token-4=0, before token-4=0, token-4=0
- Browser: before post-load=0, before post-load=0, before post-load=0, post-load=0, token-1=0, token-2=0, token-3=0, before token-4=0, before token-4=0, token-4=0
- GPU Process: before post-load=0, before post-load=0, before post-load=0, post-load=0, token-1=0, token-2=0, token-3=0, before token-4=0, before token-4=0, token-4=0
- Service: network.mojom.NetworkService: before post-load=0, before post-load=0, before post-load=0, post-load=0, token-1=0, token-2=0, token-3=0, before token-4=0, before token-4=0, token-4=0
- Service: storage.mojom.StorageService: before post-load=0, before post-load=0, before post-load=0, post-load=0, token-1=0, token-2=0, token-3=0, before token-4=0, before token-4=0, token-4=0
- Renderer: before post-load=0, before post-load=0, before post-load=0, post-load=0, token-1=0, token-2=0, token-3=0, before token-4=0, before token-4=0, token-4=0
- Service: tracing.mojom.TracingService: before post-load=0, before post-load=0, before post-load=0, post-load=0, token-1=0, token-2=0, token-3=0, before token-4=0, before token-4=0, token-4=0