FROM python:3.12-slim

LABEL maintainer="pterodactyl-ai-bot"
LABEL description="翼龙面板 AI 聊天机器人"

WORKDIR /app

# 安装依赖
COPY pyproject.toml .
RUN pip install --no-cache-dir aiohttp>=3.9.0 --break-system-packages

# 复制源代码
COPY src/ ./src/

# 设置环境变量
ENV PYTHONPATH=/app/src
ENV PYTHONUNBUFFERED=1

# 健康检查（检查进程是否存活）
HEALTHCHECK --interval=60s --timeout=10s --retries=3 \
    CMD python -c "import pterodactyl_bot" || exit 1

CMD ["python", "-m", "pterodactyl_bot.main"]
