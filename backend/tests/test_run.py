import run
import uvicorn


def test_main_starts_uvicorn_in_reload_mode(monkeypatch) -> None:
    calls: dict = {}

    def fake_run(app: str, **kwargs) -> None:
        calls["app"] = app
        calls.update(kwargs)

    monkeypatch.setattr(uvicorn, "run", fake_run)

    run.main()

    assert calls["app"] == "app.main:app"
    assert calls["host"] == "127.0.0.1"
    assert calls["port"] == 8000
    assert calls["reload"] is True
