# 贡献指南

MiLuAssistantWeb 是基于 CoPaw / QwenPaw 项目体系二次开发的 Web 版 AI 助手，主要作为 MiLu 助手项目的 Web 基座和个人项目展示仓库维护。

## 提交前检查

- 不提交运行数据、用户工作区、Provider 密钥、私有 Skills、本地模型文件或真实渠道凭据。
- 不提交 `.secret/`、本地 `.env` 实例值、Token、Cookie、私钥或未脱敏日志。
- 文档改动请同时考虑 `README.md` 与 `README.en.md` 的中英文一致性。
- 代码改动请说明影响范围，并尽量附上本地验证命令或截图。

## PR 建议

如果需要对比上游项目，建议重点查看 MiLu 命名空间改造、控制台品牌替换、本地模型 / Provider 默认配置、运行目录隔离以及公开发布前的数据清理。

PR 标题建议使用简短动词开头，例如 `docs: ...`、`fix: ...`、`feat: ...`。如需反馈问题或建议，也可以直接在本仓库提交 GitHub Issue。
