# D4Helper 静态展示页

这个目录是纯静态页面，可以直接部署到 Cloudflare Pages。

Cloudflare Pages 配置：

- Build command：留空
- Build output directory：`site`
- Root directory：留空，或保持仓库根目录

页面入口：

```text
site/index.html
```

资源文件：

```text
site/assets/
```

`index.html` 包含当前版本功能、Profile 切换示例、截图和使用说明，`script.js` 仅用于切换示例标签，不保存用户配置。页面无需构建工具，也不依赖外部脚本或字体。

发布版本时同步更新页面中的版本号、更新说明和 `assets/config-window.png`、`assets/overlay.png`，截图与 `docs/images/` 保持一致。下载入口使用固定的 `D4Helper-windows-latest.zip`，跟随 GitHub 最新正式版。
