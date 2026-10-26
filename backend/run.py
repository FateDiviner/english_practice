"""本地开发启动入口：在 backend 目录执行 `python run.py`。"""

import uvicorn

HOST = "127.0.0.1"
PORT = 8000


def main() -> None:
    """以开发模式启动 FastAPI 应用。"""
    uvicorn.run(
        "app.main:app",
        host=HOST,
        port=PORT,
        reload=True,
    )


if __name__ == "__main__":
    main()
