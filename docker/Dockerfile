# 多阶段构建基础层：API 与 Streamlit 共用同一运行环境
# 构建: docker build --target backend -t harbin-platform-api -f docker/Dockerfile .
#       docker build --target frontend -t harbin-platform-ui -f docker/Dockerfile .
FROM python:3.11-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# CJK 字体：保证容器内 PDF/Matplotlib 中文正常渲染
RUN apt-get update \
    && apt-get install -y --no-install-recommends fonts-noto-cjk fonts-wqy-zenhei \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt ./
ARG PIP_INDEX_URL=https://pypi.org/simple
RUN pip install --timeout 60 --retries 5 -i ${PIP_INDEX_URL} -r requirements.txt

# 只复制运行所需目录，原始数据（00_原始基座数据等）绝不进入镜像
COPY src ./src
COPY dashboard ./dashboard
COPY analysis/V30_Multi_Source_Fusion_R2 ./analysis/V30_Multi_Source_Fusion_R2
COPY configs ./configs
COPY .streamlit ./.streamlit

RUN useradd --create-home --uid 10001 appuser \
    && mkdir -p /app/data \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000 8501

FROM base AS backend
CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]

FROM base AS frontend
CMD ["streamlit", "run", "dashboard/app.py", "--server.port=8501", "--server.address=0.0.0.0", "--server.headless=true"]
