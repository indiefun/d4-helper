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
- 点击 / 按住自动编译为成对的按键开始与结束事件，不提供独立按下 / 抬起动作。
- 新建宏默认一条轨道，示例分为技能与鼠标两轨。同轨按 `[start, end)` 检查占用，瞬时动作占用 1ms；关闭的轨道同样校验，不允许同轨重叠。
- 属性面板随选择切换宏设置和动作设置；单个点击块只编译一次，循环属于整个宏。
- 动作时长由所有轨道最后一个动作结束时间计算，包含关闭的轨道以保持编排节奏。开启循环才加上 `loop_wait_ms`；单次运行忽略该等待。`duration_ms` 是兼容旧文件的派生值，编译器重新计算，不作为用户设置。
- 旧 schema 3 循环配置缺少 `loop_wait_ms` 时，把末尾空白换算为等待；读取不改写文件。新录制不再添加固定尾部留白，编辑画布的额外空间不参与运行。
- 同键重叠使用引用计数，最后所有者退出才释放。
- 同轨冲突放置直接拒绝，拖拽显示红色落点；时长限制在下一个动作前，属性数值修改也不能绕过约束。跨轨允许并行。
- `ReadForEditing` 允许打开旧的重叠作品，先用不改时间的拆轨副本检查其他错误；原作品在用户点击拆分、保存前保持停止。`Normalize` / `Compile` 始终拒绝同轨重叠；录制自动分轨。
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
.\dist\go\D4Helper.exe

# 指定本机便携工具链
.\build.ps1 -Go 'C:\Users\kevin\.cache\d4-helper-toolchains\go1.27.3\go\bin\go.exe'
```

Go 版只输出到 `dist/go`：程序、工作区配置、VERSION 和固定名称的便携包 `D4Helper-Studio.zip`。重复构建覆盖程序与压缩包，保留已有工作区配置；不生成暂存目录或按版本拆分的文件夹。构建脚本按程序的绝对路径关闭占用待替换文件的 Go 进程。旧版程序和便携包保留在 `dist` 根目录。项目打包规则见根目录 `AGENTS.md`。

## 验证

```powershell
go test ./...
go vet ./...
npm ci --ignore-scripts
npm test
npm run test:browser
.\tools\smoke.ps1
```

- Go：多轨合并、同键重叠与边界释放、已移除动作的拒绝、鼠标移动冲突、单次点击与旧重复参数清理、录制转换、独立计划运行、失焦释放与部分输入失败恢复。
- JSDOM：宏 / 动作属性切换、积木添加、属性修改、跨轨模型、吸附、撤销和 schema 3 保存。
- 无头 Edge：真实 HTML 拖放、跨轨移动、边缘拉伸、保存、无 JS 异常，生成 1440 / 1200 布局截图。
- 真正的桌面 EXE：强制 dry-run，等待实际 WebView 渲染后调用 Go 桥接，验证前后端宏数量与引擎状态，然后退出。

`npm run test:browser` 自己启动临时本地 HTTP 服务器，使用独立的无头 Edge，不连接用户浏览器。`tools/preview-server.py` 可供手动查看，但浏览器不能发送真实输入。

自检与旧版使用不同锁，仅限强制 dry-run；正常运行仍共用单实例锁，避免两个工具同时注入输入。

## 当前限制

Windows amd64；鼠标使用绝对屏幕坐标；不提供条件分支 / 脚本。没有框选多选或轨道片段分组。隐藏到托盘保留 WebView。完整游戏输入、长时间负载、多屏 DPI 还没有实测，不能把无输入测试当作游戏识别率保证。

最初 Go / C++ 周期计时实验保存在 `results/`，它不代表 Studio 多轨引擎的端到端性能。
