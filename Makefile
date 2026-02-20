RSS_DATA_DIR ?= "./data"
RSS_MAX_POSTS_PER_FEED ?= 50
RSS_FETCH_TIMEOUT_SEC ?= 10
RSS_DEFAULT_RANGE ?= last_month

.PHONY: build-image run-container run-local

build-image:
	docker build -t lexora-feed .

run-container: build-image
	docker run --rm -d -p 9001:80 \
		-v ${RSS_DATA_DIR}:/data \
		-e RSS_HOST="0.0.0.0" \
		-e RSS_PORT=80 \
		-e RSS_DATA_DIR=/data \
		-e RSS_MAX_POSTS_PER_FEED=$(RSS_MAX_POSTS_PER_FEED) \
		-e RSS_FETCH_TIMEOUT_SEC=$(RSS_FETCH_TIMEOUT_SEC) \
		-e RSS_DEFAULT_RANGE=$(RSS_DEFAULT_RANGE) \
		lexora-feed

run-local:
	RSS_HOST=0.0.0.0 \
	RSS_PORT=9001 \
	RSS_DATA_DIR=${RSS_DATA_DIR} \
	RSS_MAX_POSTS_PER_FEED=$(RSS_MAX_POSTS_PER_FEED) \
	RSS_FETCH_TIMEOUT_SEC=$(RSS_FETCH_TIMEOUT_SEC) \
	RSS_DEFAULT_RANGE=$(RSS_DEFAULT_RANGE) \
	go run .
