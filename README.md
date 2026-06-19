# 暗黑4鼠标助手

一个针对《暗黑破坏神 IV》的 Windows 轻量鼠标辅助工具。

默认行为：

- 侧键 1：切换右键长按。
- 侧键 2：切换左键循环短按。
- F1：切换键盘 `2`、`3` 快速交替连按。
- 只在配置的暗黑 4 窗口处于前台时生效。
- 游戏失焦后自动释放长按并停止循环。
- 游戏内显示小浮层：右键长按、左键连点、F1 2/3连按。

## 运行

```powershell
.\dist\GameMouseTool.exe
```

拷贝到其他 Windows 电脑时，把这两个文件放在一起：

```text
GameMouseTool.exe
config.json
```

## 宏开关绑定

每个宏都可以单独选择开关键。默认支持：

- 侧键 1
- 侧键 2
- F1
- F2
- F3
- F4
- F5
- F6

当前内置宏：

- 自动按住右键
- 左键自动连点
- 右键自动连点
- 2/3 快速连按

## 界面

配置窗口包含：

- 暗黑4窗口
- 宏开关绑定
- 浮层

打开暗黑 4 后点击“读取当前窗口”，可以自动填入窗口标题和进程名。

## 打包

```powershell
python -m pip install pyinstaller pystray pillow
.\build.ps1
```

输出：

```text
dist\GameMouseTool.exe
dist\config.json
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
- 发布 GitHub Release

每次构建会上传 artifact：

```text
D4MouseHelper-windows
```

发布 Release 时会自动把 `GameMouseTool.exe` 和 `config.json` 附加到 Release 资产里。

## 注意

- 如果暗黑 4 以管理员权限运行，本工具也需要以管理员权限运行。
- 部分反作弊或安全策略可能会阻止模拟输入。
- 通过托盘菜单退出时，程序会释放已按住的鼠标按键。
