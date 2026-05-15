# Release Checklist

面向 Ubuntu 发布前，建议逐项确认：

## 必做

- [ ] `config.example.yaml` 可直接复制为 `config.yaml`
- [ ] `.env.production.example` 不包含真实密钥
- [ ] `.gitignore` 已忽略 `.env`、`data/`、日志、数据库
- [ ] `scripts/install_ubuntu.sh` 可用于初始化依赖
- [ ] `scripts/start.sh` 可启动主程序
- [ ] `scripts/check.sh` 可完成最小校验
- [ ] `DEPLOY_UBUNTU.md` 与 README 一致
- [ ] WebUI 默认仅监听 `127.0.0.1`
- [ ] `config.yaml` 中不包含真实 QQ / 管理员账号

## 建议

- [ ] 增加 LICENSE
- [ ] 增加 CHANGELOG.md
- [ ] 增加 issues / PR 模板
- [ ] 增加示例截图或 WebUI 截图
- [ ] 如准备公开仓库，轮换历史上出现过的 API Key

## 发布前自测命令

```bash
chmod +x scripts/*.sh
./scripts/check.sh
python3 -m app.main
```
