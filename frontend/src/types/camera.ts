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
