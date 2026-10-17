export type SourceType = "mp4" | "webcam" | "rtsp";

/** A camera *record* in PostgreSQL. It says nothing about whether it is being processed. */
export interface Camera {
  id: number;
  name: string;
  source_type: SourceType;
  source_uri: string;
  location: string | null;
  is_active: boolean;
  created_at: string;
}

export interface CameraCreate {
  name: string;
  source_type: SourceType;
  source_uri: string;
  location?: string | null;
}

/** Live state of the worker process that processes a camera. */
export interface CameraStatus {
  camera_id: number;
  running: boolean;
  pid: number | null;
  started_at: string | null;
  events_persisted: number;
  last_error: string | null;
}

export type OverlayKey = "boxes" | "ids" | "confidence" | "zones" | "events" | "trails" | "stats" | "fps";
export type OverlaySettings = Record<OverlayKey, boolean>;

export interface LiveTrack {
  track_id: number;
  class_name: string;
  confidence: number;
  /** In a restricted zone / loitering right now. */
  alert: boolean;
}

export interface LiveInfo {
  running: boolean;
  seq: number;
  meta: null | {
    frame: number;
    stream_time: number;
    fps: number;
    tracks: LiveTrack[];
    stats: { line_in: number; line_out: number; intrusions: number; loitering: number; total_events: number };
  };
}
