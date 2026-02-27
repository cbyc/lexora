RSS_DATA_FILE ?= ./data/feeds.yaml
RSS_MAX_POSTS_PER_FEED ?= 50
RSS_FETCH_TIMEOUT_SEC ?= 10
RSS_DEFAULT_RANGE ?= last_month

.PHONY: build-image run-container run-local

build-image:
	docker build -t lexora-feed .

run-container: build-image
	docker run --rm -d -p 9001:80 \
		-v $(dir $(RSS_DATA_FILE)):/data \
		-e RSS_HOST="0.0.0.0" \
		-e RSS_PORT=80 \
		-e RSS_DATA_FILE=/data/feeds.yaml \
		-e RSS_MAX_POSTS_PER_FEED=$(RSS_MAX_POSTS_PER_FEED) \
		-e RSS_FETCH_TIMEOUT_SEC=$(RSS_FETCH_TIMEOUT_SEC) \
		-e RSS_DEFAULT_RANGE=$(RSS_DEFAULT_RANGE) \
		--name lexora-feed \
		lexora-feed

run-local:
	RSS_HOST=0.0.0.0 \
	RSS_PORT=9001 \
	RSS_DATA_FILE=$(RSS_DATA_FILE) \
	RSS_MAX_POSTS_PER_FEED=$(RSS_MAX_POSTS_PER_FEED) \
	RSS_FETCH_TIMEOUT_SEC=$(RSS_FETCH_TIMEOUT_SEC) \
	RSS_DEFAULT_RANGE=$(RSS_DEFAULT_RANGE) \
	go run .
