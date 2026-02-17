FEED_API_BASE ?= http://localhost:9001
MIND_API_BASE ?= http://localhost:9002

.PHONY: build run-image run

build:
	docker build -t lexora-console .

run-image:
	docker run --rm -d -p 9009:80 \
		-e FEED_API_BASE=$(FEED_API_BASE) \
		-e MIND_API_BASE=$(MIND_API_BASE) \
		lexora-console

run:
	envsubst '$${FEED_API_BASE} $${MIND_API_BASE}' < index.html.template > index.html
	FEED_API_BASE=$(FEED_API_BASE) MIND_API_BASE=$(MIND_API_BASE) \
		python3 -m http.server 9009
