#!/usr/bin/env bash
#
# 英语练习平台 一键启动脚本（Git Bash / MSYS）
#
# 用法：
#   ./dev.sh            # 启动全部四个服务（用户端前后端 + 管理端前后端）
#   ./dev.sh user       # 只启动用户端前后端
#   ./dev.sh admin      # 只启动管理端前后端
#   ./dev.sh --help     # 查看帮助
#
# 设计约束（本机 Git Bash 实测得出，改动前务必了解）：
#   1. 每个服务以纯后台方式启动（cmd >log 2>&1 &），这样 $! 就是服务进程本身，
#      清理时 kill 能可靠带走 uvicorn --reload 的整棵进程树并释放端口。
#      切勿改成 `cmd | sed &` 之类的管道——那样 $! 变成管道末端，kill 不到服务。
#   2. Git Bash 下 msys PID 与 Windows PID 对不上，因此清理只用 bash kill，
#      不使用 taskkill。
#   3. Ctrl+C 由 INT trap 捕获，逐个 kill 已记录的 PID 后退出。
#
set -euo pipefail

# --- 定位仓库根（脚本自身所在目录），保证从任意 cwd 调用都能解析相对路径 ---
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# --- 服务端口与路径（命令直接引用 $VENV_PY / $NODE，启动前由自检把关）---
VENV_PY="$SCRIPT_DIR/user/backend/.venv/Scripts/python.exe"
if [ ! -x "$VENV_PY" ]; then
    # 兼容非 Windows（源码安装或 WSL）
    VENV_PY="$SCRIPT_DIR/user/backend/.venv/bin/python"
fi
NODE="$(command -v node || true)"

USER_BACKEND_PORT=8000
ADMIN_BACKEND_PORT=8100
USER_FRONTEND_PORT=5173
ADMIN_FRONTEND_PORT=5174

LOG_DIR="$SCRIPT_DIR/logs/dev"
PIDS=()
NAMES=()
TAIL_PID=""
CLEANED=0

# --- 输出着色（终端非 TTY 时自动去色，避免日志里出现乱码转义）---
if [ -t 1 ]; then
    C_RESET=$'\033[0m'; C_DIM=$'\033[2m'; C_GREEN=$'\033[32m'
    C_RED=$'\033[31m'; C_YELLOW=$'\033[33m'; C_CYAN=$'\033[36m'
else
    C_RESET=""; C_DIM=""; C_GREEN=""; C_RED=""; C_YELLOW=""; C_CYAN=""
fi

log()  { printf '%s\n' "$*"; }
ok()   { printf '%s[ OK ]%s %s\n' "$C_GREEN" "$C_RESET" "$*"; }
warn() { printf '%s[warn]%s %s\n' "$C_YELLOW" "$C_RESET" "$*"; }
err()  { printf '%s[fail]%s %s\n' "$C_RED" "$C_RESET" "$*" >&2; }
step() { printf '\n%s==>%s %s\n' "$C_CYAN" "$C_RESET" "$*"; }

usage() {
    cat <<'USAGE'
英语练习平台 一键启动脚本

用法：
  ./dev.sh            启动全部四个服务（用户端 + 管端 前后端）
  ./dev.sh user       只启动用户端前后端（:5173 与 :8000）
  ./dev.sh admin      只启动管理端前后端（:5174 与 :8100）
  ./dev.sh --help     显示本帮助

说明：
  - 管理端后端复用用户端后端的 venv（user/backend/.venv）。
  - 服务日志实时聚合显在下方，同时写入 logs/dev/<服务名>.log 便于回看。
  - 按 Ctrl+C 停止全部服务。
USAGE
}

# --- 参数解析 ---
TARGET="all"
case "${1:-all}" in
    all)   TARGET="all" ;;
    user)  TARGET="user" ;;
    admin) TARGET="admin" ;;
    -h|--help|help) usage; exit 0 ;;
    *)
        err "未知参数：$1"
        echo
        usage
        exit 2
        ;;
esac

# --- 端口占用检测：返回占用该端口的 Windows PID（可能为空）---
port_pids() {
    local port="$1"
    netstat -ano 2>/dev/null \
        | grep -E "[:.]${port}[[:space:]]" \
        | grep -i "LISTEN" \
        | awk '{print $NF}' \
        | sort -u || true
}

# --- 清理：逐个 kill 记录的 PID 并回收（幂等，可被信号与 EXIT 重复触发）---
# 注意：trap 在 preflight 通过后才注册，避免“自检失败”被误报为“全部已停止”。
cleanup() {
    if [ "$CLEANED" -eq 1 ]; then
        return 0
    fi
    CLEANED=1
    trap - INT TERM EXIT
    if [ "${#PIDS[@]}" -eq 0 ]; then
        return 0
    fi
    step "停止服务"
    local pid i
    for i in "${!PIDS[@]}"; do
        pid="${PIDS[$i]}"
        if kill -0 "$pid" 2>/dev/null; then
            kill "$pid" 2>/dev/null || true
            ok "已停止 ${NAMES[$i]} (pid $pid)"
        fi
    done
    if [ -n "$TAIL_PID" ] && kill -0 "$TAIL_PID" 2>/dev/null; then
        kill "$TAIL_PID" 2>/dev/null || true
    fi
    # 回收僵尸进程，确保端口随进程退出而释放
    wait 2>/dev/null || true
    ok "全部服务已停止"
}

# Ctrl+C 路径：清理完立即退出。
# 若只 trap cleanup，bash 会把控制权交回被打断的 wait_http 轮询，
# 继续打印“启动超时 / 按 Ctrl+C 停止”这类过期提示后才返回，输出错乱。
on_signal() {
    cleanup
    exit 0
}

# --- 环境自检 ---
preflight() {
    step "环境自检"
    local fatal=0

    # 1. venv Python 可用
    if [ -x "$VENV_PY" ]; then
        ok "venv Python：$VENV_PY"
    else
        err "找不到 venv Python：$VENV_PY"
        err "  请先创建虚拟环境，或执行：cd user/backend && python -m venv .venv"
        fatal=1
    fi

    # 2. 共享层 core 可导入（editable 安装）
    if [ -x "$VENV_PY" ]; then
        if "$VENV_PY" -c "import core, core.config" >/dev/null 2>&1; then
            ok "共享层 core 可导入"
        else
            err "无法导入 core。若是新克隆仓库或刚重建 venv，执行："
            err "  cd user/backend && .venv/Scripts/python -m pip install -e ../.."
            fatal=1
        fi
    fi

    # 3. node 可用（启动前端才需要）
    if [ "$TARGET" = "all" ] || [ "$TARGET" = "user" ] || [ "$TARGET" = "admin" ]; then
        if [ -n "$NODE" ]; then
            ok "node：$NODE"
        else
            err "找不到 node，无法启动前端。请安装 Node.js 并确保在 PATH 中。"
            fatal=1
        fi
    fi

    # 4. node_modules 就位（前端）
    local fe
    for fe in user/frontend admin/frontend; do
        case "$TARGET" in
            user)  [ "$fe" = "admin/frontend" ] && continue ;;
            admin) [ "$fe" = "user/frontend" ] && continue ;;
        esac
        if [ -d "$SCRIPT_DIR/$fe/node_modules" ]; then
            ok "$fe/node_modules 已就绪"
        else
            err "$fe 缺 node_modules。请先：cd $fe && npm install"
            fatal=1
        fi
    done

    # 5. 目标端口全部空闲（撞端口是本机最常见的“起了没反应”元凶）
    local ports=()
    case "$TARGET" in
        user)  ports=("$USER_BACKEND_PORT" "$USER_FRONTEND_PORT") ;;
        admin) ports=("$ADMIN_BACKEND_PORT" "$ADMIN_FRONTEND_PORT") ;;
        all)   ports=("$USER_BACKEND_PORT" "$USER_FRONTEND_PORT" "$ADMIN_BACKEND_PORT" "$ADMIN_FRONTEND_PORT") ;;
    esac
    local p holder
    for p in "${ports[@]}"; do
        holder="$(port_pids "$p")"
        if [ -n "$holder" ]; then
            err "端口 $p 已被占用（PID: ${holder//$'\n'/ }）。"
            err "  可能是上次没退干净的孤儿进程：taskkill //PID <pid> //F  或重启终端。"
            fatal=1
        else
            ok "端口 $p 空闲"
        fi
    done

    if [ "$fatal" -ne 0 ]; then
        echo
        err "自检未通过，已中止启动（见上方 [fail] 项）。"
        exit 1
    fi
}

# --- 启动单个服务：$1=名称 $2=工作目录 $3+=启动命令 ---
start_service() {
    local name="$1"
    shift
    local workdir="$1"
    shift
    mkdir -p "$LOG_DIR"
    local logfile="$LOG_DIR/$name.log"
    : > "$logfile"

    ( cd "$SCRIPT_DIR/$workdir" && exec "$@" ) > "$logfile" 2>&1 &
    local pid=$!
    PIDS+=("$pid")
    NAMES+=("$name")
    printf '%s[start]%s %-14s %s(pid %s -> %s)%s\n' \
        "$C_GREEN" "$C_RESET" "$name" "$C_DIM" "$pid" "$logfile" "$C_RESET"
}

# --- 轮询等待 HTTP 就绪 ---
# URL 必须用 localhost 而非 127.0.0.1：本机 vite 只监听 IPv6 [::1]，
# 后端监听 IPv4 127.0.0.1，只有 localhost 会同时覆盖两个地址族。
wait_http() {
    local label="$1" url="$2" tries="${3:-80}"
    local i
    for ((i = 0; i < tries; i++)); do
        if curl -s -o /dev/null --max-time 2 "$url" 2>/dev/null; then
            return 0
        fi
        sleep 0.25
    done
    return 1
}

launch() {
    step "启动服务"

    if [ "$TARGET" = "all" ] || [ "$TARGET" = "user" ]; then
        start_service user-backend user/backend \
            "$VENV_PY" -m uvicorn app.main:app --reload --port "$USER_BACKEND_PORT"
        start_service user-frontend user/frontend \
            "$NODE" node_modules/vite/bin/vite.js --port "$USER_FRONTEND_PORT"
    fi

    if [ "$TARGET" = "all" ] || [ "$TARGET" = "admin" ]; then
        start_service admin-backend admin/backend \
            "$VENV_PY" -m uvicorn app.main:app --reload --port "$ADMIN_BACKEND_PORT"
        start_service admin-frontend admin/frontend \
            "$NODE" node_modules/vite/bin/vite.js --port "$ADMIN_FRONTEND_PORT"
    fi

    # 聚合实时日志到终端：tail -f 多文件自带 "==> 文件名 <==" 头，可区分归属
    local logs=()
    case "$TARGET" in
        user)  logs+=("$LOG_DIR/user-backend.log" "$LOG_DIR/user-frontend.log") ;;
        admin) logs+=("$LOG_DIR/admin-backend.log" "$LOG_DIR/admin-frontend.log") ;;
        all)   logs+=("$LOG_DIR/user-backend.log" "$LOG_DIR/user-frontend.log"
                     "$LOG_DIR/admin-backend.log" "$LOG_DIR/admin-frontend.log") ;;
    esac
    tail -f "${logs[@]}" &
    TAIL_PID=$!

    step "等待就绪"
    local ready=1
    if [ "$TARGET" = "all" ] || [ "$TARGET" = "user" ]; then
        if wait_http "user-backend" "http://localhost:$USER_BACKEND_PORT/api/health"; then
            ok "用户端后端  http://localhost:$USER_BACKEND_PORT"
        else
            err "用户端后端启动超时，详见 $LOG_DIR/user-backend.log"; ready=0
        fi
        if wait_http "user-frontend" "http://localhost:$USER_FRONTEND_PORT/"; then
            ok "用户端前端  http://localhost:$USER_FRONTEND_PORT"
        else
            err "用户端前端启动超时，详见 $LOG_DIR/user-frontend.log"; ready=0
        fi
    fi
    if [ "$TARGET" = "all" ] || [ "$TARGET" = "admin" ]; then
        if wait_http "admin-backend" "http://localhost:$ADMIN_BACKEND_PORT/api/admin/health"; then
            ok "管理端后端  http://localhost:$ADMIN_BACKEND_PORT"
        else
            err "管理端后端启动超时，详见 $LOG_DIR/admin-backend.log"; ready=0
        fi
        if wait_http "admin-frontend" "http://localhost:$ADMIN_FRONTEND_PORT/"; then
            ok "管理端前端  http://localhost:$ADMIN_FRONTEND_PORT"
        else
            err "管理端前端启动超时，详见 $LOG_DIR/admin-frontend.log"; ready=0
        fi
    fi

    echo
    if [ "$ready" -eq 1 ]; then
        if [ "$TARGET" = "admin" ]; then
            ok "全部就绪。管理端浏览器打开 http://localhost:$ADMIN_FRONTEND_PORT （需管理员账号）"
        else
            ok "全部就绪。浏览器打开 http://localhost:$USER_FRONTEND_PORT"
            if [ "$TARGET" = "all" ]; then
                log "  管理端：http://localhost:$ADMIN_FRONTEND_PORT （需管理员账号）"
            fi
        fi
    else
        warn "部分服务未就绪，请查看上方日志与 $LOG_DIR 下的文件。"
    fi
    log "${C_DIM}按 Ctrl+C 停止全部服务。${C_RESET}"

    # 前台阻塞：任一服务子进程退出即返回，随后由 EXIT trap 统一清理其余服务。
    # 用 wait -n（bash 4.3+）而非 wait——后者要等全部子进程退出才返回，
    # 一个服务崩掉后脚本会继续傻等，用户还以为一切正常。
    # 注意：wait -n 必须放在 if 条件位，否则服务以非零码退出会触发 set -e 直接中断。
    local exited=0
    if wait -n; then exited=0; else exited=$?; fi

    # 归属到具体服务：找出哪个 PID 已经不在了
    if [ "$CLEANED" -eq 0 ]; then
        local i
        for i in "${!PIDS[@]}"; do
            if ! kill -0 "${PIDS[$i]}" 2>/dev/null; then
                err "服务已退出：${NAMES[$i]} (pid ${PIDS[$i]})，详见 $LOG_DIR/${NAMES[$i]}.log"
            fi
        done
        [ "$exited" -ne 0 ] && warn "wait 返回码 $exited"
    fi
}

preflight

# 自检通过才注册清理：避免“端口被占 / venv 缺失”这类前置失败
# 走到 EXIT trap 后，被误报成“全部服务已停止”（实际一个都没启动）。
# HUP 必须一起 trap：关终端或 SSH 断开发的是 SIGHUP，未捕获时 bash 直接死掉，
# EXIT trap 不会执行，四个服务会全部变成占着端口的孤儿进程。
trap 'on_signal' INT TERM HUP
trap cleanup EXIT

launch
