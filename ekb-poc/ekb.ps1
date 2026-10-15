# Windows equivalent of the Makefile.  Usage:  .\ekb.ps1 <command>
#   up | down | models | seed | reset | warmup | test | security-test | logs
param([Parameter(Mandatory = $true)][string]$Command)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

switch ($Command) {
  "up"     { docker compose up -d --build --wait }
  "down"   { docker compose down }
  "logs"   { docker compose logs -f api }
  "models" {
    docker compose exec ollama ollama pull qwen2.5:7b
    docker compose exec ollama ollama pull bge-m3
  }
  "seed"   { docker compose exec api python -u -m app.seed }
  "reset"  {
    # Wipes documents, index, graph and lake; keeps the downloaded Ollama models.
    docker compose down
    docker volume rm ekb_pg_data ekb_es_data ekb_neo4j_data ekb_minio_data 2>$null
    docker compose up -d --build --wait
    docker compose exec api python -u -m app.seed
  }
  "warmup" {
    $body = '{"question":"What is the cash advance fee?"}'
    Invoke-RestMethod -Method Post -Uri http://localhost:8000/api/query -Headers @{ "X-User" = "erin" } `
      -ContentType "application/json" -Body $body | Out-Null
    Write-Host "Models loaded - ready for the demo."
  }
  "test"          { docker compose exec -w /srv api python -m pytest -q tests }
  "security-test" { docker compose exec api python -m app.security_test }
  default { Write-Host "Unknown command '$Command'. Use: up, down, models, seed, reset, warmup, test, security-test, logs" }
}
