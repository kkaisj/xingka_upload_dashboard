import { defineStore } from "pinia";

import { fetchJson, requestJson } from "../services/api";

export interface PlanRow {
  task_id: string;
  brand: string;
  region: string;
  action: string;
  status: "pending" | "running" | "done" | "failed";
  total: number;
  running_count: number;
  done_count: number;
  failed_count: number;
  pending_count: number;
}

export interface EventRow {
  work_id?: string;
  ts?: number;
  type?: string;
  brand?: string;
  region?: string;
  action?: string;
  status?: string;
  account?: string;
  job_uuid?: string;
}

export interface RobotRow {
  accountName: string;
  status?: string;
  robotClientUuid?: string;
  robotClientName?: string;
  machineName?: string;
  clientIp?: string;
  windowsUserName?: string;
  description?: string;
  ok: boolean;
  error?: string;
}

export interface ActionSummary {
  total: number;
  started: number;
  running: number;
  done: number;
  failed: number;
  pending: number;
  progress: number;
}

export interface OverviewPayload {
  updated_at: number;
  stage: { index: number; name: string };
  summary: {
    total: number;
    done: number;
    running: number;
    pending: number;
    failed: number;
  };
  work_summary: {
    total: number;
    started: number;
    running: number;
    done: number;
    failed: number;
    pending: number;
    progress: number;
  };
  action_work_summary: Record<string, ActionSummary>;
  plan: PlanRow[];
  events: EventRow[];
}

export interface GlobalConfigPayload {
  config: Record<string, string>;
  keys: string[];
}

export interface BrandProfile {
  regions: string[];
}

export interface BrandProfilesPayload {
  profiles: Record<string, BrandProfile>;
}

export interface SchedulerStatusPayload {
  enabled?: boolean;
  active?: boolean;
  running?: boolean;
  completed?: boolean;
  thread_name?: string | null;
  last_error?: string;
}

export interface RetryFailedPayload {
  ok: boolean;
  retried_count: number;
  retried_work_ids: string[];
  stage?: { index?: number; name?: string };
}

export const useMonitorStore = defineStore("monitor", {
  state: () => ({
    loading: false,
    connected: false,
    error: "",
    overview: null as OverviewPayload | null,
    selectedStage: "all" as "all" | "upload_oss" | "hashkey" | "upload_merged_file",
    selectedBrand: "" as string,
    globalConfig: {} as Record<string, string>,
    brandProfiles: {} as Record<string, BrandProfile>,
    robots: [] as RobotRow[],
    robotsLoading: false,
    schedulerStatus: null as SchedulerStatusPayload | null,
    stream: null as EventSource | null,
  }),
  getters: {
    plan(state): PlanRow[] {
      const rows = state.overview?.plan ?? [];
      if (state.selectedStage === "all") return rows;
      return rows.filter((r) => r.action === state.selectedStage);
    },
    events(state): EventRow[] {
      const rows = state.overview?.events ?? [];
      if (state.selectedStage === "all") return rows;
      return rows.filter((r) => r.action === state.selectedStage);
    },
    stageName(state): string {
      return state.overview?.stage?.name || "--";
    },
  },
  actions: {
    setStage(stage: "all" | "upload_oss" | "hashkey" | "upload_merged_file") {
      this.selectedStage = stage;
    },
    setBrand(brand: string) {
      this.selectedBrand = String(brand || "").trim();
    },
    async fetchOverview() {
      this.loading = true;
      try {
        const brandQuery = this.selectedBrand ? `?brand=${encodeURIComponent(this.selectedBrand)}` : "";
        const data = await fetchJson<OverviewPayload>(`/api/v1/overview${brandQuery}`);
        this.overview = data;
        this.error = "";
      } catch (err) {
        this.error = (err as Error).message;
      } finally {
        this.loading = false;
      }
    },
    async fetchGlobalConfig() {
      const data = await fetchJson<GlobalConfigPayload>("/api/v1/config/global");
      this.globalConfig = data.config ?? {};
    },
    async fetchBrandProfiles() {
      const data = await fetchJson<BrandProfilesPayload>("/api/v1/config/brand-profiles");
      this.brandProfiles = data.profiles ?? {};
      return this.brandProfiles;
    },
    async saveBrandProfiles(profiles: Record<string, BrandProfile>) {
      const data = await requestJson<{ ok: boolean; profiles: Record<string, BrandProfile> }>(
        "/api/v1/config/brand-profiles",
        "PUT",
        { profiles }
      );
      this.brandProfiles = data.profiles ?? {};
      return data;
    },
    async applyBrandProfile(brand: string, resetProgress: boolean) {
      const data = await requestJson<{ ok: boolean; brand: string; regions: string[]; config: Record<string, string> }>(
        "/api/v1/config/apply-brand-profile",
        "POST",
        { brand, reset_progress: resetProgress }
      );
      this.globalConfig = data.config ?? {};
      return data;
    },
    async saveGlobalConfig(config: Record<string, string>, restartScheduler = true) {
      const data = await requestJson<{ ok: boolean; config: Record<string, string> }>(
        "/api/v1/config/global",
        "PUT",
        { config, restart_scheduler: restartScheduler }
      );
      this.globalConfig = data.config ?? {};
      return data;
    },
    async fetchSchedulerStatus() {
      this.schedulerStatus = await fetchJson<SchedulerStatusPayload>("/api/v1/scheduler/status");
      return this.schedulerStatus;
    },
    async startScheduler() {
      const data = await requestJson<{ ok: boolean; started: boolean; scheduler_status: SchedulerStatusPayload }>(
        "/api/v1/scheduler/start",
        "POST",
        {}
      );
      this.schedulerStatus = data.scheduler_status ?? null;
      return data;
    },
    async retryFailedTask(row: PlanRow) {
      return await requestJson<RetryFailedPayload>("/api/v1/scheduler/retry-failed", "POST", {
        brand: row.brand,
        region: row.region,
        action: row.action,
      });
    },
    async fetchRobotStatuses(accounts?: string[]) {
      this.robotsLoading = true;
      try {
        const data = await requestJson<{ robots: RobotRow[] }>("/api/v1/config/robots/status", "POST", {
          accounts: accounts && accounts.length > 0 ? accounts : undefined,
        });
        this.robots = data.robots ?? [];
      } finally {
        this.robotsLoading = false;
      }
    },
    startStream() {
      if (this.stream) {
        return;
      }
      const brandQuery = this.selectedBrand ? `?brand=${encodeURIComponent(this.selectedBrand)}` : "";
      const es = new EventSource(`/api/v1/events/stream${brandQuery}`);
      es.addEventListener("overview", (event) => {
        try {
          const next = JSON.parse((event as MessageEvent).data) as OverviewPayload;
          this.overview = next;
          this.connected = true;
          this.error = "";
        } catch {
          this.connected = false;
        }
      });
      es.addEventListener("error", () => {
        this.connected = false;
      });
      es.onopen = () => {
        this.connected = true;
      };
      this.stream = es;
    },
    stopStream() {
      if (!this.stream) {
        return;
      }
      this.stream.close();
      this.stream = null;
      this.connected = false;
    },
  },
});
