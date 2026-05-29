# Xingka Upload 执行拆解（五地区）

## 1. 当前状态

- [x] USA：oss上传、生成hashkey 已完成
- [x] SOUTH AFRICA：oss上传、生成hashkey 已完成
- [x] SAIC VW：oss上传、生成hashkey 已完成
- [ ] MEXICO：待完成 oss上传、生成hashkey
- [ ] FAW-VW：待完成 oss上传、生成hashkey
- [ ] 五个地区 upload_db 待执行（最后统一处理）

---

## 2. 执行原则

1. upload_db 必须放在最后阶段执行。
2. upload_db 不支持并发，必须严格串行（一台机器完成后再执行下一台）。
3. oss上传 与 hashkey 不能同时执行，任一任务中只能有一个动作开关为 True。
4. 任一地区失败时，暂停后续任务，先重试或排障，再继续队列。

---

## 3. 阶段拆解

### 阶段 A：补齐非 DB 任务（可并行，但单地区内必须串行）

- [ ] 机器 A 执行 MEXICO：先 oss上传，成功后再 生成hashkey
- [ ] 机器 B 执行 FAW-VW：先 oss上传，成功后再 生成hashkey
- [ ] 收集并确认两地区输出：oss路径、hashkey、任务日志

### 阶段 B：全量预检查（建议串行核对）

- [ ] 核对 USA 参数与产物完整性
- [ ] 核对 SOUTH AFRICA 参数与产物完整性
- [ ] 核对 SAIC VW 参数与产物完整性
- [ ] 核对 MEXICO 参数与产物完整性
- [ ] 核对 FAW-VW 参数与产物完整性
- [ ] 形成 upload_db 执行队列（5 条）

### 阶段 C：upload_db（严格串行）

推荐顺序：

1. USA
2. SOUTH AFRICA
3. SAIC VW
4. MEXICO
5. FAW-VW

执行规则（每个地区都一样）：

1. 启动 upload_db
2. 等待当前任务完成
3. 查询状态/日志并确认成功
4. 记录任务结果
5. 进入下一个地区

---

## 4. upload_db 串行执行清单

- [ ] USA upload_db
- [ ] SOUTH AFRICA upload_db
- [ ] SAIC VW upload_db
- [ ] MEXICO upload_db
- [ ] FAW-VW upload_db

---

## 5. 任务记录模板（每个地区一行）

| 地区 | 阶段 | 任务ID | 开始时间 | 结束时间 | 状态 | 备注 |
|---|---|---|---|---|---|---|
| USA | upload_db |  |  |  |  |  |
| SOUTH AFRICA | upload_db |  |  |  |  |  |
| SAIC VW | upload_db |  |  |  |  |  |
| MEXICO | upload_db |  |  |  |  |  |
| FAW-VW | upload_db |  |  |  |  |  |

---

## 6. 参数模板（最终版，已删减）

说明：仅保留必要参数。oss、hashkey、upload_db 三个动作开关在一次任务里只能有一个为 True。

### 6.1 OSS 任务参数（先执行）

```python
[
  {"name": "upload_oss", "value": True,  "type": "bool"},
  {"name": "hashkey",    "value": False, "type": "bool"},
  {"name": "upload_db",  "value": False, "type": "bool"},
  {"name": "brand",      "value": "大众", "type": "str"},
  {"name": "region",     "value": "MEXICO", "type": "str"}
]
```

### 6.2 HashKey 任务参数（OSS 成功后执行）

```python
[
  {"name": "upload_oss", "value": False, "type": "bool"},
  {"name": "hashkey",    "value": True,  "type": "bool"},
  {"name": "upload_db",  "value": False, "type": "bool"},
  {"name": "brand",      "value": "大众", "type": "str"},
  {"name": "region",     "value": "MEXICO", "type": "str"}
]
```

### 6.3 Upload DB 参数（最后阶段串行执行）

```python
[
  {"name": "upload_oss", "value": False, "type": "bool"},
  {"name": "hashkey",    "value": False, "type": "bool"},
  {"name": "upload_db",  "value": True,  "type": "bool"},
  {"name": "brand",      "value": "大众", "type": "str"},
  {"name": "region",     "value": "USA", "type": "str"}
]
```

---

## 7. 机器与应用参数

### **accountName**

```python
[
"xk001@ydsjljq",
"xk001-2@ydsjljq",
"xk001-3@ydsjljq",
"xk001-4@ydsjljq",
"xk001-5@ydsjljq",
"xk001-6@ydsjljq",
"xk001-7@ydsjljq",
"xk001-8@ydsjljq",
"xk001-9@ydsjljq",
"xk001-10@ydsjljq",
"xk001-11@ydsjljq",
"xk001-12@ydsjljq",
"xk001-13@ydsjljq",
"xk001-14@ydsjljq",
"xk001-15@ydsjljq",
"xk001-16@ydsjljq",
"xk001-17@ydsjljq",
"xk001-18@ydsjljq",
"xk001-19@ydsjljq",
"xk001-20@ydsjljq",
"xk001-21@ydsjljq",
"xk001-22@ydsjljq",
"xk001-23@ydsjljq",
"xk001-24@ydsjljq",
"xk001-25@ydsjljq",
"xk001-26@ydsjljq",
"xk001-27@ydsjljq",
"xk001-28@ydsjljq",
"xk001-29@ydsjljq",
"xk001-30@ydsjljq",
"xk001-31@ydsjljq",
"xk001-32@ydsjljq",
"xk001-33@ydsjljq",
"xk001-34@ydsjljq",
"xk001-35@ydsjljq",
"xk001-36@ydsjljq",
"xk001-37@ydsjljq",
"xk001-38@ydsjljq",
"xk001-39@ydsjljq",
"xk001-40@ydsjljq",
"xk001-41@ydsjljq",
"xk001-42@ydsjljq",
"xk001-43@ydsjljq",
"xk001-44@ydsjljq",
"xk001-45@ydsjljq",
"xk001-46@ydsjljq",
"xk001-47@ydsjljq",
"xk001-48@ydsjljq",
"xk001-49@ydsjljq",
"xk001-50@ydsjljq",
"xk001-51@ydsjljq",
"xk001-52@ydsjljq",
"xk001-53@ydsjljq",
"xk001-54@ydsjljq",
"xk001-55@ydsjljq",
"xk001-56@ydsjljq",
"xk001-57@ydsjljq",
"xk001-58@ydsjljq",
"xk001-59@ydsjljq",
"xk001-60@ydsjljq",
"xk001-61@ydsjljq",
"xk001-62@ydsjljq",
"xk001-63@ydsjljq",
"xk001-64@ydsjljq",
"xk001-65@ydsjljq",
"xk001-66@ydsjljq",
"xk001-67@ydsjljq",
"xk001-68@ydsjljq",
"xk001-69@ydsjljq",
"xk001-70@ydsjljq",
"xk001-71@ydsjljq",
"xk001-72@ydsjljq",
"xk001-73@ydsjljq",
"xk001-74@ydsjljq",
"xk001-75@ydsjljq",
"xk001-76@ydsjljq",
"xk001-77@ydsjljq",
"xk001-78@ydsjljq",
"xk001-79@ydsjljq",
"xk001-80@ydsjljq",
"xk001-81@ydsjljq",
"xk001-82@ydsjljq",
"xk001-83@ydsjljq",
"xk001-84@ydsjljq",
"xk001-85@ydsjljq",
"xk001-86@ydsjljq",
"xk001-87@ydsjljq",
"xk001-88@ydsjljq",
"xk001-89@ydsjljq",
"xk001-90@ydsjljq"
]
```

### **robotUuid**

```python
fb0da7a2-febe-429f-9b88-66e5e1a3ce9d
```

---

## 8. 可直接运行参数清单（按顺序）

说明：
- 每一步执行时，`upload_oss / hashkey / upload_db` 只能有一个为 `True`
- 阶段 A 可两台机器并行，但单地区必须先 `oss` 再 `hashkey`
- 阶段 C 必须严格串行

### 8.1 阶段 A（补齐 MEXICO、FAW-VW）

1. `MEXICO - OSS`
```python
[
  {"name": "upload_oss", "value": True,  "type": "bool"},
  {"name": "hashkey",    "value": False, "type": "bool"},
  {"name": "upload_db",  "value": False, "type": "bool"},
  {"name": "brand",      "value": "大众", "type": "str"},
  {"name": "region",     "value": "MEXICO", "type": "str"}
]
```

2. `MEXICO - HashKey`（仅在上一步成功后执行）
```python
[
  {"name": "upload_oss", "value": False, "type": "bool"},
  {"name": "hashkey",    "value": True,  "type": "bool"},
  {"name": "upload_db",  "value": False, "type": "bool"},
  {"name": "brand",      "value": "大众", "type": "str"},
  {"name": "region",     "value": "MEXICO", "type": "str"}
]
```

3. `FAW-VW - OSS`
```python
[
  {"name": "upload_oss", "value": True,  "type": "bool"},
  {"name": "hashkey",    "value": False, "type": "bool"},
  {"name": "upload_db",  "value": False, "type": "bool"},
  {"name": "brand",      "value": "大众", "type": "str"},
  {"name": "region",     "value": "FAW-VW", "type": "str"}
]
```

4. `FAW-VW - HashKey`（仅在上一步成功后执行）
```python
[
  {"name": "upload_oss", "value": False, "type": "bool"},
  {"name": "hashkey",    "value": True,  "type": "bool"},
  {"name": "upload_db",  "value": False, "type": "bool"},
  {"name": "brand",      "value": "大众", "type": "str"},
  {"name": "region",     "value": "FAW-VW", "type": "str"}
]
```

### 8.2 阶段 C（upload_db 串行，按以下 5 步）

1. `USA - upload_db`
```python
[
  {"name": "upload_oss", "value": False, "type": "bool"},
  {"name": "hashkey",    "value": False, "type": "bool"},
  {"name": "upload_db",  "value": True,  "type": "bool"},
  {"name": "brand",      "value": "大众", "type": "str"},
  {"name": "region",     "value": "USA", "type": "str"}
]
```

2. `SOUTH AFRICA - upload_db`
```python
[
  {"name": "upload_oss", "value": False, "type": "bool"},
  {"name": "hashkey",    "value": False, "type": "bool"},
  {"name": "upload_db",  "value": True,  "type": "bool"},
  {"name": "brand",      "value": "大众", "type": "str"},
  {"name": "region",     "value": "SOUTH AFRICA", "type": "str"}
]
```

3. `SAIC VW - upload_db`
```python
[
  {"name": "upload_oss", "value": False, "type": "bool"},
  {"name": "hashkey",    "value": False, "type": "bool"},
  {"name": "upload_db",  "value": True,  "type": "bool"},
  {"name": "brand",      "value": "大众", "type": "str"},
  {"name": "region",     "value": "SAIC VW", "type": "str"}
]
```

4. `MEXICO - upload_db`
```python
[
  {"name": "upload_oss", "value": False, "type": "bool"},
  {"name": "hashkey",    "value": False, "type": "bool"},
  {"name": "upload_db",  "value": True,  "type": "bool"},
  {"name": "brand",      "value": "大众", "type": "str"},
  {"name": "region",     "value": "MEXICO", "type": "str"}
]
```

5. `FAW-VW - upload_db`
```python
[
  {"name": "upload_oss", "value": False, "type": "bool"},
  {"name": "hashkey",    "value": False, "type": "bool"},
  {"name": "upload_db",  "value": True,  "type": "bool"},
  {"name": "brand",      "value": "大众", "type": "str"},
  {"name": "region",     "value": "FAW-VW", "type": "str"}
]
```

---

## 9. 旧版启动方式（已下线）

### 9.1 启动前

确保 `.env` 已配置以下关键项：

- `CONSOLE_ACCESS_KEY_ID`
- `CONSOLE_ACCESS_SECRET`
- `CONSOLE_HOST`
- `FEISHU_WEBHOOK_URL`
- `FEISHU_SECRET`
- `ROBOT_UUID`
- `ACCOUNT_NAMES`
- `TASK_STATE_FILE`（默认 `.task_state.json`）
- `TASK_EVENT_FILE`（默认 `.task_events.jsonl`）
- `MONITOR_PORT`（默认 `8787`）

旧版根目录启动方式已移除：`scheduler.py`、`monitor_server.py`、`ui-dashboard.html` 不再作为运行入口。

当前仅支持第 11 节的前后端分离启动方式。

---

## 10. 新调度模式（唯一生效）

> 从当前版本开始，仅保留新调度架构，旧兼容逻辑已移除。

### 10.1 执行规则

1. `oss` 阶段：并发执行（`PARALLEL_REGIONS` × `ACCOUNT_NAMES`）
2. `hashkey` 阶段：并发执行（同上），仅在 `oss` 全量完成后开始
3. `upload_db` 阶段：严格串行（同一时刻仅一台机器）
4. 失败自动重试：重试次数由 `MAX_RETRIES` 控制

### 10.2 必要环境变量（新增）

- `MAX_RETRIES`：失败自动重试次数（默认 `2`）
- `PARALLEL_REGIONS`：并发阶段地区（默认 `USA,SOUTH AFRICA,SAIC VW,MEXICO,FAW-VW`）
- `UPLOAD_DB_REGIONS`：`upload_db` 串行地区顺序（默认 `USA,SOUTH AFRICA,SAIC VW,MEXICO,FAW-VW`）
- `SCHEDULER_ONLY_UPLOAD_DB`：设为 `true` 时仅执行 `upload_db` 阶段（不调度 `oss/hashkey`）

### 10.3 状态文件格式（仅新格式）

`TASK_STATE_FILE`（默认 `.task_state.json`）的 `inflight` 必须是数组，且每个元素必须有 `work_id`：

```json
{
  "brand": "大众",
  "brands": ["大众"],
  "stage_index": 0,
  "stage_name": "oss",
  "parallel_regions": ["MEXICO", "FAW-VW"],
  "upload_regions": ["USA", "SOUTH AFRICA", "SAIC VW", "MEXICO", "FAW-VW"],
  "accounts": ["xk001@ydsjljq"],
  "done": ["大众|MEXICO:oss:xk001@ydsjljq"],
  "failed": [],
  "attempts": {"大众|MEXICO:oss:xk001@ydsjljq": 1},
  "inflight": [
    {
      "brand": "大众",
      "work_id": "大众|MEXICO:oss:xk001-2@ydsjljq",
      "task": {"brand": "大众", "region": "MEXICO", "action": "oss"},
      "region": "MEXICO",
      "action": "oss",
      "account": "xk001-2@ydsjljq",
      "job_uuid": "xxxx",
      "attempt": 1,
      "started_at": 1776410653
    }
  ]
}
```

### 10.4 升级注意事项

- 旧格式状态文件（例如 `inflight` 为对象、没有 `work_id`）不再支持。
- 如果启动时报状态格式错误，请删除旧的 `TASK_STATE_FILE` 后重启后端服务。

---

## 11. 前后端分离启动方式（Vue3 + FastAPI）

目录结构：

- `frontend/`：Vue3 + Vite + Naive UI + Pinia
- `backend/`：FastAPI（使用 `uv` 管理依赖）

当前生效架构：

1. `backend`：提供 API + SSE，并内置调度器线程
2. `frontend`：展示看板（通过 `/api` 访问后端）
3. 调度逻辑与控制台接口已全部内聚到 `backend/app/services/`

### 11.1 启动后端（终端 1）

```bash
cd backend
uv sync
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

说明：

- 后端启动时会自动内置启动调度器（`BACKEND_EMBED_SCHEDULER=true`，默认开启）。
- 不需要也不能再额外运行根目录调度脚本（已下线）。

接口地址：

```text
http://127.0.0.1:8000/api/v1/overview
```

调度器状态接口：

```text
http://127.0.0.1:8000/api/v1/scheduler/status
```

### 11.2 启动前端（终端 2）

```bash
cd frontend
npm install
npm run dev
```

访问地址：

```text
http://127.0.0.1:5173
```

> 前端已配置 Vite 代理：`/api` -> `http://127.0.0.1:8000`。

### 11.3 后端接口清单

- `GET /api/v1/health`：健康检查
- `GET /api/v1/overview`：看板汇总数据
- `GET /api/v1/plan`：执行计划表
- `GET /api/v1/events`：事件列表（支持 `limit`）
- `GET /api/v1/events/stream`：事件流（SSE）
- `GET /api/v1/scheduler/status`：内置调度器运行状态

### 11.4 前后端分离必要环境变量（新增）

- `BACKEND_EMBED_SCHEDULER`：是否由后端内置启动调度器（默认 `true`）
- `BACKEND_HOST`：后端监听地址（默认 `0.0.0.0`）
- `BACKEND_PORT`：后端监听端口（默认 `8000`）
- `BACKEND_CORS_ORIGINS`：后端跨域白名单（逗号分隔）
