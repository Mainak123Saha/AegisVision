import type { Camera, CameraCreate, CameraStatus } from "../types/camera";
import { apiGet, apiSend } from "./client";

export const getCameras = () => apiGet<Camera[]>("/api/cameras");
export const getCameraStatus = (id: number) => apiGet<CameraStatus>(`/api/cameras/${id}/status`);
export const createCamera = (body: CameraCreate) => apiSend<Camera>("POST", "/api/cameras", body);
export const deleteCamera = (id: number) => apiSend<void>("DELETE", `/api/cameras/${id}`);
export const startCamera = (id: number) => apiSend<CameraStatus>("POST", `/api/cameras/${id}/start`);
export const stopCamera = (id: number) => apiSend<CameraStatus>("POST", `/api/cameras/${id}/stop`);
