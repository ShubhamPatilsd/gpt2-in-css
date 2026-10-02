.PHONY: build transformer pretrained benchmark interactive analyze-full output-head-baselines output-head-search clustered-output-head hierarchical-output-head matrix-backends test-matrix-backends font-metric-vector font-metric-vector-benchmark test-font-metric-vector additive-font-vector custom-property-vector test-additive-font-vector numeric-vector-mlp test-numeric-vector-mlp matrix-scaling test-matrix-scaling matrix-shards test-matrix-shards packed-font-shards signed-hvar-chain test-signed-hvar-chain gpt2-hvar-chain test-gpt2-hvar-chain shadow-depth-probe gpt2-block-css test-gpt2-block-css view-timeline-fc test-view-timeline-fc packed-timeline-precision bilinear-hvar-attention test-bilinear-hvar-attention qkv-transport test-qkv-transport container-packed-block test-container-packed-block svg-filter-matvec svg-filter-gpt2 svg-filter-full-block svg-filter-output-head test-svg-filter-output-head svg-multitoken-attention test-svg-multitoken-attention test-svg-filter-full-block test-svg-filter-grouped-layernorm test-svg-filter-bucketed-twelve-blocks test-svg-filter-two-blocks test-svg-filter-twelve-blocks trace-svg-filter-blocks multitoken-attention test-multitoken-attention attention-context-scaling test-attention-context-scaling geometry-streaming-attention test-geometry-streaming-attention composed-qk-probe test-composed-qk-probe tinystories-step tinystories-recurrent tinystories-nested tinystories-tokenizer-font tinystories-dynamic tinystories-all precompress-tinystories precompress-tinystories-experiments serve-tinystories timeline-hvar-projection test-timeline-hvar-projection test clean
.PHONY: projected-kv-attention benchmark-projected-kv-attention projected-kv-full-block benchmark-projected-kv-full-block benchmark-projected-kv-containment benchmark-projected-kv-breakdown

build:
	python3 tools/build.py

transformer:
	python3 tools/build_transformer.py

pretrained:
	python3 tools/build_pretrained_gpt2.py

benchmark: pretrained
	@echo "open http://localhost:4173/pretrained/benchmark.html"

interactive: pretrained
	@echo "open http://localhost:4173/pretrained/interactive.html"

analyze-full:
	python3 tools/analyze_full_gpt2.py

output-head-baselines:
	python3 tools/build_output_head_benchmark.py

output-head-search:
	python3 tools/analyze_output_head_search.py --clusters 64 128 256 512 1024 2048 4096

clustered-output-head:
	python3 tools/build_clustered_output_head_benchmark.py

hierarchical-output-head:
	python3 tools/analyze_hierarchical_output_head.py

matrix-backends:
	uv run --with fonttools --with numpy --with pillow --with brotli python tools/build_matrix_backend_prototypes.py

test-matrix-backends: matrix-backends
	uv run --with fonttools --with numpy --with pillow --with brotli python tools/test_matrix_backend_prototypes.py

font-metric-vector:
	PYTHONPATH=tools uv run --with fonttools --with numpy --with brotli python tools/build_font_metric_vector_probe.py

font-metric-vector-benchmark:
	PYTHONPATH=tools uv run --with fonttools --with numpy --with brotli python tools/build_font_metric_vector_benchmark.py --ttf

additive-font-vector:
	for size in 64 256 768; do uv run --with fonttools --with numpy --with pillow --with brotli python tools/build_additive_font_vector_probe.py $$size; done

custom-property-vector: additive-font-vector
	for size in 64 256 768; do PYTHONPATH=tools uv run --with fonttools --with numpy --with pillow --with brotli python tools/build_custom_property_vector_probe.py $$size; done

test-additive-font-vector: custom-property-vector
	PYTHONPATH=tools uv run --with fonttools --with numpy --with pillow --with brotli python tools/test_additive_font_vector_probe.py

numeric-vector-mlp: gpt2-block-css
	PYTHONPATH=tools uv run --with fonttools --with numpy --with pillow --with brotli python tools/build_additive_mlp_vector.py

test-numeric-vector-mlp: numeric-vector-mlp
	PYTHONPATH=tools uv run --with fonttools --with numpy --with pillow --with brotli python tools/test_additive_mlp_vector.py

test-font-metric-vector: font-metric-vector
	PYTHONPATH=tools uv run --with fonttools --with numpy --with brotli python tools/test_font_metric_vector_probe.py

matrix-scaling:
	for size in 64 128 256; do uv run --with fonttools --with numpy --with pillow --with brotli python tools/build_variable_font_scaling.py --size $$size; done

test-matrix-scaling:
	for size in 64 128 256; do uv run --with fonttools --with numpy --with pillow --with brotli python tools/test_variable_font_scaling.py --size $$size; done

matrix-shards:
	uv run --with fonttools --with numpy --with pillow --with brotli python tools/build_variable_font_shards.py

test-matrix-shards:
	uv run --with fonttools --with numpy --with pillow --with brotli python tools/test_variable_font_shards.py

packed-font-shards:
	uv run --with fonttools --with numpy --with pillow --with brotli python tools/build_packed_font_shards.py

signed-hvar-chain:
	uv run --with fonttools --with numpy --with pillow --with brotli python tools/build_signed_hvar_chain.py

test-signed-hvar-chain: signed-hvar-chain
	uv run --with fonttools --with numpy --with pillow --with brotli python tools/test_signed_hvar_chain.py

gpt2-hvar-chain:
	uv run --with fonttools --with numpy --with pillow --with brotli python tools/build_gpt2_hvar_chain.py

test-gpt2-hvar-chain: gpt2-hvar-chain
	uv run --with fonttools --with numpy --with pillow --with brotli python tools/test_gpt2_hvar_chain.py

shadow-depth-probe:
	python3 tools/build_shadow_depth_probe.py

gpt2-block-css:
	uv run --with fonttools --with numpy --with pillow --with brotli python tools/build_gpt2_block_css.py

test-gpt2-block-css: gpt2-block-css
	uv run --with fonttools --with numpy --with pillow --with brotli python tools/test_gpt2_block_css.py

view-timeline-fc:
	uv run --with fonttools --with numpy --with pillow --with brotli python tools/build_view_timeline_fc.py

test-view-timeline-fc: view-timeline-fc
	uv run --with fonttools --with numpy --with pillow --with brotli python tools/test_view_timeline_fc.py

packed-timeline-precision:
	uv run --with numpy python tools/build_packed_timeline_precision.py

bilinear-hvar-attention:
	PYTHONPATH=tools uv run --with fonttools --with numpy --with pillow --with brotli python tools/build_bilinear_hvar_attention.py

test-bilinear-hvar-attention: bilinear-hvar-attention
	BILINEAR_HVAR_VARIANTS=css,exact4 BILINEAR_HVAR_ROUNDS=4 /Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node tools/test_bilinear_hvar_attention.mjs

qkv-transport:
	PYTHONPATH=tools uv run --with fonttools --with numpy --with pillow --with brotli python tools/build_qkv_transport_comparison.py

test-qkv-transport: qkv-transport
	PYTHONPATH=tools uv run --with fonttools --with numpy --with pillow --with brotli python tools/analyze_qkv_packing_precision.py
	QKV_TRANSPORT_ROUNDS=5 /Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node tools/test_qkv_transport_comparison.mjs

container-packed-block:
	PYTHONPATH=tools uv run --with fonttools --with numpy --with pillow --with brotli python tools/build_container_packed_block.py

test-container-packed-block: container-packed-block
	CONTAINER_PACKED_BLOCK_ROUNDS=7 /Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node tools/test_container_packed_block.mjs
	CONTAINER_PACKED_PREFIX_ROUNDS=7 /Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node tools/test_container_packed_block_prefixes.mjs

svg-filter-matvec:
	for size in 4 16 64 128 256 512 768; do uv run --with numpy --with pillow python tools/build_svg_filter_matvec_probe.py --size $$size; done
	uv run --with numpy --with pillow python tools/build_svg_filter_fc_probe.py

svg-filter-gpt2:
	uv run --with fonttools --with numpy --with pillow --with brotli python tools/build_svg_filter_gpt2_attention.py
	SVG_FC_GROUP=1 SVG_PROJECTION_GROUP=1 uv run --with fonttools --with numpy --with pillow --with brotli python tools/build_svg_filter_gpt2_fc.py

svg-filter-full-block:
	uv run --with fonttools --with numpy --with pillow --with brotli python tools/build_svg_filter_full_block.py

test-svg-filter-full-block: svg-filter-full-block
	SVG_TIMING_RUNS=2 SVG_MUTATION_RUNS=20 /Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node tools/test_svg_filter_chain.mjs

test-svg-filter-grouped-layernorm: svg-filter-full-block
	/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node tools/test_svg_filter_grouped_layernorm.mjs

test-svg-filter-bucketed-twelve-blocks: svg-filter-full-block
	/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node tools/test_svg_filter_bucketed_twelve_blocks.mjs

svg-filter-output-head: svg-filter-full-block
	PYTHONPATH=tools uv run --with numpy --with pillow python tools/build_svg_output_head.py

test-svg-filter-output-head: svg-filter-output-head
	/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node tools/test_svg_output_head.mjs

svg-multitoken-attention: multitoken-attention
	PYTHONPATH=tools uv run --with numpy --with pillow python tools/build_svg_multitoken_attention.py

test-svg-multitoken-attention: svg-multitoken-attention
	/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node tools/test_svg_multitoken_attention.mjs
	uv run --with numpy --with brotli --with pillow --with fonttools python tools/verify_svg_filter_bucketed_tokens.py

test-svg-filter-two-blocks: svg-filter-full-block
	/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node tools/test_svg_filter_two_blocks.mjs

test-svg-filter-twelve-blocks: svg-filter-full-block
	/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node tools/test_svg_filter_twelve_blocks.mjs

trace-svg-filter-blocks: svg-filter-full-block
	/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node tools/trace_svg_filter_blocks.mjs

multitoken-attention:
	uv run --with fonttools --with numpy --with pillow --with brotli python tools/build_multitoken_attention_css.py
	uv run --with fonttools --with numpy --with pillow --with brotli python tools/build_multitoken_attention_css.py --score-backend bilinear
	uv run --with fonttools --with numpy --with pillow --with brotli python tools/build_multitoken_attention_css.py --qkv-transport container

test-multitoken-attention: multitoken-attention
	uv run --with fonttools --with numpy --with pillow --with brotli python tools/test_multitoken_attention_css.py
	/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node tools/test_multitoken_attention_browser.mjs
	MULTITOKEN_ATTENTION_URL=http://127.0.0.1:4178/experiments/gpt2-block-css/view-timeline-attention-2token-qkv-container.html MULTITOKEN_ATTENTION_REFERENCE=../experiments/gpt2-block-css/view-timeline-attention-2token-qkv-container-reference.json /Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node tools/test_multitoken_attention_browser.mjs
	ATTENTION_SCORE_ROUNDS=4 /Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node tools/benchmark_multitoken_attention_score_backends.mjs

attention-context-scaling:
	uv run --with fonttools --with numpy --with pillow --with brotli python tools/analyze_qkv_packing_precision.py
	for transport in container timeline; do for context in 1 2 4 8; do uv run --with fonttools --with numpy --with pillow --with brotli python tools/build_attention_context_scaling.py --qkv-transport $$transport --context $$context; done; done
	for context in 1 2 4 8; do uv run --with fonttools --with numpy --with pillow --with brotli python tools/build_streaming_attention_context.py --context $$context; done
	for context in 1 2 4 8 16; do uv run --with fonttools --with numpy --with pillow --with brotli python tools/build_streaming_attention_context.py --key-transport anchor --context $$context; done

test-attention-context-scaling: attention-context-scaling
	ATTENTION_CONTEXT_ROUNDS=3 /Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node tools/benchmark_attention_context_scaling.mjs

geometry-streaming-attention:
	uv run --with fonttools --with numpy --with pillow --with brotli python tools/analyze_attention_context_precision.py
	for context in 2 4 8 16; do uv run --with fonttools --with numpy --with pillow --with brotli python tools/build_geometry_streaming_attention.py --context $$context; done
	for context in 2 4 8 16; do uv run --with fonttools --with numpy --with pillow --with brotli python tools/build_geometry_streaming_attention.py --context $$context --with-projection; done
	for reduction in flat inline; do for context in 2 4 8 16; do uv run --with fonttools --with numpy --with pillow --with brotli python tools/build_geometry_streaming_attention.py --context $$context --with-projection --reduction $$reduction; done; done
	for context in 2 4 8 16 32; do uv run --with fonttools --with numpy --with pillow --with brotli python tools/build_geometry_streaming_attention.py --context $$context --with-projection --reduction flat --source-topology siblings; done
	for context in 2 8 16; do uv run --with fonttools --with numpy --with pillow --with brotli python tools/build_geometry_streaming_attention.py --context $$context --with-projection --reduction flat --source-topology siblings --isolate-query-inheritance; done
	for context in 2 8 16; do uv run --with fonttools --with numpy --with pillow --with brotli python tools/build_geometry_streaming_attention.py --context $$context --with-projection --reduction flat --source-topology siblings --split-query-cache; done

test-geometry-streaming-attention: geometry-streaming-attention
	GEOMETRY_STREAMING_PROJECTED=1 GEOMETRY_STREAMING_ROUNDS=3 /Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node tools/benchmark_geometry_streaming_attention.mjs
	GEOMETRY_STREAMING_PROJECTED=1 GEOMETRY_STREAMING_REDUCTION=flat GEOMETRY_STREAMING_ROUNDS=3 /Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node tools/benchmark_geometry_streaming_attention.mjs
	GEOMETRY_STREAMING_PROJECTED=1 GEOMETRY_STREAMING_REDUCTION=inline GEOMETRY_STREAMING_ROUNDS=3 /Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node tools/benchmark_geometry_streaming_attention.mjs
	GEOMETRY_STREAMING_PROJECTED=1 GEOMETRY_STREAMING_REDUCTION=flat GEOMETRY_STREAMING_SOURCE_TOPOLOGY=siblings ATTENTION_CONTEXTS=2,4,8,16,32 GEOMETRY_STREAMING_ROUNDS=3 /Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node tools/benchmark_geometry_streaming_attention.mjs

geometry-streaming-full-tail:
	uv run --with fonttools --with numpy --with pillow --with brotli python tools/build_geometry_streaming_full_tail.py

test-geometry-streaming-full-tail: geometry-streaming-full-tail
	GEOMETRY_FULL_TAIL_CONTEXTS=2,8,16 GEOMETRY_FULL_TAIL_ROUNDS=3 GEOMETRY_FULL_TAIL_VARIANTS=attention,tail-isolated,connected,gated,display-gated,dual-boundary node tools/benchmark_geometry_streaming_full_tail.mjs

profile-geometry-streaming-full-tail: geometry-streaming-full-tail
	GEOMETRY_FULL_TAIL_PROFILE_CONTEXT=16 node tools/profile_geometry_streaming_full_tail.mjs

benchmark-geometry-streaming-full-tail-mutation: geometry-streaming-full-tail
	GEOMETRY_FULL_TAIL_MUTATION_CONTEXTS=8,16 GEOMETRY_FULL_TAIL_MUTATION_ROUNDS=7 node tools/benchmark_geometry_streaming_full_tail_mutation.mjs

geometry-score-track-groups:
	for group in 1 2 4 8; do PYTHONPATH=tools uv run --with fonttools --with numpy --with pillow --with brotli python tools/build_geometry_streaming_attention.py --context 16 --with-projection --reduction flat --source-topology siblings --score-track-group-size $$group; done

feature-selected-metric-pair:
	PYTHONPATH=tools uv run --with numpy --with fonttools python tools/build_feature_selected_metric_pair.py
	node tools/test_feature_selected_metric_pair.mjs

feature-selected-qk:
	PYTHONPATH=tools uv run --with numpy --with fonttools --with brotli --with pillow python tools/build_feature_selected_qk.py
	FEATURE_QK_ROUNDS=7 node tools/test_feature_selected_qk.mjs

feature-selected-qk-all-heads:
	PYTHONPATH=tools uv run --with numpy --with fonttools --with brotli --with pillow python tools/build_feature_selected_qk_all_heads.py
	FEATURE_QK_ALL_HEADS_ROUNDS=3 node tools/test_feature_selected_qk_all_heads.mjs

feature-selected-attention: feature-selected-qk-all-heads
	for context in 2 4 8 16 32; do PYTHONPATH=tools uv run --with numpy --with fonttools --with brotli --with pillow python tools/build_geometry_streaming_attention.py --context $$context --score-backend feature --value-backend mixed-input --source-topology siblings --reduction flat --with-projection; done

benchmark-feature-selected-attention: feature-selected-attention
	ATTENTION_CONTEXTS=2,4,8,16,32 GEOMETRY_STREAMING_ROUNDS=3 GEOMETRY_STREAMING_PROJECTED=1 GEOMETRY_STREAMING_REDUCTION=flat GEOMETRY_STREAMING_SCORE_BACKEND=feature GEOMETRY_STREAMING_VALUE_BACKEND=mixed-input GEOMETRY_STREAMING_SOURCE_TOPOLOGY=siblings node tools/benchmark_geometry_streaming_attention.mjs

profile-feature-selected-attention: feature-selected-attention
	node tools/profile_feature_selected_attention.mjs

projected-kv-attention:
	PYTHONPATH=tools uv run --with numpy --with fonttools --with brotli --with pillow python tools/build_projected_kv_qk.py
	for context in 2 8 16 32; do PYTHONPATH=tools uv run --with numpy --with fonttools --with brotli --with pillow python tools/build_geometry_streaming_attention.py --context $$context --score-backend feature-kv --value-backend cached-v --source-topology siblings --reduction flat --with-projection; done
	for context in 16 32; do PYTHONPATH=tools uv run --with numpy --with fonttools --with brotli --with pillow python tools/build_geometry_streaming_attention.py --context $$context --score-backend feature-kv --value-backend cached-v --live-current-kv --source-topology siblings --reduction flat --with-projection; done
	for context in 16 32; do PYTHONPATH=tools uv run --with numpy --with fonttools --with brotli --with pillow python tools/build_geometry_streaming_attention.py --context $$context --score-backend feature-kv --value-backend cached-v --live-current-kv --source-topology siblings --reduction flat --with-projection --projection-transport packet12; done
	for context in 16 32; do PYTHONPATH=tools uv run --with numpy --with fonttools --with brotli --with pillow python tools/build_geometry_streaming_attention.py --context $$context --score-backend css-kv --value-backend cached-v --live-current-kv --source-topology siblings --reduction flat --with-projection --projection-transport packet12; done

benchmark-projected-kv-attention: projected-kv-attention
	ATTENTION_CONTEXTS=2,8,16,32 GEOMETRY_STREAMING_ROUNDS=3 GEOMETRY_STREAMING_PROJECTED=1 GEOMETRY_STREAMING_REDUCTION=flat GEOMETRY_STREAMING_SCORE_BACKEND=feature-kv GEOMETRY_STREAMING_VALUE_BACKEND=cached-v GEOMETRY_STREAMING_SOURCE_TOPOLOGY=siblings node tools/benchmark_geometry_streaming_attention.mjs

projected-kv-full-block: projected-kv-attention
	PYTHONPATH=tools uv run --with numpy --with fonttools --with brotli --with pillow --with safetensors python tools/build_multitoken_block0_output_ranges.py
	PYTHONPATH=tools uv run --with numpy --with fonttools --with brotli --with pillow --with safetensors python tools/build_projected_kv_full_block.py --contexts 16 32 --projection-transports timeline packet12 --score-backends feature-kv
	PYTHONPATH=tools uv run --with numpy --with fonttools --with brotli --with pillow --with safetensors python tools/build_projected_kv_full_block.py --contexts 16 32 --projection-transports packet12 --score-backends css-kv

benchmark-projected-kv-full-block: projected-kv-full-block
	PROJECTED_KV_FULL_BLOCK_PROJECTION=packet12 PROJECTED_KV_FULL_BLOCK_SCORE_BACKEND=css-kv PROJECTED_KV_FULL_BLOCK_VARIANT=multitoken-direct PROJECTED_KV_FULL_BLOCK_ROUNDS=3 node tools/benchmark_projected_kv_full_block.mjs

benchmark-projected-kv-containment: projected-kv-full-block
	PROJECTED_KV_CONTAINMENT_ROUNDS=1 node tools/benchmark_projected_kv_containment.mjs

benchmark-projected-kv-breakdown: projected-kv-full-block
	node tools/benchmark_qkv_stage_mutation.mjs
	node tools/benchmark_attention_projection_mutation.mjs
	GEOMETRY_FULL_TAIL_MUTATION_CONTEXTS=16,32 GEOMETRY_FULL_TAIL_MUTATION_ROUNDS=7 GEOMETRY_FULL_TAIL_MUTATION_KINDS=query GEOMETRY_FULL_TAIL_MUTATION_VARIANTS=attention-projected-kv-live-current-packet12,attention-css-kv-live-current-packet12 node tools/benchmark_geometry_streaming_full_tail_mutation.mjs
	PROJECTED_KV_BLOCK_MUTATION_SCORE_BACKEND=feature-kv node tools/benchmark_projected_kv_block_mutation.mjs
	PROJECTED_KV_BLOCK_MUTATION_SCORE_BACKEND=css-kv node tools/benchmark_projected_kv_block_mutation.mjs
	PROJECTED_KV_BLOCK_MUTATION_ISOLATED_TAIL=1 node tools/benchmark_projected_kv_block_mutation.mjs
	node tools/benchmark_mlp_vector_replay.mjs

hvar-raster-qkv-attention:
	PYTHONPATH=tools uv run --with numpy --with fonttools --with brotli --with pillow --with safetensors python tools/build_hvar_raster_qkv_attention.py

test-hvar-raster-qkv-attention: hvar-raster-qkv-attention
	HVAR_RASTER_QKV_FILE=qkv-groups.html HVAR_RASTER_QKV_ALLOW_INVALID_CONNECTED=1 HVAR_RASTER_QKV_ROUNDS=7 /Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node tools/test_hvar_raster_qkv_attention.mjs

query-binning:
	PYTHONPATH=tools uv run --with numpy --with safetensors python tools/analyze_query_binning.py

lowrank-attention:
	PYTHONPATH=tools uv run --with numpy --with safetensors python tools/analyze_lowrank_attention.py

composed-qk-probe:
	uv run --with fonttools --with numpy --with pillow --with brotli python tools/build_composed_qk_probe.py

test-composed-qk-probe: composed-qk-probe
	COMPOSED_QK_ROUNDS=7 /Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node tools/test_composed_qk_probe.mjs

direct-css-block:
	PYTHONPATH=tools uv run --with fonttools --with numpy --with pillow --with brotli python tools/build_direct_css_block.py --full

test-direct-css-block: direct-css-block
	PYTHONPATH=tools uv run --with fonttools --with numpy --with pillow --with brotli python tools/test_direct_css_block.py

anchor-geometry-chain:
	python3 tools/build_anchor_geometry_chain.py

test-anchor-geometry-chain: anchor-geometry-chain
	ANCHOR_GEOMETRY_ROUNDS=3 /Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node tools/test_anchor_geometry_chain.mjs
	ANCHOR_GEOMETRY_VARIANTS=384-1-balanced,512-1-balanced,768-1-balanced ANCHOR_GEOMETRY_MUTATIONS=7 /Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node tools/test_anchor_geometry_mutation.mjs

grid-subgrid-gpt2-fc:
	PYTHONPATH=tools uv run --with numpy --with brotli --with fonttools --with pillow python tools/build_grid_subgrid_gpt2_fc.py

test-grid-subgrid-gpt2-fc: grid-subgrid-gpt2-fc
	GRID_GPT2_FC_MODE=grid node tools/benchmark_grid_subgrid_gpt2_fc.mjs
	GRID_GPT2_FC_MODE=timeline node tools/benchmark_grid_subgrid_gpt2_fc.mjs
	node tools/test_counter_vector_reduction.mjs

svg-signed-bitplane-dot:
	PYTHONPATH=tools uv run --with numpy --with pillow --with safetensors python tools/build_svg_signed_bitplane_dot.py

test-svg-signed-bitplane-dot: svg-signed-bitplane-dot
	node tools/test_svg_signed_bitplane_dot.mjs

.PHONY: hvar-five-metric-fullwidth test-hvar-five-metric-fullwidth hvar-five-metric-scale test-hvar-five-metric-scale font-metric-chain test-font-metric-chain cross-shard-font-composition test-cross-shard-font-composition ideal-vector-carrier test-ideal-vector-carrier hvar-vector-oracle test-hvar-vector-oracle hvar-packed-output-rows test-hvar-packed-output-rows single-glyph-vector-raster test-single-glyph-vector-raster css-gelu-projection test-css-gelu-projection exact-css-gelu-two-block test-exact-css-gelu-two-block exact-css-gelu-topologies test-exact-css-gelu-topologies exact-gelu-vector-oracle test-exact-gelu-vector-oracle test-anchor-function-number-probe test-preactivation-packet profile-hvar-two-block-toggle

hvar-five-metric-fullwidth:
	PYTHONPATH=tools uv run --with numpy --with fonttools python tools/build_hvar_five_metric_fullwidth.py

test-hvar-five-metric-fullwidth: hvar-five-metric-fullwidth
	node tools/test_hvar_five_metric_fullwidth.mjs

hvar-five-metric-scale:
	PYTHONPATH=tools uv run --with numpy --with fonttools --with safetensors python tools/build_hvar_five_metric_scale.py

test-hvar-five-metric-scale: hvar-five-metric-scale
	node tools/test_hvar_five_metric_scale.mjs

font-metric-chain:
	PYTHONPATH=tools uv run --with numpy --with fonttools python tools/build_font_metric_chain_probe.py

test-font-metric-chain: font-metric-chain
	node tools/test_font_metric_chain_probe.mjs

cross-shard-font-composition:
	PYTHONPATH=tools uv run --with numpy --with fonttools --with brotli --with pillow python tools/build_cross_shard_font_composition_probe.py

test-cross-shard-font-composition: cross-shard-font-composition
	node tools/test_cross_shard_font_composition_probe.mjs

ideal-vector-carrier:
	PYTHONPATH=tools uv run --with numpy --with fonttools --with brotli --with safetensors --with pillow python tools/build_ideal_vector_carrier_probe.py

test-ideal-vector-carrier: ideal-vector-carrier
	IDEAL_VECTOR_FRESH_ROUNDS=16 IDEAL_VECTOR_CACHE_ROUNDS=24 IDEAL_VECTOR_CACHE_WARMUPS=5 node tools/test_ideal_vector_carrier_probe.mjs

hvar-vector-oracle:
	node tools/capture_hvar_vector_oracle.mjs
	PYTHONPATH=tools uv run --with fonttools --with numpy --with pillow --with brotli python tools/build_hvar_vector_oracle.py

test-hvar-vector-oracle: hvar-vector-oracle
	HVAR_ORACLE_ROUNDS=5 node tools/benchmark_hvar_vector_oracle.mjs

hvar-packed-output-rows:
	PYTHONPATH=tools uv run --with numpy --with fonttools --with brotli --with safetensors --with pillow python tools/build_hvar_packed_output_rows.py

test-hvar-packed-output-rows: hvar-packed-output-rows
	HVAR_PACKED_ROUNDS=24 HVAR_PACKED_WARMUPS=5 node tools/test_hvar_packed_output_rows.mjs

single-glyph-vector-raster:
	for shape in 64:64 256:256 256:3072; do inputs=$${shape%:*}; outputs=$${shape#*:}; SINGLE_GLYPH_INPUTS=$$inputs SINGLE_GLYPH_OUTPUTS=$$outputs PYTHONPATH=tools uv run --with numpy --with fonttools --with brotli python tools/build_single_glyph_vector_raster.py; done

test-single-glyph-vector-raster: single-glyph-vector-raster
	for shape in 64:64 256:256 256:3072; do inputs=$${shape%:*}; outputs=$${shape#*:}; SINGLE_GLYPH_INPUTS=$$inputs SINGLE_GLYPH_OUTPUTS=$$outputs node tools/test_single_glyph_vector_raster.mjs; done

css-gelu-projection:
	PYTHONPATH=tools uv run --with numpy --with pillow --with fonttools --with brotli python tools/build_css_gelu_projection.py

test-css-gelu-projection: css-gelu-projection
	node tools/test_css_gelu_projection.mjs

exact-css-gelu-two-block:
	PYTHONPATH=tools uv run --with numpy --with pillow --with fonttools --with brotli python tools/build_exact_css_gelu_two_block.py

test-exact-css-gelu-two-block: exact-css-gelu-two-block
	EXACT_GELU_TWO_BLOCK_ROUNDS=6 node tools/benchmark_exact_css_gelu_two_block.mjs

exact-css-gelu-topologies: exact-css-gelu-two-block
	PYTHONPATH=tools uv run --with numpy --with pillow --with fonttools --with brotli python tools/build_exact_css_gelu_parallel_two_block.py
	PYTHONPATH=tools uv run --with numpy --with pillow --with fonttools --with brotli python tools/build_exact_css_gelu_hybrid_two_block.py
	PYTHONPATH=tools uv run --with numpy --with pillow --with fonttools --with brotli python tools/build_exact_css_gelu_shadow_hybrid_two_block.py
	PYTHONPATH=tools uv run --with numpy --with pillow --with fonttools --with brotli python tools/build_exact_css_gelu_inline_two_block.py

test-exact-css-gelu-topologies: exact-css-gelu-topologies
	EXACT_PARALLEL_ONLY=exact-serial,exact-shadow-hybrid-1 EXACT_PARALLEL_ROUNDS=8 EXACT_PARALLEL_OUTPUT=exact-css-gelu-shadow-hybrid-one-results.json node tools/benchmark_exact_css_gelu_parallel_two_block.mjs
	EXACT_PARALLEL_ONLY=exact-serial,exact-inline EXACT_PARALLEL_ROUNDS=8 EXACT_PARALLEL_OUTPUT=exact-css-gelu-inline-results.json node tools/benchmark_exact_css_gelu_parallel_two_block.mjs

exact-gelu-vector-oracle: exact-css-gelu-two-block
	node tools/capture_exact_gelu_vector_oracle.mjs
	PYTHONPATH=tools uv run --with numpy python tools/build_exact_gelu_vector_oracle.py

test-exact-gelu-vector-oracle: exact-gelu-vector-oracle
	EXACT_GELU_ORACLE_ROUNDS=6 node tools/benchmark_exact_gelu_vector_oracle.mjs

test-anchor-function-number-probe:
	node tools/test_anchor_function_number_probe.mjs

test-preactivation-packet:
	node tools/test_preactivation_packet_exact.mjs
	PREACTIVATION_PACKET_ROUNDS=8 node tools/compare_preactivation_packet_transports.mjs

profile-hvar-two-block-toggle:
	node tools/profile_hvar_two_block_toggle_trace.mjs

.PHONY: grid-argmax test-grid-argmax grid-argmax-group-sweep test-grid-argmax-group-sweep grid-hierarchical-output-head test-grid-hierarchical-output-head hvar-token-embedding-lookup test-hvar-token-embedding-lookup hvar-embedding-qkv-chain test-hvar-embedding-qkv-chain packed-hvar-transport-scaling test-packed-hvar-transport-scaling registered-hvar-full-mlp test-registered-hvar-full-mlp hvar-grid-output-head test-hvar-grid-output-head

grid-argmax:
	python3 tools/build_grid_argmax_probe.py
	python3 tools/build_grid_hierarchical_argmax.py

test-grid-argmax: grid-argmax
	node tools/test_grid_argmax.mjs
	node tools/test_grid_hierarchical_argmax.mjs

grid-argmax-group-sweep:
	python3 tools/build_grid_argmax_group_sweep.py

test-grid-argmax-group-sweep: grid-argmax-group-sweep
	node tools/test_grid_argmax_group_sweep.mjs

grid-hierarchical-output-head:
	PYTHONPATH=tools python3 tools/build_grid_hierarchical_output_head.py

test-grid-hierarchical-output-head: grid-hierarchical-output-head
	node tools/test_grid_hierarchical_output_head.mjs

hvar-token-embedding-lookup:
	PYTHONPATH=tools uv run --with numpy --with fonttools --with brotli --with pillow python tools/build_hvar_token_embedding_lookup.py

test-hvar-token-embedding-lookup: hvar-token-embedding-lookup
	node tools/test_hvar_token_embedding_lookup.mjs

hvar-embedding-qkv-chain: hvar-token-embedding-lookup
	PYTHONPATH=tools uv run --with numpy --with fonttools --with brotli --with pillow python tools/build_hvar_embedding_qkv_chain.py

test-hvar-embedding-qkv-chain: hvar-embedding-qkv-chain
	HVAR_EMBEDDING_QKV_VARIANT=b6 node tools/test_hvar_embedding_qkv_chain.mjs
	HVAR_EMBEDDING_QKV_VARIANT=b12 node tools/test_hvar_embedding_qkv_chain.mjs

packed-hvar-transport-scaling:
	PYTHONPATH=tools uv run --with numpy --with fonttools --with brotli --with pillow python tools/build_packed_hvar_transport_scaling.py

test-packed-hvar-transport-scaling: packed-hvar-transport-scaling
	PACKED_HVAR_MODE=animation node tools/test_packed_hvar_transport_scaling.mjs
	PACKED_HVAR_MODE=registered node tools/test_packed_hvar_transport_scaling.mjs

registered-hvar-full-mlp:
	ANCHOR_PACKED_MLP_LAYOUT=local-2d ANCHOR_PACKED_SINK=hvar ANCHOR_PACKED_HVAR_BITS=12 ANCHOR_PACKED_HVAR_SHARD=128 PYTHONPATH=tools uv run --with numpy --with fonttools --with brotli --with pillow --with safetensors python tools/build_anchor_packed_full_mlp.py

test-registered-hvar-full-mlp: registered-hvar-full-mlp
	REGISTERED_HVAR_MLP_ROUNDS=9 node tools/test_registered_hvar_full_mlp.mjs

timeline-hvar-projection: view-timeline-fc

test-timeline-hvar-projection: timeline-hvar-projection
	TIMELINE_HVAR_ROUNDS=9 node tools/test_view_timeline_hvar_projection.mjs

view-timeline-two-block-exact-current: view-timeline-fc
	TWO_BLOCK_SOURCE_MODE=exact TWO_BLOCK_REBUILD_FONTS=0 uv run --with fonttools --with numpy --with pillow --with brotli python tools/build_view_timeline_two_block_probe.py
	TWO_BLOCK_SOURCE_MODE=exact-global TWO_BLOCK_FC_EASING_GELU=1 TWO_BLOCK_FC_EASING_STOPS=513 TWO_BLOCK_PROJECTION_EASING=1 TWO_BLOCK_PROJECTION_EASING_STOPS=257 TWO_BLOCK_GLOBAL_PROJECTION=1 TWO_BLOCK_REBUILD_FONTS=0 uv run --with fonttools --with numpy --with pillow --with brotli python tools/build_view_timeline_two_block_probe.py

test-view-timeline-two-block-exact-current: view-timeline-two-block-exact-current
	VIEW_TIMELINE_TWO_BLOCK_FILE=view-timeline-two-block-full-exact.html VIEW_TIMELINE_TWO_BLOCK_REFERENCE=view-timeline-two-block-full-exact-reference.json VIEW_TIMELINE_TWO_BLOCK_MUTATION_ROUNDS=11 VIEW_TIMELINE_TWO_BLOCK_FRAMES=4 VIEW_TIMELINE_TWO_BLOCK_RESULT=view-timeline-two-block-full-exact-current-browser.json node tools/test_view_timeline_two_block_mutation.mjs
	VIEW_TIMELINE_TWO_BLOCK_FILE=view-timeline-two-block-full-exact-b0-global-projection-fc-easing-gelu-s513-projection-easing-s257-global-projection.html VIEW_TIMELINE_TWO_BLOCK_REFERENCE=view-timeline-two-block-full-exact-b0-global-projection-fc-easing-gelu-s513-projection-easing-s257-global-projection-reference.json VIEW_TIMELINE_TWO_BLOCK_MUTATION_ROUNDS=11 VIEW_TIMELINE_TWO_BLOCK_FRAMES=4 VIEW_TIMELINE_TWO_BLOCK_RESULT=view-timeline-two-block-full-exact-both-global-projection-current-browser.json node tools/test_view_timeline_two_block_mutation.mjs
	VIEW_TIMELINE_TWO_BLOCK_FILE=view-timeline-two-block-full-packed4-exact-b0-global-projection-fc-easing-gelu-s513-projection-easing-s257-global-projection.html VIEW_TIMELINE_TWO_BLOCK_REFERENCE=view-timeline-two-block-full-exact-b0-global-projection-fc-easing-gelu-s513-projection-easing-s257-global-projection-reference.json VIEW_TIMELINE_TWO_BLOCK_MUTATION_ROUNDS=11 VIEW_TIMELINE_TWO_BLOCK_FRAMES=4 VIEW_TIMELINE_TWO_BLOCK_RESULT=view-timeline-two-block-full-packed4-exact-both-global-projection-current-browser.json node tools/test_view_timeline_two_block_mutation.mjs

hvar-grid-output-head: hvar-token-embedding-lookup hvar-embedding-qkv-chain
	PYTHONPATH=tools uv run --with numpy --with fonttools --with brotli --with pillow python tools/build_hvar_grid_output_head.py

test-hvar-grid-output-head: hvar-grid-output-head
	node tools/test_hvar_grid_output_head.mjs

gpt2-hvar-grid-output-head:
	PYTHONPATH=tools uv run --with numpy --with fonttools --with brotli --with pillow --with safetensors python tools/build_gpt2_hvar_grid_output_head.py

test-gpt2-hvar-grid-output-head: gpt2-hvar-grid-output-head
	GPT2_HVAR_GRID_HEAD_ROUNDS=7 node tools/test_gpt2_hvar_grid_output_head.mjs

gpt2-hvar-grid-output-head-global11:
	PYTHONPATH=tools uv run --with numpy --with fonttools --with brotli --with pillow --with safetensors python tools/build_gpt2_hvar_grid_output_head_global.py

test-gpt2-hvar-grid-output-head-global11: gpt2-hvar-grid-output-head-global11
	GPT2_HVAR_GRID_HEAD_DIR=gpt2-hvar-grid-output-head-global11 GPT2_HVAR_GRID_HEAD_ROUNDS=5 node tools/test_gpt2_hvar_grid_output_head.mjs

gpt2-hvar-grid-output-head-global11-shard256:
	GPT2_HVAR_HEAD_SHARD=256 GPT2_HVAR_GLOBAL_HEAD_DIR=gpt2-hvar-grid-output-head-global11-shard256 PYTHONPATH=tools uv run --with numpy --with fonttools --with brotli --with pillow --with safetensors python tools/build_gpt2_hvar_grid_output_head_global.py

test-gpt2-hvar-grid-output-head-global11-shard256: gpt2-hvar-grid-output-head-global11-shard256
	GPT2_HVAR_GRID_HEAD_DIR=gpt2-hvar-grid-output-head-global11-shard256 GPT2_HVAR_GRID_HEAD_ROUNDS=5 node tools/test_gpt2_hvar_grid_output_head.mjs

gpt2-hvar-grid-output-head-cascade-near-dither7-shard256:
	GPT2_HVAR_HEAD_SHARD=256 GPT2_CASCADE_NEAR_SELECTOR=1 GPT2_CASCADE_NEAR_DITHER_PHASES=7 GPT2_CASCADE_COARSE_DIR=gpt2-hvar-grid-output-head-global11-shard256-inline-tie GPT2_CASCADE_OUTPUT_DIR=gpt2-hvar-grid-output-head-cascade-near-dither7-shard256 PYTHONPATH=tools uv run --with numpy --with pillow --with fonttools --with brotli --with safetensors python tools/build_gpt2_hvar_grid_output_head_cascade_compact.py

gpt2-hvar-grid-output-head-cascade-near-dither7-shard256-staged: gpt2-hvar-grid-output-head-cascade-near-dither7-shard256
	GPT2_STAGED_HEAD_SOURCE=gpt2-hvar-grid-output-head-cascade-near-dither7-shard256 python3 tools/build_gpt2_selective_output_head_staged.py

test-gpt2-hvar-grid-output-head-cascade-near-dither7-shard256-staged: gpt2-hvar-grid-output-head-cascade-near-dither7-shard256-staged
	GPT2_STAGED_HEAD_SOURCE=gpt2-hvar-grid-output-head-cascade-near-dither7-shard256 GPT2_STAGED_HEAD_ROUNDS=5 node tools/test_gpt2_selective_output_head_staged.mjs

avar2-hvar-composition:
	PYTHONPATH=tools uv run --with numpy --with fonttools --with brotli --with pillow python tools/build_avar2_hvar_composition_probe.py

test-avar2-hvar-composition: avar2-hvar-composition
	node tools/test_avar2_hvar_composition_probe.mjs

avar2-hvar-mlp:
	PYTHONPATH=tools uv run --with numpy --with fonttools --with brotli --with pillow python tools/build_avar2_hvar_mlp_probe.py

test-avar2-hvar-mlp: avar2-hvar-mlp
	node tools/test_avar2_hvar_mlp_probe.mjs

avar2-hvar-mlp-scaling:
	PYTHONPATH=tools uv run --with numpy --with fonttools --with brotli --with pillow python tools/build_avar2_hvar_mlp_scaling.py

test-avar2-hvar-mlp-scaling: avar2-hvar-mlp-scaling
	node tools/test_avar2_hvar_mlp_scaling.mjs

avar2-hvar-real-gpt2-tile:
	PYTHONPATH=tools uv run --with numpy --with fonttools --with brotli --with pillow python tools/build_avar2_hvar_real_gpt2_tile.py

test-avar2-hvar-real-gpt2-tile: avar2-hvar-real-gpt2-tile
	node tools/test_avar2_hvar_real_gpt2_tile.mjs

analyze-gpt2-fc-lowrank:
	PYTHONPATH=tools uv run --with numpy python tools/analyze_gpt2_fc_lowrank.py

analyze-gpt2-mlp-input-quantization:
	PYTHONPATH=tools uv run --with numpy python tools/analyze_gpt2_mlp_input_quantization.py

test-anchor-registered-axis-gather:
	node tools/test_anchor_registered_axis_gather.mjs

hvar-parallel-mlp-group:
	PYTHONPATH=tools uv run --with numpy --with fonttools --with brotli --with pillow python tools/build_hvar_parallel_mlp_group.py

test-hvar-parallel-mlp-group: hvar-parallel-mlp-group
	node tools/test_hvar_parallel_mlp_group.mjs

avar2-gelu-linear-hvar-group:
	HVAR_MLP_GROUP_BACKEND=avar2-gelu PYTHONPATH=tools uv run --with numpy --with fonttools --with brotli --with pillow python tools/build_hvar_parallel_mlp_group.py

test-avar2-gelu-linear-hvar-group: avar2-gelu-linear-hvar-group
	HVAR_MLP_GROUP_DIR=avar2-gelu-linear-hvar-group node tools/test_hvar_parallel_mlp_group.mjs

hvar-parallel-full-mlp:
	PYTHONPATH=tools uv run --with numpy --with fonttools --with brotli --with pillow python tools/build_hvar_parallel_full_mlp.py

test-hvar-parallel-full-mlp: hvar-parallel-full-mlp
	node tools/test_hvar_parallel_full_mlp.mjs

profile-hvar-parallel-full-mlp: hvar-parallel-full-mlp
	node tools/profile_hvar_parallel_full_mlp.mjs

avar2-gelu-linear-hvar-full-mlp:
	HVAR_FULL_MLP_BACKEND=avar2-gelu PYTHONPATH=tools uv run --with numpy --with fonttools --with brotli --with pillow python tools/build_hvar_parallel_full_mlp.py

test-avar2-gelu-linear-hvar-full-mlp: avar2-gelu-linear-hvar-full-mlp
	HVAR_FULL_MLP_DIR=avar2-gelu-linear-hvar-full-mlp node tools/test_hvar_parallel_full_mlp.mjs

profile-avar2-gelu-linear-hvar-full-mlp: avar2-gelu-linear-hvar-full-mlp
	HVAR_FULL_MLP_DIR=avar2-gelu-linear-hvar-full-mlp node tools/profile_hvar_parallel_full_mlp.mjs

test-avar2-gelu-linear-hvar-full-mlp-connected: avar2-gelu-linear-hvar-full-mlp
	HVAR_FULL_MLP_DIR=avar2-gelu-linear-hvar-full-mlp HVAR_FULL_MLP_PAGE=connected-sharded-input.html node tools/test_hvar_parallel_full_mlp.mjs

profile-avar2-gelu-linear-hvar-full-mlp-connected: avar2-gelu-linear-hvar-full-mlp
	HVAR_FULL_MLP_DIR=avar2-gelu-linear-hvar-full-mlp HVAR_FULL_MLP_PAGE=connected-sharded-input.html node tools/profile_hvar_parallel_full_mlp.mjs

test-avar2-gelu-linear-hvar-full-mlp-sharded-connected: avar2-gelu-linear-hvar-full-mlp
	HVAR_FULL_MLP_DIR=avar2-gelu-linear-hvar-full-mlp HVAR_FULL_MLP_PAGE=connected-sharded-input.html node tools/test_hvar_parallel_full_mlp.mjs

avar2-gelu-linear-hvar-full-mlp-g13:
	HVAR_FULL_MLP_BACKEND=avar2-gelu HVAR_FULL_MLP_GROUPS=13 PYTHONPATH=tools uv run --with numpy --with fonttools --with brotli --with pillow python tools/build_hvar_parallel_full_mlp.py

test-avar2-gelu-linear-hvar-full-mlp-g13-connected: avar2-gelu-linear-hvar-full-mlp-g13
	HVAR_FULL_MLP_DIR=avar2-gelu-linear-hvar-full-mlp-g13 HVAR_FULL_MLP_PAGE=connected-input.html node tools/test_hvar_parallel_full_mlp.mjs

profile-avar2-gelu-linear-hvar-full-mlp-g13-connected: avar2-gelu-linear-hvar-full-mlp-g13
	HVAR_FULL_MLP_DIR=avar2-gelu-linear-hvar-full-mlp-g13 HVAR_FULL_MLP_PAGE=connected-input.html node tools/profile_hvar_parallel_full_mlp.mjs

test-avar2-gelu-linear-hvar-full-mlp-g13-layernorm: avar2-gelu-linear-hvar-full-mlp-g13
	HVAR_FULL_MLP_DIR=avar2-gelu-linear-hvar-full-mlp-g13 HVAR_FULL_MLP_PAGE=connected-layernorm-input.html node tools/test_hvar_parallel_full_mlp.mjs

test-avar2-gelu-linear-hvar-full-mlp-g13-attention: avar2-gelu-linear-hvar-full-mlp-g13
	HVAR_FULL_MLP_DIR=avar2-gelu-linear-hvar-full-mlp-g13 HVAR_FULL_MLP_PAGE=connected-attention-input.html node tools/test_hvar_parallel_full_mlp.mjs

test-avar2-gelu-linear-hvar-full-mlp-g13-attention-numeric: avar2-gelu-linear-hvar-full-mlp-g13
	HVAR_FULL_MLP_DIR=avar2-gelu-linear-hvar-full-mlp-g13 HVAR_FULL_MLP_PAGE=connected-attention-numeric-input.html node tools/test_hvar_parallel_full_mlp.mjs

test-avar2-gelu-linear-hvar-full-mlp-g13-full-block: avar2-gelu-linear-hvar-full-mlp-g13
	HVAR_FULL_MLP_DIR=avar2-gelu-linear-hvar-full-mlp-g13 HVAR_FULL_MLP_PAGE=connected-attention-full-block.html node tools/test_hvar_parallel_full_mlp.mjs

test-avar2-gelu-linear-hvar-full-mlp-g13-full-block-captured: avar2-gelu-linear-hvar-full-mlp-g13
	HVAR_FULL_MLP_DIR=avar2-gelu-linear-hvar-full-mlp-g13 HVAR_FULL_MLP_PAGE=connected-attention-full-block-captured.html node tools/test_hvar_parallel_full_mlp.mjs

test-avar2-gelu-linear-hvar-full-mlp-g13-next-layernorm: avar2-gelu-linear-hvar-full-mlp-g13
	HVAR_FULL_MLP_DIR=avar2-gelu-linear-hvar-full-mlp-g13 HVAR_FULL_MLP_PAGE=connected-attention-full-block-next-layernorm.html node tools/test_hvar_parallel_full_mlp.mjs

compare-avar2-gelu-linear-hvar-full-block-capture: avar2-gelu-linear-hvar-full-mlp-g13
	node tools/compare_hvar_full_block_capture.mjs

test-avar2-gelu-linear-hvar-two-block-shadow-staged: avar2-gelu-linear-hvar-full-mlp-g13
	HVAR_FULL_MLP_DIR=avar2-gelu-linear-hvar-full-mlp-g13 HVAR_FULL_MLP_PAGE=connected-two-block-shadow-staged.html node tools/test_hvar_parallel_full_mlp.mjs

test-avar2-gelu-linear-hvar-two-block-serial-projection: avar2-gelu-linear-hvar-full-mlp-g13
	HVAR_FULL_MLP_DIR=avar2-gelu-linear-hvar-full-mlp-g13 HVAR_FULL_MLP_PAGE=connected-two-block-serial-projection.html node tools/test_hvar_parallel_full_mlp.mjs

test-avar2-gelu-linear-hvar-two-block-serial-layoutless: avar2-gelu-linear-hvar-full-mlp-g13
	HVAR_FULL_MLP_DIR=avar2-gelu-linear-hvar-full-mlp-g13 HVAR_FULL_MLP_PAGE=connected-two-block-serial-projection-layoutless.html node tools/test_hvar_parallel_full_mlp.mjs

compare-avar2-gelu-linear-hvar-block-scaling: avar2-gelu-linear-hvar-full-mlp-g13
	node tools/compare_hvar_block_scaling.mjs

compare-avar2-gelu-linear-hvar-staged-groups: avar2-gelu-linear-hvar-full-mlp avar2-gelu-linear-hvar-full-mlp-g13
	node tools/compare_hvar_staged_group_counts.mjs

compare-avar2-gelu-linear-hvar-content-visibility: avar2-gelu-linear-hvar-full-mlp-g13
	node tools/compare_hvar_content_visibility_staging.mjs

profile-avar2-gelu-linear-hvar-two-block-stages: avar2-gelu-linear-hvar-full-mlp-g13
	node tools/profile_hvar_two_block_stages.mjs

profile-avar2-gelu-linear-hvar-full-mlp-g13-attention: avar2-gelu-linear-hvar-full-mlp-g13
	HVAR_FULL_MLP_DIR=avar2-gelu-linear-hvar-full-mlp-g13 HVAR_FULL_MLP_PAGE=connected-attention-input.html node tools/profile_hvar_parallel_full_mlp.mjs

compare-avar2-gelu-linear-hvar-prefixes: avar2-gelu-linear-hvar-full-mlp-g13
	HVAR_COMPARE_SET=layernorm node tools/compare_hvar_connected_grouping.mjs

compare-avar2-gelu-linear-hvar-numeric: avar2-gelu-linear-hvar-full-mlp avar2-gelu-linear-hvar-full-mlp-g13 avar2-gelu-linear-hvar-full-mlp-g16
	HVAR_COMPARE_SET=numeric node tools/compare_hvar_connected_grouping.mjs

avar2-gelu-linear-hvar-full-mlp-g16:
	HVAR_FULL_MLP_BACKEND=avar2-gelu HVAR_FULL_MLP_GROUPS=16 PYTHONPATH=tools uv run --with numpy --with fonttools --with brotli --with pillow python tools/build_hvar_parallel_full_mlp.py

test-avar2-gelu-linear-hvar-full-mlp-g16-connected: avar2-gelu-linear-hvar-full-mlp-g16
	HVAR_FULL_MLP_DIR=avar2-gelu-linear-hvar-full-mlp-g16 HVAR_FULL_MLP_PAGE=connected-input.html node tools/test_hvar_parallel_full_mlp.mjs

profile-avar2-gelu-linear-hvar-full-mlp-g16-connected: avar2-gelu-linear-hvar-full-mlp-g16
	HVAR_FULL_MLP_DIR=avar2-gelu-linear-hvar-full-mlp-g16 HVAR_FULL_MLP_PAGE=connected-input.html node tools/profile_hvar_parallel_full_mlp.mjs

compare-avar2-gelu-linear-hvar-connected-grouping:
	node tools/compare_hvar_connected_grouping.mjs

test-gpt2-hvar-grid-output-head-global11-inline-tie: gpt2-hvar-grid-output-head-global11
	GPT2_HVAR_GRID_HEAD_DIR=gpt2-hvar-grid-output-head-global11-inline-tie GPT2_HVAR_GRID_HEAD_ROUNDS=3 node tools/test_gpt2_hvar_grid_output_head.mjs

gpt2-hvar-grid-output-head-global16-twoplane:
	PYTHONPATH=tools uv run --with numpy --with fonttools --with brotli --with pillow --with safetensors python tools/build_gpt2_hvar_grid_output_head_twoplane.py

test-gpt2-hvar-grid-output-head-global16-twoplane: gpt2-hvar-grid-output-head-global16-twoplane
	GPT2_HVAR_GRID_HEAD_DIR=gpt2-hvar-grid-output-head-global16-twoplane GPT2_HVAR_GRID_HEAD_ROUNDS=3 node tools/test_gpt2_hvar_grid_output_head.mjs

gpt2-hvar-grid-output-head-cascade: gpt2-hvar-grid-output-head-global11 gpt2-hvar-grid-output-head-global16-twoplane
	PYTHONPATH=tools uv run --with numpy --with pillow --with fonttools --with brotli --with safetensors python tools/build_gpt2_hvar_grid_output_head_cascade.py

test-gpt2-hvar-grid-output-head-cascade: gpt2-hvar-grid-output-head-cascade
	GPT2_CASCADE_ROUNDS=3 node tools/test_gpt2_hvar_grid_output_head_cascade.mjs

gpt2-hvar-grid-output-head-cascade-compact: gpt2-hvar-grid-output-head-global11 gpt2-hvar-grid-output-head-global16-twoplane
	PYTHONPATH=tools uv run --with numpy --with pillow --with fonttools --with brotli --with safetensors python tools/build_gpt2_hvar_grid_output_head_cascade_compact.py

test-gpt2-hvar-grid-output-head-cascade-compact: gpt2-hvar-grid-output-head-cascade-compact
	GPT2_CASCADE_DIR=gpt2-hvar-grid-output-head-cascade-compact GPT2_CASCADE_ROUNDS=3 node tools/test_gpt2_hvar_grid_output_head_cascade.mjs

gpt2-hvar-grid-output-head-cascade-dither8: gpt2-hvar-grid-output-head-global11 gpt2-hvar-grid-output-head-global16-twoplane
	GPT2_CASCADE_DITHER_PHASES=8 PYTHONPATH=tools uv run --with numpy --with pillow --with fonttools --with brotli --with safetensors python tools/build_gpt2_hvar_grid_output_head_cascade_compact.py

test-gpt2-hvar-grid-output-head-cascade-dither8: gpt2-hvar-grid-output-head-cascade-dither8
	GPT2_CASCADE_DIR=gpt2-hvar-grid-output-head-cascade-dither8 GPT2_CASCADE_ROUNDS=3 node tools/test_gpt2_hvar_grid_output_head_cascade.mjs

gpt2-hvar-grid-output-head-cascade-dither8-sparse5: gpt2-hvar-grid-output-head-global11 gpt2-hvar-grid-output-head-global16-twoplane
	GPT2_CASCADE_DITHER_PHASES=8 GPT2_CASCADE_ACTIVE_LOCALS=6,11,13,198,221 PYTHONPATH=tools uv run --with numpy --with pillow --with fonttools --with brotli --with safetensors python tools/build_gpt2_hvar_grid_output_head_cascade_compact.py

test-gpt2-hvar-grid-output-head-cascade-dither8-sparse5: gpt2-hvar-grid-output-head-cascade-dither8-sparse5
	GPT2_CASCADE_DIR=gpt2-hvar-grid-output-head-cascade-dither8-sparse5 GPT2_CASCADE_ROUNDS=3 node tools/test_gpt2_hvar_grid_output_head_cascade.mjs

gpt2-hvar-grid-output-head-cascade-near-selector: gpt2-hvar-grid-output-head-global11 gpt2-hvar-grid-output-head-global16-twoplane
	GPT2_CASCADE_NEAR_SELECTOR=1 PYTHONPATH=tools uv run --with numpy --with pillow --with fonttools --with brotli --with safetensors python tools/build_gpt2_hvar_grid_output_head_cascade_compact.py

test-gpt2-hvar-grid-output-head-cascade-near-selector: gpt2-hvar-grid-output-head-cascade-near-selector
	GPT2_CASCADE_DIR=gpt2-hvar-grid-output-head-cascade-near-selector GPT2_CASCADE_ROUNDS=1 GPT2_CASCADE_SETTLE_PASSES=3 node tools/test_gpt2_hvar_grid_output_head_cascade.mjs

gpt2-hvar-grid-output-head-cascade-near-dither8: gpt2-hvar-grid-output-head-global11 gpt2-hvar-grid-output-head-global16-twoplane
	GPT2_CASCADE_NEAR_SELECTOR=1 GPT2_CASCADE_NEAR_DITHER_PHASES=8 PYTHONPATH=tools uv run --with numpy --with pillow --with fonttools --with brotli --with safetensors python tools/build_gpt2_hvar_grid_output_head_cascade_compact.py

test-gpt2-hvar-grid-output-head-cascade-near-dither8: gpt2-hvar-grid-output-head-cascade-near-dither8
	GPT2_CASCADE_DIR=gpt2-hvar-grid-output-head-cascade-near-dither8 GPT2_CASCADE_ROUNDS=3 GPT2_CASCADE_SETTLE_PASSES=5 node tools/test_gpt2_hvar_grid_output_head_cascade.mjs

gpt2-hvar-grid-output-head-cascade-near-dither7: gpt2-hvar-grid-output-head-global11 gpt2-hvar-grid-output-head-global16-twoplane
	GPT2_CASCADE_NEAR_SELECTOR=1 GPT2_CASCADE_NEAR_DITHER_PHASES=7 PYTHONPATH=tools uv run --with numpy --with pillow --with fonttools --with brotli --with safetensors python tools/build_gpt2_hvar_grid_output_head_cascade_compact.py

test-gpt2-hvar-grid-output-head-cascade-near-dither7: gpt2-hvar-grid-output-head-cascade-near-dither7
	GPT2_CASCADE_DIR=gpt2-hvar-grid-output-head-cascade-near-dither7 GPT2_CASCADE_ROUNDS=3 GPT2_CASCADE_SETTLE_PASSES=5 node tools/test_gpt2_hvar_grid_output_head_cascade.mjs

two-block-gpt2-selective-output-head: gpt2-hvar-grid-output-head-cascade-near-dither7
	python3 tools/build_two_block_gpt2_selective_output_head.py

test-two-block-gpt2-selective-output-head: two-block-gpt2-selective-output-head
	node tools/test_two_block_gpt2_selective_output_head.mjs

two-block-manual-stage-boundary:
	python3 tools/build_two_block_stage_boundary.py

test-two-block-manual-stage-boundary: two-block-manual-stage-boundary
	node tools/test_two_block_stage_boundary.mjs

gpt2-selective-output-head-staged: gpt2-hvar-grid-output-head-cascade-near-dither7
	python3 tools/build_gpt2_selective_output_head_staged.py

test-gpt2-selective-output-head-staged: gpt2-selective-output-head-staged
	node tools/test_gpt2_selective_output_head_staged.mjs

two-block-gpt2-selective-output-head-internally-staged: gpt2-selective-output-head-staged
	TWO_BLOCK_SELECTIVE_INTERNAL_STAGING=1 python3 tools/build_two_block_gpt2_selective_output_head.py

test-two-block-gpt2-selective-output-head-internally-staged: two-block-gpt2-selective-output-head-internally-staged
	TWO_BLOCK_SELECTIVE_INTERNAL_STAGING=1 node tools/test_two_block_gpt2_selective_output_head.mjs

gpt2-hvar-grid-output-head-cascade-subfonts: gpt2-hvar-grid-output-head-cascade-compact
	PYTHONPATH=tools uv run --with fonttools --with brotli python tools/build_gpt2_hvar_grid_output_head_cascade_subfonts.py

test-gpt2-hvar-grid-output-head-cascade-subfonts: gpt2-hvar-grid-output-head-cascade-subfonts
	GPT2_CASCADE_DIR=gpt2-hvar-grid-output-head-cascade-subfonts GPT2_CASCADE_ROUNDS=3 node tools/test_gpt2_hvar_grid_output_head_cascade.mjs

two-block-gpt2-output-head: view-timeline-two-block-exact-current gpt2-hvar-grid-output-head
	PYTHONPATH=tools uv run --with numpy --with safetensors python tools/build_two_block_gpt2_output_head.py

test-two-block-gpt2-output-head: two-block-gpt2-output-head
	TWO_BLOCK_HEAD_STAGED=1 TWO_BLOCK_HEAD_FRAMES=4 TWO_BLOCK_HEAD_SCORE_FRAMES=2 TWO_BLOCK_HEAD_ROUNDS=5 node tools/test_two_block_gpt2_output_head.mjs

test-two-block-gpt2-output-head-auto: two-block-gpt2-output-head
	node tools/test_two_block_gpt2_output_head_auto.mjs

tinystories-step:
	python3 tools/build_tinystories_step.py

tinystories-recurrent:
	python3 tools/build_tinystories_recurrent.py

tinystories-nested:
	python3 tools/build_tinystories_nested.py

tinystories-tokenizer-font:
	uv run --with fonttools --with numpy python tools/build_metric_tokenizer_font.py --full --token-ids --positions 4 --output tinystories

tinystories-dynamic: clustered-output-head tinystories-tokenizer-font
	python3 tools/build_tinystories_dynamic.py

tinystories-all: clustered-output-head tinystories-step tinystories-recurrent tinystories-nested tinystories-dynamic

precompress-tinystories:
	python3 tools/precompress_tinystories.py

precompress-tinystories-experiments:
	python3 tools/precompress_tinystories.py --experiments

serve-tinystories: precompress-tinystories
	python3 tools/serve_precompressed.py

test:
	python3 tools/test_css_number.py
	python3 tools/test_precompressed_server.py
	python3 tools/analyze_row_score_quantization.py --bits 10 --require-exact
	uv run --with fonttools --with numpy python tools/test_token_id_font.py

clean:
	rm -f index.html model.css transformer/index.html transformer/model.css pretrained/index.html pretrained/benchmark.html pretrained/model.css pretrained/autoregressive.css pretrained/interactive.html pretrained/interactive-2.html pretrained/interactive-3.html pretrained/interactive-4.html pretrained/recurrent.css pretrained/prompt-position-0.css pretrained/prompt-position-1.css pretrained/prompt-position-2.css pretrained/prompt-position-3.css tinystories/step.css tinystories/recurrent.css tinystories/dynamic-recurrent.css tinystories/dynamic-prompt.css tinystories/dynamic.html tinystories/nested-runtime.css tinystories/streaming.css tinystories/gpt2-token-id-0-full.ttf tinystories/gpt2-token-id-1-full.ttf
.PHONY: screen-svg-asymmetric-ranges screen-svg-rgb-dither screen-svg-output-head-calibration test-hvar-raster-direct-scale evaluate-svg-w8a8-generation test-svg-internal-precision test-svg-cross-browser-precision test-svg-avif-precision test-svg-hdr-carrier test-svg-hdr-compute-chain test-svg-hdr-codebook test-svg-hdr-matvec test-opsz-container-handoff test-inline-attention-reducer analyze-gpt2-blockwise-cauchy-head test-gpt2-blockwise-cauchy-head analyze-gpt2-groupwise-cauchy-head test-gpt2-groupwise-cauchy-head test-gpt2-groupwise-cauchy-cascade test-gpt2-groupwise-cauchy-blockflow-gate analyze-gpt2-groupwise-q16-cascade test-gpt2-groupwise-cauchy-blockflow-cascade test-gpt2-groupwise-cauchy-blockflow-unrolled22 test-gpt2-groupwise-production-rescale test-counter-matrix test-smil-stage-scheduler test-two-block-smil-stage test-two-block-smil-selector-stage test-full-inference-smil-scheduler test-full-inference-event-scheduler test-gpt2-output-head-containment test-gpt2-output-head-multiline analyze-gpt2-supervised-group-router analyze-gpt2-ivf-group-router analyze-gpt2-overlapping-ivf analyze-gpt2-mips-lsh analyze-gpt2-hnsw-output-head analyze-gpt2-hnsw-trace analyze-gpt2-hnsw-batched-frontier test-gsub-graph-selector analyze-gpt2-nonlinear-group-router analyze-gpt2-certified-vocabulary-ball-tree analyze-gpt2-quantized-head-certification test-gpt2-certified-int10-upper-head

screen-svg-asymmetric-ranges:
	uv run --with numpy python tools/screen_svg_asymmetric_ranges.py

screen-svg-rgb-dither:
	uv run --with numpy python tools/screen_svg_rgb_dither_ensemble.py

screen-svg-output-head-calibration:
	uv run --with numpy python tools/screen_svg_output_head_calibration.py

evaluate-svg-w8a8-generation:
	uv run --with numpy python tools/evaluate_svg_w8a8_generation.py

test-svg-internal-precision:
	python3 tools/build_svg_internal_precision_probe.py
	node tools/test_svg_internal_precision_probe.mjs
	SVG_COLOR_PROFILE=display-p3 node tools/test_svg_internal_precision_probe.mjs

test-svg-cross-browser-precision:
	python3 tools/build_svg_cross_browser_precision.py
	SVG_PRECISION_BROWSER=chromium node tools/test_svg_cross_browser_precision.mjs
	PLAYWRIGHT_BROWSERS_PATH=/tmp/gpt2-css-playwright-browsers \
		SVG_PRECISION_BROWSER=firefox node tools/test_svg_cross_browser_precision.mjs

test-svg-avif-precision:
	python3 tools/build_svg_avif_precision_probe.py
	node tools/test_svg_avif_precision_probe.mjs

test-svg-hdr-carrier:
	python3 tools/build_svg_hdr_carrier_probe.py
	node tools/test_svg_hdr_carrier_probe.mjs

test-svg-hdr-compute-chain:
	python3 tools/build_svg_hdr_compute_chain_probe.py
	node tools/test_svg_hdr_compute_chain_probe.mjs

test-svg-hdr-codebook:
	python3 tools/build_svg_hdr_codebook_probe.py --stage raw
	node tools/test_svg_hdr_codebook_probe.mjs raw
	python3 tools/build_svg_hdr_codebook_probe.py --stage calibrated
	node tools/test_svg_hdr_codebook_probe.mjs calibrated
	python3 tools/build_svg_hdr_codebook_probe.py --stage finalize

test-svg-hdr-matvec: test-svg-hdr-codebook
	python3 tools/build_svg_hdr_matvec_probe.py
	node tools/test_svg_hdr_matvec_probe.mjs

test-opsz-container-handoff:
	PYTHONPATH=tools uv run --with numpy --with fonttools --with brotli --with pillow python tools/build_opsz_container_handoff.py
	OPSZ_HANDOFF_ROUNDS=11 node tools/test_opsz_container_handoff.mjs

test-inline-attention-reducer:
	PYTHONPATH=tools uv run --with numpy --with fonttools --with brotli python tools/build_inline_attention_reducer_probe.py
	node tools/test_inline_attention_reducer_probe.mjs

analyze-gpt2-blockwise-cauchy-head:
	PYTHONPATH=tools uv run --with numpy python tools/analyze_gpt2_blockwise_cauchy_head.py

test-gpt2-blockwise-cauchy-head:
	PYTHONPATH=tools uv run --with numpy --with fonttools --with brotli python tools/build_gpt2_blockwise_cauchy_browser_probe.py
	node tools/test_gpt2_blockwise_cauchy_browser_probe.mjs

analyze-gpt2-groupwise-cauchy-head:
	PYTHONPATH=tools uv run --with numpy python tools/analyze_gpt2_groupwise_cauchy_head.py

test-gpt2-groupwise-cauchy-head:
	PYTHONPATH=tools uv run --with numpy --with fonttools --with brotli python tools/build_gpt2_groupwise_cauchy_browser_probe.py
	node tools/test_gpt2_groupwise_cauchy_browser_probe.mjs

test-gpt2-groupwise-cauchy-cascade:
	PYTHONPATH=tools uv run --with numpy python tools/build_gpt2_groupwise_cauchy_cascade.py
	node tools/test_gpt2_groupwise_cauchy_cascade.mjs

test-gpt2-groupwise-cauchy-blockflow-gate:
	PYTHONPATH=tools uv run --with numpy python tools/build_gpt2_groupwise_cauchy_blockflow_gate.py
	node tools/test_gpt2_groupwise_cauchy_blockflow_gate.mjs

analyze-gpt2-groupwise-q16-cascade:
	PYTHONPATH=tools uv run --with numpy python tools/analyze_gpt2_groupwise_q16_cascade.py

test-gpt2-groupwise-cauchy-blockflow-cascade:
	PYTHONPATH=tools uv run --with numpy --with fonttools --with brotli --with pillow python tools/build_gpt2_groupwise_cauchy_blockflow_cascade.py
	node tools/test_gpt2_groupwise_cauchy_blockflow_cascade.mjs

test-gpt2-groupwise-cauchy-blockflow-unrolled22:
	GPT2_CERTIFIED_STAGES=22 GPT2_CERTIFIED_GATE=1 \
	GPT2_CERTIFIED_CASCADE_DIR=gpt2-hvar-grid-output-head-certified-int10-unrolled22-gated \
	PYTHONPATH=tools uv run --with numpy --with fonttools --with brotli --with pillow \
	python tools/build_certified_int10_unrolled_cascade.py
	MIXED_HOT2_STAGES=22 \
	MIXED_HOT2_OUTPUT_DIR=gpt2-mixed-precision-hot2-upper-shard256-unrolled22 \
	MIXED_HOT2_ONE_STEP_DIR=gpt2-hvar-grid-output-head-certified-upper-int10-one-step-shard256 \
	MIXED_HOT2_BASELINE_DIR=gpt2-hvar-grid-output-head-certified-int10-unrolled22-gated \
	MIXED_HOT2_COARSE_DIR=gpt2-hvar-grid-output-head-certified-upper-int10-shard256 \
	PYTHONPATH=tools uv run --with numpy --with fonttools --with brotli --with pillow \
	python tools/build_mixed_precision_hot2_upper_probe.py
	MIXED_HOT2_COMPOSE_SOURCE=gpt2-mixed-precision-hot2-upper-shard256-unrolled22 \
	MIXED_HOT2_COMPOSE_OUTPUT=gpt2-mixed-hot2-blockflow-group-max-shard256-unrolled22 \
	python3 tools/build_mixed_hot2_shard256_blockflow_probe.py
	GROUPWISE_CASCADE_SOURCE=gpt2-mixed-hot2-blockflow-group-max-shard256-unrolled22 \
	GROUPWISE_CASCADE_OUTPUT=gpt2-groupwise-cauchy-blockflow-cascade-unrolled22 \
	PYTHONPATH=tools uv run --with numpy --with fonttools --with brotli --with pillow \
	python tools/build_gpt2_groupwise_cauchy_blockflow_cascade.py
	GROUPWISE_CASCADE_DIRECTORY=gpt2-groupwise-cauchy-blockflow-cascade-unrolled22 \
	node tools/test_gpt2_groupwise_cauchy_blockflow_cascade.mjs

test-gpt2-groupwise-production-rescale:
	GPT2_CERTIFIED_STAGES=23 GPT2_CERTIFIED_GATE=1 \
	GPT2_CERTIFIED_CASCADE_DIR=gpt2-hvar-grid-output-head-certified-int10-unrolled23-gated \
	PYTHONPATH=tools uv run --with numpy --with fonttools --with brotli --with pillow \
	python tools/build_certified_int10_unrolled_cascade.py
	MIXED_HOT2_STAGES=23 \
	MIXED_HOT2_OUTPUT_DIR=gpt2-mixed-precision-hot2-upper-shard256-unrolled23 \
	MIXED_HOT2_ONE_STEP_DIR=gpt2-hvar-grid-output-head-certified-upper-int10-one-step-shard256 \
	MIXED_HOT2_BASELINE_DIR=gpt2-hvar-grid-output-head-certified-int10-unrolled23-gated \
	MIXED_HOT2_COARSE_DIR=gpt2-hvar-grid-output-head-certified-upper-int10-shard256 \
	PYTHONPATH=tools uv run --with numpy --with fonttools --with brotli --with pillow \
	python tools/build_mixed_precision_hot2_upper_probe.py
	MIXED_HOT2_COMPOSE_SOURCE=gpt2-mixed-precision-hot2-upper-shard256-unrolled23 \
	MIXED_HOT2_COMPOSE_OUTPUT=gpt2-mixed-hot2-blockflow-group-max-shard256-unrolled23 \
	python3 tools/build_mixed_hot2_shard256_blockflow_probe.py
	GROUPWISE_CASCADE_SOURCE=gpt2-mixed-hot2-blockflow-group-max-shard256-unrolled23 \
	GROUPWISE_CASCADE_OUTPUT=gpt2-groupwise-cauchy-blockflow-cascade-unrolled23 \
	PYTHONPATH=tools uv run --with numpy --with fonttools --with brotli --with pillow \
	python tools/build_gpt2_groupwise_cauchy_blockflow_cascade.py
	PYTHONPATH=tools uv run --with numpy python tools/analyze_gpt2_groupwise_q16_cascade.py
	PYTHONPATH=tools uv run --with numpy --with fonttools --with brotli --with pillow --with safetensors \
	python tools/build_gpt2_groupwise_production_rescale.py
	GROUPWISE_CASCADE_DIRECTORY=gpt2-groupwise-cauchy-blockflow-production-range \
	node tools/test_gpt2_groupwise_cauchy_blockflow_cascade.mjs

test-counter-matrix:
	PYTHONPATH=tools uv run --with numpy --with fonttools --with brotli python tools/build_counter_matrix_probe.py
	node tools/test_counter_container_scope.mjs
	COUNTER_TIMELINE_ROUNDS=7 node tools/test_counter_timeline_matrix_probe.mjs

test-smil-stage-scheduler:
	python3 tools/build_smil_stage_scheduler.py
	SMIL_STAGE_ROUNDS=5 node tools/test_smil_stage_scheduler.mjs

test-two-block-smil-stage:
	python3 tools/build_two_block_smil_stage.py
	TWO_BLOCK_SMIL_ROUNDS=3 node tools/test_two_block_smil_stage.mjs

test-two-block-smil-selector-stage:
	python3 tools/build_two_block_smil_selector_stage.py
	TWO_BLOCK_SMIL_SELECTOR_ROUNDS=3 node tools/test_two_block_smil_selector_stage.mjs

test-full-inference-smil-scheduler:
	python3 tools/build_full_inference_smil_scheduler.py
	FULL_INFERENCE_SMIL_ROUNDS=1 node tools/test_full_inference_smil_scheduler.mjs

test-full-inference-event-scheduler:
	python3 tools/build_full_inference_event_scheduler.py
	FULL_INFERENCE_EVENT_ROUNDS=1 node tools/test_full_inference_event_scheduler.mjs

test-gpt2-output-head-containment:
	node tools/test_output_head_group_containment.mjs

test-gpt2-output-head-multiline:
	python3 tools/build_multiline_output_head_probe.py
	node tools/test_multiline_output_head_probe.mjs

analyze-gpt2-supervised-group-router:
	PYTHONPATH=tools python3 tools/analyze_gpt2_supervised_group_router.py

analyze-gpt2-ivf-group-router: analyze-gpt2-supervised-group-router
	PYTHONPATH=tools python3 tools/analyze_gpt2_ivf_group_router.py

analyze-gpt2-overlapping-ivf: analyze-gpt2-ivf-group-router
	PYTHONPATH=tools python3 tools/analyze_gpt2_overlapping_ivf.py

analyze-gpt2-mips-lsh: analyze-gpt2-supervised-group-router
	PYTHONPATH=tools python3 tools/analyze_gpt2_mips_lsh.py

analyze-gpt2-hnsw-output-head: analyze-gpt2-supervised-group-router
	PYTHONPATH=tools uv run --with hnswlib==0.8.0 --with numpy \
		python tools/analyze_gpt2_hnsw_output_head.py

analyze-gpt2-hnsw-trace: analyze-gpt2-supervised-group-router
	tools/build_instrumented_hnswlib.sh
	PYTHONPATH=tools python3 tools/analyze_gpt2_hnsw_trace.py

analyze-gpt2-hnsw-batched-frontier: analyze-gpt2-hnsw-trace
	PYTHONPATH=tools python3 tools/analyze_gpt2_hnsw_batched_frontier.py

test-gsub-graph-selector:
	PYTHONPATH=tools uv run --with fonttools --with brotli \
		python tools/build_gsub_graph_selector_probe.py
	node tools/test_gsub_graph_selector_probe.mjs

analyze-gpt2-nonlinear-group-router: analyze-gpt2-supervised-group-router
	PYTHONPATH=tools python3 tools/analyze_gpt2_nonlinear_group_router.py

analyze-gpt2-certified-vocabulary-ball-tree: analyze-gpt2-supervised-group-router
	PYTHONPATH=tools python3 tools/analyze_certified_vocabulary_ball_tree.py

analyze-gpt2-quantized-head-certification: analyze-gpt2-supervised-group-router
	PYTHONPATH=tools python3 tools/analyze_gpt2_quantized_head_certification.py

analyze-gpt2-browser-certification-budget: analyze-gpt2-supervised-group-router
	PYTHONPATH=tools uv run --with numpy --with fonttools --with brotli python tools/analyze_gpt2_browser_certification_budget.py

analyze-gpt2-certified-tail-strategies: analyze-gpt2-supervised-group-router
	PYTHONPATH=tools uv run --with numpy --with fonttools --with brotli python tools/analyze_gpt2_certified_tail_strategies.py

test-gpt2-certified-int10-upper-head:
	PYTHONPATH=tools uv run --with numpy --with fonttools --with brotli python tools/build_certified_int10_upper_head.py
	node tools/test_certified_int10_upper_head.mjs

build-gpt2-rowwise11-head:
	GPT2_HVAR_HEAD_DIR=gpt2-hvar-grid-output-head-rowwise11-shard80-range266 \
	GPT2_HVAR_HEAD_BITS=11 GPT2_HVAR_HEAD_SHARD=80 \
	GPT2_HVAR_HEAD_INPUT_RANGE=266.248396912 PYTHONPATH=tools \
	uv run --with numpy --with fonttools --with brotli --with pillow \
	python tools/build_gpt2_hvar_grid_output_head.py

test-gpt2-rowwise11-head: build-gpt2-rowwise11-head
	GPT2_HVAR_GRID_HEAD_DIR=gpt2-hvar-grid-output-head-rowwise11-shard80-range266 \
	GPT2_HVAR_GRID_HEAD_ROUNDS=3 node tools/test_gpt2_hvar_grid_output_head.mjs

test-gpt2-certified-rowwise11-upper-head: build-gpt2-rowwise11-head
	GPT2_HVAR_HEAD_BITS=11 GPT2_HVAR_HEAD_SHARD=80 \
	GPT2_CERTIFIED_SOURCE_DIR=gpt2-hvar-grid-output-head-rowwise11-shard80-range266 \
	GPT2_CERTIFIED_OUTPUT_DIR=gpt2-hvar-grid-output-head-certified-upper-rowwise11-range266 \
	PYTHONPATH=tools uv run --with numpy --with fonttools --with brotli python tools/build_certified_int10_upper_head.py
	GPT2_CERTIFIED_HEAD_DIR=gpt2-hvar-grid-output-head-certified-upper-rowwise11-range266 \
	node tools/test_certified_int10_upper_head.mjs

test-gpt2-certified-int10-one-step-cascade: test-gpt2-certified-int10-upper-head
	GPT2_CASCADE_COARSE_DIR=gpt2-hvar-grid-output-head-certified-upper-int10 \
	GPT2_CASCADE_OUTPUT_DIR=gpt2-hvar-grid-output-head-certified-upper-int10-one-step \
	PYTHONPATH=tools uv run --with numpy --with fonttools --with brotli python tools/build_gpt2_hvar_grid_output_head_cascade_compact.py
	node tools/test_certified_int10_one_step_cascade.mjs

test-gpt2-certified-int10-remaining-upper: test-gpt2-certified-int10-one-step-cascade
	PYTHONPATH=tools uv run --with numpy --with fonttools --with brotli python tools/build_certified_int10_remaining_upper_probe.py
	node tools/test_certified_int10_remaining_upper_probe.mjs

test-gpt2-certified-int10-two-step: test-gpt2-certified-int10-remaining-upper
	PYTHONPATH=tools uv run --with numpy --with fonttools --with brotli python tools/build_certified_int10_two_step_probe.py
	node tools/test_certified_int10_two_step_probe.mjs

test-gpt2-certified-int10-unrolled:
	GPT2_CERTIFIED_STAGES=$${GPT2_CERTIFIED_STAGES:-6} \
	GPT2_CERTIFIED_SLACK_BUCKETS=$${GPT2_CERTIFIED_SLACK_BUCKETS:-24} \
	PYTHONPATH=tools uv run --with numpy --with fonttools --with brotli --with pillow \
	python tools/build_certified_int10_unrolled_cascade.py
	GPT2_CERTIFIED_STAGES=$${GPT2_CERTIFIED_STAGES:-6} \
	node tools/test_certified_int10_unrolled_cascade.mjs

test-gpt2-certified-int10-unrolled-gated:
	GPT2_CERTIFIED_STAGES=$${GPT2_CERTIFIED_STAGES:-6} \
	GPT2_CERTIFIED_SLACK_BUCKETS=$${GPT2_CERTIFIED_SLACK_BUCKETS:-24} \
	GPT2_CERTIFIED_GATE=1 PYTHONPATH=tools \
	uv run --with numpy --with fonttools --with brotli --with pillow \
	python tools/build_certified_int10_unrolled_cascade.py
	GPT2_CERTIFIED_STAGES=$${GPT2_CERTIFIED_STAGES:-6} \
	GPT2_CERTIFIED_GATE=1 node tools/test_certified_int10_unrolled_cascade.mjs

test-gpt2-certified-int10-unrolled-linear-mask:
	GPT2_CERTIFIED_STAGES=$${GPT2_CERTIFIED_STAGES:-61} \
	GPT2_CERTIFIED_SLACK_BUCKETS=$${GPT2_CERTIFIED_SLACK_BUCKETS:-24} \
	GPT2_CERTIFIED_GATE=1 GPT2_CERTIFIED_INCREMENTAL_MASK=1 PYTHONPATH=tools \
	uv run --with numpy --with fonttools --with brotli --with pillow \
	python tools/build_certified_int10_unrolled_cascade.py
	GPT2_CERTIFIED_STAGES=$${GPT2_CERTIFIED_STAGES:-61} \
	GPT2_CERTIFIED_GATE=1 GPT2_CERTIFIED_INCREMENTAL_MASK=1 \
	node tools/test_certified_int10_unrolled_cascade.mjs

test-gpt2-certified-int10-unrolled-packed-mask:
	GPT2_CERTIFIED_STAGES=$${GPT2_CERTIFIED_STAGES:-61} \
	GPT2_CERTIFIED_SLACK_BUCKETS=$${GPT2_CERTIFIED_SLACK_BUCKETS:-24} \
	GPT2_CERTIFIED_GATE=1 GPT2_CERTIFIED_PACKED_MASK=1 PYTHONPATH=tools \
	uv run --with numpy --with fonttools --with brotli --with pillow \
	python tools/build_certified_int10_unrolled_cascade.py
	GPT2_CERTIFIED_STAGES=$${GPT2_CERTIFIED_STAGES:-61} \
	GPT2_CERTIFIED_GATE=1 GPT2_CERTIFIED_PACKED_MASK=1 \
	node tools/test_certified_int10_unrolled_cascade.mjs

test-gpt2-certified-int10-parallel-pair:
	PYTHONPATH=tools uv run --with numpy --with fonttools --with brotli --with pillow \
	python tools/build_certified_int10_parallel_pair_probe.py
	node tools/test_certified_int10_parallel_pair_probe.mjs

test-gpt2-certified-int10-parallel-pair-twoplane:
	PYTHONPATH=tools uv run --with numpy --with fonttools --with brotli --with pillow \
	python tools/build_certified_int10_parallel_pair_probe.py
	python3 tools/build_certified_int10_parallel_pair_twoplane_probe.py
	node tools/test_certified_int10_parallel_pair_twoplane_probe.mjs

test-gpt2-certified-int10-parallel-tail:
	PYTHONPATH=tools uv run --with numpy --with fonttools --with brotli \
	--with pillow --with safetensors \
	python tools/build_certified_int10_parallel_tail_probe.py
	GPT2_PARALLEL_TAIL_STRESS=1 \
	node tools/test_certified_int10_parallel_tail_probe.mjs

test-gpt2-certified-int10-batched-tail:
	GPT2_CERTIFIED_BATCH_SIZES=$${GPT2_CERTIFIED_BATCH_SIZES:-1,2,4,8} \
	PYTHONPATH=tools uv run --with numpy --with fonttools --with brotli --with pillow \
	python tools/build_certified_int10_batched_tail_probe.py
	GPT2_CERTIFIED_BATCH_SIZES=$${GPT2_CERTIFIED_BATCH_SIZES:-1,2,4,8} \
	GPT2_BATCH_STRESS=1 node tools/test_certified_int10_batched_tail_probe.mjs

test-position-try-upper-router:
	PYTHONPATH=tools uv run --with numpy \
	python tools/build_position_try_upper_router_probe.py
	node tools/test_position_try_upper_router_probe.mjs

test-hvar-raster-direct-scale:
	@for outputs in 1 8 16 32 64 128 256 512 768; do \
		HVAR_DIRECT_INPUTS=64 HVAR_DIRECT_OUTPUTS=$$outputs \
		uv run --with numpy --with fonttools --with brotli --with pillow --with safetensors \
		python tools/build_hvar_raster_direct_projection_probe.py; \
		HVAR_DIRECT_INPUTS=64 HVAR_DIRECT_OUTPUTS=$$outputs HVAR_DIRECT_ROUNDS=7 \
		node tools/test_hvar_raster_direct_projection_probe.mjs; \
	done
