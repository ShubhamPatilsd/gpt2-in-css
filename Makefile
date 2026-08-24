.PHONY: build transformer pretrained benchmark interactive analyze-full clean

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

clean:
	rm -f index.html model.css transformer/index.html transformer/model.css pretrained/index.html pretrained/benchmark.html pretrained/model.css pretrained/autoregressive.css pretrained/interactive.html pretrained/interactive.js pretrained/interactive-1.css pretrained/interactive-2.css pretrained/interactive-3.css pretrained/interactive-4.css pretrained/prompt-data.json
