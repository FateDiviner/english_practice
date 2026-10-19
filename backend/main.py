"""后端开发服务器启动入口。

用法（在 backend/ 目录下）：
    .venv/Scripts/python main.py        # Windows
    .venv/bin/python main.py            # macOS / Linux

默认监听 127.0.0.1:8000 并开启热重载，可用环境变量覆盖：
    BACKEND_HOST=0.0.0.0 BACKEND_PORT=9000 BACKEND_RELOAD=0
"""

from __future__ import annotations

import os

import uvicorn

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8000
# 关闭热重载的取值：设为其中任一即为 False
_RELOAD_OFF = {"0", "false", "no", "off"}


def build_run_kwargs() -> dict[str, object]:
    """组装 uvicorn.run 参数。

    抽成独立函数是为了让测试能校验配置而不真的占住 8000 端口。
    """
    return {
        "app": "app.main:app",
        "host": os.getenv("BACKEND_HOST", DEFAULT_HOST),
        "port": int(os.getenv("BACKEND_PORT", str(DEFAULT_PORT))),
        "reload": os.getenv("BACKEND_RELOAD", "1").strip().lower() not in _RELOAD_OFF,
    }


def main() -> None:
    """以 ASGI 字符串形式启动，热重载子进程才能正确重新导入 app 包。"""
    uvicorn.run(**build_run_kwargs())


if __name__ == "__main__":
    main()
