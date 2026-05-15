# QQ AI Bot

一个基于 **NapCat + OneBot11 + OpenAI 兼容接口** 的 QQ 多功能社群机器人，面向 **Ubuntu / Linux 部署** 做了整理，适合作为私有部署项目或二次开发骨架。

## 特性

- OneBot11 / NapCat WebSocket 事件接入
- AI 对话与工具调用
- 天气、IP、翻译、搜图、点歌、GitHub 等工具能力
- 提醒、积分、投票、关键词、欢迎语、群管理
- MCP 工具扩展
- WebUI 管理界面
- SQLite 默认落地，开箱即用

## 项目结构

```text
app/                # 主程序
personas/           # 人设配置
scripts/            # Ubuntu 辅助脚本
deploy/systemd/     # systemd 服务模板
data/               # 运行时数据（默认不提交）
```

## 快速开始（Ubuntu）

在项目根目录执行：

```bash
chmod +x scripts/*.sh
cp config.example.yaml config.yaml
cp .env.production.example .env
./scripts/install_ubuntu.sh
./scripts/check.sh
./scripts/start.sh
```

如果你是先把项目上传到 `/opt/qq-ai-bot`，那就在 **`/opt/qq-ai-bot` 目录内** 执行上面的命令。

也可以手动部署：

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp config.example.yaml config.yaml
cp .env.production.example .env
python3 -m app.main
```

## 关键文件

- `config.example.yaml`：公开可分发的配置示例
- `.env.production.example`：生产环境变量示例
- `DEPLOY_UBUNTU.md`：完整 Ubuntu 部署说明
- `deploy/systemd/qq-ai-bot@.service`：systemd 模板
- `RELEASE_CHECKLIST.md`：发布前自查清单

## 安全说明

这个仓库已经按公开分发做了基础去敏处理，但你仍应注意：

- 不要提交 `.env`
- 不要提交 `data/` 下的数据库、日志、消息记录
- 不要在 `config.yaml` 中保留真实 QQ 号、管理员信息或内部地址
- 如果历史上泄露过 API Key，请直接轮换

## 默认行为

- WebUI 默认监听 `127.0.0.1:7860`
- NapCat 默认连接 `ws://127.0.0.1:3001`
- 数据库默认使用 `sqlite:///data/bot.db`

## 发布建议

如果你准备公开发布或发给别人用，建议至少做到：

1. 复制 `config.example.yaml` 为 `config.yaml`
2. 复制 `.env.production.example` 为 `.env`
3. 填入你自己的 API Key
4. 部署并确认 NapCat WebSocket 可连通
5. 用 `scripts/check.sh` 做最小校验

## 许可证

当前仓库未附带 LICENSE。若要公开开源，建议你补一个明确许可证（如 MIT / Apache-2.0 / GPL-3.0）。
