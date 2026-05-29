# 前后端启动方式（当前唯一生效）

## 1. 架构说明

1. `backend/`：FastAPI API 服务，内置调度器（Scheduler）。
2. `frontend/`：Vue3 + Vite + Pinia + Naive UI 看板。
3. 根目录旧入口已下线：`scheduler.py`、`monitor_server.py`、`ui-dashboard.html`。

## 2. 启动后端

后端环境变量文件放在 `backend/.env`。第一次部署可以从模板复制：

```powershell
cd backend
Copy-Item .env.example .env
```

```powershell
cd backend
uv sync
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

后端启动后不会自动开始调度，请在看板点击“开启全局调度”。

## 3. 启动前端

```powershell
cd frontend
npm install
npm run dev
```

## 4. 访问地址

1. 前端看板：`http://127.0.0.1:5173`
2. 概览接口：`http://127.0.0.1:8000/api/v1/overview`
3. 调度状态：`http://127.0.0.1:8000/api/v1/scheduler/status`

## 5. 关键环境变量

1. `BACKEND_EMBED_SCHEDULER=true`
2. `BRAND`（当前单品牌）
3. `PARALLEL_REGIONS`（当前品牌要执行的地区）
4. `ACCOUNT_NAMES`（参与调度的机器账号）
5. `POLL_SECONDS`（轮询间隔）
6. `MAX_RETRIES`（失败重试次数）
7. `MAX_PARALLEL_OSS`（upload_oss 并发）
8. `MAX_PARALLEL_HASHKEY`（hashkey 并发）
9. `MAX_PARALLEL_UPLOAD_MERGED_FILE`（upload_merged_file 并发）

## 6. 注意事项

1. 修改并发、地区、重试等 `backend/.env` 配置后，重启后端生效。
2. 不要再尝试运行根目录旧调度脚本，避免误解与重复调度。
3. 后端测试放在 `backend/tests/`，运行方式：

```powershell
cd backend
uv run python -m unittest discover -s tests
```
