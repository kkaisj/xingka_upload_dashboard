# 星卡任务看板使用文档

## 1. 项目用途

本项目用于调度影刀/云扩机器人批量执行上传任务，并通过 Web 看板实时查看执行进度、机器人状态和事件流。

当前任务流程为单品牌、按地区顺序执行：

```text
地区 1: upload_oss -> hashkey -> upload_merged_file
地区 2: upload_oss -> hashkey -> upload_merged_file
...
```

三个阶段含义：

1. `upload_oss`：上传图片到 OSS。
2. `hashkey`：生成 hashkey。
3. `upload_merged_file`：上传合并文件到 OSS。

## 2. 目录说明

```text
xingka_upload/
├─ backend/                 # FastAPI 后端，内置调度器
│  ├─ .env                  # 后端真实配置，不要提交
│  ├─ .env.example          # 配置模板，可提交
│  ├─ app/
│  │  ├─ api/v1/            # API 路由
│  │  ├─ core/config.py     # 后端配置读取
│  │  └─ services/          # 调度、看板数据、飞书通知、影刀接口
│  └─ tests/                # 后端测试
├─ frontend/                # Vue3 + Vite + Pinia + Naive UI 前端
├─ .task_state.json         # 当前任务状态
├─ .task_events.jsonl       # 事件流历史
├─ startup.md               # 启动方式
└─ usage.md                 # 本使用文档
```

## 3. 首次配置

进入后端目录，复制配置模板：

```powershell
cd backend
Copy-Item .env.example .env
```

然后编辑：

```text
backend/.env
```

不要把真实 `.env` 提交到代码仓库。

## 4. 必填配置

### 平台接口

```env
CONSOLE_ACCESS_KEY_ID=
CONSOLE_ACCESS_SECRET=
CONSOLE_HOST=https://api.yingdao.com/
ROBOT_UUID=
```

说明：

1. `CONSOLE_ACCESS_KEY_ID`：控制台 access key id。
2. `CONSOLE_ACCESS_SECRET`：控制台 access secret。
3. `CONSOLE_HOST`：平台接口地址。
4. `ROBOT_UUID`：要调度的应用 UUID。

### 飞书通知

```env
FEISHU_WEBHOOK_URL=
FEISHU_SECRET=
```

通知会以飞书卡片发送：

1. 任务启动：蓝色。
2. 任务完成：绿色。
3. 任务重试：橙色。
4. 任务失败：红色。

### 当前品牌

```env
BRAND=奥迪
```

当前系统按单品牌运行。切换品牌时，修改 `BRAND`，再按需要调整地区和状态文件。

### 地区配置

```env
PARALLEL_REGIONS=ARGENTINA,BRAZIL,FAW-VW,MEXICO,SAIC VW,SOUTH AFRICA,USA
REGION_CATALOG=ARGENTINA,BRAZIL,FAW-VW,MEXICO,SAIC VW,SOUTH AFRICA,USA
```

说明：

1. `PARALLEL_REGIONS`：本次调度真正要跑的地区，顺序会影响执行顺序。
2. `REGION_CATALOG`：前端配置页展示用的地区目录。

如果要新增地区，需要同时确认：

1. 平台任务参数支持该地区名称。
2. `PARALLEL_REGIONS` 包含该地区。
3. `REGION_CATALOG` 包含该地区，方便前端展示。

### 机器配置

```env
ACCOUNT_NAMES=xk001@ydsjljq,xk001-2@ydsjljq
```

说明：

1. 这里填写参与调度的机器人账号，逗号分隔。
2. 数量不固定，可以少于或多于 90 台。
3. 调度器会按这里的账号列表生成每个阶段的机器任务。

## 5. 并发和重试配置

```env
POLL_SECONDS=20
MAX_RETRIES=3
MAX_PARALLEL_OSS=10
MAX_PARALLEL_HASHKEY=90
MAX_PARALLEL_UPLOAD_MERGED_FILE=10
```

说明：

1. `POLL_SECONDS`：每隔多少秒查询一次任务状态。
2. `MAX_RETRIES`：失败后最多重试次数。`3` 表示最多重试 3 次，加首次执行最多 4 次。
3. `MAX_PARALLEL_OSS`：`upload_oss` 阶段最大并发机器数。
4. `MAX_PARALLEL_HASHKEY`：`hashkey` 阶段最大并发机器数。
5. `MAX_PARALLEL_UPLOAD_MERGED_FILE`：`upload_merged_file` 阶段最大并发机器数。

如果平台或容器容易失败，优先降低：

1. `MAX_PARALLEL_OSS`
2. `MAX_PARALLEL_UPLOAD_MERGED_FILE`

## 6. 启动服务

后端：

```powershell
cd backend
uv sync
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

前端：

```powershell
cd frontend
npm install
npm run dev
```

访问：

```text
http://127.0.0.1:5173
```

后端启动后不会自动开始调度。需要在看板点击：

```text
开启全局调度
```

## 7. 调度如何判断任务完成

核心代码在：

```text
backend/app/services/scheduler_engine.py
```

运行循环在 `Scheduler.run_forever()`：

```text
1. _poll_inflight()        查询运行中的任务
2. _advance_stage_if_ready() 判断当前阶段是否全部完成
3. _start_stage_work()     启动下一批任务
4. 等待 POLL_SECONDS 秒
5. 继续循环
```

### inflight

`.task_state.json` 里的 `inflight` 表示已经启动、但还没有终态结果的任务。

每条记录大概包含：

```json
{
  "brand": "奥迪",
  "work_id": "奥迪|BRAZIL:upload_oss:xk001-19@ydsjljq",
  "region": "BRAZIL",
  "action": "upload_oss",
  "account": "xk001-19@ydsjljq",
  "job_uuid": "xxx",
  "attempt": 1,
  "started_at": 1778728692
}
```

### done

`.task_state.json` 里的 `done` 表示已经成功完成的机器任务。

格式：

```text
品牌|地区:阶段:机器账号
```

示例：

```text
奥迪|BRAZIL:upload_oss:xk001-11@ydsjljq
```

### failed

`.task_state.json` 里的 `failed` 表示超过重试上限后仍失败的任务。

如果某个阶段存在 failed，调度器不会继续推进到下一阶段，需要先处理失败任务。

## 8. 状态码规则

调度器认为以下状态是未完成：

```text
created
waiting
running
stopping
```

调度器认为以下状态是终态：

```text
finish
stopped
error
skipped
cancel
```

其中只有：

```text
finish
```

会进入 `done`。

其他终态会进入重试逻辑，超过上限后进入 `failed`。

## 9. 切换品牌

推荐流程：

1. 确认当前品牌已经全部跑完。
2. 备份当前状态文件：

```powershell
Copy-Item .task_state.json ".task_state.<品牌名>.backup.json"
Copy-Item .task_events.jsonl ".task_events.<品牌名>.backup.jsonl"
```

3. 修改 `backend/.env`：

```env
BRAND=新品牌
PARALLEL_REGIONS=新地区1,新地区2
REGION_CATALOG=新地区1,新地区2
ACCOUNT_NAMES=新机器1,新机器2
```

4. 如需从零开始新品牌，清空或重命名旧状态文件：

```powershell
Rename-Item .task_state.json ".task_state.old.json"
Rename-Item .task_events.jsonl ".task_events.old.jsonl"
```

5. 重启后端。
6. 打开看板，确认执行计划正确。
7. 点击“开启全局调度”。

## 10. 手动跳过已完成任务

如果某些任务已经在平台完成，但状态文件里没有记录，可以使用：

```env
PRECOMPLETED_TASKS=
```

格式：

```text
地区:阶段,地区:阶段
```

示例：

```env
PRECOMPLETED_TASKS=USA:upload_oss,USA:hashkey
```

注意：

1. 阶段名必须是 `upload_oss`、`hashkey`、`upload_merged_file`。
2. 不建议写旧名称 `oss`，调度器不会识别。
3. 这会把该地区该阶段下所有配置机器都标记为完成。

## 11. 常见操作

### 查看调度状态

```text
http://127.0.0.1:8000/api/v1/scheduler/status
```

### 查看概览数据

```text
http://127.0.0.1:8000/api/v1/overview
```

### 重启后端

关闭当前后端进程后重新执行：

```powershell
cd backend
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 运行测试

```powershell
cd backend
uv run python -m unittest discover -s tests
```

## 12. 故障处理

### 看板没有启动任务

检查：

1. 是否点击了“开启全局调度”。
2. `BACKEND_EMBED_SCHEDULER=true`。
3. `ACCOUNT_NAMES` 不为空。
4. `ROBOT_UUID` 是否正确。
5. 平台机器人是否是 `idle`。
6. `.task_state.json` 是否已有 `failed` 阻塞当前阶段。

### 任务一直在 inflight

可能原因：

1. 平台接口查询不到终态。
2. `job_uuid` 对应任务仍在运行。
3. 网络异常导致轮询失败。
4. 后端服务中断后没有继续轮询。

处理方式：

1. 在平台确认该 `job_uuid` 实际状态。
2. 如果确实已完成但本地没有更新，可以等待下一轮轮询。
3. 如果长期异常，先备份 `.task_state.json`，再手动修正对应记录。

### 出现 failed

处理方式：

1. 查看 `.task_events.jsonl` 找失败原因和机器账号。
2. 在平台确认该机器是否异常。
3. 修复后，如果要重新跑，需要从 `.task_state.json` 的 `failed` 中移除对应 `work_id`。
4. 重启后端或等待调度循环继续。

### 飞书通知乱码

当前发送时使用：

```text
Content-Type: application/json; charset=utf-8
```

如果仍乱码，优先确认：

1. `.env` 文件是 UTF-8。
2. Windows 终端编码不会影响 HTTP 请求体。
3. 飞书机器人 webhook 和密钥是否正确。

## 13. 不建议随意修改的文件

调度相关核心文件：

```text
backend/app/services/scheduler_engine.py
backend/app/services/embedded_scheduler.py
backend/app/services/rpa_console.py
backend/app/services/overview_service.py
```

如果要改调度顺序、重试策略、并发策略，建议先补测试：

```text
backend/tests/test_scheduler.py
```

再改实现。
