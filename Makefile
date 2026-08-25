.PHONY: build transformer pretrained benchmark interactive analyze-full output-head-baselines output-head-search clustered-output-head hierarchical-output-head tinystories-step tinystories-recurrent tinystories-nested tinystories-all precompress-tinystories serve-tinystories test clean

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

tinystories-step:
	python3 tools/build_tinystories_step.py

tinystories-recurrent:
	python3 tools/build_tinystories_recurrent.py

tinystories-nested:
	python3 tools/build_tinystories_nested.py

tinystories-all: clustered-output-head tinystories-step tinystories-recurrent tinystories-nested

precompress-tinystories:
	python3 tools/precompress_tinystories.py

serve-tinystories: precompress-tinystories
	python3 tools/serve_precompressed.py

test:
	python3 tools/test_css_number.py
	python3 tools/test_precompressed_server.py

clean:
	rm -f index.html model.css transformer/index.html transformer/model.css pretrained/index.html pretrained/benchmark.html pretrained/model.css pretrained/autoregressive.css pretrained/interactive.html pretrained/interactive-2.html pretrained/interactive-3.html pretrained/interactive-4.html pretrained/recurrent.css pretrained/prompt-position-0.css pretrained/prompt-position-1.css pretrained/prompt-position-2.css pretrained/prompt-position-3.css tinystories/step.css tinystories/recurrent.css tinystories/nested-runtime.css tinystories/streaming.css
