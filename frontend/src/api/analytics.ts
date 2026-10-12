import type { AnalyticsSummary, HourlyBucket } from "../types/event";
import { apiGet } from "./client";

export interface Period {
  start?: string;
  end?: string;
  camera_id?: number;
}

export const getSummary = (p: Period = {}) => apiGet<AnalyticsSummary>("/api/analytics/summary", { ...p });
export const getHourly = (p: Period = {}) => apiGet<HourlyBucket[]>("/api/analytics/hourly", { ...p });
