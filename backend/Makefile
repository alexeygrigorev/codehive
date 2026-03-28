.PHONY: run test setup shell coverage publish-build publish-test publish publish-clean infra-up infra-down infra-status

run:
	uv run codehive serve

test:
	uv run pytest

setup:
	uv sync --dev

shell:
	uv shell

coverage:
	uv run pytest --cov=codehive --cov-report=term-missing

publish-build:
	uv run hatch build

publish-test:
	uv run hatch publish --repo test

publish:
	uv run hatch publish

publish-clean:
	rm -r dist/

infra-up:
	docker compose -f ../docker-compose.yml up -d

infra-down:
	docker compose -f ../docker-compose.yml down

infra-status:
	docker compose -f ../docker-compose.yml ps
