# Enterprise Knowledge Base — local POC
.PHONY: up down reset logs models seed ui test security-test eval warmup

up:            ## start the core stack
	docker compose up -d --build

down:          ## stop (data kept in named volumes)
	docker compose down

reset:         ## wipe all data (keeps the downloaded Ollama models), restart, re-seed
	docker compose down
	-docker volume rm ekb_pg_data ekb_es_data ekb_neo4j_data ekb_minio_data
	docker compose up -d --build --wait
	docker compose exec api python -m app.seed

logs:
	docker compose logs -f api

models:        ## pull the LLM and embedding models into Ollama
	docker compose exec ollama ollama pull qwen2.5:7b
	docker compose exec ollama ollama pull bge-m3

seed:          ## generate synthetic PDFs and load them through the maker-checker workflow
	docker compose exec api python -m app.seed

test:          ## unit tests (no services needed)
	docker compose exec -w /srv api python -m pytest -q tests

security-test: ## a user without RISK_POLICY must never receive restricted content
	docker compose exec api python -m app.security_test

eval:
	docker compose exec api python -m app.security_test

warmup:        ## load models onto the GPU before a demo
	curl -s -X POST localhost:8000/api/query -H "X-User: erin" -H "Content-Type: application/json" -d "{\"question\":\"What is the cash advance fee?\"}" > /dev/null && echo warm
