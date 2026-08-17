#!/usr/bin/env bash
# Document Intelligence Agent launcher (Linux/macOS).
# First-run setup + daily launch in one file: installs uv if missing, creates
# .venv in the project root via `uv sync`, pulls the required Ollama models,
# starts ArcadeDB in Docker, then runs the Streamlit app.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

echo "=== Document Intelligence Agent launcher ==="

if ! command -v uv >/dev/null 2>&1; then
    echo "[setup] uv not found, installing..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
    if ! command -v uv >/dev/null 2>&1; then
        echo "[error] Could not install uv automatically. Install it from https://docs.astral.sh/uv/ and re-run this script."
        exit 1
    fi
fi

if ! command -v ollama >/dev/null 2>&1; then
    echo "[error] Ollama not found. Install it from https://ollama.com/download, then re-run this script."
    exit 1
fi

if ! command -v docker >/dev/null 2>&1; then
    echo "[error] Docker not found. Install Docker (or Docker Desktop), then re-run this script."
    exit 1
fi

echo "[setup] Syncing Python dependencies (uv sync)..."
uv sync

echo "[setup] Checking local Ollama models (pulling any that are missing; first run may take a while)..."
ollama list | grep -q "nomic-embed-text-v2-moe" || ollama pull nomic-embed-text-v2-moe
ollama list | grep -q "qwen3.5:2b" || ollama pull qwen3.5:2b

echo "[setup] Checking ArcadeDB container..."
if docker ps --filter "name=docintel-arcadedb" --format "{{.Names}}" | grep -q "^docintel-arcadedb$"; then
    echo "[setup] ArcadeDB already running."
elif docker ps -a --filter "name=docintel-arcadedb" --format "{{.Names}}" | grep -q "^docintel-arcadedb$"; then
    echo "[setup] Starting existing ArcadeDB container..."
    docker start docintel-arcadedb
else
    echo "[setup] Creating ArcadeDB container (data persisted in ./arcadedb-data)..."
    docker run -d --name docintel-arcadedb -p 2480:2480 -p 2424:2424 \
        -v "$(pwd)/arcadedb-data:/home/arcadedb/databases" \
        --env JAVA_OPTS="-Darcadedb.server.rootPassword=playwithdata" \
        arcadedata/arcadedb:26.5.1
fi

if [ ! -f ".env" ]; then
    echo "[setup] No .env found. API keys will be read from your shell environment variables."
    echo "[setup] To use a .env file instead, copy .env.example to .env and fill it in."
fi

echo "[run] Starting Streamlit app..."
uv run streamlit run app.py
