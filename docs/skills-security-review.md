# GitHub 分析 skills 安全审查

核对日期：2026-09-21。仅静态阅读公开仓库，不安装、不执行第三方代码，不向候选项目发送聊天或密钥。以下结论仅覆盖所列版本及文件，不是安全认证；未来更新必须重新核对。Skill 是给代理的指令，不是天然隔离的安全插件；即使没有脚本，也可能诱导代理读取或上传资料。

## 1. chat-relationship-analysis：低执行风险，分析结论需谨慎

来源：[Puss-M/chat-relationship-analysis](https://github.com/Puss-M/chat-relationship-analysis/tree/2c0699d33e188fa82b72dbf28ce605e93b4bd11a)。固定提交 `2c0699d33e188fa82b72dbf28ce605e93b4bd11a`。

已查看递归文件树，并完整阅读全部 3 个文件：`SKILL.md`、`agents/openai.yaml`、`references/framework.md`。此版本没有可执行脚本、安装钩子、依赖清单、网络接口、上传地址或删除命令。指令强调原文证据、反证和不作诊断，未发现索取 API Key、读取系统凭据或绕过约束的指令。

适合单个联系人的沟通分析。不建议照搬固定关系标签、0–5 评分：这些不是校准过的心理测量，可能制造确定感。原目录没有发现许可证文件，因此不复制分发其正文；本应用自行编写更保守的「沟通模式」提示词，不判定对方内心或爱意概率。分析仍在所选模型上进行，所谓纯文本 skill 不代表数据一定留在本机。

## 2. chat-export-report：适合话题目录，需修正身份假设

来源：[Innei/SKILL 的 chat-export-report](https://github.com/Innei/SKILL/blob/8036216a9da656281edd0437aa4e07bc911adb96/skills/research/chat-export-report/SKILL.md)。固定提交 `8036216a9da656281edd0437aa4e07bc911adb96`。

已查看递归树并完整阅读该 skill 唯一正文 `skills/research/chat-export-report/SKILL.md`；未审计整个多 skill 仓库。该目录无配套执行脚本。正文涉及 `wc`、`grep`、`find/ls` 和按范围读取文件，未发现下载执行、密钥读取或指定外传地址。文件名仍须当数据处理，不能直接拼接 shell 命令。

适合分层主题报告和带日期的证据引用。重要缺陷：正文把特定姓名前缀固定认作用户，并把一些关系信号作较强解释；直接套用会误认发言者。大档案抽样还可能遗漏关键上下文。仅借鉴证据可追溯和分层目录的思路，不照搬角色规则，不复制代码或提示词。本应用按结构化 sender 字段处理，并明确当前筛选范围。

## 3. wetrace-skill：暂不安装 / 接入

来源：[afumu/wetrace-skill](https://github.com/afumu/wetrace-skill/tree/6280e9c106a2549340bf750ccae71f4053ed4710)。固定提交 `6280e9c106a2549340bf750ccae71f4053ed4710`。

范围：文件树、入口和 Python 客户端关键网络/写盘/删除路径初筛；未完整审计全部 references，也未审计其依赖的 Wetrace 服务或二进制，不能视为通过审查。

具体发现（`scripts/wetrace_api.py`）：

- 客户端允许传任意 `base_url`，未限定回环地址或 HTTPS；默认地址是本机，但可配置性使“永不外传”不能成立。
- 使用默认 `urllib.request.urlopen`，未显式禁用代理/重定向，也未设置超时和响应体大小上限。
- 客户端暴露 `delete_session`，调用 `DELETE /sessions/{id}`；命令行未直接提供删除子命令，但 Python 能力存在，超出本应用只读分析范围。
- 导出将 talker 参数拼入文件名，并以 `wb` 写盘；未见路径段净化和拒绝覆盖保护。
- 错误处理会输出服务返回正文，若服务带回敏感内容可能泄露。

这些是风险面，不是认定作者恶意。当前已有提取桥接，无需额外扩大到另一个服务及其删除能力。

## 本应用采用的边界

- 没有安装任何以上第三方 skills；只提供审查记录和来源供选择。
- 三个分析模式使用自行编写的固定提示词；模型没有工具调用、shell、文件访问或发信能力。
- DeepSeek 只请求固定官方 HTTPS 地址，拒绝重定向，不使用环境代理，不自动重试；限制请求范围和响应体大小。
- Key 不写入档案、日志或浏览器存储；0.2.1 起可手动选择 Windows DPAPI 当前账户加密保存于独立凭据目录。错误不回显上游正文；返回结果按文本展示，不执行模型生成的 HTML。
- 对正文中的提示注入做数据/指令区分，但提示词不能彻底消除模型误判。消息 ID 引用不是事实校验，仍需人工回查。
- 本审查不覆盖原有提取组件 weflow-cli 的完整供应链；不要将这份分析 skill 审查当作整个应用的安全认证。
