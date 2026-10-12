import type { EventPage, EventType, Severity } from "../types/event";
import { apiGet } from "./client";

export interface EventFilters {
  event_type?: EventType | "";
  severity?: Severity | "";
  camera_id?: number | "";
  start?: string;
  end?: string;
  limit?: number;
  offset?: number;
}

/** The backend returns a paginated object `{ items, total, limit, offset }`. */
export const getEvents = (filters: EventFilters = {}) =>
  apiGet<EventPage>("/api/events", { ...filters });
