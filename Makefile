all: scrape summarize tag

scrape:
	uv run flask scrape

summarize:
	uv run flask summarize

tag:
	uv run flask tag

