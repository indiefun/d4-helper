# D4Helper

D4Helper 是一个针对《暗黑破坏神 IV》的 Windows 轻量辅助工具，用来减少重复按键和长按操作带来的疲劳。

它不是通用宏编辑器，而是面向暗黑 4 的简单宏开关工具：只在配置的游戏窗口处于前台时生效，窗口失焦后会自动释放长按并停止循环。

## 默认行为

- 侧键 1：切换右键长按。
- 侧键 2：切换左键连点。
- F1：切换 `2 -> 3` 循环连按。
- F2：切换右键连点。
- 游戏内浮层显示每个启用宏的开关键、名称和开关状态。

## 截图

配置页面：

![配置页面](docs/images/config-window.png)

游戏内浮层：

![游戏内浮层](docs/images/overlay.png)

## 运行

```powershell
.\dist\D4Helper.exe
```

拷贝到其他 Windows 电脑时，把这些文件放在一起：

```text
D4Helper.exe
config.json
VERSION
```

## 使用教程

1. 启动暗黑 4，并进入游戏窗口。
2. 启动 `D4Helper.exe`。
3. 在配置页面点击“读取当前窗口”，让工具记录暗黑 4 的窗口标题和进程名。
4. 按需要调整 4 个宏槽位的开关键、动作、目标按键和间隔档位。
5. 点击“保存并应用”，配置会立即生效并写入 `config.json`。
6. 回到暗黑 4，使用配置好的开关键开启或关闭对应宏。
7. 不需要显示配置页面时，可以关闭窗口或最小化到托盘，程序会继续在后台运行。

默认配置适合先直接试用：

- 侧键 1 开启或关闭右键长按。
- 侧键 2 开启或关闭左键连点。
- F1 开启或关闭 `2 -> 3` 循环连按。
- F2 开启或关闭右键连点。

浮层会显示当前启用宏的开关键、名称和开关状态。鼠标移动到浮层区域时，浮层会临时避让，避免遮挡游戏操作。

## 宏配置

工具使用 4 个宏槽位。每个宏都可以单独设置：

- 是否启用
- 名称
- 开关键
- 动作
- 循环槽位
- 间隔档位

开关键以录制为主。每个开关键显示框右侧都有“录”和“选”按钮：

- 录：点击后按一次目标键即可录入。
- 选：从常用键里快速选择。

常用开关键：

- 侧键 1
- 侧键 2
- 鼠标中键
- F1-F12
- 数字 0-9
- 字母 A-Z
- 空格、Tab、Enter、Backspace
- Shift、Ctrl、Alt、CapsLock
- Insert、Delete、Home、End、PageUp、PageDown
- 方向键

可选动作：

- 无
- 自动按住
- 循环连按

槽位支持：

- 无
- 左键
- 右键
- 鼠标中键
- 数字 0-9
- 字母 A-Z
- F1-F12
- 空格、Tab、Enter、Backspace
- Shift、Ctrl、Alt、CapsLock
- Insert、Delete、Home、End、PageUp、PageDown
- 方向键

每个槽位显示框右侧也有“录”和“选”按钮。录入按键时，按 Esc 可以取消。左键可以作为槽位动作使用，但不能作为宏开关键，避免点击界面时误触发。

### 自动按住

`自动按住` 只使用槽位 1。

例如：

```text
动作：自动按住
槽位 1：右键
```

表示按一次开关键后自动按住右键，再按一次开关键后释放右键。

### 循环连按

`循环连按` 会按照槽位顺序触发，并自动跳过“无”。

例如：

```text
2 / 3 / 无 / 无
```

会循环：

```text
2 -> 3 -> 2 -> 3
```

间隔档位：

- 标准 - 100ms
- 稳定 - 150ms
- 慢速 - 250ms
- 很慢 - 500ms

建议先使用“标准 - 100ms”或“稳定 - 150ms”。间隔越慢越稳定，越不容易漏按。

## 界面

配置窗口包含：

- 暗黑4窗口
- 宏配置
- 浮层
- 版本更新
- 支持项目

打开暗黑 4 后点击“读取当前窗口”，可以自动填入窗口标题和进程名。

浮层会按三列显示每个启用宏：开关键、名称、图形开关状态。浮层高度会根据启用宏数量自动计算。鼠标移动到浮层区域时，浮层会临时避让；鼠标离开后会回到原位置。

配置窗口标题栏会显示当前版本号，例如：

```text
D4Helper v0.1.0
```

“版本更新”区域可以手动检查 GitHub Release 是否有新版本。发现新版后，点击“查看更新”会打开 Release 页面，由用户自行决定是否下载更新；程序不会自动下载或替换 exe。

## 打包

```powershell
python -m pip install pyinstaller pystray pillow
.\build.ps1
```

输出：

```text
dist\D4Helper.exe
dist\config.json
dist\VERSION
```

版本号记录在 [VERSION](VERSION)。

本地构建会读取 `VERSION`，并把版本写入：

```text
dist\VERSION
```

同时，构建脚本也会把 `VERSION` 打进 exe 内部。运行时版本号读取顺序为：

1. exe 同目录的 `VERSION`
2. exe 内置的 `VERSION`
3. 读取失败时显示 `unknown`

## GitHub Actions

仓库包含自动打包流程：

```text
.github/workflows/build.yml
```

触发方式：

- push 到 `main` 或 `master`
- pull request
- 手动运行 workflow
- push `v*` 标签，例如 `v0.1.0`

每次构建会上传 artifact：

```text
D4Helper-v版本号-windows
```

推送 tag 时会自动创建 GitHub Release，并上传：

```text
D4Helper-v版本号-windows.zip
```

## 版本升级与发布

发布新版本时：

1. 修改 [VERSION](VERSION)，例如改成 `0.2.0`。
2. 提交版本号和代码改动。
3. 创建与 `VERSION` 对应的 tag，格式必须是 `v版本号`。
4. 推送 tag。

示例：

```powershell
git add VERSION README.md
git commit -m "Bump version to 0.2.0"
git tag v0.2.0
git push
git push origin v0.2.0
```

GitHub Actions 会校验 tag 和 [VERSION](VERSION) 是否匹配。例如 `VERSION` 是 `0.2.0` 时，tag 必须是 `v0.2.0`。

## 注意

- 如果暗黑 4 以管理员权限运行，本工具也需要以管理员权限运行。
- 部分反作弊或安全策略可能会阻止模拟输入。
- 通过托盘菜单退出时，程序会释放已按住的鼠标和键盘按键。

## 支持项目

如果这个工具对你有帮助，可以扫码打赏支持。打赏是完全自愿的，不影响任何功能。

![打赏二维码](assets/donate.jpg)

## 许可证

本项目使用 MIT License，详见 [LICENSE](LICENSE)。
