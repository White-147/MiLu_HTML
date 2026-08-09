#!/bin/sh
# MiLuAssistantWeb Web 版入口：
# 1. 若设置了 MILU_DEEPSEEK_API_KEY，首次启动生成 providers.json（legacy 格式，应用启动时自动迁移）
# 2. 启动 milu app 监听平台注入的 $PORT
set -e

export MILU_WORKING_DIR="${MILU_WORKING_DIR:-/app/working}"
export MILU_SECRET_DIR="${MILU_SECRET_DIR:-$MILU_WORKING_DIR/.secret}"
mkdir -p "$MILU_SECRET_DIR"

# 注入 DeepSeek provider（仅当 key 存在且尚未配置 active model 时，避免覆盖运行期用户修改）
if [ -n "$MILU_DEEPSEEK_API_KEY" ] && [ ! -f "$MILU_SECRET_DIR/active_model.json" ]; then
  cat > "$MILU_SECRET_DIR/providers.json" <<EOF
{
  "providers": {},
  "custom_providers": {
    "deepseek": {
      "name": "DeepSeek",
      "base_url": "https://api.deepseek.com/v1",
      "api_key": "$MILU_DEEPSEEK_API_KEY",
      "chat_model": "OpenAIChatModel",
      "models": []
    }
  },
  "active_llm": {
    "provider_id": "deepseek",
    "model": "deepseek-chat"
  }
}
EOF
  echo "DeepSeek provider injected."
fi

# 平台约定端口（Zeabur/Koyeb/HF 注入 $PORT），未注入时回退 8088
exec milu app --host 0.0.0.0 --port "${PORT:-8088}"
