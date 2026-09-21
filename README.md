# WeChat Memory · 微信记忆

把自己的微信聊天记录整理成可导出的档案、聊天目录、AI 摘要和照片日历。

**当前是独立本地应用：Python 核心 + 浏览器界面。** Windows 新增通过固定版本 `weflow-cli 1.7.0` 读取会话、提取聊天 JSON 并自动保存；Mac 仍使用文件导入。兼容标准 JSON、she-love-me JSON、常见 weflow-cli / CipherTalk JSON，以及时间戳 Markdown / TXT。尚未使用真实 Windows 微信账号端到端验证，不能保证特定微信版本兼容。

## Windows 快速使用

准备 Windows 10/11 x64、Python 3.11+、Node.js 22.13+ 和已登录的 Windows 微信。下载本仓库的 Windows 启动包并解压，然后依次运行：

1. `setup-windows.cmd`：首次联网安装应用和提取组件。
2. `init-wechat-windows.cmd`：首次初始化；按终端提示操作，若访问进程权限不足则右键以管理员身份运行。
3. `start-windows.cmd`：打开应用，进入「Windows 提取」，检测环境 → 读取会话 → 选择会话 → 提取并保存。

下载入口：[Windows launcher kit](https://github.com/whiteplanck/wechat-memory/actions/workflows/windows.yml) 成功运行的 Artifacts。启动包是带安装脚本的源码包，仍需要 Python / Node，不是免环境 EXE。完整安装、保存位置和排障步骤见 [Windows 使用说明](docs/windows.md)。

提取范围是**这台电脑可读取的聊天**，不会自动补回手机未迁移的历史或未下载的附件；JSON 提取尚未集成上游富媒体 HTML 导出。

## 打开本地应用

在仓库目录运行（基础功能需要 Python 3.11+，无额外依赖）：

```sh
python3 -m wechat_memory.server
```

启动后自动打开 `http://127.0.0.1:8765`。先点击「试用虚构示例」，或「导入聊天记录」选择文件。可展开「导入设置」指定格式、会话名和无时区记录的默认时区。左侧按会话/日期浏览，搜索内容或参与者，导出当前筛选；「本地备份」打包保存聊天及附件，「照片日历」查看月历和导出 ICS，「AI 分析」连接本机 Ollama或导出可交给其他模型的分析材料。

**导入的聊天现在自动保存到本地**：默认目录为 `~/Documents/WeChatMemory`（Mac 的「文稿」文件夹下）。每次导入生成独立 JSON 档案，相同内容重复导入复用已有文件，不覆盖旧档案。刷新或重启后自动打开最新保存的档案，也可从左侧「本地档案」选择历史档案。「关闭当前档案」只关闭视图，不删除磁盘文件。虚构示例不会自动保存。

JSON 档案可直接复制备份，也可重新导入。自动存档保存文字、时间、参与者、附件路径，以及首次导入的原始内容；重复导入复用原档案及其首次导入元信息。**自动存档不复制附件，复制照片/视频请使用「本地备份」**。AI 生成结果和单独扫描的 EXIF 日历仍需点击各自导出按钮另存。档案为未加密的本地 JSON，不会上传 GitHub。可通过 `--data-dir /你的目录` 指定其他保存位置；这只切换目录，不会搬移旧档案。

照片目录扫描需要下面的 `photos` 扩展；安装后也可以使用 `wechat-memory-app` 启动。按 Ctrl+C 关闭服务，端口被占用时加 `--port 8766`，不希望自动打开浏览器则加 `--no-browser`。

本地界面仅监听 `127.0.0.1`，校验 Host、来源和会话令牌，不加载外部脚本或字体。单文件导入限制为 19 MB；本地照片扫描只读取元数据，不上传照片。网页 AI 界面仅连接默认本机 Ollama，不开放远程模型配置。

## 聊天和附件一起备份

1. 导入记录或打开一个已有档案，切换「本地备份」。
2. 如果有附件，填写导出工具生成的附件根目录。消息中的相对路径必须能在此目录下找到对应文件；绝对路径必须仍处于该目录内。
3. 点击「生成本地备份包」。程序在 `~/Documents/WeChatMemory/bundles/` 下建立新的独立文件夹，不覆盖旧备份。
4. 在该文件夹打开 `index.html` 离线查看；迁移或备份时复制**整个文件夹**。

备份包括：按会话分目录的聊天网页 / Markdown / JSON、复制后的附件、附件清单、全量统计、聊天目录、图片消息日期日历和分析材料。`archive-original.json` 保留原始档案，`messages.json` 的媒体路径只指向已成功复制的附件。

不在指定目录内的文件、指向目录外的符号链接、网络 URL、缺失文件和超限文件不会复制，原因写入 `attachments-manifest.json`。上限为单个文件 100 MB、总计 1 GB。留空附件目录仍会生成文字备份，未复制的附件引用保留在原始档案和清单中。复制完成后可独立于原附件目录使用；从备份重新导入 `messages.json` 后，附件根目录应选择该备份文件夹。

「导出分析材料」使用当前筛选生成全量统计及均匀抽取的最多 60 条消息，每条最多 300 字，明确记录取样和截断数量。备份包还为每个会话生成独立的分析材料；生成材料不调用模型、不上传内容，不把均匀样本当作完整语境。

## 已实现

- 多来源导入、时间戳单位转换、原始内容保留、按会话/日期筛选，导出 JSON / Markdown。
- 本地自动存档，以及按会话组织、包含实际附件的离线备份包。
- 会话 → 日期 → 消息 ID 的目录树，以及消息数、参与者、消息类型和每日统计。
- 可选 Ollama 模型分析，输出摘要、话题树和待办；要求模型引用消息 ID，但结果仍需人工核对。
- 图片消息按发送日期生成 `.ics` 日历；本地照片按 EXIF 原始拍摄日期生成日历，没有日期的照片明确跳过并报告。
- 默认本地处理，AI 必须手动调用；远程模型额外要求 `--allow-remote`，且必须使用 HTTPS。

## 快速开始

需要 Python 3.11+。基础功能无第三方依赖，可直接在仓库目录运行：

```sh
python3 -m wechat_memory.cli export examples/demo.json --output output/chat.md
python3 -m wechat_memory.cli tree examples/demo.json --output output/tree.json
python3 -m wechat_memory.cli stats examples/demo.json --output output/stats.json
python3 -m wechat_memory.cli calendar examples/demo.json --output output/photos.ics
```

输出文件已存在时会报错，请使用新文件名。附件仅导出引用，不复制图片文件。日历为全天事件，不含照片二进制，也不会自动同步到系统日历；可手动导入支持 ICS 的日历应用。

安装照片扩展和命令行入口：

```sh
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[photos]'
wechat-memory photos /path/to/your/photos --output output/capture-dates.ics
```

支持 JPEG / PNG / WebP / TIFF 的 EXIF 日期，暂不支持 HEIC、OCR 或从画面识别行程。拍摄日期使用照片元数据中的日期；图片消息使用其记录的时区和发送日期，二者不等同。

## AI 模型

安装并启动 Ollama、下载你选择的模型后（模型名必须是本机已有模型）：

```sh
wechat-memory analyze examples/demo.json --model YOUR_LOCAL_MODEL --output output/analysis.md
```

通过 [Ollama 官方 Chat API](https://docs.ollama.com/api/chat) 接入。默认 `http://127.0.0.1:11434`；`--endpoint` 可指定兼容的 Ollama 服务。当前不支持云端 API 密钥或其他协议。单次请求限制为 30000 字符，超过时明确报错；使用 `--conversation '会话名称' --day 2026-09-19` 缩小范围，不会静默截断。

分析发送筛选后的完整消息字段（包括参与者和附件路径），当前未做自动脱敏。除显式调用模型外，导出、目录和统计均无网络访问。不自动下载模型。

## 输入格式

网页导入会自动识别已支持的结构，也可手动指定来源。weflow-cli 使用 `localId / createTime / localType / parsedContent` 等字段，CipherTalk 支持 `messageId / direction / content` 等字段；she-love-me 支持 `contact_display / local_id / sender / timestamp / content / transcript`。支持 Unix 秒、毫秒、微秒、纳秒；无时区日期默认明确按 UTC+08:00 解释，可在导入设置切换 UTC。格式错误会终止本次导入，不静默丢弃消息。

Markdown / TXT 示例：

```text
[2026-09-19 09:30] 小林: 周末去拍照吧。
这里是上一条消息的第二行。
[2026-09-19 09:31] 我: 好的。
```

以下是本项目的标准格式（命令行核心仍使用此格式）：

参见 [虚构示例](examples/demo.json)。根对象包含 `messages` 数组，或直接传入数组。每条消息必须有字符串字段 `id`、`conversation`、`sender`、`timestamp`、`text`。`timestamp` 使用带时区的 ISO 8601；同一会话内 ID 不可重复。

可选字段：`type`（text/image/audio/video/file/other，默认 text）和 `media`（附件路径字符串数组）。目录和日历按消息自身时区分组。

## 开发路线

1. 在真实 Windows 微信账号上验证提取兼容性，补充导出器错误诊断和附件提取。
2. 增加应用内附件预览、原生文件夹选择与大档案增量备份。
3. 添加多模型提供商、密钥存储、脱敏、长聊天分块及可验证的引用。
4. 添加图片内容理解与事件提取，由用户确认日期和事件后写入日历。
5. 打包安装、增量导入、加密存储、备份恢复。

接口边界见 [架构说明](docs/architecture.md)。真实聊天放在 `data/`，导出放在 `output/`，两者均被 Git 忽略。不要把聊天、照片、数据库、模型密钥提交到仓库；Git 忽略规则不是内容检测器。

## 验证

```sh
python3 -m unittest discover -s tests -v
```

CI 在 Python 3.11 / 3.13 验证核心和照片功能。AI 测试使用模拟响应，真实模型连通性需在配置本机模型后验证。

本次改进参考 [she-love-me](https://github.com/863401402/she-love-me) 的多来源导入、联系人独立目录和统计/模型材料分层思路；具体字段、版本与兼容性边界见 [参考记录](docs/reference-notes.md)。本项目仍以本地保存为中心，不提供恋爱评分或心理诊断。外部格式尚未使用真实导出文件联调；当前环境无可连接浏览器，新增界面尚未完成浏览器交互验证。
