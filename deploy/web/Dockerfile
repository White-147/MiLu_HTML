# MiLuAssistantWeb Web 版部署镜像（Zeabur / Koyeb 等容器平台通用）
# 相比 deploy/Dockerfile（桌面版，含 xfce4 图形界面 + Chromium）：去掉全部 GUI 依赖，纯 Web 单容器
# 模型 API key 不写入镜像：运行时由 entrypoint.sh 从环境变量 MILU_DEEPSEEK_API_KEY 注入 providers.json
# Stage 1: console 前端构建（dist 不入库，构建时注入）
FROM node:20-alpine AS console-builder
WORKDIR /app/console
COPY console/package.json console/package-lock.json ./
RUN npm ci --include=dev
COPY console/ ./
RUN npm run build

# Stage 2: Python 运行时
FROM python:3.10-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1
COPY pyproject.toml setup.py README.md ./
COPY src ./src
COPY --from=console-builder /app/console/dist ./src/milu/console/
RUN pip install --no-cache-dir .

ENV MILU_WORKING_DIR=/app/working
ENV MILU_SECRET_DIR=/app/working/.secret
# 仅启用需要的频道；浏览器/GUI 相关频道在容器内不可用，全部排除
ENV MILU_DISABLED_CHANNELS=imessage
# 容器内标志（部分逻辑依赖）
ENV MILU_RUNNING_IN_CONTAINER=1

# 构建时初始化工作目录（config.json + HEARTBEAT.md）
RUN milu init --defaults --accept-security

COPY deploy/web/entrypoint.sh /entrypoint.sh
EXPOSE 8088
ENTRYPOINT ["sh", "/entrypoint.sh"]
