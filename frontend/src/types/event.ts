export type EventType = "LINE_CROSSED" | "INTRUSION_DETECTED" | "LOITERING";
export type Severity = "INFO" | "WARNING" | "CRITICAL";

export const EVENT_TYPES: EventType[] = ["LINE_CROSSED", "INTRUSION_DETECTED", "LOITERING"];
export const SEVERITIES: Severity[] = ["INFO", "WARNING", "CRITICAL"];

export interface EventItem {
  event_id: string;
  event_type: EventType;
  track_id: number;
  camera_id: number | null;
  /** Seconds on the video stream's clock (not a wall-clock time). */
  timestamp: number;
  severity: Severity;
  metadata: Record<string, unknown>;
  /** ISO 8601 wall-clock time the event was created. */
  created_at: string;
}

export interface EventPage {
  items: EventItem[];
  total: number;
  limit: number;
  offset: number;
}

export interface AnalyticsSummary {
  start: string;
  end: string;
  camera_id: number | null;
  total_events: number;
  intrusion_events: number;
  loitering_events: number;
  line_crossed_events: number;
  visitors_in: number;
  visitors_out: number;
  by_type: Record<string, number>;
  by_severity: Record<string, number>;
  by_camera: Record<string, number>;
}

export interface HourlyBucket {
  hour: string;
  total: number;
  by_type: Record<string, number>;
}
