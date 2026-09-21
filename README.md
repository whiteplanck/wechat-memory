# WeChat Memory · 微信记忆

把自己的微信聊天记录整理成可导出的档案、聊天目录、AI 摘要和照片日历。

Windows 用户可使用内置 Python/Node 的 **EXE 安装版**：从 [GitHub Releases](https://github.com/whiteplanck/wechat-memory/releases) 下载 `WeChatMemory-Setup-版本-x64.exe` 和对应 SHA256，运行安装程序，再打开桌面快捷方式。首次提取需要登录微信并从开始菜单运行 **Initialize WeChat**。安装包尚未签名，请核对来源与 SHA256；卸载保留聊天。详见 [Windows 使用说明](docs/windows.md)。

## 0.4.0 · 情感、人物与回忆

「情感与关系」提供两位发言者各自指向对方的统计、沟通画像卡片、指标条形图、月度情感词线索、大事时间线及可选 AI 深读。默认全量本地统计；不受顶部搜索影响，可选会话、起止日期、时区、新会话间隔和夜间排除。群聊拒绝计算双向关系。

- **可核查指标**：消息/轮次数、消息份额、主动发起、回复时延中位数及四分位、有效/排除样本数、分享轮次、亲近/支持/积极/宣泄词线索，以及披露后相邻回应中的支持线索。可展开消息 ID 和原文。
- **量化边界**：双向「互动投入指数」0–100，不是“喜欢你的概率”或经验证的心理量表。公式为窗口内接续率×50% + 双方发起份额×30% + 本人分享轮次率×20%，这些权重是产品启发式，**不是论文给出的权重**。回复速度、宣泄不直接计分；样本不足显示“—”，不是零分。不输出 MBTI、依恋类型或心理疾病诊断。
- **大事节点**：表白、争执、道歉/修复、承诺、蜜月旅行、分开先作为关键词候选；原文可能是在否定、转述或谈未来。用户确认/排除、修改实际日期、添加备注后长期保存。热恋阶段可手动记录起止日期，不用消息量峰值自动判定。ICS 只导出已确认节点，阶段结束日写在描述中。
- **AI 深读**：沿用本机 Ollama 或 DeepSeek Key，分别解释双方的情感表达、分享和支持、冲突修复及反证。云端每次确认，单次完整文本上限 30,000 字符，超限需缩小日期范围；没有悄悄抽样、自动批量扣费。结果自动存入本地关系报告，但 AI 引文和解释仍需人工核查，不自动确认事件。
- **人物与回忆**：已保存档案的图片/视频/语音按消息发送日期组成回忆日，可手动标记人物、写说明，按人物筛选。当前是文字索引与附件引用，**尚无缩略图、人脸聚类或自动人物识别**；不把拍照者/发信人自动当作照片中的人。
- **本地语音转写**：安装版包含 faster-whisper 识别组件，但**不含模型权重**。用户准备可信的完整本地模型目录后，单条识别 16 kHz / 单声道 / 16-bit PCM WAV（≤10 分钟、≤20 MB）。不上传音频，不自动下载模型。微信 SILK/加密语音、缺失原音目前不能直接识别，须先由可信工具导出为上述 WAV，并在导入记录的 `media` 中指向该文件。尚未做真实微信语音识别准确率验证；识别候选必须核对后保存，再勾选纳入关系分析。

源码语音扩展：`pip install -e '.[speech]'`。采用 [faster-whisper](https://github.com/SYSTRAN/faster-whisper) 的 CPU INT8、本地模型路径与 `local_files_only=True`；模型目录需 `model.bin`、`config.json`、`tokenizer.json`。模型文件和音频均为不可信输入，只从可信来源取得。实际识别质量取决于模型、方言、背景噪声；可能出现漏字、错字或无声幻觉。

### 心理学论文及适用边界

以下研究用于选择观察维度，**没有任何一篇验证本应用的词典、权重或“爱意预测”准确率**。

1. Laurenceau, J.-P., Feldman Barrett, L., & Pietromonaco, P. R. (1998). *Intimacy as an Interpersonal Process: The Importance of Self-Disclosure, Partner Disclosure, and Perceived Partner Responsiveness in Interpersonal Exchanges*. JPSP, 74(5), 1238–1251. [DOI: 10.1037/0022-3514.74.5.1238](https://doi.org/10.1037/0022-3514.74.5.1238) · [作者公开论文](https://affective-science.org/pubs/1998/LaurenFBPl1998.pdf)。启发：结合自我披露及对方回应，不只数消息。论文的“感知回应”需要当事人体验，不能等同于词典命中或回复速度。
2. Gable, S. L., Reis, H. T., Impett, E. A., & Asher, E. R. (2004). *What Do You Do When Things Go Right? The Intrapersonal and Interpersonal Benefits of Sharing Positive Events*. JPSP, 87(2), 228–245. [DOI: 10.1037/0022-3514.87.2.228](https://doi.org/10.1037/0022-3514.87.2.228) · [作者实验室](https://labs.psych.ucsb.edu/gable/shelly/publications/395)。启发：查看分享好消息后是否得到积极支持；图片/链接数量本身不代表回应质量。
3. Templeton, E. M., Chang, L. J., Reynolds, E. A., LeBeaumont, M. D. C., & Wheatley, T. (2022). *Fast Response Times Signal Social Connection in Conversation*. PNAS, 119(4), e2116915119. [DOI: 10.1073/pnas.2116915119](https://doi.org/10.1073/pnas.2116915119) · [全文](https://pmc.ncbi.nlm.nih.gov/articles/PMC8794835/)。研究的是实时口语轮替，**不能直接迁移到异步微信**。因此展示回复分布、夜间排除及样本量，但不设置“几分钟不回就是不喜欢”的阈值，也不把速度计入总分。

工程参考：[UniUni2000/wechat-chat-analyzer](https://github.com/UniUni2000/wechat-chat-analyzer)，审阅版本 `0bd27551ca686104d10e1ec7f296c9d7895eb4e0`。借鉴指标拆分与月度趋势的组织方式；独立实现本项目代码，没有安装其 skill、运行解密/进程扫描脚本或引入其依赖。安全审阅范围及限制见 [参考说明](docs/relationship-method.md)。

### 长期保存格式

采用开放 JSON + 离线 HTML / Markdown + ICS，不依赖在线账户才能打开。

```text
Documents/WeChatMemory/
  <内容 SHA256>.json       不可变原始档案，含消息 ID、带时区时间、原始导入及附件引用
  annotations/<档案ID>.json  人物、说明、核对转写、ASR候选/秒级分段/音频SHA256、人工修订历史
  relationships/<报告ID>.json 范围、方法版本、指标、原文证据、大事日期/状态、AI结果
  bundles/<独立备份>/
    archive-original.json   原始档案
    messages.json           可移植消息及已复制附件的相对路径
    annotations.json        人物/回忆/转写和修订历史
    messages-with-transcripts.json  明确标记的转写衍生视图（非原文）
    relationships.json      与档案匹配的关系报告和大事
    attachments/            内容哈希命名的原始附件
    attachments-manifest.json 每个附件的来源、复制状态、大小、SHA256或缺失原因
    bundle-manifest.json    格式版本 + 各文件大小及SHA256
    contacts/.../chat.html  按会话的可离线阅读版本
    photos.ics              图片消息日历
```

原始消息的 `(conversation, id)` 是关联键，保留发送时间及其时区。大事的“提及时间”和“实际发生时间”分开，语音分段时间以音频开始为零点；不把转写当原始微信文字。核对转写在衍生视图中明确标记，供关系分析选择使用。报告和标签自动保存在本机，备份时复制完整文件夹。自动存档仅保存附件引用，**必须指定附件根目录生成备份才能保存实际音视频**。

备份包可独立阅读和检查哈希；当前“导入 messages.json”仅恢复聊天，**不会自动恢复 annotations / relationships**，完整迁移应复制整个 `Documents/WeChatMemory` 数据目录。Key 使用独立 DPAPI 存储，不进入这些备份。聊天/报告/标签仍是本地明文，建议使用磁盘加密和独立备份；本机保存不等于零安全风险。

**Windows 0.3.0 安装版是独立桌面窗口：原生 WinForms 外壳 + 内嵌 WebView2 + 本地 Python 核心。** 启动不再打开系统浏览器或后台控制台，关闭窗口同时停止本应用后台及其提取子进程。源码模式仍可使用浏览器。Windows 通过固定版本 `weflow-cli 1.7.0` 读取会话、提取聊天 JSON 并自动保存；Mac 仍使用文件导入。兼容标准 JSON、she-love-me JSON、常见 weflow-cli / CipherTalk JSON，以及时间戳 Markdown / TXT。尚未使用真实 Windows 微信账号端到端验证，不能保证特定微信版本兼容。

桌面版适用 Windows 10 1903+ / Windows 11 x64，需要 .NET Framework 4.8 和微软 WebView2 Runtime；缺少 WebView2 时安装程序调用附带的微软签名引导程序联网补齐。现有深色界面、聊天目录、备份、日历和加密保存 Key 均沿用。窗口顶部可打开微信初始化（此步骤仍有独立交互控制台），导出使用系统另存为对话框。没有向页面暴露文件/命令桥接，禁止导航到外部网页，禁用密码自动保存和开发者工具。桌面界面仍是 HTML 技术，不是所有控件重写成原生控件，也不是浏览器快捷方式。

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

本地界面仅监听 `127.0.0.1`，校验 Host、来源和会话令牌，不加载外部脚本或字体。单文件导入限制为 19 MB；本地照片扫描只读取元数据，不上传照片。网页 AI 默认本机 Ollama；可手动切换 DeepSeek，粘贴 Key 并逐次确认云端发送。

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

### DeepSeek API（网页）

在「AI 分析」选择 **DeepSeek API**，粘贴自己的 API Key，选择分析模式，勾选本次发送确认后点击分析。接口固定为 `https://api.deepseek.com/chat/completions`；默认模型 `deepseek-flash`，也可手动填入官方支持的模型名。模型名以 [DeepSeek 官方文档](https://api-docs.deepseek.com/) 为准（核对日期：2026-09-21）。

可选模式：摘要/话题树/时间线、沟通模式与反证、待办与约定。这些是应用内置的受限提示词，不运行第三方 skill 脚本，不给模型执行命令或读取文件的工具。GitHub 候选 skill 的版本、审查范围及风险见 [安全审查记录](docs/skills-security-review.md)。

只发送当前筛选的文本、会话名、发言者、时间、类型和消息 ID；不发送独立附件路径字段或附件文件。正文中的隐私并不会自动脱敏。单次最多 30000 字符，超限拒绝，不静默截断。API 可能收费，无自动重试。结果用纯文本显示，点击「导出分析」保存 Markdown 到浏览器下载目录。未用真实 Key 调用付费 API；测试使用模拟响应。

Windows 0.2.1 起支持「加密保存 Key」：使用 [Windows DPAPI](https://learn.microsoft.com/en-us/windows/win32/api/dpapi/nf-dpapi-cryptprotectdata) 当前用户保护，密文位于 `%LOCALAPPDATA%\WeChatMemory\credentials\deepseek.dpapi`，与聊天档案分开。保存后输入框留空即可使用，重启仍有效；填入其他 Key 仅用于本次，点击保存才替换。支持删除已保存 Key，不回显密钥，不写入浏览器存储或 GitHub。未点击保存则仍是临时 Key。非 Windows 平台不降级为明文保存。

保护并非绝对：当前 Windows 账户下的恶意程序仍可能取得凭据，重装系统或换账户可能无法解密。卸载保留凭据以便重装继续使用；需要清除时先点击「删除已保存 Key」。本机删除不等于服务商撤销，也无法收回已发送的请求。Key 失效、余额不足时仍需自行更新；保存 Key 不取消每次云端发送确认。

### Ollama（本地 / CLI）

安装并启动 Ollama、下载你选择的模型后（模型名必须是本机已有模型）：

```sh
wechat-memory analyze examples/demo.json --model YOUR_LOCAL_MODEL --output output/analysis.md
```

通过 [Ollama 官方 Chat API](https://docs.ollama.com/api/chat) 接入。默认 `http://127.0.0.1:11434`；CLI 的 `--endpoint` 可指定兼容的 Ollama 服务，非本地服务须 `--allow-remote`。DeepSeek 目前使用上述网页入口。单次请求限制为 30000 字符，超过时明确报错；使用 `--conversation '会话名称' --day 2026-09-19` 缩小范围，不会静默截断。

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
3. 扩展模型提供商和跨平台凭据存储，增加脱敏、长聊天分块及可验证的引用。
4. 添加图片内容理解与事件提取，由用户确认日期和事件后写入日历。
5. 打包安装、增量导入、加密存储、备份恢复。

接口边界见 [架构说明](docs/architecture.md)。真实聊天放在 `data/`，导出放在 `output/`，两者均被 Git 忽略。不要把聊天、照片、数据库、模型密钥提交到仓库；Git 忽略规则不是内容检测器。

## 验证

```sh
python3 -m unittest discover -s tests -v
```

CI 在 Python 3.11 / 3.13 验证核心和照片功能。AI 测试使用模拟响应，真实模型连通性需在配置本机模型后验证。

本次改进参考 [she-love-me](https://github.com/863401402/she-love-me) 的多来源导入、联系人独立目录和统计/模型材料分层思路；具体字段、版本与兼容性边界见 [参考记录](docs/reference-notes.md)。本项目仍以本地保存为中心，不提供恋爱评分或心理诊断。外部格式尚未使用真实导出文件联调；当前环境无可连接浏览器，新增界面尚未完成浏览器交互验证。
