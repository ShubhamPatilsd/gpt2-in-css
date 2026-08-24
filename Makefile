.PHONY: build transformer pretrained analyze-full clean

build:
	python3 tools/build.py

transformer:
	python3 tools/build_transformer.py

pretrained:
	python3 tools/build_pretrained_gpt2.py

analyze-full:
	python3 tools/analyze_full_gpt2.py

clean:
	rm -f index.html model.css transformer/index.html transformer/model.css pretrained/index.html pretrained/model.css
