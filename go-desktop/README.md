# D4Helper Studio · 模块与验证

执行核心与编辑模型已分离。生产代码不导入旧 macro 配置包，该包已移除。

```text
frontend/model.js + app.js   拖放、轨道、属性、播放头、预览、撤销
         ↓ workspace schema 3
internal/timeline           轨道/块校验、共享时钟、多轨合并、轨迹展开
         ↓ sequence.Plan
internal/sequence           原始事件与计划；无 UI、JSON 轨道、快捷键依赖
         ↓
internal/engine
  core.go                   执行状态与计划应用
  execution.go              截止时间调度、计划启动/停止
  input_state.go            输入所有权、部分发送追踪、释放重试
  recording.go              输入事件录制
  controller.go             快捷键、窗口状态、录入与状态快照
  worker.go                 OS 线程、命令队列、等待唤醒
         ↓ Driver.Send
internal/win                SendInput、键鼠事件、前台通知、托盘、浮层
```

`internal/timing` 提供可取消、可被命令提前唤醒的高分辨率等待。无活动宏时无限等待，不做忙循环。

## 语义

- 轨道同一绝对时间上的事件合并，轨道顺序不表示顺序执行。
- 点击 / 按住编译为开始与结束事件，按下 / 抬起在全宏范围配对。
- 同键重叠使用引用计数，最后所有者退出才释放。
- 同一时间先释放，再移动，再按下，再滚动，排序确定。
- 平滑移动生成间隔不超过约 8ms 的采样事件；录制轨迹保留采集点和相对时间。
- 事件总数、轨道数和总长度有上限；异常或部分发送停用执行并尝试释放。
- 调度发生明显延迟时平移剩余事件，避免把按住时长压成瞬间输入。

编辑器和执行器不再包含四槽模式或一键启动组。一个宏的多轨同时编译、同时启动。

## 文件与构建

只读取 `workspace.timeline.json`。旧 `config.json` / `config.go.json` 不自动导入。格式不是 schema 3 时明确报错，不改写原文件。

```powershell
# 仓库根目录
.\build.ps1
.\dist\studio\D4Helper.exe

# 指定本机便携工具链
.\build.ps1 -Go 'C:\Users\kevin\.cache\d4-helper-toolchains\go1.27.3\go\bin\go.exe'
```

便携包：`dist/D4Helper-Studio-v3.0.0-alpha.1.zip`。新输出与上轮 `dist/go` 分开。

## 验证

```powershell
go test ./...
go vet ./...
npm ci --ignore-scripts
npm test
npm run test:browser
.\tools\smoke.ps1
```

- Go：多轨合并、同键重叠、跨轨按下/抬起、鼠标移动冲突、重复点击、录制转换、独立计划运行、失焦释放与部分输入失败恢复。
- JSDOM：积木添加、属性修改、跨轨模型、吸附、撤销和 schema 3 保存。
- 无头 Edge：真实 HTML 拖放、跨轨移动、边缘拉伸、保存、无 JS 异常，生成 1440 / 1200 布局截图。
- 真正的桌面 EXE：强制 dry-run，等待实际 WebView 渲染后调用 Go 桥接，验证前后端宏数量与引擎状态，然后退出。

`npm run test:browser` 自己启动临时本地 HTTP 服务器，使用独立的无头 Edge，不连接用户浏览器。`tools/preview-server.py` 可供手动查看，但浏览器不能发送真实输入。

自检与旧版使用不同锁，仅限强制 dry-run；正常运行仍共用单实例锁，避免两个工具同时注入输入。

## 当前限制

Windows amd64；鼠标使用绝对屏幕坐标；不提供条件分支 / 脚本。没有框选多选或轨道片段分组。隐藏到托盘保留 WebView。完整游戏输入、长时间负载、多屏 DPI 还没有实测，不能把无输入测试当作游戏识别率保证。

最初 Go / C++ 周期计时实验保存在 `results/`，它不代表 Studio 多轨引擎的端到端性能。
