# D4Helper 静态展示页

这个目录是纯静态页面，可以部署到 Cloudflare Workers 或 Cloudflare Pages，无需构建。

## Cloudflare Workers Builds

仓库根目录的 `wrangler.jsonc` 将 `site/` 配置为静态资源目录，不需要 Worker 脚本入口。

- Root directory：仓库根目录，留空或 `/`，不要设为 `site`
- Build command：留空
- Deploy command：`npx wrangler deploy`
- 非生产分支的版本上传命令：`npx wrangler versions upload`
- 构建环境变量：`SKIP_DEPENDENCY_INSTALL=true`，跳过根目录中旧版桌面程序的 Python 依赖安装

`wrangler deploy` 会发布并启用新版本；`wrangler versions upload` 只上传版本，不会切换生产流量。

如果日志出现 `Missing entry-point to Worker script or to assets directory`，请确认部署分支包含根目录的 `wrangler.jsonc`，且 Root directory 指向仓库根目录。

本地验证部署配置（不上传）：

```powershell
npx wrangler deploy --dry-run
```

## Cloudflare Pages

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

`index.html` 依次展示免费开源定位、角色配置交互示例、三步上手、核心功能、实际截图、开源许可、下载和常见问题。导航栏提供 GitHub 仓库直达链接；默认快捷键及常见问题使用原生折叠区域，无 JavaScript 时也可阅读。

`script.js` 仅用于切换角色配置示例，支持点击和方向键、Home、End，不保存用户配置。页面无需构建工具，也不依赖外部脚本或字体。

网站中的开源说明须与根目录 `LICENSE`、`NOTICE` 保持一致。当前源码为 `GPL-3.0-only`；v1.7.0 等历史 MIT 版本仍适用原许可，不能通过网站文案追溯变更旧版授权。

发布版本时同步更新页面中的版本号、更新说明和 `assets/config-window.png`、`assets/overlay.png`，截图与 `docs/images/` 保持一致。下载入口使用固定的 `D4Helper-windows-latest.zip`，跟随 GitHub 最新正式版。
