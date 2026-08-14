@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"

echo === Document Intelligence Agent launcher ===

where uv >nul 2>nul
if errorlevel 1 (
    echo [setup] uv not found, installing...
    winget install --id=astral-sh.uv -e --accept-source-agreements --accept-package-agreements
    if errorlevel 1 (
        echo [error] Could not install uv automatically. Install it from https://docs.astral.sh/uv/ and re-run this file.
        pause
        exit /b 1
    )
    set "PATH=%USERPROFILE%\.local\bin;%PATH%"
)

where ollama >nul 2>nul
if errorlevel 1 (
    echo [error] Ollama not found. Install it from https://ollama.com/download, then re-run this file.
    pause
    exit /b 1
)

where docker >nul 2>nul
if errorlevel 1 (
    echo [error] Docker not found. Install Docker Desktop from https://www.docker.com/products/docker-desktop/, then re-run this file.
    pause
    exit /b 1
)

echo [setup] Syncing Python dependencies (uv sync)...
uv sync
if errorlevel 1 (
    echo [error] uv sync failed.
    pause
    exit /b 1
)

echo [setup] Checking local Ollama models (pulling any that are missing; first run may take a while)...
ollama list | findstr /C:"nomic-embed-text-v2-moe" >nul || ollama pull nomic-embed-text-v2-moe
ollama list | findstr /C:"qwen3.5:2b" >nul || ollama pull qwen3.5:2b

echo [setup] Checking ArcadeDB container...
docker ps --filter "name=docintel-arcadedb" --format "{{.Names}}" | findstr /C:"docintel-arcadedb" >nul
if not errorlevel 1 (
    echo [setup] ArcadeDB already running.
) else (
    docker ps -a --filter "name=docintel-arcadedb" --format "{{.Names}}" | findstr /C:"docintel-arcadedb" >nul
    if not errorlevel 1 (
        echo [setup] Starting existing ArcadeDB container...
        docker start docintel-arcadedb
    ) else (
        echo [setup] Creating ArcadeDB container (data persisted in .\arcadedb-data)...
        docker run -d --name docintel-arcadedb -p 2480:2480 -p 2424:2424 ^
            -v "%~dp0arcadedb-data:/home/arcadedb/databases" ^
            --env JAVA_OPTS="-Darcadedb.server.rootPassword=playwithdata" ^
            arcadedata/arcadedb:26.5.1
    )
)

if not exist ".env" (
    echo [setup] No .env found. API keys will be read from your system environment variables.
    echo [setup] To use a .env file instead, copy .env.example to .env and fill it in.
)

echo [run] Starting Streamlit app...
uv run streamlit run app.py

pause
