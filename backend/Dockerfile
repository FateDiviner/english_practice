# 后端镜像。多阶段没意义——依赖都是二进制轮子，直接装即可。
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    # 容器里必须绑 0.0.0.0，绑 127.0.0.1 的话 nginx 反代连不上
    BACKEND_HOST=0.0.0.0 \
    # 关热重载：容器里 reload 的子进程在信号处理上很麻烦，重建容器更快也更干净
    BACKEND_RELOAD=0 \
    # faiss 的 C++ 文件写入在 Windows 走 ANSI 代码页，容器内路径是纯 ASCII 不受影响；
    # 但显式钉死索引目录，避免有人把它挂到含中文的 bind mount 上
    RAG_INDEX_DIR=/app/data/rag_index

WORKDIR /app

# 先装依赖再拷源码：源码变更频率远高于依赖，这样能命中层缓存
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY scripts ./scripts
COPY data ./data
# 入口文件必须显式拷进来：CMD 是 python main.py，漏了它容器一起来就退出
COPY main.py ./main.py

# 索引目录单独建出来并交给 volume，镜像里不放索引文件
RUN mkdir -p /app/data/rag_index

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=3)"

CMD ["python", "main.py"]
