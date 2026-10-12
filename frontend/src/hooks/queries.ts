import { useQueries, useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { getHourly, getSummary } from "../api/analytics";
import { getCameraStatus, getCameras } from "../api/cameras";
import { getEvents, type EventFilters } from "../api/events";
import type { Camera, CameraStatus } from "../types/camera";

const LIVE_MS = 5000; // poll so the dashboard follows the running cameras

export const useCameras = () =>
  useQuery({ queryKey: ["cameras"], queryFn: getCameras, refetchInterval: LIVE_MS });

/**
 * Real processing status per camera, taken from the backend's worker state.
 * A camera record existing does NOT mean it is being monitored.
 */
export function useCameraStatuses(cameras: Camera[] | undefined) {
  const results = useQueries({
    queries: (cameras ?? []).map((c) => ({
      queryKey: ["camera-status", c.id],
      queryFn: () => getCameraStatus(c.id),
      refetchInterval: LIVE_MS,
    })),
  });
  const map: Record<number, CameraStatus | undefined> = {};
  (cameras ?? []).forEach((c, i) => {
    map[c.id] = results[i]?.data;
  });
  return map;
}

export const useEvents = (filters: EventFilters) =>
  useQuery({
    queryKey: ["events", filters],
    queryFn: () => getEvents(filters),
    refetchInterval: LIVE_MS,
    placeholderData: (prev) => prev, // keep the old page visible while filters change
  });

export const useSummary = (start: string) =>
  useQuery({ queryKey: ["summary", start], queryFn: () => getSummary({ start }), refetchInterval: LIVE_MS });

export const useHourly = (start: string) =>
  useQuery({ queryKey: ["hourly", start], queryFn: () => getHourly({ start }), refetchInterval: 15000 });

/** Start of the local day as an ISO string (fixed for the lifetime of the component). */
export function useTodayStart(): string {
  const [start] = useState(() => {
    const d = new Date();
    d.setHours(0, 0, 0, 0);
    return d.toISOString();
  });
  return start;
}

/**  ago (relative to when the page mounted) as an ISO string, so the query key stays stable. */
export function useHoursAgo(hours: number): string {
  const [mountedAt] = useState(() => Date.now());
  return new Date(Math.floor(mountedAt / 60000) * 60000 - hours * 3600_000).toISOString();
}
