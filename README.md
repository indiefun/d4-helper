# D4Helper

一个针对《暗黑破坏神 IV》的 Windows 轻量鼠标辅助工具。

默认行为：

- 侧键 1：切换右键长按。
- 侧键 2：切换左键连点。
- F1：切换 `2 -> 3` 循环连按。
- 只在配置的暗黑 4 窗口处于前台时生效。
- 游戏失焦后自动释放长按并停止循环。

## 运行

```powershell
.\dist\D4Helper.exe
```

拷贝到其他 Windows 电脑时，把这两个文件放在一起：

```text
D4Helper.exe
config.json
```

## 宏配置

工具使用 4 个宏槽位。每个宏都可以单独设置：

- 是否启用
- 名称
- 开关键
- 动作
- 循环槽位
- 间隔档位

可选开关键：

- 侧键 1
- 侧键 2
- F1
- F2
- F3
- F4
- F5
- F6

可选动作：

- 无
- 自动按住
- 循环连按

槽位支持：

- 无
- 1
- 2
- 3
- 4
- 空格
- 左键
- 右键

自动按住只使用槽位 1，例如：

```text
动作：自动按住
槽位1：右键
```

表示按一次开关键后自动按住右键，再按一次开关键后释放右键。

循环连按会按照槽位顺序触发，并自动跳过“无”。例如：

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

打开暗黑 4 后点击“读取当前窗口”，可以自动填入窗口标题和进程名。

浮层会按三列显示每个启用宏：开关键、名称、图形开关状态。浮层高度会根据启用宏数量自动计算。鼠标移动到浮层区域时，浮层会临时避让；鼠标离开后会回到原位置。

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
- 通过托盘菜单退出时，程序会释放已按住的鼠标按键。

## 许可证

本项目使用 MIT License，详见 [LICENSE](LICENSE)。
