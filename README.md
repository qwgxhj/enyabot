# EnyaBot

一个基于 **NapCat + OneBot11 + OpenAI 兼容接口** 的 QQ 多功能社群机器人，支持 AI 对话、群管理、工具调用、MCP 扩展等功能。

## 功能特性

### AI 对话
- 支持 OpenAI 兼容接口的 AI 对话（GPT-4、Claude 等）
- 多角色人设切换（默认内置 Alicia、Gentle Assistant、Strict Admin）
- 上下文记忆与长期记忆管理
- AI 工具调用能力

### 群管理工具
- **群管理**：踢人、禁言
- **入群欢迎**：自定义欢迎语、入群验证问题
- **积分系统**：签到、查询积分
- **投票系统**：创建投票、参与投票、查看结果
- **定时消息**：支持 cron 表达式定时发送
- **日程管理**：添加/查看/删除日程事件

### 插件功能
- **天气查询**：查询城市天气
- **翻译服务**：支持中英日韩法德西俄等多语言互译
- **以图搜图**：识别动漫截图、插画（SauceNAO）
- **音乐点歌**：搜索音乐、获取播放链接
- **表情包生成**：文字表情包生成
- **GitHub 集成**：查询仓库信息、Release 动态
- **IP 归属地查询**
- **姓名重名查询**
- **KFC 疯狂星期四文案**
- **随机超能力文案**
- **媒体链接解析**

### 关键词系统
- **基础关键词**：简单关键词回复
- **增强关键词**：支持正则表达式、随机回复、冷却时间

### 其他功能
- **提醒服务**：定时提醒任务
- **长期记忆**：记录/检索重要信息
- **群聊总结**：AI 总结聊天记录
- **小游戏**：猜词游戏、问答游戏
- **语录系统**：添加/搜索/随机语录
- **倒计时**：创建/查看倒计时
- **MCP 工具扩展**：支持 Model Context Protocol

### WebUI 管理界面
- 可视化配置管理
- 数据查询与监控

## 项目结构

```text
app/                    # 主程序
├── adapters/           # NapCat 适配器
├── ai/                 # AI 客户端、提示词、记忆管理
├── config/             # 配置管理
├── core/               # 核心路由、权限、审计
├── db/                 # 数据库会话
├── models/             # 数据模型
├── plugins/            # 插件系统
│   ├── api/            # API 类插件
│   ├── direct/         # 直接功能插件
│   └── mcp/            # MCP 桥接
├── schemas/            # 数据验证
├── services/           # 业务服务
├── tools/              # 工具注册
└── webui/              # WebUI 管理界面
personas/               # 人设配置文件
scripts/                # 部署脚本
deploy/systemd/         # systemd 服务模板
data/                   # 运行时数据（不提交）
```

## 快速开始

### 环境要求
- Python 3.10+
- NapCat（OneBot11 协议实现）

### 1. 克隆项目

```bash
git clone https://github.com/qwgxhj/enyabot.git
cd enyabot
```

### 2. 安装依赖

```bash
python3 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 3. 配置

复制并编辑配置文件：

```bash
cp config.example.yaml config.yaml
cp .env.example .env
```

**编辑 `.env` 文件：**

```ini
APP_NAME=qq-ai-bot
APP_ENV=dev
APP_DEBUG=true
DATABASE_URL=sqlite:///data/bot.db
OPENAI_API_KEY=your-api-key-here
OPENAI_BASE_URL=https://api.openai.com/v1
DEFAULT_MODEL=gpt-4o-mini

# 翻译（可选）
DEEPL_AUTH_KEY=
BAIDU_TRANSLATE_APP_ID=
BAIDU_TRANSLATE_SECRET=

# 搜图（可选）
SAUCENAO_API_KEY=

# 音乐（可选）
NETEASE_API_BASE=https://api.injahow.cn/meting/

# GitHub（可选）
GITHUB_TOKEN=
```

**编辑 `config.yaml` 文件：**

```yaml
app:
  name: qq-ai-bot
  env: prod

bot:
  master_qq: '你的QQ号'
  master2_qq: []

webui:
  host: "127.0.0.1"
  port: 7860

napcat:
  ws_url: ws://127.0.0.1:3001
  reconnect_interval: 5
  heartbeat_interval: 30

ai:
  default_provider: main
  default_persona: alicia
  max_context_rounds: 12
  memory_enabled: true
  tool_call_enabled: true
  trigger_prefixes:
    - 阿玉
    - ayu
    - /ai

rate_limit:
  user_ai_per_minute: 6
  group_ai_per_minute: 20

features:
  weather: true
  reminder: true
  moderation: true
  score: true
  ai: true

mcp:
  enabled: false
  servers: []
```

### 4. 启动机器人

```bash
python -m app.main
```

### 5. 配置 NapCat

在 NapCat 中添加反向 WebSocket 连接：

```
ws://127.0.0.1:3001
```

## Ubuntu 一键部署

```bash
chmod +x scripts/*.sh
./scripts/install_ubuntu.sh
./scripts/check.sh
./scripts/start.sh
```

## systemd 服务部署

```bash
sudo cp deploy/systemd/qq-ai-bot@.service /etc/systemd/system/
sudo systemctl enable qq-ai-bot@your-user
sudo systemctl start qq-ai-bot@your-user
```

## 使用说明

### AI 对话

- **触发方式**：发送 `阿玉 你好`、`ayu 你好` 或 `/ai 你好`
- **切换人设**：使用 `list_personas`、`switch_persona` 工具
- **记忆管理**：使用 `remember_fact` 记录信息，`recall_memory` 检索信息

### 群管理

需要管理员权限的功能：
- 踢人：`mute_member`、`kick_member`
- 关键词管理：`add_keyword`、`add_keyword_rule`
- 定时消息：`create_scheduled_message`
- 欢迎语设置：`set_welcome`、`set_verify_question`

### 常用命令示例

```
# 天气查询
天气 北京

# 翻译
翻译 Hello World

# 音乐点歌
点歌 周杰伦 晴天

# 以图搜图
搜图 [图片]

# GitHub 查询
github qwgxhj enyabot

# 签到
签到

# 积分查询
积分

# 创建投票
投票 今天吃什么 | 火锅 | 烧烤 | 日料

# 设置欢迎语
欢迎语 欢迎 {nickname} 加入 {group_name}！

# 创建提醒
提醒 10 分钟后开会

# 添加日程
日程 明天 14:00 项目会议 会议室A
```

### WebUI 管理

访问 `http://127.0.0.1:7860` 打开 WebUI 管理界面。

## 配置说明

### 环境变量（.env）

| 变量 | 说明 | 默认值 |
|------|------|--------|
| OPENAI_API_KEY | AI 服务 API Key | 必填 |
| OPENAI_BASE_URL | AI 服务地址 | https://api.openai.com/v1 |
| DEFAULT_MODEL | 默认模型 | gpt-4o-mini |
| SAUCENAO_API_KEY | SauceNAO 搜图 Key | 可选 |
| GITHUB_TOKEN | GitHub API Token | 可选 |

### 配置文件（config.yaml）

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| bot.master_qq | 管理员 QQ 号 | 空 |
| webui.host/port | WebUI 监听地址 | 127.0.0.1:7860 |
| napcat.ws_url | NapCat WebSocket 地址 | ws://127.0.0.1:3001 |
| ai.trigger_prefixes | AI 触发前缀 | 阿玉, ayu, /ai |
| ai.max_context_rounds | 最大上下文轮数 | 12 |
| rate_limit.* | 频率限制 | 用户 6次/分，群 20次/分 |

## 安全说明

- **不要提交 `.env` 文件**（包含 API Key）
- **不要提交 `data/` 目录**（包含数据库、日志）
- **不要提交 `config.yaml`**（包含个人 QQ 号）
- 如果 API Key 泄露，请立即轮换

## 许可证

MIT
