import type { Camera, CameraCreate, CameraStatus, LiveInfo, OverlaySettings, ZonesConfig } from "../types/camera";
import { API_BASE_URL, apiGet, apiSend } from "./client";

export const getCameras = () => apiGet<Camera[]>("/api/cameras");
export const getCameraStatus = (id: number) => apiGet<CameraStatus>(`/api/cameras/${id}/status`);
export const createCamera = (body: CameraCreate) => apiSend<Camera>("POST", "/api/cameras", body);
export const deleteCamera = (id: number) => apiSend<void>("DELETE", `/api/cameras/${id}`);
export const startCamera = (id: number) => apiSend<CameraStatus>("POST", `/api/cameras/${id}/start`);
export const stopCamera = (id: number) => apiSend<CameraStatus>("POST", `/api/cameras/${id}/stop`);

export const getOverlay = (id: number) => apiGet<OverlaySettings>(`/api/cameras/${id}/overlay`);
export const updateOverlay = (id: number, changes: Partial<OverlaySettings>) =>
  apiSend<OverlaySettings>("PATCH", `/api/cameras/${id}/overlay`, changes);
export const getZones = (id: number) => apiGet<ZonesConfig>(`/api/cameras/${id}/zones`);
export const updateZones = (id: number, body: ZonesConfig) =>
  apiSend<ZonesConfig>("PUT", `/api/cameras/${id}/zones`, body);
export const getLiveInfo = (id: number) => apiGet<LiveInfo>(`/api/cameras/${id}/live`);
/** MJPEG stream URL, used directly as an <img src>. */
export const streamUrl = (id: number, attempt = 0) =>
  `${API_BASE_URL}/api/cameras/${id}/stream${attempt ? `?t=${attempt}` : ""}`;

