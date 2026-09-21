# she-love-me 参考与本项目取舍

参考项目：https://github.com/863401402/she-love-me

查看版本：`80aec1d6851f87bfbc1e3311d47b179aa6d5bb5a`，查看日期：2026-09-21。上游采用 MIT 许可证。本次借鉴数据格式与工作流，新增模块在本仓库独立实现，没有安装、执行上游的导出器或读取微信进程。

参考范围：`scripts/convert_weflow_cli.py`、`scripts/convert_ciphertalk.py`、`scripts/convert_markdown.py`、`scripts/message_normalizer.py`、`scripts/contact_bundle.py` 和 README。

落地改进：

- 兼容上游标准消息结构中的 `contact_display`、`local_id`、`sender`、`timestamp`、`content`、`transcript`。
- 兼容已核对的 weflow-cli / CipherTalk 常见 JSON 字段；识别 Unix 秒/毫秒/微秒/纳秒及 ISO 日期。
- 接受 `[YYYY-MM-DD HH:MM] 发送者: 内容` 的 Markdown / TXT，保留后续多行文本；未带时区时使用界面明确显示的 UTC 偏移。
- 聊天 JSON 原文/原对象随首次导入写入档案，未知媒体元信息保留在原始内容，不静默丢弃无效消息。
- 按会话生成离线备份文件夹，消息引用与附件清单相连；附件只从用户指定根目录复制，不联网下载。
- 统计基于全部选中消息，分析材料文本使用有明确覆盖说明的均匀样本。未采用上游的关系评分、心理诊断或“已读不回”推断。

边界：上游说明中的微信提取默认面向 Windows；其 macOS 路径也是导入已有文件。此项目仍没有直接读取 Mac 微信或解密数据库，不能因为导入格式兼容就声称具备提取能力。当前兼容性以虚构字段样例和测试验证，尚无真实导出文件联调；导出器的其他版本/嵌套格式需提供样例后新增适配。
