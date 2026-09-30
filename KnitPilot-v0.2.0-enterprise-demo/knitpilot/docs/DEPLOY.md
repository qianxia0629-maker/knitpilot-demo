# KnitPilot API 演示部署

## 当前可上线内容

这是无数据库的企业试用演示：`/demo/` 是 Next.js 静态界面；`/health`、`/docs`、`POST /v1/calculate` 和 `POST /v1/operations/preview` 由 FastAPI 提供。可手动修改确认尺寸、密度和机台参数，查看 SVG 技术图、QC 与 JSON 草稿。还没有真实文件识别、账号体系和持久化；请只用非敏感测试数据试用。共享访问码只是演示入口，不能替代正式多租户鉴权。

## Cloudflare（当前部署路径）

请按 `docs/CLOUDFLARE.md` 使用 Workers Git 构建。网页和 Python 计算 API 同源部署，使用现有确定性计算引擎。

## 备选：Render Web Service

仓库根目录有 `render.yaml` 和 `Dockerfile`：多阶段构建 Next.js 静态界面与 Python API，免费 Web Service 使用 `/health` 健康检查。先将整个 `knitpilot/` 内容推到 GitHub 仓库根目录，然后在 Render Dashboard 中选择 **New → Blueprint**，连接仓库并应用配置。首次创建时 Render 会要求填写 `KNITPILOT_DEMO_TOKEN`；请设置随机且不易猜到的演示访问码，仅向试用人员单独提供。服务名称 `knitpilot-api` 如被占用，可先修改。无状态演示不用开数据库。

部署完成后，用 Render 实际提供的 `https://<service>.onrender.com` 检查：

1. `/health` 应返回 `{"status":"ok"}`；`/demo/` 应显示网页界面。
2. 在界面填写演示访问码并点击“生成工艺初稿”。示例预期后片起针 122、衣长 200 转，QC 全部通过。
3. 修改胸宽为 60 cm，重新生成，检查起针变化及 QC；在前片技术图点击袖窿/领窝，查看对应工艺参数；下载 JSON 草稿。
4. `/docs` 可供研发核对接口；调用计算接口需请求头 `X-Demo-Token`。

免费实例闲置一段时间会休眠，首次访问可能需要等待。免费服务文件系统不持久，当前 API 不存储状态。正式上线前需要个人账号、版本数据库、组织隔离、速率限制、生产数据治理和工厂验证。企业试用应明确这是非生产演示。

## 本地或容器前验收

```bash
python -m pip install -e '.[dev]'
python -m pytest -q --cov=packages.engine --cov-branch --cov-fail-under=90
cd apps/web && npm ci && npm run build && cd ../..
KNITPILOT_DEMO_TOKEN=local-demo uvicorn apps.api.main:app --host 0.0.0.0 --port 8000
```

另开终端执行 `curl http://127.0.0.1:8000/health`。不应在仓库或聊天中粘贴部署平台密钥。
