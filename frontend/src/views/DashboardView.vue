<template>
  <div class="layout">
    <aside class="sidebar">
      <div class="brand">
        <div class="logo">X</div>
        <div>
          <h1>Xingka</h1>
          <p>Task Monitor</p>
        </div>
      </div>
      <nav class="nav">
        <div class="nav-item" :class="{ active: activeView === 'overview' }" @click="activeView = 'overview'">实时总览</div>
        <div class="nav-item" :class="{ active: activeView === 'config' }" @click="activeView = 'config'">全局配置</div>
      </nav>
    </aside>

    <main class="main">
      <header class="header">
        <div class="title">上传任务监控看板</div>
        <div class="sync">
          <span class="dot" />
          <span>最近刷新 {{ updatedAtText }}</span>
          <n-tag :type="schedulerStatusType" size="small">
            {{ schedulerStatusLabel }}
          </n-tag>
          <n-button size="small" type="primary" :disabled="!!store.schedulerStatus?.active" @click="startScheduler">
            {{ store.schedulerStatus?.active ? '全局调度已开启' : '开启全局调度' }}
          </n-button>
          <n-button size="small" tertiary @click="refreshAll">刷新</n-button>
        </div>
      </header>

      <section v-if="activeView === 'overview'" class="content">
        <article class="card next-card">
          <div class="panel-title">下一批任务</div>
          <div v-if="nextTask" class="next-task">
            <div class="next-main">{{ nextTask.region }} / {{ actionLabel(nextTask.action) }}</div>
            <div class="next-sub">
              待启动 {{ nextTask.pending_count }}，运行中 {{ nextTask.running_count }}，已完成 {{ nextTask.done_count }}，并发上限 {{ nextParallelLimit }}
            </div>
          </div>
          <div v-else class="next-sub">当前没有待执行任务</div>
        </article>

        <div class="cards">
          <article class="card metric-card">
            <div class="metric-label">当前品牌</div>
            <div class="metric-value accent-copper">{{ currentBrandLabel }}</div>
          </article>
          <article class="card metric-card">
            <div class="metric-label">当前阶段</div>
            <div class="metric-value accent-copper">{{ stageName }}</div>
          </article>
          <article class="card metric-card">
            <div class="metric-label">Upload OSS 阶段</div>
            <div class="metric-value accent-blue">{{ oss.done }}/{{ oss.total }}</div>
            <div class="metric-detail">运行 {{ oss.running }} 完成 {{ oss.done }} 失败 {{ oss.failed }}</div>
          </article>
          <article class="card metric-card">
            <div class="metric-label">Hashkey 阶段</div>
            <div class="metric-value accent-green">{{ hashkey.done }}/{{ hashkey.total }}</div>
            <div class="metric-detail">运行 {{ hashkey.running }} 完成 {{ hashkey.done }} 失败 {{ hashkey.failed }}</div>
          </article>
          <article class="card metric-card">
            <div class="metric-label">Upload Merged File 阶段</div>
            <div class="metric-value accent-amber">{{ uploadMergedFile.done }}/{{ uploadMergedFile.total }}</div>
            <div class="metric-detail">运行 {{ uploadMergedFile.running }} 完成 {{ uploadMergedFile.done }} 失败 {{ uploadMergedFile.failed }}</div>
          </article>
          <article class="card metric-card">
            <div class="metric-label">全局完成率</div>
            <div class="metric-value accent-copper">{{ Math.floor(workSummary.progress || 0) }}%</div>
            <div class="metric-detail">总量 {{ workSummary.total || 0 }}</div>
          </article>
        </div>

        <article class="card">
          <div class="panel-title">总进度</div>
          <div class="bar-wrap">
            <div class="bar" :style="{ width: `${Math.floor(workSummary.progress || 0)}%` }" />
          </div>
        </article>

        <article class="card">
          <div class="panel-title">阶段筛选</div>
          <div class="stage-switch">
            <n-button size="small" :type="store.selectedStage === 'all' ? 'primary' : 'default'" @click="store.setStage('all')">全部</n-button>
            <n-button size="small" :type="store.selectedStage === 'upload_oss' ? 'primary' : 'default'" @click="store.setStage('upload_oss')">Upload OSS</n-button>
            <n-button size="small" :type="store.selectedStage === 'hashkey' ? 'primary' : 'default'" @click="store.setStage('hashkey')">Hashkey</n-button>
            <n-button size="small" :type="store.selectedStage === 'upload_merged_file' ? 'primary' : 'default'" @click="store.setStage('upload_merged_file')">Upload Merged File</n-button>
          </div>
        </article>

        <article class="card">
          <div class="panel-title">机器人状态（当前配置机器）</div>
          <n-data-table :columns="robotColumns" :data="store.robots" :bordered="false" size="small" :max-height="300" />
        </article>

        <div class="grid-2">
          <article class="card plan-panel">
            <div class="panel-title">执行计划（当前查看品牌）</div>
            <n-data-table
              :columns="columns"
              :data="store.plan"
              :bordered="false"
              size="small"
              :pagination="{ pageSize: 30 }"
              :max-height="520"
              :scroll-x="1120"
            />
          </article>

          <article class="card event-panel">
            <div class="panel-title">事件流（当前查看品牌）</div>
            <n-scrollbar class="event-scrollbar">
              <ul class="events">
                <li v-for="(item, idx) in store.events" :key="`${item.work_id || idx}`" class="event">
                  <div class="event-top">
                    <span class="event-title">
                      <n-tag size="small" :type="eventType(item.type)">{{ eventTypeLabel(item.type) }}</n-tag>
                    </span>
                    <span class="event-time">{{ formatTime(item.ts) }}</span>
                  </div>
                  <div class="event-sub">
                    {{ item.brand || '-' }} / {{ item.region || '-' }} / {{ actionLabel(item.action) }} / {{ item.account || '-' }}
                  </div>
                  <div class="event-meta">{{ item.status || item.job_uuid || '-' }}</div>
                </li>
              </ul>
            </n-scrollbar>
          </article>
        </div>
      </section>

      <section v-else class="content">
        <article class="card">
          <div class="panel-title">全局配置（单品牌）</div>

          <div class="config-tip">
            <div>参数规则：</div>
            <div>1. 上传 OSS：`upload_oss=true` + `brand` + `region`</div>
            <div>2. 生成 Hashkey：`hashkey=true` + `brand` + `region`</div>
            <div>3. 上传合并文件：`upload_merged_file=true` + `brand` + `region`</div>
          </div>

          <div class="db-map-box">
            <div class="db-map-head">
              <div class="db-map-title">切换运行品牌</div>
              <n-tag size="small" type="info">当前：{{ configDraft.BRAND || '--' }}</n-tag>
            </div>
            <div class="brand-switch-row">
              <label class="cfg-item">
                <span>选择品牌档案</span>
                <n-select
                  v-model:value="selectedSwitchBrand"
                  class="brand-select"
                  :options="brandSelectOptions"
                  placeholder="请选择品牌"
                  size="large"
                  filterable
                />
              </label>
              <label class="region-check-item reset-check">
                <input v-model="switchResetProgress" type="checkbox" />
                <span>切换时重置该品牌进度</span>
              </label>
              <n-button type="primary" :disabled="!selectedSwitchBrand" @click="openSwitchBrandConfirm">切换当前运行品牌</n-button>
            </div>
            <div class="hint">切换后会自动同步该品牌的地区到当前调度配置。</div>
          </div>

          <div class="db-map-box">
            <div class="db-map-head">
              <div class="db-map-title">品牌配置档案</div>
              <div class="stage-switch">
                <n-button size="small" @click="addBrandProfileRow">新增品牌</n-button>
                <n-button size="small" type="primary" @click="saveBrandProfileDraft">保存档案</n-button>
              </div>
            </div>
            <div class="brand-profile-layout">
              <aside class="brand-profile-list">
                <button
                  v-for="row in brandProfileRows"
                  :key="row.id"
                  class="brand-profile-tab"
                  :class="{ active: row.id === activeBrandProfileId }"
                  @click="activeBrandProfileId = row.id"
                >
                  {{ row.brand || '未命名品牌' }}
                </button>
              </aside>
              <section class="brand-profile-editor">
                <template v-if="activeBrandProfile">
                  <label class="cfg-item">
                    <span>品牌名称</span>
                    <input v-model="activeBrandProfile.brand" placeholder="例如：大众" />
                  </label>
                  <div class="region-toolbar">
                    <n-button size="tiny" @click="addActiveBrandRegion">新增地区</n-button>
                    <n-button size="tiny" tertiary @click="removeActiveBrandProfile">删除品牌</n-button>
                  </div>
                  <div class="db-map-table brand-region-table">
                    <div class="db-map-row db-map-header db-map-row-2">
                      <div>地区名称</div>
                      <div>操作</div>
                    </div>
                    <div v-for="region in activeBrandProfile.regions" :key="region.id" class="db-map-row db-map-row-2">
                      <input v-model="region.name" placeholder="例如：USA" />
                      <n-button size="small" tertiary @click="removeActiveBrandRegion(region.id)">删除</n-button>
                    </div>
                  </div>
                  <div class="hint">档案只保存品牌和地区模板。需要切换当前调度时，请使用上方“切换当前运行品牌”。</div>
                </template>
                <div v-else class="hint">还没有品牌档案，请先新增品牌。</div>
              </section>
            </div>
          </div>

          <div class="config-grid">
            <label class="cfg-item full">
              <span>CONSOLE_ACCESS_KEY_ID</span>
              <input v-model="configDraft.CONSOLE_ACCESS_KEY_ID" />
            </label>
            <label class="cfg-item full">
              <span>CONSOLE_ACCESS_SECRET</span>
              <input v-model="configDraft.CONSOLE_ACCESS_SECRET" />
            </label>
            <label class="cfg-item">
              <span>CONSOLE_HOST</span>
              <input v-model="configDraft.CONSOLE_HOST" placeholder="https://api.winrobot360.com" />
            </label>
            <label class="cfg-item">
              <span>ROBOT_UUID</span>
              <input v-model="configDraft.ROBOT_UUID" />
            </label>
            <label class="cfg-item full">
              <span>FEISHU_WEBHOOK_URL</span>
              <input v-model="configDraft.FEISHU_WEBHOOK_URL" />
            </label>
            <label class="cfg-item full">
              <span>FEISHU_SECRET</span>
              <input v-model="configDraft.FEISHU_SECRET" />
            </label>
            <label class="cfg-item">
              <span>品牌（单品牌）</span>
              <input v-model="configDraft.BRAND" />
            </label>
            <label class="cfg-item">
              <span>阶段严格顺序</span>
              <input v-model="configDraft.SCHEDULER_STRICT_STAGE_ORDER" placeholder="true/false" />
            </label>
            <label class="cfg-item">
              <span>并发 OSS</span>
              <input v-model="configDraft.MAX_PARALLEL_OSS" />
            </label>
            <label class="cfg-item">
              <span>并发 Hashkey</span>
              <input v-model="configDraft.MAX_PARALLEL_HASHKEY" />
            </label>
            <label class="cfg-item">
              <span>并发上传合并文件</span>
              <input v-model="configDraft.MAX_PARALLEL_UPLOAD_MERGED_FILE" />
            </label>
            <label class="cfg-item">
              <span>重试次数</span>
              <input v-model="configDraft.MAX_RETRIES" />
            </label>
            <label class="cfg-item">
              <span>轮询间隔秒</span>
              <input v-model="configDraft.POLL_SECONDS" />
            </label>
            <label class="cfg-item full">
              <span>机器账号 ACCOUNT_NAMES（逗号分隔）</span>
              <textarea v-model="configDraft.ACCOUNT_NAMES" rows="4" />
            </label>
          </div>

          <div class="config-actions">
            <n-button type="primary" @click="saveConfig">保存配置</n-button>
          </div>
          <div class="hint">保存后不会自动开始调度，请回到实时总览点击“开始调度”。</div>
        </article>
      </section>
    </main>
    <n-modal v-model:show="showRetryConfirm" preset="card" class="switch-brand-modal" title="确认重试失败任务">
      <div class="confirm-copy">
        <p>将重试 <strong>{{ retryTargetText }}</strong> 下当前失败的任务。</p>
        <p>本次只会清理这一组的失败标记和尝试次数，不会影响其他品牌、地区或阶段。</p>
      </div>
      <template #footer>
        <div class="modal-actions">
          <n-button tertiary @click="showRetryConfirm = false">取消</n-button>
          <n-button type="primary" :loading="retryApplying" @click="confirmRetryFailed">确认重试</n-button>
        </div>
      </template>
    </n-modal>
    <n-modal v-model:show="showSwitchBrandConfirm" preset="card" class="switch-brand-modal" title="确认切换当前运行品牌">
      <div class="confirm-copy">
        <p>将把品牌档案“{{ selectedSwitchBrand || '-' }}”应用到当前调度配置。</p>
        <p>系统会同步 <strong>BRAND</strong> 和 <strong>PARALLEL_REGIONS</strong>，看板与后续调度都会切到该品牌。</p>
        <p v-if="switchResetProgress">已勾选重置进度：会清理该品牌当前任务进度，并从新配置重新开始。</p>
        <p v-else>未勾选重置进度：会保留该品牌已有任务状态，仅切换当前运行配置。</p>
        <p>如果调度服务正在运行，应用配置后可能会重启调度服务。</p>
      </div>
      <template #footer>
        <div class="modal-actions">
          <n-button tertiary @click="showSwitchBrandConfirm = false">取消</n-button>
          <n-button type="primary" :loading="switchBrandApplying" @click="confirmSwitchBrand">确认切换</n-button>
        </div>
      </template>
    </n-modal>
  </div>
</template>

<script setup lang="ts">
import { computed, h, onBeforeUnmount, onMounted, reactive, ref } from "vue";
import { NButton, NTag, type DataTableColumns } from "naive-ui";

import { type PlanRow, type RobotRow, useMonitorStore } from "../stores/monitor";

const store = useMonitorStore();
const activeView = ref<"overview" | "config">("overview");
const configDraft = reactive<Record<string, string>>({});
const REGION_PRESET = ["ARGENTINA", "BRAZIL", "FAW-VW", "MEXICO", "SAIC VW", "SOUTH AFRICA", "USA"];
type BrandProfileRegionRow = { id: number; name: string };
type BrandProfileRow = { id: number; brand: string; regions: BrandProfileRegionRow[] };
const brandProfileRows = ref<BrandProfileRow[]>([]);
const activeBrandProfileId = ref<number | null>(null);
const selectedSwitchBrand = ref("");
const switchResetProgress = ref(false);
const showSwitchBrandConfirm = ref(false);
const switchBrandApplying = ref(false);
const showRetryConfirm = ref(false);
const retryApplying = ref(false);
const retryTarget = ref<PlanRow | null>(null);
let brandProfileSeed = 1;
let brandProfileRegionSeed = 1;
let robotTimer: number | null = null;

const workSummary = computed(() => store.overview?.work_summary ?? {});
const actionSummary = computed(() => store.overview?.action_work_summary ?? {});
const oss = computed(() => actionSummary.value.upload_oss ?? { total: 0, done: 0, running: 0, failed: 0, progress: 0 });
const hashkey = computed(() => actionSummary.value.hashkey ?? { total: 0, done: 0, running: 0, failed: 0, progress: 0 });
const uploadMergedFile = computed(
  () => actionSummary.value.upload_merged_file ?? { total: 0, done: 0, running: 0, failed: 0, progress: 0 }
);
const stageName = computed(() => store.stageName || "--");
const updatedAtText = computed(() => formatTime(store.overview?.updated_at));
const currentBrandLabel = computed(() => store.selectedBrand || store.overview?.brand || configDraft.BRAND || "--");
const schedulerStatusLabel = computed(() => {
  if (store.schedulerStatus?.completed) return "调度已完成";
  if (store.schedulerStatus?.running) return "调度运行中";
  if (store.schedulerStatus?.active) return "调度已开启";
  return "调度未启动";
});
const schedulerStatusType = computed<"default" | "info" | "success" | "warning" | "error">(() => {
  if (store.schedulerStatus?.last_error) return "error";
  if (store.schedulerStatus?.completed) return "success";
  if (store.schedulerStatus?.running) return "success";
  if (store.schedulerStatus?.active) return "info";
  return "warning";
});
const nextTask = computed(() => store.overview?.plan?.find((row) => row.status === "running" || row.status === "pending" || row.status === "failed") ?? null);
const nextParallelLimit = computed(() => {
  const action = nextTask.value?.action;
  if (action === "upload_oss") return configDraft.MAX_PARALLEL_OSS || "10";
  if (action === "hashkey") return configDraft.MAX_PARALLEL_HASHKEY || "90";
  if (action === "upload_merged_file") return configDraft.MAX_PARALLEL_UPLOAD_MERGED_FILE || "10";
  return "--";
});
const retryTargetText = computed(() => {
  const row = retryTarget.value;
  if (!row) return "-";
  return `${row.brand} / ${row.region} / ${actionLabel(row.action)}`;
});
const brandProfileNames = computed(() => Object.keys(store.brandProfiles).sort((a, b) => a.localeCompare(b, "zh-Hans-CN")));
const brandSelectOptions = computed(() => brandProfileNames.value.map((brand) => ({ label: brand, value: brand })));
const activeBrandProfile = computed(() => brandProfileRows.value.find((row) => row.id === activeBrandProfileId.value) ?? null);

const columns: DataTableColumns<PlanRow> = [
  { title: "品牌", key: "brand", width: 100 },
  { title: "地区", key: "region", width: 140 },
  { title: "动作", key: "action", width: 120 },
  {
    title: "状态",
    key: "status",
    width: 100,
    render: (row) => h(NTag, { type: statusType(row.status), size: "small" }, { default: () => statusLabel(row.status) }),
  },
  { title: "总数", key: "total", width: 80 },
  { title: "运行中", key: "running_count", width: 90 },
  { title: "已完成", key: "done_count", width: 90 },
  { title: "失败", key: "failed_count", width: 80 },
  { title: "待启动", key: "pending_count", width: 90 },
  {
    title: "操作",
    key: "actions",
    width: 110,
    render: (row) =>
      row.failed_count > 0
        ? h(
            NButton,
            { size: "tiny", type: "error", tertiary: true, onClick: () => openRetryFailedConfirm(row) },
            { default: () => "重试失败" }
          )
        : "-",
  },
  { title: "任务标识", key: "task_id", minWidth: 220 },
];

const robotColumns: DataTableColumns<RobotRow> = [
  { title: "机器账号", key: "accountName", width: 220 },
  {
    title: "状态",
    key: "status",
    width: 110,
    render: (row) =>
      h(
        NTag,
        { size: "small", type: row.ok ? (row.status === "idle" ? "success" : "warning") : "error" },
        { default: () => (row.ok ? row.status || "-" : "error") }
      ),
  },
  { title: "机器名", key: "machineName", width: 160 },
  { title: "IP", key: "clientIp", width: 140 },
  { title: "描述", key: "description", minWidth: 180 },
];

function statusLabel(status: string): string {
  if (status === "done") return "已完成";
  if (status === "running") return "进行中";
  if (status === "failed") return "失败";
  return "待执行";
}

function statusType(status: string): "default" | "info" | "success" | "warning" | "error" {
  if (status === "done") return "success";
  if (status === "running") return "info";
  if (status === "failed") return "error";
  return "warning";
}

function eventTypeLabel(type?: string): string {
  if (type === "started") return "任务启动";
  if (type === "completed") return "任务完成";
  if (type === "retry") return "自动重试";
  if (type === "failed") return "任务失败";
  return type || "事件";
}

function eventType(type?: string): "default" | "info" | "success" | "warning" | "error" {
  if (type === "completed") return "success";
  if (type === "failed") return "error";
  if (type === "retry") return "warning";
  return "info";
}

function actionLabel(action?: string): string {
  if (action === "upload_oss") return "上传图片到 OSS";
  if (action === "hashkey") return "生成 Hashkey";
  if (action === "upload_merged_file") return "上传合并文件到 OSS";
  return action || "--";
}

function formatTime(ts?: number): string {
  if (!ts) return "--";
  const d = new Date(ts * 1000);
  const p = (v: number) => String(v).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`;
}

function parseAccountsFromDraft(): string[] {
  const raw = String(configDraft.ACCOUNT_NAMES || "");
  return raw
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);
}

function orderedUniqueRegions(rawList: string[]): string[] {
  const seen = new Set<string>();
  const custom: string[] = [];
  for (const item of rawList) {
    const v = String(item || "").trim();
    if (!v || seen.has(v)) continue;
    seen.add(v);
    if (!REGION_PRESET.includes(v)) custom.push(v);
  }
  const baseOrdered = REGION_PRESET.filter((r) => seen.has(r));
  return [...baseOrdered, ...custom];
}

function syncBrandProfilesFromStore(preferredActiveBrand = "", preferredSwitchBrand = "") {
  const rows = Object.entries(store.brandProfiles).map(([brand, profile]) => ({
    id: brandProfileSeed++,
    brand,
    regions: orderedUniqueRegions(profile.regions || []).map((name) => ({ id: brandProfileRegionSeed++, name })),
  }));
  brandProfileRows.value = rows;
  const current = String(configDraft.BRAND || "").trim();
  const activeBrand = String(preferredActiveBrand || current).trim();
  const switchBrand = String(preferredSwitchBrand || current).trim();
  activeBrandProfileId.value = rows.find((row) => row.brand === activeBrand)?.id ?? rows.find((row) => row.brand === current)?.id ?? rows[0]?.id ?? null;
  selectedSwitchBrand.value = switchBrand && store.brandProfiles[switchBrand] ? switchBrand : current && store.brandProfiles[current] ? current : rows[0]?.brand ?? "";
}

function buildBrandProfilePayload() {
  const out: Record<string, { regions: string[] }> = {};
  for (const row of brandProfileRows.value) {
    const brand = String(row.brand || "").trim();
    const regions = orderedUniqueRegions(row.regions.map((r) => r.name).filter(Boolean));
    if (brand && regions.length > 0) {
      out[brand] = { regions };
    }
  }
  return out;
}

function addBrandProfileRow() {
  const row: BrandProfileRow = {
    id: brandProfileSeed++,
    brand: "",
    regions: REGION_PRESET.map((name) => ({ id: brandProfileRegionSeed++, name })),
  };
  brandProfileRows.value.push(row);
  activeBrandProfileId.value = row.id;
}

function removeActiveBrandProfile() {
  const activeId = activeBrandProfileId.value;
  brandProfileRows.value = brandProfileRows.value.filter((row) => row.id !== activeId);
  activeBrandProfileId.value = brandProfileRows.value[0]?.id ?? null;
}

function addActiveBrandRegion() {
  activeBrandProfile.value?.regions.push({ id: brandProfileRegionSeed++, name: "" });
}

function removeActiveBrandRegion(id: number) {
  const row = activeBrandProfile.value;
  if (!row) return;
  row.regions = row.regions.filter((region) => region.id !== id);
  if (row.regions.length === 0) {
    row.regions.push({ id: brandProfileRegionSeed++, name: "" });
  }
}

async function saveBrandProfileDraft() {
  const activeBrandBeforeSave = String(activeBrandProfile.value?.brand || "").trim();
  const switchBrandBeforeSave = String(selectedSwitchBrand.value || "").trim();
  const data = await store.saveBrandProfiles(buildBrandProfilePayload());
  store.brandProfiles = data.profiles ?? {};
  syncBrandProfilesFromStore(activeBrandBeforeSave, switchBrandBeforeSave);
}

async function refreshAll() {
  await store.fetchOverview();
  await store.fetchSchedulerStatus();
  await store.fetchRobotStatuses(parseAccountsFromDraft());
}

async function startScheduler() {
  await store.startScheduler();
  await refreshAll();
}

function openRetryFailedConfirm(row: PlanRow) {
  retryTarget.value = row;
  showRetryConfirm.value = true;
}

async function confirmRetryFailed() {
  if (!retryTarget.value) return;
  retryApplying.value = true;
  try {
    await store.retryFailedTask(retryTarget.value);
    showRetryConfirm.value = false;
    retryTarget.value = null;
    await refreshAll();
  } finally {
    retryApplying.value = false;
  }
}

async function saveConfig() {
  await store.saveGlobalConfig(configDraft, false);
  await store.fetchGlobalConfig();
  Object.assign(configDraft, store.globalConfig);
  store.setBrand("");
  store.stopStream();
  await store.fetchOverview();
  store.startStream();
  await store.fetchRobotStatuses(parseAccountsFromDraft());
}

function openSwitchBrandConfirm() {
  if (!String(selectedSwitchBrand.value || "").trim()) return;
  showSwitchBrandConfirm.value = true;
}

async function confirmSwitchBrand() {
  const brand = String(selectedSwitchBrand.value || "").trim();
  if (!brand) return;
  switchBrandApplying.value = true;
  try {
    await store.applyBrandProfile(brand, switchResetProgress.value);
    await store.fetchGlobalConfig();
    Object.assign(configDraft, store.globalConfig);
    activeBrandProfileId.value = brandProfileRows.value.find((row) => row.brand === brand)?.id ?? activeBrandProfileId.value;
    store.setBrand("");
    store.stopStream();
    await store.fetchOverview();
    store.startStream();
    await store.fetchRobotStatuses(parseAccountsFromDraft());
    showSwitchBrandConfirm.value = false;
  } finally {
    switchBrandApplying.value = false;
  }
}

onMounted(async () => {
  await store.fetchGlobalConfig();
  await store.fetchBrandProfiles();
  Object.assign(configDraft, store.globalConfig);
  syncBrandProfilesFromStore();
  store.setBrand("");
  await store.fetchOverview();
  await store.fetchSchedulerStatus();
  await store.fetchRobotStatuses(parseAccountsFromDraft());
  store.startStream();
  robotTimer = window.setInterval(() => {
    store.fetchRobotStatuses(parseAccountsFromDraft());
  }, 15000);
});

onBeforeUnmount(() => {
  store.stopStream();
  if (robotTimer !== null) {
    clearInterval(robotTimer);
    robotTimer = null;
  }
});
</script>
