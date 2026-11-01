#!/usr/bin/env bash
# 重启 Paper-Wiki Web：杀掉旧进程 →（可选）重装包、重建前端 → 不带代理环境在 0.0.0.0:8080 后台拉起
# → 日志写入 logs/paper-wiki-web.log → 打印 http://<本机IP>:<端口>
#
# 用法（在任意目录执行均可）：
#   ./deploy/no-root/redeploy-web.sh
#   SKIP_FRONTEND=1 SKIP_INSTALL=1 ./deploy/no-root/redeploy-web.sh   # 只重启
#
# 常用环境变量：
#   PAPER_WIKI_HOME   项目根目录，默认取本脚本所在仓库根
#   PAPER_WIKI_BIN    paper-wiki 可执行文件，默认 conda env paper-wiki
#   PAPER_WIKI_HOST   监听地址，默认 0.0.0.0（本机 + 局域网都能访问）
#   PAPER_WIKI_PORT   端口，默认 8080
#   PAPER_WIKI_LOG    日志文件，默认 $PAPER_WIKI_HOME/logs/paper-wiki-web.log
#   PAPER_WIKI_PID    pid 文件，默认 $PAPER_WIKI_HOME/logs/paper-wiki-web.pid
#   PAPER_WIKI_LOG_MAX_MB  启动前日志超过该大小则轮转为 .1，默认 50
#   PAPER_WIKI_KEEP_PROXY=1  服务进程保留当前 shell 的代理变量（默认清除）
#   SKIP_FRONTEND=1   跳过 npm run build
#   SKIP_INSTALL=1    跳过 pip install -e .
#
# 说明：pip / npm 安装阶段沿用当前 shell 的代理；Web 服务进程本身默认清除
# HTTP(S)_PROXY / ALL_PROXY，部署完成后即使代理挂了服务也照常可用。
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="${PAPER_WIKI_HOME:-$(cd "$SCRIPT_DIR/../.." && pwd)}"
CONDA_BIN="${HOME}/miniconda3/envs/paper-wiki/bin/paper-wiki"
PAPER_WIKI_BIN="${PAPER_WIKI_BIN:-}"
if [[ -z "$PAPER_WIKI_BIN" ]]; then
  if [[ -x "$CONDA_BIN" ]]; then
    PAPER_WIKI_BIN="$CONDA_BIN"
  elif [[ -x "$PROJECT_DIR/.venv/bin/paper-wiki" ]]; then
    PAPER_WIKI_BIN="$PROJECT_DIR/.venv/bin/paper-wiki"
  elif command -v paper-wiki >/dev/null 2>&1; then
    PAPER_WIKI_BIN="$(command -v paper-wiki)"
  else
    echo "找不到 paper-wiki 可执行文件，请设置 PAPER_WIKI_BIN" >&2
    exit 1
  fi
fi

HOST="${PAPER_WIKI_HOST:-0.0.0.0}"
PORT="${PAPER_WIKI_PORT:-8080}"
LOG_FILE="${PAPER_WIKI_LOG:-$PROJECT_DIR/logs/paper-wiki-web.log}"
PID_FILE="${PAPER_WIKI_PID:-$PROJECT_DIR/logs/paper-wiki-web.pid}"
LOG_MAX_MB="${PAPER_WIKI_LOG_MAX_MB:-50}"
KEEP_PROXY="${PAPER_WIKI_KEEP_PROXY:-0}"
SKIP_FRONTEND="${SKIP_FRONTEND:-0}"
SKIP_INSTALL="${SKIP_INSTALL:-0}"
PROXY_VARS=(HTTP_PROXY HTTPS_PROXY ALL_PROXY FTP_PROXY http_proxy https_proxy all_proxy ftp_proxy)

cd "$PROJECT_DIR"

log() {
  echo "[$(date '+%F %T')] $*"
}

local_curl() {
  curl --noproxy '*' -fsS -m 3 "$@"
}

kill_existing() {
  log "停止已有 paper-wiki web 进程..."
  pkill -f "paper-wiki web" 2>/dev/null || true
  pkill -f "uvicorn paper_wiki.web.app:app" 2>/dev/null || true

  for _ in $(seq 1 20); do
    if ! pgrep -f "paper-wiki web" >/dev/null 2>&1 \
      && ! ss -lnt 2>/dev/null | grep -q ":${PORT} "; then
      break
    fi
    sleep 0.5
  done

  if pgrep -f "paper-wiki web" >/dev/null 2>&1; then
    log "仍有残留进程，发送 SIGKILL..."
    pkill -9 -f "paper-wiki web" 2>/dev/null || true
    sleep 1
  fi

  if ss -lnt 2>/dev/null | grep -q ":${PORT} "; then
    log "警告：端口 ${PORT} 仍被占用，请手动检查："
    ss -lntp 2>/dev/null | grep ":${PORT} " || true
    exit 1
  fi

  rm -f "$PID_FILE"
  log "旧进程已清理"
}

rebuild_frontend() {
  if [[ "$SKIP_FRONTEND" == "1" ]]; then
    log "跳过前端构建（SKIP_FRONTEND=1）"
    return
  fi
  if [[ ! -d "$PROJECT_DIR/web/frontend" ]]; then
    log "未找到 web/frontend，跳过前端构建"
    return
  fi
  log "构建前端..."
  (
    cd "$PROJECT_DIR/web/frontend"
    if [[ -f package-lock.json ]]; then
      npm ci
    else
      npm install
    fi
    npm run build
  )
  log "前端构建完成 → web/frontend/dist/"
}

reinstall_package() {
  if [[ "$SKIP_INSTALL" == "1" ]]; then
    log "跳过 pip install -e .（SKIP_INSTALL=1）"
    return
  fi
  local python_bin
  python_bin="$(dirname "$PAPER_WIKI_BIN")/python"
  if [[ ! -x "$python_bin" ]]; then
    python_bin="python3"
  fi
  log "刷新本地包安装：$python_bin -m pip install -e ."
  "$python_bin" -m pip install --no-build-isolation -e "$PROJECT_DIR" >/tmp/paper-wiki-redeploy-pip.log 2>&1 \
    || {
      log "pip install 失败，详见 /tmp/paper-wiki-redeploy-pip.log"
      tail -n 40 /tmp/paper-wiki-redeploy-pip.log >&2 || true
      exit 1
    }
}

rotate_log() {
  mkdir -p "$(dirname "$LOG_FILE")" "$(dirname "$PID_FILE")"
  if [[ -f "$LOG_FILE" ]]; then
    local size_mb=$(( $(stat -c %s "$LOG_FILE") / 1024 / 1024 ))
    if (( size_mb >= LOG_MAX_MB )); then
      mv -f "$LOG_FILE" "$LOG_FILE.1"
      log "日志超过 ${LOG_MAX_MB}MB，已轮转为 $LOG_FILE.1"
    fi
  fi
}

lan_ip() {
  local ip
  ip="$(ip -4 route get 1.1.1.1 2>/dev/null | awk '{for (i = 1; i < NF; i++) if ($i == "src") {print $(i + 1); exit}}')"
  if [[ -z "$ip" ]]; then
    ip="$(hostname -I 2>/dev/null | awk '{print $1}')"
  fi
  echo "${ip:-<本机IP>}"
}

start_server() {
  rotate_log
  log "启动 paper-wiki web on ${HOST}:${PORT}"
  echo "[$(date '+%F %T')] redeploy starting paper-wiki web on ${HOST}:${PORT}" >> "$LOG_FILE"

  local -a launch_env=(env)
  if [[ "$KEEP_PROXY" != "1" ]]; then
    for var in "${PROXY_VARS[@]}"; do
      launch_env+=(-u "$var")
    done
    log "服务进程已清除代理环境变量（PAPER_WIKI_KEEP_PROXY=1 可保留）"
  fi

  # setsid + nohup：脱离当前终端会话，SSH 断开后服务继续运行。
  setsid nohup "${launch_env[@]}" "$PAPER_WIKI_BIN" web --host "$HOST" --port "$PORT" \
    >> "$LOG_FILE" 2>&1 < /dev/null &
  local pid=$!
  echo "$pid" > "$PID_FILE"
  log "已后台启动 pid=$pid，日志 → $LOG_FILE"

  for _ in $(seq 1 30); do
    if local_curl "http://127.0.0.1:${PORT}/api/health" >/dev/null 2>&1; then
      log "健康检查通过：http://127.0.0.1:${PORT}/api/health"
      return 0
    fi
    if ! kill -0 "$pid" 2>/dev/null; then
      log "进程已退出，请查看日志尾部："
      tail -n 40 "$LOG_FILE" >&2 || true
      exit 1
    fi
    sleep 0.5
  done

  log "启动超时，进程仍在跑但健康检查未通过。最近日志："
  tail -n 40 "$LOG_FILE" >&2 || true
  exit 1
}

log "项目目录：$PROJECT_DIR"
log "可执行文件：$PAPER_WIKI_BIN"
kill_existing
reinstall_package
rebuild_frontend
start_server
if [[ "$HOST" == "0.0.0.0" ]]; then
  log "部署完成，访问地址：http://$(lan_ip):${PORT}"
else
  log "部署完成，访问地址：http://${HOST}:${PORT}"
fi
log "查看日志：tail -f $LOG_FILE"
