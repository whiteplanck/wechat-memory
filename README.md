# WeChat Memory · 微信记忆

把自己的微信聊天记录整理成可导出的档案、聊天目录、AI 摘要和照片日历。

**当前是独立本地应用原型：Python 核心 + 浏览器界面，后续打包桌面版。** 支持标准 JSON 文件；尚未实现直接读取微信数据库、微信备份解析或客户端注入。示例完全虚构，不包含真实聊天或照片。

## 打开本地应用

在仓库目录运行（基础功能需要 Python 3.11+，无额外依赖）：

```sh
python3 -m wechat_memory.server
```

启动后自动打开 `http://127.0.0.1:8765`。先点击「试用虚构示例」，或「导入聊天记录」选择标准 JSON 文件。左侧按会话/日期浏览，搜索内容或参与者，导出当前筛选；「照片日历」查看月历和导出 ICS，「AI 分析」连接本机 Ollama。

记录只在当前页面内存中保留，刷新或关闭后需重新导入；当前不自动保存档案。照片目录扫描需要下面的 `photos` 扩展；安装后也可以使用 `wechat-memory-app` 启动。按 Ctrl+C 关闭服务，端口被占用时加 `--port 8766`，不希望自动打开浏览器则加 `--no-browser`。

本地界面仅监听 `127.0.0.1`，校验 Host、来源和会话令牌，不加载外部脚本或字体。JSON 导入限制为 19 MB，附件只显示路径引用；本地照片扫描只读取元数据，不上传照片。网页 AI 界面仅连接默认本机 Ollama，不开放远程模型配置。

## 已实现

- 标准 JSON 校验、按会话/日期筛选，导出 JSON / Markdown。
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

参见 [虚构示例](examples/demo.json)。根对象包含 `messages` 数组，或直接传入数组。每条消息必须有字符串字段 `id`、`conversation`、`sender`、`timestamp`、`text`。`timestamp` 使用带时区的 ISO 8601；同一会话内 ID 不可重复。

可选字段：`type`（text/image/audio/video/file/other，默认 text）和 `media`（附件路径字符串数组）。目录和日历按消息自身时区分组。

## 开发路线

1. 确定首个微信平台/版本，接入用户授权的聊天导出来源。
2. 在现有本地界面上增加档案持久化、附件预览和原生文件夹选择。
3. 添加多模型提供商、密钥存储、脱敏、长聊天分块及可验证的引用。
4. 添加图片内容理解与事件提取，由用户确认日期和事件后写入日历。
5. 打包安装、增量导入、加密存储、备份恢复。

接口边界见 [架构说明](docs/architecture.md)。真实聊天放在 `data/`，导出放在 `output/`，两者均被 Git 忽略。不要把聊天、照片、数据库、模型密钥提交到仓库；Git 忽略规则不是内容检测器。

## 验证

```sh
python3 -m unittest discover -s tests -v
```

CI 在 Python 3.11 / 3.13 验证核心和照片功能。AI 测试使用模拟响应，真实模型连通性需在配置本机模型后验证。
