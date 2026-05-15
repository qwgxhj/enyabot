# QQ AI Bot - Ubuntu 部署指南

这份文档是面向 **Ubuntu / Debian 系 Linux** 的部署说明，并且已经去除了作者本机路径、真实密钥示例和个人账号信息。

## 1. 系统要求

- Ubuntu 22.04+（推荐）
- Python 3.11+
- git
- NapCat（QQ 协议端，需你自行按 Linux 版方式部署）
- 可选：Node.js / npm（当你要启用某些基于 `npx` 的 MCP 服务时）

## 2. 安装基础环境

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip git curl
```

如果你需要 `npx` 来运行 MCP 服务：

```bash
sudo apt install -y nodejs npm
```

## 3. 获取项目

### 方式一：git clone

```bash
cd /opt
sudo mkdir -p qq-ai-bot
sudo chown "$USER":"$USER" qq-ai-bot
git clone <你的仓库地址> /opt/qq-ai-bot
```

### 方式二：从本地机器上传

在**你的本地终端**执行，把整个项目目录传到 Ubuntu：

```bash
scp -r /path/to/enyabot/* user@your-ubuntu-host:/opt/qq-ai-bot/
```

> 不要再使用 Windows 本机绝对路径写死在文档里；按你自己的实际路径替换 `/path/to/enyabot/` 即可。

## 4. 创建虚拟环境并安装依赖

```bash
cd /opt/qq-ai-bot
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

## 5. 配置环境变量

```bash
cp .env.production.example .env
nano .env
```

建议内容：

```env
APP_NAME=qq-ai-bot
APP_ENV=prod
APP_DEBUG=false
DATABASE_URL=sqlite:///data/bot.db

OPENAI_API_KEY=
OPENAI_BASE_URL=https://api.openai.com/v1
DEFAULT_MODEL=gpt-4o-mini

SAUCENAO_API_KEY=
NETEASE_API_BASE=https://api.injahow.cn/meting/
GITHUB_TOKEN=
```

说明：

- `OPENAI_API_KEY`：填你自己的接口密钥
- `OPENAI_BASE_URL`：如果你用的是第三方 OpenAI 兼容平台，改成对应地址
- `.env` **不要提交进 git**

## 6. 配置主文件 `config.yaml`

```bash
cp config.example.yaml config.yaml
nano config.yaml
```

建议从当前仓库里已经去敏后的默认值出发，重点确认这些字段：

```yaml
bot:
  master_qq: ''
  master2_qq: []

webui:
  host: "127.0.0.1"
  port: 7860

napcat:
  ws_url: ws://127.0.0.1:3001
  reconnect_interval: 5
  heartbeat_interval: 30
```

建议：

- `master_qq` 留空后，首次可通过机器人命令再绑定
- `webui.host` 默认保持 `127.0.0.1`，更安全
- 若你要远程访问 WebUI，优先使用 **Nginx/Caddy 反向代理 + 认证**，不要直接裸露到公网

## 7. 部署 NapCat（Linux）

NapCat 不属于这个项目本身，但机器人依赖它提供 OneBot11 WebSocket。

请按 NapCat 官方 Linux 文档部署，目标是让它最终提供一个类似下面的地址：

```text
ws://127.0.0.1:3001
```

项目当前默认就是连接这个本地地址。

## 8. 启动项目

```bash
cd /opt/qq-ai-bot
source .venv/bin/activate
python3 -m app.main
```

如果只想单独启动 WebUI：

```bash
python3 -m app.webui
```

默认 WebUI：

```text
http://127.0.0.1:7860
```

## 9. 配置 systemd 后台运行

创建服务文件：

```bash
sudo nano /etc/systemd/system/qq-ai-bot.service
```

内容示例：

```ini
[Unit]
Description=QQ AI Bot
After=network.target

[Service]
Type=simple
User=<你的Linux用户名>
WorkingDirectory=/opt/qq-ai-bot
ExecStart=/opt/qq-ai-bot/.venv/bin/python -m app.main
Restart=always
RestartSec=10
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
```

启用并启动：

```bash
sudo systemctl daemon-reload
sudo systemctl enable qq-ai-bot
sudo systemctl start qq-ai-bot
sudo systemctl status qq-ai-bot
```

查看日志：

```bash
sudo journalctl -u qq-ai-bot -f
```

## 10. 防火墙建议

如果只是本机使用：

- 不需要开放 `7860`
- 不需要开放 `3001`

如果你确实要外部访问 WebUI：

```bash
sudo ufw allow 7860/tcp
```

但更推荐：

- WebUI 继续监听 `127.0.0.1`
- 用 Nginx / Caddy 做 HTTPS 反向代理
- 加上基础认证或统一登录保护

## 11. 常见排查

### NapCat 连不上

```bash
ss -tlnp | grep 3001
```

确认 `config.yaml` 里的 `napcat.ws_url` 和 NapCat 实际监听地址一致。

### WebUI 无法访问

```bash
ss -tlnp | grep 7860
```

如果你把 `webui.host` 设成了 `127.0.0.1`，那就只能本机访问或通过反代访问。

### AI 接口报错

先检查 `.env` 是否真的填了：

- `OPENAI_API_KEY`
- `OPENAI_BASE_URL`
- `DEFAULT_MODEL`

也可以手动测一下你自己的接口：

```bash
curl -H "Authorization: Bearer <你的API_KEY>" <你的OPENAI_BASE_URL>/models
```

## 12. 仓库清理建议

如果你准备把这个项目公开或发给别人，建议额外确认：

- `.env` 没有真实密钥
- `config.yaml` 没有真实 QQ / 主人账号
- `data/` 目录不要提交
- 日志、数据库、消息记录不要提交
- 如历史提交里出现过真实密钥，请**轮换密钥**，不要只删文件
