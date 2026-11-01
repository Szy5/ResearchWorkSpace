# Paper-Wiki 部署文档

本文档描述把 Paper-Wiki 部署到一台你自己控制的 Linux 服务器（云 VPS 或家庭服务器均可）的最简单方式：**不使用 Docker**，后端用 systemd 常驻，前端构建成静态文件后交给 nginx 托管并反代 `/api`。适合单人自用场景。

## 部署架构

```
浏览器
  │  http(s)://<你的域名或IP>/
  ▼
nginx (80/443)
  ├── /            → 静态文件 web/frontend/dist/（npm run build 产物）
  └── /api/*       → 反代到 127.0.0.1:8000
                          │
                          ▼
                 uvicorn（systemd 常驻，仅监听 127.0.0.1，不直接暴露公网）
                          │
                          ▼
        本地文件：KnowledgeBase/{raw,artifacts,graph_state,graph_updates}/ .env
        （可选）Neo4j 图谱实例
```

前端所有请求都走相对路径 `/api/...`，和页面同源，所以生产环境不需要处理跨域（CORS）问题，nginx 把两者放在同一个 origin 下即可。

> **没有 sudo/root 权限？** 下面 1-4 步（拉代码、装依赖、配 `.env`、建前端）照做，从「5. 用 systemd 常驻后端」开始跳到文末「附录：没有管理员权限时怎么部署」一节。

## 前置条件

- 一台 Linux 服务器（本文以 Ubuntu/Debian 为例，其他发行版把包管理器命令换掉即可），有 sudo 权限。
- Python **3.11+**
- Node.js **20+**（前端用 Vite 8，太旧的 Node 构建不了）
- nginx
- git
- 一个可用的 OpenAI 兼容 LLM API（`MODEL_NAME` / `BASE_URL` / `API_KEY`）
- 可选：域名（不用域名的话直接用服务器公网 IP 访问，跳过 HTTPS 那一步）

```bash
sudo apt update
sudo apt install -y python3.11 python3.11-venv nginx git
# Node：推荐用 nvm 装，避免发行版自带版本太旧
curl -fsSL https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.1/install.sh | bash
source ~/.bashrc
nvm install 20
```



## 1. 拉取代码

```bash
sudo mkdir -p /opt/paper-wiki
sudo chown $USER:$USER /opt/paper-wiki
git clone https://github.com/Szy5/ResearchWorkSpace.git /opt/paper-wiki
cd /opt/paper-wiki
```

后面所有路径都以 `/opt/paper-wiki` 为例，换成别的路径记得同步改 `deploy/` 下两个模板文件里的路径。

## 2. Python 环境与依赖

```bash
cd /opt/paper-wiki
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install --no-build-isolation -e .
```

装完后 `.venv/bin/paper-wiki` 应该可以直接跑：

```bash
.venv/bin/paper-wiki --help
```



## 3. 配置 `.env`

```bash
cp .env.example .env
chmod 600 .env
```

编辑 `.env`，至少填好 LLM 相关三项；Neo4j / 微信发布 / Zotero 推荐是可选功能，用不到就不填：

```bash
MODEL_NAME=your-model-name
BASE_URL=https://your-api-base-url/v1
API_KEY=your-api-key
```

`.env` 含密钥，`chmod 600` 之后只有部署用户自己能读，也不要打包进任何日志或截图。

## 4. 构建前端

```bash
cd /opt/paper-wiki/web/frontend
npm ci
npm run build
```

产物在 `web/frontend/dist/`，是纯静态文件，之后交给 nginx 直接托管，不需要跑 `npm run dev`。以后代码更新了，重新跑一次 `npm ci && npm run build` 即可。

## 5. 用 systemd 常驻后端

仓库里已经准备好模板 [deploy/systemd/paper-wiki-web.service](deploy/systemd/paper-wiki-web.service)。按你的实际用户和路径改一下：

```bash
sudo cp deploy/systemd/paper-wiki-web.service /etc/systemd/system/paper-wiki-web.service
sudo vim /etc/systemd/system/paper-wiki-web.service
```

需要确认/修改的几行：

- `User=` / `Group=`：跑这个服务的系统用户（不建议用 root，用你当前登录用户或专门建一个即可）。
- `WorkingDirectory=`：项目根目录，例如 `/opt/paper-wiki`。
- `ExecStart=`：venv 里 `paper-wiki` 可执行文件的绝对路径，例如 `/opt/paper-wiki/.venv/bin/paper-wiki web --host 127.0.0.1 --port 8000`。
- `ReadWritePaths=`：程序需要写入的几个目录，路径要和 `WorkingDirectory` 保持一致。

改完启动：

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now paper-wiki-web
sudo systemctl status paper-wiki-web
```

确认后端本地可访问：

```bash
curl http://127.0.0.1:8000/api/health
# {"status":"ok"}
```

看日志：

```bash
journalctl -u paper-wiki-web -f
```



## 6. 用 nginx 托管前端并反代 API

模板在 [deploy/nginx/paper-wiki.conf](deploy/nginx/paper-wiki.conf)：

```bash
sudo cp deploy/nginx/paper-wiki.conf /etc/nginx/sites-available/paper-wiki
sudo vim /etc/nginx/sites-available/paper-wiki
```

改两处：

- `server_name`：你的域名，没有域名就填服务器公网 IP。
- `root`：前端构建产物路径，例如 `/opt/paper-wiki/web/frontend/dist`。

启用并重载：

```bash
sudo ln -s /etc/nginx/sites-available/paper-wiki /etc/nginx/sites-enabled/paper-wiki
sudo nginx -t
sudo systemctl reload nginx
```

浏览器打开 `http://<域名或IP>/`，应该能看到 Paper-Wiki 首页；随手点一下"检索/添加"验证 `/api` 请求能通。

## 7. 可选：HTTPS（有域名才需要）

只有 IP、没有域名可以跳过这一步（浏览器地址栏用 `http://IP` 即可）。有域名且已经把 A 记录指向服务器：

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain
```

certbot 会自动改写 nginx 配置加上 443 监听和证书路径，并配好自动续期。

## 8. 防火墙

后端 uvicorn 只监听 `127.0.0.1`，本来就不会被公网直接访问，只需要放行 nginx 用到的端口：

```bash
sudo ufw allow OpenSSH
sudo ufw allow 'Nginx Full'   # 80 + 443
sudo ufw enable
sudo ufw status
```



## 更新部署

以后改了代码想更新到服务器：

```bash
cd /opt/paper-wiki
git pull

# 后端依赖变了才需要
source .venv/bin/activate && pip install -r requirements.txt

# 前端有改动才需要
cd web/frontend && npm ci && npm run build

# 重启后端
sudo systemctl restart paper-wiki-web
```

nginx 配置没变的话不用碰；`systemctl restart` 期间接口会有几秒不可用，个人使用影响不大。

## 数据与备份

以下目录是有状态数据（见 `.gitignore`），服务器上要自己备份：

- `KnowledgeBase/raw/`：论文 LaTeX 源码
- `KnowledgeBase/artifacts/`：解析和生成的产物、审查状态、`.jobs` / `.recommendations` / `.publishing`
- `KnowledgeBase/graph_state/` / `KnowledgeBase/graph_updates/`：Layer 2 图谱快照和增量事件
- `.env`：密钥配置

个人用推荐定期 `tar` 打包后同步到别的地方（网盘、对象存储、另一台机器），例如加一条 cron：

```bash
0 3 * * * tar -czf /home/$USER/backups/paper-wiki-$(date +\%F).tar.gz -C /opt/paper-wiki KnowledgeBase .env
```



## 常见问题

**浏览器打开是空白页 / 404**
多半是没跑 `npm run build`，或者 nginx 配置里 `root` 路径写错了，检查 `web/frontend/dist/index.html` 是否存在。

**页面能打开，但点操作都报错，Network 里** `/api/xxx` **是 502**
后端没起来或者端口不对。先 `curl http://127.0.0.1:8000/api/health` 确认 uvicorn 活着，再 `journalctl -u paper-wiki-web -e` 看报错。

`/api` **请求返回 404 而不是转发到后端**
检查 nginx 配置里 `location /api/` 这段是否被写在了 `location /` 前面被吞掉，或者反代块的 `proxy_pass` 地址/端口有没有改错。

**跨域（CORS）报错**
正常部署方式下前端和 API 是同源的，不应该出现 CORS 报错；如果出现了，说明前端没有走 nginx 反代（比如你直接用 `http://IP:8000` 打开了前端，或者前端和 nginx 分别部署在了不同端口/域名），检查访问路径和 nginx 配置。

**想用 Neo4j 图谱功能（Layer 2）**
本文档只覆盖 Web 原型的部署，图谱功能需要额外一个 Neo4j 实例（自建或 Neo4j Aura 云服务），装好后在 `.env` 填 `NEO4J_URI` / `NEO4J_USERNAME` / `NEO4J_PASSWORD` / `NEO4J_DATABASE` 即可，其余用法见 [README.md](README.md) 里图谱相关章节。

## 附录：没有管理员权限（无 root/sudo）时怎么部署

如果你在服务器上只有普通用户权限，思路不变，但要绕开三个需要 root 的地方：装系统包、写 systemd 系统级 unit、监听 80/443 端口。跟前面比主要变化：

- **不用 nginx**：后端进程自己把前端静态文件一起提供。`create_app()`（[app.py](src/paper_wiki/web/app.py)）里已经内置了这个逻辑——`web/frontend/dist` 存在就会被挂载到 `/`，跟 `/api/*` 走同一个进程、同一个端口，不用额外配置。
- Python / Node 用 conda 和 nvm 装，都装在 `$HOME` 下，不需要 root。
- 端口只能用 1024 以上的（比如 8080），不能占用 80/443。
- 进程常驻优先用 `systemctl --user`；不具备条件就退化成自重启 shell 循环 + `crontab` 开机拉起。

### 1. 拉代码、装依赖、配置 .env、建前端

跟前面 [1](#1-拉取代码)-[4](#4-构建前端) 步一样，Python 环境换成 conda（本项目 README 本来就推荐这种方式）：

```bash
# 没装过 conda 就先装一个（装到 $HOME，不需要 root）
curl -fsSL https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-Linux-x86_64.sh -o /tmp/miniforge.sh
bash /tmp/miniforge.sh -b -p "$HOME/miniforge3"
source "$HOME/miniforge3/etc/profile.d/conda.sh"

conda create -n paper-wiki -c conda-forge python=3.11 -y
conda activate paper-wiki

cd ~/paper-wiki   # 换成你 git clone 的实际路径
pip install -r requirements.txt
pip install --no-build-isolation -e .
```

Node 继续用前面提到的 nvm（本来就不需要 root）。`.env` 配置和 `npm run build` 步骤完全不变。前端 build 完之后，`web/frontend/dist` 一存在，后端启动时就会自动挂载它，**不需要装 nginx**。

### 2. 常驻进程

**优先方式：`systemctl --user`**（大部分现代发行版默认支持，不需要 root）：

```bash
mkdir -p ~/.config/systemd/user
cp deploy/systemd/paper-wiki-web.user.service ~/.config/systemd/user/paper-wiki-web.service
vim ~/.config/systemd/user/paper-wiki-web.service   # 改 WorkingDirectory / ExecStart 里的实际路径

systemctl --user daemon-reload
systemctl --user enable --now paper-wiki-web
systemctl --user status paper-wiki-web
journalctl --user -u paper-wiki-web -f
```

有个坑：默认情况下 SSH 一断开，你的用户级 systemd 实例会被回收，服务跟着停。想让它在你不登录时也常驻，需要开启 "linger"：

```bash
loginctl enable-linger $USER
```

**这一条本身需要 root**（要 `sudo` 或者请管理员在你的账号上开一次）。这是一次性的最小请求，跟要一个完整的 sudo 账号不是一回事，可以先试试请求这一条；实在申请不到，用下面的兜底方案。

**兜底方式：`redeploy-web.sh` + cron 开机拉起**（完全不需要任何权限）：

```bash
cd ~/paper-wiki
./deploy/no-root/redeploy-web.sh
```

脚本用 `setsid nohup` 后台启动，SSH 断开后服务继续运行；默认清除 `HTTP(S)_PROXY` / `ALL_PROXY` 再启动服务进程，部署好之后不依赖本机代理（安装依赖、构建前端阶段仍沿用当前 shell 的代理）。

加一条 crontab，服务器重启后自动拉起：

```bash
crontab -e
# 加一行（路径换成你的实际路径；cron 不会自动 source conda，PAPER_WIKI_BIN 必须写死绝对路径）：
@reboot SKIP_FRONTEND=1 SKIP_INSTALL=1 PAPER_WIKI_BIN=/home/youruser/miniconda3/envs/paper-wiki/bin/paper-wiki /home/youruser/paper-wiki/deploy/no-root/redeploy-web.sh >> /home/youruser/paper-wiki/logs/cron.log 2>&1
```

日志在 `$PAPER_WIKI_HOME/logs/paper-wiki-web.log`（`PAPER_WIKI_LOG` 可改），每次部署时超过 50MB 会轮转为 `.1`。停止服务：`pkill -f "paper-wiki web"`。

### 3. 怎么访问

**推荐：SSH 端口转发**，不用对公网暴露任何端口，最省心也最安全：

```bash
ssh -L 8080:127.0.0.1:8080 youruser@your-server
```

本地浏览器打开 `http://127.0.0.1:8080` 即可。两个 unit/脚本模板默认都监听 `127.0.0.1:8080`，配这个方式刚好。

**如果想不经过 SSH、直接用浏览器打开 `http://服务器IP:8080`**：`redeploy-web.sh` 默认就监听 `0.0.0.0`（1024 以上端口不需要 root 就能监听在任意网卡），部署完成时会打印该地址。但这台机器现有的防火墙是否放行这个端口不由你决定（改防火墙规则通常也要 root），连不通就只能找管理员开个口子，或者退回 SSH 转发方案。

**如果想要正经域名 + HTTPS**：纯无 root 环境做不到——标准的 `certbot --nginx` 需要写 `/etc`，监听 443 也需要 root。唯一体面的办法是请有权限的人帮你加**一条**反代规则，把域名转发到你这个用户进程监听的 `127.0.0.1:8080`，这是一次性的最小请求，不等于把服务器管理权交给你。

### 4. 更新部署

跟前面的更新流程一样（`git pull` → 依赖变了重装 → 前端有改动重新 `npm run build`），重启方式换成：

```bash
systemctl --user restart paper-wiki-web
# 或者兜底方案下：
./deploy/no-root/redeploy-web.sh
```

**一键重启（推荐）**：仓库提供了 `deploy/no-root/redeploy-web.sh`，会杀掉旧的 `paper-wiki web`，重装包、重建前端（这两步沿用当前 shell 的代理），再用 `setsid nohup` 在 `0.0.0.0:8080` 后台拉起服务，最后打印 `http://<本机IP>:8080`：

- 服务进程会清除 `HTTP(S)_PROXY` / `ALL_PROXY` 等代理变量，部署完成后不依赖本机代理。若本机访问 arXiv / LLM API（如 `api.key77qiqi.com`）必须走代理，部署时设 `PAPER_WIKI_KEEP_PROXY=1`；也可在 `.env` 单独设 `LLM_HTTP_PROXY=...` 只给 LLM 走代理。
- 日志追加写入 `logs/paper-wiki-web.log`，启动前超过 50MB（`PAPER_WIKI_LOG_MAX_MB`）会轮转为 `.1`；pid 写入 `logs/paper-wiki-web.pid`。`logs/` 已加入 `.gitignore`。
- SSH 断开后服务继续运行。

```bash
cd ~/projects/Paper-wiki   # 换成你的实际路径
./deploy/no-root/redeploy-web.sh

# 只要重启、不重建前端：
SKIP_FRONTEND=1 SKIP_INSTALL=1 ./deploy/no-root/redeploy-web.sh

# 查看日志
tail -f logs/paper-wiki-web.log
```