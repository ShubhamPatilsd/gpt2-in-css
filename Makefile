.PHONY: build transformer clean

build:
	python3 tools/build.py

transformer:
	python3 tools/build_transformer.py

clean:
	rm -f index.html model.css transformer/index.html transformer/model.css
