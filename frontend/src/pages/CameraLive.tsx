import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Eye, Maximize2, Minimize2, PanelRightClose, PanelRightOpen, Play, Square, TriangleAlert, User } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { getLiveInfo, getOverlay, startCamera, stopCamera, streamUrl, updateOverlay } from "../api/cameras";
import { Alert, Button, EmptyState, ErrorState, Spinner } from "../components/common/ui";
import { useCameras } from "../hooks/queries";
import type { OverlayKey, OverlaySettings } from "../types/camera";

const TOGGLES: { key: OverlayKey; label: string; hint: string }[] = [
  { key: "boxes", label: "Boxes", hint: "Bounding box around each person" },
  { key: "ids", label: "Person ID", hint: "Tracker ID label (Person #7)" },
  { key: "confidence", label: "Confidence", hint: "Detection confidence %" },
  { key: "zones", label: "Zones & lines", hint: "Restricted zones, loitering areas, counting line" },
  { key: "events", label: "Event banners", hint: "Intrusion / loitering / crossing alerts" },
  { key: "trails", label: "Trails", hint: "Recent path of each person" },
  { key: "stats", label: "Totals", hint: "Running event counts" },
  { key: "fps", label: "FPS", hint: "Processing speed" },
];

export default function CameraLive() {
  const { cameraName } = useParams<{ cameraName: string }>();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const cameras = useCameras();

  const decodedName = cameraName ? decodeURIComponent(cameraName) : "";
  const camera = cameras.data?.find(
    (c) => c.name.toLowerCase() === decodedName.toLowerCase() || String(c.id) === decodedName
  );

  const [streamFailed, setStreamFailed] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const imgRef = useRef<HTMLImageElement>(null);

  const camId = camera?.id ?? 0;
  const overlayKey = ["overlay", camId];

  const overlay = useQuery({
    queryKey: overlayKey,
    queryFn: () => getOverlay(camId),
    enabled: !!camera,
  });

  const live = useQuery({
    queryKey: ["live", camId],
    queryFn: () => getLiveInfo(camId),
    refetchInterval: 700,
    staleTime: 0,
    enabled: !!camera,
  });

  const refreshStatus = () => {
    qc.invalidateQueries({ queryKey: ["cameras"] });
    if (camera) {
      qc.invalidateQueries({ queryKey: ["camera-status", camera.id] });
      qc.invalidateQueries({ queryKey: ["live", camera.id] });
    }
  };

  const start = useMutation({
    mutationFn: () => startCamera(camId),
    onSuccess: () => {
      setStreamFailed(false);
      setAttempt((a) => a + 1);
      refreshStatus();
    },
  });

  const stop = useMutation({
    mutationFn: () => stopCamera(camId),
    onSuccess: refreshStatus,
  });

  const toggle = useMutation({
    mutationFn: (changes: Partial<OverlaySettings>) => updateOverlay(camId, changes),
    onMutate: async (changes) => {
      await qc.cancelQueries({ queryKey: overlayKey });
      const prev = qc.getQueryData<OverlaySettings>(overlayKey);
      if (prev) qc.setQueryData(overlayKey, { ...prev, ...changes });
      return { prev };
    },
    onError: (_e, _c, ctx) => ctx?.prev && qc.setQueryData(overlayKey, ctx.prev),
    onSettled: () => qc.invalidateQueries({ queryKey: overlayKey }),
  });

  const toggleFullscreen = async () => {
    if (!document.fullscreenElement) {
      await containerRef.current?.requestFullscreen().catch(() => {});
    } else {
      await document.exitFullscreen().catch(() => {});
    }
  };

  useEffect(() => {
    const onFsChange = () => setIsFullscreen(!!document.fullscreenElement);
    document.addEventListener("fullscreenchange", onFsChange);
    return () => document.removeEventListener("fullscreenchange", onFsChange);
  }, []);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape" && !document.fullscreenElement) {
        navigate("/cameras");
      }
    };
    window.addEventListener("keydown", onKey);
    const img = imgRef.current;
    return () => {
      window.removeEventListener("keydown", onKey);
      if (img) img.src = ""; // closes MJPEG connection so worker stops rendering
    };
  }, [navigate]);

  if (cameras.isLoading) {
    return (
      <div className="fixed inset-0 z-50 grid place-items-center bg-bg">
        <Spinner label="Loading camera…" />
      </div>
    );
  }

  if (cameras.isError) {
    return (
      <div className="fixed inset-0 z-50 grid place-items-center bg-bg p-6">
        <ErrorState error={cameras.error} onRetry={() => cameras.refetch()} />
      </div>
    );
  }

  if (!camera) {
    return (
      <div className="fixed inset-0 z-50 flex flex-col items-center justify-center gap-4 bg-bg p-6">
        <EmptyState title={`Camera "${decodedName}" not found`} hint="Check the camera name or return to the cameras list." />
        <Button onClick={() => navigate("/cameras")}>
          <ArrowLeft size={14} /> Back to Cameras
        </Button>
      </div>
    );
  }

  const running = live.data?.running ?? camera.is_active;
  const meta = live.data?.meta;
  const tracks = [...(meta?.tracks ?? [])].sort((a, b) => a.track_id - b.track_id);

  return (
    <div ref={containerRef} className="fixed inset-0 z-50 flex flex-col bg-black text-ink select-none">
      {/* Top Bar */}
      <header className="z-20 flex items-center justify-between border-b border-white/10 bg-[#0a0f1f]/90 px-5 py-3 backdrop-blur-md">
        <div className="flex items-center gap-3.5">
          <Button onClick={() => navigate("/cameras")} className="!px-3 !py-1.5 text-xs">
            <ArrowLeft size={14} /> Cameras
          </Button>
          <div className="h-4 w-px bg-white/15" />
          {running ? (
            <span className="inline-flex items-center gap-1.5 rounded-md bg-bad px-2.5 py-1 text-[11px] font-bold tracking-wider text-white shadow-lg shadow-bad/30">
              <span className="size-1.5 animate-pulse rounded-full bg-white" /> LIVE
            </span>
          ) : (
            <span className="inline-flex items-center gap-1.5 rounded-md border border-white/15 bg-white/5 px-2.5 py-1 text-[11px] font-semibold uppercase tracking-wider text-mute">
              Stopped
            </span>
          )}
          <div className="flex items-baseline gap-2.5">
            <h1 className="text-lg font-bold tracking-tight text-white">{camera.name}</h1>
            {camera.location && <span className="text-xs text-mute">· {camera.location}</span>}
          </div>
        </div>

        <div className="flex items-center gap-2.5">
          {running ? (
            <Button variant="danger" className="!px-3.5 !py-1.5 text-xs" disabled={stop.isPending} onClick={() => stop.mutate()}>
              <Square size={13} /> Stop stream
            </Button>
          ) : (
            <Button variant="primary" className="!px-3.5 !py-1.5 text-xs" disabled={start.isPending} onClick={() => start.mutate()}>
              <Play size={13} /> Start monitoring
            </Button>
          )}
          <Button variant="icon" onClick={toggleFullscreen} title={isFullscreen ? "Exit fullscreen" : "Enter fullscreen"}>
            {isFullscreen ? <Minimize2 size={15} /> : <Maximize2 size={15} />}
          </Button>
          <Button variant="icon" onClick={() => setSidebarOpen((o) => !o)} title={sidebarOpen ? "Hide details panel" : "Show details panel"}>
            {sidebarOpen ? <PanelRightClose size={15} /> : <PanelRightOpen size={15} />}
          </Button>
        </div>
      </header>

      {/* Main Content Area: Fullscreen Video + Optional Right Panel */}
      <div className="relative flex min-h-0 flex-1 overflow-hidden">
        {/* Video Canvas */}
        <div className="relative flex flex-1 flex-col items-center justify-center overflow-hidden bg-black">
          {!running ? (
            <div className="flex flex-col items-center gap-3 p-10 text-center">
              <p className="text-base font-medium text-mute">Camera monitoring is currently stopped.</p>
              <Button variant="primary" disabled={start.isPending} onClick={() => start.mutate()}>
                <Play size={14} /> Start monitoring
              </Button>
            </div>
          ) : streamFailed ? (
            <div className="flex flex-col items-center gap-3 p-10 text-center">
              <TriangleAlert size={28} className="text-warn" />
              <span className="text-mute">The video stream was interrupted.</span>
              <Button onClick={() => { setStreamFailed(false); setAttempt((a) => a + 1); }}>Reconnect</Button>
            </div>
          ) : (
            <>
              {!meta && (
                <div className="absolute inset-0 grid place-items-center bg-black/60 z-10">
                  <Spinner label="Waiting for first frame…" />
                </div>
              )}
              <img
                key={attempt}
                ref={imgRef}
                src={streamUrl(camera.id)}
                alt={`Live view of ${camera.name}`}
                onError={() => setStreamFailed(true)}
                className="h-full w-full object-contain"
              />
            </>
          )}

          {/* Floating Bottom Overlay Bar */}
          <div className="pointer-events-none absolute inset-x-0 bottom-0 z-20 flex flex-col items-center bg-gradient-to-t from-black/90 via-black/50 to-transparent px-6 pb-5 pt-10">
            <div className="pointer-events-auto flex flex-wrap items-center justify-center gap-2 rounded-2xl border border-white/15 bg-[#0c1330]/85 px-4 py-2.5 shadow-2xl backdrop-blur-md">
              <span className="mr-1 flex items-center gap-1.5 text-[11.5px] font-semibold uppercase tracking-wider text-mute">
                <Eye size={13} /> Overlays
              </span>
              {overlay.isError && <Alert>Couldn't load overlay settings</Alert>}
              {TOGGLES.map(({ key, label, hint }) => {
                const on = overlay.data?.[key] ?? false;
                return (
                  <button
                    key={key}
                    title={hint}
                    disabled={!overlay.data}
                    onClick={() => toggle.mutate({ [key]: !on })}
                    className={`cursor-pointer rounded-full border px-3 py-1 text-xs font-medium transition disabled:opacity-50 ${
                      on
                        ? "border-brand/70 bg-brand/25 text-white shadow-sm shadow-brand/20"
                        : "border-white/10 bg-white/5 text-mute hover:border-white/20 hover:text-ink"
                    }`}
                  >
                    <span className={`mr-1.5 inline-block size-2 rounded-full ${on ? "bg-ok" : "bg-mute/50"}`} />
                    {label}
                  </button>
                );
              })}
            </div>
          </div>
        </div>

        {/* Collapsible Side Panel for Live Detections & Stats */}
        {sidebarOpen && (
          <aside className="flex w-80 shrink-0 flex-col gap-4 overflow-y-auto border-l border-white/10 bg-[#0d142c]/95 p-4 backdrop-blur-md max-md:absolute max-md:inset-y-0 max-md:right-0 max-md:z-30">
            <div className="grid grid-cols-2 gap-2 text-center">
              <Info label="Processing" value={meta ? `${meta.fps} fps` : "–"} />
              <Info
                label="Video time"
                value={meta ? `${Math.floor(meta.stream_time / 60)}:${String(Math.floor(meta.stream_time % 60)).padStart(2, "0")}` : "–"}
              />
              <Info label="Intrusions" value={meta?.stats.intrusions ?? "–"} />
              <Info label="Loitering" value={meta?.stats.loitering ?? "–"} />
              <Info label="Line IN" value={meta?.stats.line_in ?? "–"} />
              <Info label="Line OUT" value={meta?.stats.line_out ?? "–"} />
            </div>

            <div className="flex items-center justify-between text-[12px] font-semibold uppercase tracking-wider text-mute">
              <span>Tracked now</span>
              <span className="rounded-full bg-brand/20 px-2 py-0.5 text-[11px] text-brand">{tracks.length}</span>
            </div>

            {tracks.length === 0 ? (
              <div className="rounded-xl border border-white/5 bg-white/[0.02] py-8 text-center text-[13px] text-mute">
                No one in view
              </div>
            ) : (
              <ul className="m-0 flex flex-1 list-none flex-col gap-2 overflow-y-auto p-0">
                {tracks.map((t) => (
                  <li
                    key={t.track_id}
                    className={`flex items-center gap-2.5 rounded-xl border px-3 py-2 text-[13px] ${
                      t.alert ? "border-bad/50 bg-bad/15" : "border-white/10 bg-white/5"
                    }`}
                  >
                    <User size={14} className={t.alert ? "text-bad" : "text-mute"} />
                    <span className="font-semibold text-white">#{t.track_id}</span>
                    <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-white/10">
                      <div
                        className="h-full rounded-full bg-gradient-to-r from-brand to-sky2"
                        style={{ width: `${t.confidence * 100}%` }}
                      />
                    </div>
                    <span className="w-9 text-right font-mono text-xs text-ink">{Math.round(t.confidence * 100)}%</span>
                    {t.alert && <TriangleAlert size={14} className="text-bad" />}
                  </li>
                ))}
              </ul>
            )}

            <p className="mt-auto text-[11.5px] leading-snug text-mute">
              Overlay toggles apply live to the video stream; events are always detected and saved in the background.
            </p>
          </aside>
        )}
      </div>
    </div>
  );
}

function Info({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-xl border border-white/5 bg-white/5 px-2.5 py-2">
      <div className="text-base font-bold leading-tight text-white">{value}</div>
      <div className="text-[11px] text-mute">{label}</div>
    </div>
  );
}
