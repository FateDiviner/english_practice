"""dev.sh 一键启动脚本的守护测试。

固化重构过程中实际踩过的三个坑，防止回归：
  1. 健康检查写 127.0.0.1 打不通 vite 的 IPv6 监听（本机 vite 只绑 [::1]）；
  2. 漏 trap HUP 时，关终端会让四个服务变成占端口的孤儿；
  3. trap 注册过早，自检失败会被误报成“全部服务已停止”。
"""

from __future__ import annotations

import shutil
import socket
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
DEV_SH = REPO_ROOT / "dev.sh"
BASH = shutil.which("bash")

pytestmark = pytest.mark.skipif(
    BASH is None, reason="Git Bash 不在 PATH 中，无法执行 dev.sh"
)


def run_dev(*args: str, timeout: int = 60) -> subprocess.CompletedProcess[str]:
    """以 bash 执行 dev.sh 并返回结果。"""
    assert BASH is not None
    return subprocess.run(
        [BASH, str(DEV_SH), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=str(REPO_ROOT),
        timeout=timeout,
    )


@pytest.fixture(scope="module")
def script_text() -> str:
    return DEV_SH.read_text(encoding="utf-8")


def _line_index(text: str, wanted: str) -> int:
    """返回整行 strip 后等于 wanted 的那一行的起始偏移。"""
    offset = 0
    for line in text.splitlines(keepends=True):
        if line.strip() == wanted:
            return offset
        offset += len(line)
    raise AssertionError(f"未找到整行 {wanted!r}")


class TestScriptIntegrity:
    def test_script_exists(self):
        assert DEV_SH.is_file()

    def test_no_crlf(self):
        """CR 会让 bash 逐行报错，脚本必须是纯 LF。"""
        raw = DEV_SH.read_bytes()
        assert b"\r\n" not in raw, "dev.sh 含 CRLF 行尾"

    @pytest.mark.skipif(BASH is None, reason="Git Bash 不在 PATH 中")
    def test_runnable_by_bash(self):
        """以 bash 实跑 --help，比看 st_mode 更贴近真实属性。

        Windows 上 Python 的 st_mode 执行位不可靠，故不作断言。
        """
        assert run_dev("--help").returncode == 0

    @pytest.mark.skipif(BASH is None, reason="Git Bash 不在 PATH 中")
    def test_syntax(self):
        """bash -n 语法检查。"""
        proc = subprocess.run(
            [BASH, "-n", str(DEV_SH)],
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        assert proc.returncode == 0, proc.stderr

    def test_shebang(self):
        first = DEV_SH.read_text(encoding="utf-8").splitlines()[0]
        assert first == "#!/usr/bin/env bash"


class TestSignalHandling:
    def test_traps_hup(self, script_text: str):
        """漏 trap HUP：关终端/SSH 断开会留下四个占端口的孤儿进程。"""
        assert "HUP" in script_text, "dev.sh 必须 trap HUP，否则退出时孤儿占端口"

    def test_signal_traps_on_signal_handler(self, script_text: str):
        """信号路径要走 on_signal（清理后立即退出），不能只 trap cleanup。"""
        assert "on_signal" in script_text
        # 清理完若把控制权交回被打断的 wait_http，会继续打印过期提示
        assert "exit 0" in script_text

    def test_cleanup_is_idempotent(self, script_text: str):
        """cleanup 可能被信号与 EXIT 重复触发，必须幂等。"""
        assert "CLEANED" in script_text

    def test_trap_registered_after_preflight(self, script_text: str):
        """trap 晚注册：自检失败时不该走 EXIT 清理、误报“全部已停止”。"""
        # 只认整行的 preflight 调用；注释里 “trap 在 preflight 之后” 会造成误判
        assert _line_index(script_text, "trap 'on_signal' INT TERM HUP") > _line_index(
            script_text, "preflight"
        ), "trap 必须在 preflight 调用之后注册"


class TestHealthCheckUrls:
    def test_uses_localhost_not_loopback(self, script_text: str):
        """健康检查必须用 localhost。

        本机 vite 只监听 IPv6 [::1]，后端只监听 IPv4 127.0.0.1，
        写死 127.0.0.1 会让两个前端永远被判为“启动超时”。
        """
        checked = 0
        for line in script_text.splitlines():
            if "wait_http" in line and "http://" in line:
                checked += 1
                assert "127.0.0.1" not in line, (
                    f"健康检查用了 127.0.0.1，打不通 IPv6 监听：{line.strip()}"
                )
                assert "http://localhost:" in line, f"非 localhost URL：{line.strip()}"
        assert checked >= 4, f"只找到 {checked} 条健康检查，四个服务应各一条"


class TestPreflight:
    @pytest.fixture
    def occupied_port(self):
        """占用 8000，使 user 目标的自检必然失败且不启动任何服务。"""
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(("127.0.0.1", 8000))
            sock.listen(1)
        except OSError:
            sock.close()
            pytest.skip("8000 已被占用，无法构造端口冲突场景")
        yield 8000
        sock.close()

    @pytest.mark.skipif(BASH is None, reason="Git Bash 不在 PATH 中")
    def test_aborts_on_port_conflict(self, occupied_port: int):
        """端口被占时必须中止，且不得误报“全部服务已停止”（实际一个都没启动）。"""
        proc = run_dev("user")
        out = proc.stdout + proc.stderr
        assert proc.returncode == 1, out
        assert "已被占用" in out
        assert "自检未通过" in out
        # 关键回归：一个服务都没启动，就绝不能说“已停止”
        assert "全部服务已停止" not in out
        assert "[start]" not in out

    def test_preflight_failure_exits_one(self, script_text: str):
        """自检失败必须以非零码退出。"""
        assert "exit 1" in script_text
        assert "自检未通过" in script_text

    def test_checks_all_four_ports(self, script_text: str):
        for port in ("8000", "5173", "8100", "5174"):
            assert port in script_text, f"未检查端口 {port}"


class TestTargetModes:
    def test_single_target_accepted(self, script_text: str):
        """user/admin 两个单端模式必须被参数解析接受。

        只做静态断言——真跑 dev.sh user 会启动服务并阻塞在 wait，
        且可能在并行跑测试时抢占端口。
        """
        for target in ("user", "admin"):
            assert f'TARGET="{target}"' in script_text, f"参数解析未接受 {target}"

    def test_target_defaults_to_all(self, script_text: str):
        assert 'TARGET="all"' in script_text
        assert 'case "${1:-all}" in' in script_text

    def test_target_gates_service_launch(self, script_text: str):
        """每个服务都必须受 TARGET 控制，否则单端模式会多起服务。"""
        for service in ("user-backend", "user-frontend", "admin-backend", "admin-frontend"):
            assert service in script_text, f"缺少 {service} 的启动定义"


class TestCli:
    @pytest.mark.skipif(BASH is None, reason="Git Bash 不在 PATH 中")
    def test_help_exits_zero(self):
        proc = run_dev("--help")
        assert proc.returncode == 0
        assert "用法" in proc.stdout

    @pytest.mark.skipif(BASH is None, reason="Git Bash 不在 PATH 中")
    def test_unknown_argument_exits_two(self):
        proc = run_dev("not-a-target")
        assert proc.returncode == 2
        # err() 输出到 stderr，且随后还会打印 usage 到 stdout
        assert "未知参数" in proc.stderr
