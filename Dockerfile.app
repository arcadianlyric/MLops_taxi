FROM python:3.9-slim

WORKDIR /app

# 安装基础依赖
RUN pip install --no-cache-dir \
    fastapi==0.104.1 \
    uvicorn==0.24.0 \
    pydantic==2.5.0 \
    streamlit==1.28.0 \
    requests==2.31.0 \
    pandas==2.1.3 \
    numpy==1.26.2 \
    plotly==5.18.0

# 复制应用代码
COPY api/taxi_simple_api.py /app/api/
COPY ui/streamlit_app.py /app/ui/
COPY ui/*.py /app/ui/

# 创建空的集成模块（避免导入错误）
RUN mkdir -p /app/ui && \
    touch /app/ui/__init__.py && \
    echo "def feast_ui(): pass" > /app/ui/feast_ui_integration.py && \
    echo "def kafka_ui(): pass" > /app/ui/kafka_ui_integration.py && \
    echo "def mlflow_ui(): pass" > /app/ui/mlflow_ui_integration.py && \
    echo "def get_mlmd_ui_integration(): pass" > /app/ui/mlmd_ui_integration.py

EXPOSE 8000 8501

# 默认命令
CMD ["uvicorn", "api.taxi_simple_api:app", "--host", "0.0.0.0", "--port", "8000"]
