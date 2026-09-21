# Windows 微信提取与本地保存

目标环境：Windows 10/11 x64、Python 3.11+、Node.js 22.13+、已登录的兼容 Windows 微信 4.x。此版本调用 `weflow-cli 1.7.0`，不是自行实现微信数据库解密。实际兼容性取决于微信版本和本机数据，尚未用真实 Windows 微信账号端到端验证。

## 首次使用

### EXE 安装版（无需自行安装 Python / Node）

下载成功的 **Windows EXE installer** 构建中的 `WeChatMemory-Installer-x64` 附件，解压后运行 `WeChatMemory-Setup-0.2.0-x64.exe`。仅支持 Windows 10/11 x64；安装到当前用户的应用目录，无需管理员权限，不修改系统 PATH。

安装后打开桌面 **WeChat Memory**。首次提取时，在 Windows 微信登录自己的账号，再从开始菜单打开 **Initialize WeChat**，根据提示初始化（只有访问微信进程确需权限时才以管理员身份运行该快捷方式）。应用使用系统浏览器显示界面，使用期间保留启动控制台，关闭窗口即可停止本地服务。

安装包内置运行环境及固定版本提取组件，安装本身不联网；云端 AI 请求仍需手动确认。包尚未代码签名，可能提示未知发布者，请核对私有仓库来源和同包 SHA256，不要关闭安全软件。卸载保留 Documents/WeChatMemory 内的聊天，以及提取工具在用户目录中的配置；不会自动删除敏感数据。

CI 使用虚构记录验证安装、独立运行环境、导入存档及卸载保留数据，不等于真实微信账号提取已经验证。

### 源码启动版（需自行安装运行环境）

1. 安装 [Python](https://www.python.org/downloads/windows/)（包含 `py` 启动器，选 64 位）和 [Node.js](https://nodejs.org/en/download)（22.13 或更新的受支持版本），重开终端使 PATH 生效。
2. 从 GitHub Actions 的 **Windows launcher kit** 成功运行中下载 `WeChatMemory-Windows` 附件，解压下载的附件及其中的 ZIP；也可下载整个仓库源码。不要直接在压缩包内运行。
3. 双击 `setup-windows.cmd`。安装需要联网：创建项目 `.venv`，安装应用和提取依赖，将固定版本 weflow-cli 安装到 `%LOCALAPPDATA%\WeChatMemory\tools\weflow`，不修改全局 npm 包。
4. 在这台电脑登录自己的微信。需要保存的历史应先通过微信支持的迁移方式转到此电脑，并确认电脑微信中能够查看。
5. 双击 `init-wechat-windows.cmd`，按提取工具的交互提示完成初始化；若提示访问进程权限不足，右键脚本选择「以管理员身份运行」。初始化可能读取微信进程中的数据库访问信息并写入该工具自己的本机配置，不会传到本应用网页或 GitHub。
6. 双击 `start-windows.cmd`，在打开的本地页面进入 **Windows 提取 → 检测环境 → 读取会话 → 选择会话 → 提取并保存到本地**。

程序请求所选会话的全部可读取消息（`--limit 0`），验证工具返回的文件、消息数量和覆盖字段后归档。当前不提供自动批量导出所有会话。会话列表最多 1000 项，可按关键词筛选。

## 保存位置

默认在 `%USERPROFILE%\Documents\WeChatMemory`，以界面显示的实际路径为准（不自动跟随 OneDrive 的文档目录重定向）：

- 根目录的 JSON：可重新打开的聊天档案。
- `raw/<本次任务>/`：提取工具原始 JSON；转换失败也保留，以便检查或重新导入。
- `bundles/`：点击「本地备份」后生成的按会话离线档案。

**提取 JSON 不等于已备份全部媒体。** 这条集成没有调用上游富媒体 HTML 导出、网络图片下载或语音转写。原始 JSON 中可能有图片元数据/嵌入内容，但应用当前只把已有 `media` 本地路径纳入附件复制；需要核对原文件后使用「本地备份」指定附件根目录。不宣称手机全部历史、已删除消息或未下载附件已被恢复。

## 排障

- 环境检测没有通过：重新运行 `setup-windows.cmd`，检查 Node/Python 版本及安装错误。
- 初始化失败：确认微信已登录，必要时用管理员终端初始化；不要把密钥、数据库或完整日志发到公开 Issue。
- 自定义微信数据目录：在仓库目录终端运行 `.venv\Scripts\python.exe -m wechat_memory.windows_exporter init --path "D:\WeChatData"`。
- 初始化完成却没有会话：这不算成功验收。确认当前账号、微信数据目录和电脑是否拥有聊天；不要将空列表视为备份完成。
- 提取失败：原始文件保留在任务目录，应用不会伪造成功档案；单次提取超时 10 分钟，自动停止任务。当前自动归档文件上限 256 MB。
- 端口占用：运行 `.venv\Scripts\python.exe -m wechat_memory.server --port 8766`。

## 版本与验证边界

已核对 npm 的 `weflow-cli@1.7.0` 发布包命令：`check --json`、`sessions --json`、`export <ID> json --limit 0 --contract weflow-v1 --json --non-interactive`。实际初始化命令为交互式 `init`，不能用网页里的成功提示代替初始化。

上游来源：[仓库](https://github.com/zhuobichen/weflow-cli)、[操作说明](https://github.com/zhuobichen/weflow-cli/blob/master/OPERATIONS.md)。集成只调用环境检测、会话读取和 JSON 导出，不调用发送消息、AI 分析、删除数据、退出账号或全盘扫描命令。

Windows CI 验证本应用、安装组件及基本环境检查；CI 没有真实微信账号，不能据此声称已在某个微信版本提取成功。请区分两种分发：源码脚本包需要自行安装 Python 和 Node；EXE 安装包内置运行环境，均使用本地浏览器界面。
