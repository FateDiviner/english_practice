"""启动入口 main.py 的参数组装与调用测试。

不真的拉起服务器：uvicorn.run 被替换为记录器，避免测试占用 8000 端口。
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest

import main


@pytest.fixture
def clean_env(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """清掉三个入口环境变量，保证默认值断言不受宿主环境干扰。"""
    for name in ("BACKEND_HOST", "BACKEND_PORT", "BACKEND_RELOAD"):
        monkeypatch.delenv(name, raising=False)
    yield


class TestBuildRunKwargs:
    def test_defaults(self, clean_env: None) -> None:
        kwargs = main.build_run_kwargs()
        assert kwargs["app"] == "app.main:app"
        assert kwargs["host"] == "127.0.0.1"
        assert kwargs["port"] == 8000
        assert kwargs["reload"] is True

    def test_env_override(self, monkeypatch: pytest.MonkeyPatch, clean_env: None) -> None:
        monkeypatch.setenv("BACKEND_HOST", "0.0.0.0")
        monkeypatch.setenv("BACKEND_PORT", "9000")
        monkeypatch.setenv("BACKEND_RELOAD", "0")
        kwargs = main.build_run_kwargs()
        assert kwargs["host"] == "0.0.0.0"
        assert kwargs["port"] == 9000
        assert kwargs["reload"] is False

    @pytest.mark.parametrize("value", ["0", "false", "False", "no", "NO", "off", " OFF "])
    def test_reload_falsey_values(self, monkeypatch: pytest.MonkeyPatch, clean_env: None, value: str) -> None:
        monkeypatch.setenv("BACKEND_RELOAD", value)
        assert main.build_run_kwargs()["reload"] is False

    @pytest.mark.parametrize("value", ["1", "true", "yes", ""])
    def test_reload_truthy_values(self, monkeypatch: pytest.MonkeyPatch, clean_env: None, value: str) -> None:
        monkeypatch.setenv("BACKEND_RELOAD", value)
        assert main.build_run_kwargs()["reload"] is True

    def test_port_must_be_integer(self, monkeypatch: pytest.MonkeyPatch, clean_env: None) -> None:
        monkeypatch.setenv("BACKEND_PORT", "not-a-port")
        with pytest.raises(ValueError):
            main.build_run_kwargs()


class TestMain:
    def test_main_invokes_uvicorn_run(self, monkeypatch: pytest.MonkeyPatch, clean_env: None) -> None:
        calls: list[dict[str, Any]] = []

        def fake_run(**kwargs: Any) -> None:
            calls.append(kwargs)

        monkeypatch.setattr(main.uvicorn, "run", fake_run)
        main.main()

        assert len(calls) == 1
        assert calls[0]["app"] == "app.main:app"
        assert calls[0]["host"] == "127.0.0.1"
        assert calls[0]["port"] == 8000

    def test_main_passes_overridden_port(self, monkeypatch: pytest.MonkeyPatch, clean_env: None) -> None:
        calls: list[dict[str, Any]] = []
        monkeypatch.setattr(main.uvicorn, "run", lambda **kwargs: calls.append(kwargs))
        monkeypatch.setenv("BACKEND_PORT", "8888")
        main.main()
        assert calls[0]["port"] == 8888
