.PHONY: build clean

build:
	python3 tools/build.py

clean:
	rm -f index.html model.css

