FROM python:3.10-slim

WORKDIR /app/backend

# 复制依赖文件
COPY backend/pyproject.toml backend/poetry.lock /app/backend/

# 安装 Poetry 及依赖
RUN pip install poetry \
    && poetry config virtualenvs.create false \
    && poetry install --no-dev

# 复制后端代码
COPY backend/ /app/backend/

# 設置 PYTHONPATH
ENV PYTHONPATH=/app

EXPOSE 8000

CMD ["poetry", "run", "uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
