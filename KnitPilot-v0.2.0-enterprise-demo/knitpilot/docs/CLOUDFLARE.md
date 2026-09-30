# KnitPilot 企业演示：Cloudflare 部署

部署为一个 Python Worker，静态网页由 Workers Static Assets 提供。首页跳转 `/demo/`；网页通过同源 `/v1/calculate` 和 `/v1/operations/preview` 使用共享 Python 引擎。无需另开数据库。当前版本没有真实 OCR、用户账号或持久化历史版本。

## 1. 先上传部署补丁

当前 GitHub 仓库是 `qianxia0629-maker/knitpilot-demo`。项目位于：

`KnitPilot-v0.2.0-enterprise-demo/knitpilot/`

打开该目录，选择 **Add file → Upload files**。把部署补丁 ZIP 解压后，进入 `cloudflare-patch` 文件夹，将其中的文件和文件夹全部拖到上传区域，提交到 `main`。不要拖整个 `cloudflare-patch` 外层文件夹，也不要上传 ZIP 本身。

补丁替换 `apps/api/main.py`、`apps/web/package.json` 等文件，新增 `deploy/cloudflare/`、`scripts/` 和部署文档。不要删除原有 `packages/` 和 `fixtures/`。

提交后，应能在项目目录中看到 `scripts/cloudflare_build.sh` 与 `deploy/cloudflare/wrangler.jsonc`。如果以后把项目移到仓库根目录，则下一步的根目录填 `/`。

## 2. 创建 Worker

进入 [Cloudflare Dashboard](https://dash.cloudflare.com/)，选择 **Workers & Pages → Create application → 导入 Git 仓库**（界面也可能标为 Connect Git / Import a repository），授权 Cloudflare 读取 GitHub 仓库并选择 `knitpilot-demo`。创建 **Worker**，使用 Git 构建。

| 设置 | 值 |
| --- | --- |
| 项目 / Worker 名称 | `knitpilot-demo`（与 wrangler.jsonc 一致） |
| 生产分支 | `main` |
| Root directory / 根目录 | `KnitPilot-v0.2.0-enterprise-demo/knitpilot` |
| Build command / 构建命令 | `bash scripts/cloudflare_build.sh` |
| Deploy command / 部署命令 | `bash scripts/cloudflare_deploy.sh` |

如名称已被同账号占用，先修改 `deploy/cloudflare/wrangler.jsonc` 的 `name`，并让面板项目名称一致。

在 **Build variables**（构建变量）中填写：

| 名称 | 值 |
| --- | --- |
| `PYTHON_VERSION` | `3.13` |
| `NODE_VERSION` | `22` |
| `SKIP_DEPENDENCY_INSTALL` | `1` |

脚本自行安装网页依赖与 uv。部署时 uv 使用独立的 `deploy/cloudflare/pyproject.toml` 和 `uv.lock`，只打包 FastAPI / Pydantic 等运行依赖，不将 Uvicorn、Postgres 驱动或测试工具放入 Worker。构建变量控制构建过程，不能代替运行时访问码。

点击部署，等待构建完成。Cloudflare 会提供实际的 `workers.dev` 网址。首次访问可能能打开页面但无法计算，需要配置下一步访问码。

## 3. 配置试用访问码

在该 Worker 的 **Settings → Variables and Secrets** 添加：

| 类型 | 名称 | 值 |
| --- | --- | --- |
| Secret | `KNITPILOT_DEMO_TOKEN` | 自己设置的随机英文字母与数字组成的访问码 |

保存并按面板提示部署新版本。`KNITPILOT_REQUIRE_DEMO_TOKEN=1` 已在代码配置中开启，未设置访问码时计算接口返回 503，码不正确时返回 401。网页是公开演示入口，访问码只保护计算和修改预览接口。请将码单独发给试用人员；不要写入 GitHub 或聊天。

## 4. 验收

1. 打开实际网址，确认进入 `/demo/`，样式和 SVG 技术图正常。
2. `/health` 应返回 `{"status":"ok"}`。
3. 填访问码，点击“生成工艺初稿”。默认样例预期后片起针 122、衣长 200 转，QC 通过。
4. 胸宽改成 60 cm 后重新计算，针数应随引擎重算；点击技术图袖窿、领窝查看工艺，再下载 JSON 草稿。
5. 用错误访问码试算，确认拒绝；不要用真实企业敏感数据做首次验收。

## 开发者本地检查

```bash
npm --prefix apps/web ci
npm --prefix apps/web run build
python scripts/prepare_cloudflare.py
cd deploy/cloudflare
uv run --python 3.13 --locked pywrangler deploy --dry-run
uv run --python 3.13 --locked pywrangler dev
```

本地访问码可在 `deploy/cloudflare/.dev.vars` 写 `KNITPILOT_DEMO_TOKEN="local-demo"`；该文件不提交。打包检查不等于线上验收，只有 Cloudflare 部署成功后才有可分享的试用网址。

## 常见失败

- 找不到 `scripts/cloudflare_build.sh`：根目录填错，或补丁被多套了一层目录。
- `uv` / `pywrangler` 依赖问题：贴构建日志中的第一条具体错误，确认 Python 构建变量是 3.13。
- 页面样式或样例缺失：确认构建日志包含 `Cloudflare bundle prepared`；不要直接上传未经构建的 Next.js 源码作为静态资产。
- 页面能开、试算返回 503：运行时 Secret 尚未设置；返回 401：访问码错误。
- GitHub 授权看不到仓库：在 Cloudflare 的 GitHub 安装设置中允许读取 `knitpilot-demo`。

参考：[Python Workers / FastAPI](https://developers.cloudflare.com/workers/languages/python/packages/fastapi/)、[Workers Builds 配置](https://developers.cloudflare.com/workers/ci-cd/builds/configuration/)、[构建镜像](https://developers.cloudflare.com/workers/ci-cd/builds/build-image/)。

## 本次交付验证（2026-09-30）

- CPython 3.13 下 74 项测试通过；计算引擎含分支覆盖率 99.23%。
- Next.js Webpack 生产构建、TypeScript 检查通过。
- Wrangler 4.144.0 / workers-py 1.17.5 的部署 dry-run 成功，已包含共享 Python 模块与静态资产。
- 本地 workerd 无法解析其 Python 运行时下载域名，未完成真实 Workers 运行时验收；尚未发布到 Cloudflare。面板部署后仍需执行以上线上验收步骤。
