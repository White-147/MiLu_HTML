#!/bin/bash
# 启动 Chromium with CDP 9222 端口

PORT=9222

# 如果已存在，先杀掉
if curl -s http://localhost:$PORT/json >/dev/null 2>&1; then
    echo "Port $PORT already in use, killing existing process..."
    pkill -f "remote-debugging-port=$PORT" 2>/dev/null
    sleep 1
fi

echo "Starting Chromium with remote debugging on port $PORT..."

chromium-browser \
    --headless=new \
    --remote-debugging-port=$PORT \
    --no-sandbox \
    --remote-allow-origins=* \
    --disable-gpu \
    --disable-dev-shm-usage \
    --disable-software-rasterizer \
    --disable-extensions \
    --disable-plugins \
    &

sleep 3

# 验证
if curl -s http://localhost:$PORT/json >/dev/null 2>&1; then
    echo "✅ Chromium started successfully on port $PORT"
    curl -s http://localhost:$PORT/json | jq -r '.[0] .webSocketDebuggerUrl'
else
    echo "❌ Failed to start Chromium"
    exit 1
fi
