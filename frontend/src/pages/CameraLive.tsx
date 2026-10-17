import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowLeft, Check, Eye, Hourglass, Maximize2, Minimize2, PanelRightClose, PanelRightOpen,
  Pencil, Play, ShieldAlert, Slash, Square, Trash2, TriangleAlert, Undo2, User, X,
} from "lucide-react";
import { useCallback, useEffect, useRef, useState, type MouseEvent } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { getLiveInfo, getOverlay, getZones, startCamera, stopCamera, streamUrl, updateOverlay, updateZones } from "../api/cameras";
import { Alert, Button, EmptyState, ErrorState, Spinner } from "../components/common/ui";
import { useCameras } from "../hooks/queries";
import type { LineSpec, OverlayKey, OverlaySettings, ZoneRule, ZoneSpec, ZonesConfig } from "../types/camera";

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

type DrawTool = "none" | "intrusion" | "loitering" | "line";

interface Rect { left: number; top: number; width: number; height: number }

const EMPTY_ZONES: ZoneSpec[] = [];
const EMPTY_LINES: LineSpec[] = [];

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
  const [sidebarTab, setSidebarTab] = useState<"live" | "zones">("live");
  const [isFullscreen, setIsFullscreen] = useState(false);

  // Interactive zone drawing state
  const [editingZones, setEditingZones] = useState(false);
  const [tool, setTool] = useState<DrawTool>("none");
  const [draftPts, setDraftPts] = useState<[number, number][]>([]);
  const [hoverPt, setHoverPt] = useState<[number, number] | null>(null);
  const [newName, setNewName] = useState("");
  const [newLoiterSec, setNewLoiterSec] = useState(5);
  const [imgRect, setImgRect] = useState<Rect | null>(null);

  const containerRef = useRef<HTMLDivElement>(null);
  const videoWrapRef = useRef<HTMLDivElement>(null);
  const imgRef = useRef<HTMLImageElement>(null);
  const retryCountRef = useRef(0);
  const retryTimerRef = useRef<number | null>(null);

  const camId = camera?.id ?? 0;
  const overlayKey = ["overlay", camId];
  const zonesKey = ["zones", camId];

  const overlay = useQuery({
    queryKey: overlayKey,
    queryFn: () => getOverlay(camId),
    enabled: !!camera,
  });

  const zonesQuery = useQuery({
    queryKey: zonesKey,
    queryFn: () => getZones(camId),
    enabled: !!camera,
  });

  const localZones = zonesQuery.data?.zones ?? EMPTY_ZONES;
  const localLines = zonesQuery.data?.lines ?? EMPTY_LINES;

  const live = useQuery({
    queryKey: ["live", camId],
    queryFn: () => getLiveInfo(camId),
    refetchInterval: 700,
    staleTime: 0,
    enabled: !!camera,
  });

  // Compute rendered letterboxed image bounds inside the video container
  const updateImgRect = useCallback(() => {
    const img = imgRef.current;
    const wrap = videoWrapRef.current;
    if (!img || !wrap) return;
    const cw = wrap.clientWidth;
    const ch = wrap.clientHeight;
    const nw = img.naturalWidth || 960;
    const nh = img.naturalHeight || 540;
    if (!cw || !ch || !nw || !nh) return;
    const scale = Math.min(cw / nw, ch / nh);
    const width = nw * scale;
    const height = nh * scale;
    const left = (cw - width) / 2;
    const top = (ch - height) / 2;
    setImgRect({ left, top, width, height });
  }, []);

  useEffect(() => {
    updateImgRect();
    const wrap = videoWrapRef.current;
    if (!wrap) return;
    const ro = new ResizeObserver(updateImgRect);
    ro.observe(wrap);
    window.addEventListener("resize", updateImgRect);
    return () => {
      ro.disconnect();
      window.removeEventListener("resize", updateImgRect);
    };
  }, [updateImgRect, sidebarOpen, isFullscreen]);

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

  const saveZones = useMutation({
    mutationFn: (payload: ZonesConfig) => updateZones(camId, payload),
    onMutate: async (payload) => {
      await qc.cancelQueries({ queryKey: zonesKey });
      const prev = qc.getQueryData<ZonesConfig>(zonesKey);
      qc.setQueryData(zonesKey, payload);
      return { prev };
    },
    onError: (_e, _p, ctx) => ctx?.prev && qc.setQueryData(zonesKey, ctx.prev),
    onSuccess: (saved) => {
      qc.setQueryData(zonesKey, saved);
      // Make sure zones overlay is enabled so the user sees their saved zones on the stream
      if (overlay.data && !overlay.data.zones) {
        toggle.mutate({ zones: true });
      }
    },
  });

  const { mutate: mutateZones } = saveZones;

  const persistZones = useCallback(
    (nextZones: ZoneSpec[], nextLines: LineSpec[]) => {
      mutateZones({
        camera_id: String(camId),
        coords: "normalized",
        zones: nextZones,
        lines: nextLines,
      });
    },
    [camId, mutateZones]
  );

  const finishDraft = useCallback(() => {
    if (tool === "line") {
      if (draftPts.length < 2) return;
      const idx = localLines.length + 1;
      const name = newName.trim() || `Line ${idx}`;
      const id = name.toLowerCase().replace(/[^a-z0-9]+/g, "_") + "_" + Date.now().toString(36).slice(-4);
      const nextLines: LineSpec[] = [
        ...localLines,
        { id, name, points: [draftPts[0], draftPts[1]], cooldown: 1.0 },
      ];
      setDraftPts([]);
      setNewName("");
      setTool("none");
      persistZones(localZones, nextLines);
      return;
    }

    if (tool === "intrusion" || tool === "loitering") {
      if (draftPts.length < 3) return;
      const idx = localZones.length + 1;
      const defaultLabel = tool === "intrusion" ? `Intrusion Zone ${idx}` : `Loitering Zone ${idx}`;
      const name = newName.trim() || defaultLabel;
      const id = name.toLowerCase().replace(/[^a-z0-9]+/g, "_") + "_" + Date.now().toString(36).slice(-4);
      const rules: ZoneRule[] = [tool];
      const nextZones: ZoneSpec[] = [
        ...localZones,
        {
          id,
          name,
          points: draftPts,
          rules,
          loiter_seconds: tool === "loitering" ? Math.max(1, Number(newLoiterSec) || 5) : 5,
        },
      ];
      setDraftPts([]);
      setNewName("");
      setTool("none");
      persistZones(nextZones, localLines);
    }
  }, [tool, draftPts, localLines, localZones, newName, newLoiterSec, persistZones]);

  const handleCanvasClick = (e: MouseEvent<SVGSVGElement>) => {
    if (!editingZones || tool === "none") return;
    const rect = e.currentTarget.getBoundingClientRect();
    if (!rect.width || !rect.height) return;
    const x = Number(Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width)).toFixed(4));
    const y = Number(Math.max(0, Math.min(1, (e.clientY - rect.top) / rect.height)).toFixed(4));

    if (tool === "line") {
      if (draftPts.length === 0) {
        setDraftPts([[x, y]]);
      } else {
        const p1 = draftPts[0];
        const idx = localLines.length + 1;
        const name = newName.trim() || `Line ${idx}`;
        const id = name.toLowerCase().replace(/[^a-z0-9]+/g, "_") + "_" + Date.now().toString(36).slice(-4);
        const nextLines: LineSpec[] = [
          ...localLines,
          { id, name, points: [p1, [x, y]], cooldown: 1.0 },
        ];
        setDraftPts([]);
        setNewName("");
        setTool("none");
        persistZones(localZones, nextLines);
      }
      return;
    }

    // If clicking near the first vertex with >= 3 points, close the polygon
    if (draftPts.length >= 3) {
      const [fx, fy] = draftPts[0];
      const distPx = Math.hypot((x - fx) * rect.width, (y - fy) * rect.height);
      if (distPx < 16) {
        finishDraft();
        return;
      }
    }

    setDraftPts((prev) => [...prev, [x, y]]);
  };

  const handleCanvasMove = (e: MouseEvent<SVGSVGElement>) => {
    if (!editingZones || tool === "none") return;
    const rect = e.currentTarget.getBoundingClientRect();
    if (!rect.width || !rect.height) return;
    const x = Number(Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width)).toFixed(4));
    const y = Number(Math.max(0, Math.min(1, (e.clientY - rect.top) / rect.height)).toFixed(4));
    setHoverPt([x, y]);
  };

  const deleteZone = (id: string) => {
    persistZones(
      localZones.filter((z) => z.id !== id),
      localLines
    );
  };

  const deleteLine = (id: string) => {
    persistZones(
      localZones,
      localLines.filter((l) => l.id !== id)
    );
  };

  const clearAllZones = () => {
    persistZones([], []);
  };

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
      if (e.key === "Enter" && editingZones && draftPts.length >= 3) {
        e.preventDefault();
        finishDraft();
        return;
      }
      if (e.key === "Escape") {
        if (draftPts.length > 0 || tool !== "none") {
          setDraftPts([]);
          setTool("none");
          return;
        }
        if (editingZones) {
          setEditingZones(false);
          return;
        }
        if (!document.fullscreenElement) {
          navigate("/cameras");
        }
      }
    };
    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("keydown", onKey);
    };
  }, [navigate, editingZones, draftPts.length, tool, finishDraft]);

  // Close MJPEG connection ONLY when the component unmounts
  useEffect(() => {
    const imgEl = imgRef;
    const timerRef = retryTimerRef;
    return () => {
      if (timerRef.current !== null) {
        window.clearTimeout(timerRef.current);
      }
      if (imgEl.current) {
        imgEl.current.src = "";
      }
    };
  }, []);

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

  const selectTool = (next: DrawTool) => {
    setEditingZones(true);
    setSidebarOpen(true);
    setSidebarTab("zones");
    setDraftPts([]);
    setTool(next);
  };

  return (
    <div ref={containerRef} className="fixed inset-0 z-50 flex flex-col bg-black text-ink select-none">
      {/* Top Bar */}
      <header className="z-20 flex flex-wrap items-center justify-between gap-2 border-b border-white/10 bg-[#0a0f1f]/90 px-5 py-3 backdrop-blur-md">
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
          <Button
            variant={editingZones ? "primary" : "default"}
            className="!px-3.5 !py-1.5 text-xs"
            onClick={() => {
              const next = !editingZones;
              setEditingZones(next);
              if (next) {
                setSidebarOpen(true);
                setSidebarTab("zones");
              } else {
                setTool("none");
                setDraftPts([]);
              }
            }}
          >
            <Pencil size={13} /> {editingZones ? "Done drawing" : "Draw zones & lines"}
          </Button>

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
        <div ref={videoWrapRef} className="relative flex flex-1 flex-col items-center justify-center overflow-hidden bg-black">
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
              <Button
                onClick={() => {
                  retryCountRef.current = 0;
                  setStreamFailed(false);
                  setAttempt((a) => a + 1);
                }}
              >
                Reconnect
              </Button>
            </div>
          ) : (
            <>
              {!meta && (
                <div className="absolute inset-0 z-10 grid place-items-center bg-black/60">
                  <Spinner label="Waiting for first frame…" />
                </div>
              )}
              <img
                key={attempt}
                ref={imgRef}
                src={streamUrl(camera.id, attempt)}
                alt={`Live view of ${camera.name}`}
                onLoad={() => {
                  retryCountRef.current = 0;
                  setStreamFailed(false);
                  updateImgRect();
                }}
                onError={() => {
                  if (retryCountRef.current < 3) {
                    retryCountRef.current += 1;
                    if (retryTimerRef.current !== null) {
                      window.clearTimeout(retryTimerRef.current);
                    }
                    retryTimerRef.current = window.setTimeout(() => {
                      setAttempt((a) => a + 1);
                    }, 800);
                  } else {
                    setStreamFailed(true);
                  }
                }}
                className="h-full w-full object-contain"
              />
            </>
          )}

          {/* Interactive SVG Drawing Overlay aligned with the video frame */}
          {editingZones && imgRect && (
            <svg
              viewBox="0 0 1000 1000"
              preserveAspectRatio="none"
              onClick={handleCanvasClick}
              onMouseMove={handleCanvasMove}
              onMouseLeave={() => setHoverPt(null)}
              style={{
                left: imgRect.left,
                top: imgRect.top,
                width: imgRect.width,
                height: imgRect.height,
              }}
              className={`absolute z-15 overflow-visible ${
                tool !== "none" ? "cursor-crosshair ring-2 ring-brand/60" : "pointer-events-none"
              }`}
            >
              {/* Saved Zones preview in editor mode */}
              {localZones.map((z) => {
                const isIntrusion = z.rules.includes("intrusion");
                const stroke = isIntrusion ? "#fb7185" : "#fbbf24";
                const fill = isIntrusion ? "rgba(251, 113, 133, 0.22)" : "rgba(251, 191, 36, 0.22)";
                const pts = z.points.map(([px, py]) => `${px * 1000},${py * 1000}`).join(" ");
                const [lx, ly] = z.points[0] ?? [0, 0];
                return (
                  <g key={z.id}>
                    <polygon points={pts} fill={fill} stroke={stroke} strokeWidth={3} strokeDasharray="8 4" />
                    <text x={lx * 1000 + 8} y={ly * 1000 + 22} fill={stroke} fontSize={22} fontWeight="bold">
                      {z.name} ({z.rules.join("+")})
                    </text>
                  </g>
                );
              })}

              {/* Saved Lines preview in editor mode */}
              {localLines.map((ln) => {
                const [[x1, y1], [x2, y2]] = ln.points;
                return (
                  <g key={ln.id}>
                    <line
                      x1={x1 * 1000}
                      y1={y1 * 1000}
                      x2={x2 * 1000}
                      y2={y2 * 1000}
                      stroke="#38bdf8"
                      strokeWidth={4}
                      strokeDasharray="10 5"
                    />
                    <circle cx={x1 * 1000} cy={y1 * 1000} r={6} fill="#38bdf8" />
                    <circle cx={x2 * 1000} cy={y2 * 1000} r={6} fill="#38bdf8" />
                    <text x={(x1 + x2) * 500 + 8} y={(y1 + y2) * 500 - 10} fill="#38bdf8" fontSize={22} fontWeight="bold">
                      {ln.name}
                    </text>
                  </g>
                );
              })}

              {/* Currently Drawn Polygon / Line Draft */}
              {draftPts.length > 0 && (
                <g>
                  {(() => {
                    const color = tool === "intrusion" ? "#fb7185" : tool === "loitering" ? "#fbbf24" : "#38bdf8";
                    const allPts = hoverPt ? [...draftPts, hoverPt] : draftPts;
                    const polyStr = allPts.map(([px, py]) => `${px * 1000},${py * 1000}`).join(" ");
                    return (
                      <>
                        {tool !== "line" && allPts.length >= 3 && (
                          <polygon
                            points={polyStr}
                            fill={tool === "intrusion" ? "rgba(251,113,133,0.28)" : "rgba(251,191,36,0.28)"}
                            stroke={color}
                            strokeWidth={3.5}
                          />
                        )}
                        <polyline points={polyStr} fill="none" stroke={color} strokeWidth={3.5} />
                        {draftPts.map(([px, py], i) => (
                          <circle
                            key={i}
                            cx={px * 1000}
                            cy={py * 1000}
                            r={i === 0 && draftPts.length >= 3 && tool !== "line" ? 10 : 6}
                            fill={i === 0 ? "#ffffff" : color}
                            stroke={color}
                            strokeWidth={3}
                          />
                        ))}
                      </>
                    );
                  })()}
                </g>
              )}
            </svg>
          )}

          {/* Top Floating Drawing Toolbar when in editing mode */}
          {editingZones && (
            <div className="pointer-events-none absolute inset-x-0 top-4 z-20 flex flex-col items-center gap-2 px-4">
              <div className="pointer-events-auto flex flex-wrap items-center gap-2 rounded-2xl border border-white/15 bg-[#0c1330]/95 px-4 py-2.5 shadow-2xl backdrop-blur-md">
                <span className="mr-1 text-xs font-semibold uppercase tracking-wider text-mute">Draw field:</span>
                <button
                  onClick={() => selectTool(tool === "intrusion" ? "none" : "intrusion")}
                  className={`flex cursor-pointer items-center gap-1.5 rounded-xl border px-3 py-1.5 text-xs font-semibold transition ${
                    tool === "intrusion"
                      ? "border-bad bg-bad/25 text-white shadow-sm shadow-bad/30"
                      : "border-white/10 bg-white/5 text-ink hover:bg-white/10"
                  }`}
                >
                  <ShieldAlert size={14} className="text-bad" /> + Intrusion Zone
                </button>
                <button
                  onClick={() => selectTool(tool === "loitering" ? "none" : "loitering")}
                  className={`flex cursor-pointer items-center gap-1.5 rounded-xl border px-3 py-1.5 text-xs font-semibold transition ${
                    tool === "loitering"
                      ? "border-warn bg-warn/25 text-white shadow-sm shadow-warn/30"
                      : "border-white/10 bg-white/5 text-ink hover:bg-white/10"
                  }`}
                >
                  <Hourglass size={14} className="text-warn" /> + Loitering Zone
                </button>
                <button
                  onClick={() => selectTool(tool === "line" ? "none" : "line")}
                  className={`flex cursor-pointer items-center gap-1.5 rounded-xl border px-3 py-1.5 text-xs font-semibold transition ${
                    tool === "line"
                      ? "border-sky2 bg-sky2/25 text-white shadow-sm shadow-sky2/30"
                      : "border-white/10 bg-white/5 text-ink hover:bg-white/10"
                  }`}
                >
                  <Slash size={14} className="text-sky2" /> + Crossing Line
                </button>

                {tool !== "none" && (
                  <>
                    <div className="mx-1 h-4 w-px bg-white/15" />
                    <input
                      value={newName}
                      onChange={(e) => setNewName(e.target.value)}
                      placeholder={
                        tool === "intrusion" ? "Zone name (e.g. Staff area)" : tool === "loitering" ? "Zone name (e.g. Waiting)" : "Line name"
                      }
                      className="w-44 rounded-lg border border-white/15 bg-black/40 px-2.5 py-1 text-xs text-white outline-none focus:border-brand"
                    />
                    {tool === "loitering" && (
                      <label className="flex items-center gap-1 text-xs text-mute">
                        Threshold (s):
                        <input
                          type="number"
                          min={1}
                          max={600}
                          value={newLoiterSec}
                          onChange={(e) => setNewLoiterSec(Number(e.target.value))}
                          className="w-14 rounded-lg border border-white/15 bg-black/40 px-2 py-1 text-xs text-white outline-none focus:border-brand"
                        />
                      </label>
                    )}
                    {tool !== "line" && (
                      <Button
                        variant="primary"
                        className="!px-3 !py-1 text-xs"
                        disabled={draftPts.length < 3}
                        onClick={finishDraft}
                      >
                        <Check size={13} /> Complete ({draftPts.length} pts)
                      </Button>
                    )}
                    <Button
                      className="!px-2.5 !py-1 text-xs"
                      disabled={draftPts.length === 0}
                      onClick={() => setDraftPts((pts) => pts.slice(0, -1))}
                      title="Undo last point"
                    >
                      <Undo2 size={13} />
                    </Button>
                    <Button
                      className="!px-2.5 !py-1 text-xs"
                      onClick={() => {
                        setDraftPts([]);
                        setTool("none");
                      }}
                    >
                      <X size={13} /> Cancel
                    </Button>
                  </>
                )}
              </div>

              {tool !== "none" && (
                <div className="rounded-full bg-black/75 px-3.5 py-1 text-xs text-mute backdrop-blur">
                  {tool === "line"
                    ? draftPts.length === 0
                      ? "Click the start point of the counting line on the video"
                      : "Click the end point of the counting line"
                    : draftPts.length < 3
                    ? `Click on the video to place polygon corners (${draftPts.length}/3 minimum)`
                    : "Click more corners, or click the first white point / press Enter / click Complete to save"}
                </div>
              )}
            </div>
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

        {/* Collapsible Side Panel for Live Detections & Custom Zones */}
        {sidebarOpen && (
          <aside className="flex w-84 shrink-0 flex-col gap-4 overflow-y-auto border-l border-white/10 bg-[#0d142c]/95 p-4 backdrop-blur-md max-md:absolute max-md:inset-y-0 max-md:right-0 max-md:z-30">
            {/* Sidebar Switcher */}
            <div className="grid grid-cols-2 rounded-xl border border-white/10 bg-white/5 p-1">
              <button
                onClick={() => setSidebarTab("live")}
                className={`cursor-pointer rounded-lg py-1.5 text-xs font-semibold transition ${
                  sidebarTab === "live" ? "bg-brand text-white" : "text-mute hover:text-white"
                }`}
              >
                Live Details ({tracks.length})
              </button>
              <button
                onClick={() => setSidebarTab("zones")}
                className={`cursor-pointer rounded-lg py-1.5 text-xs font-semibold transition ${
                  sidebarTab === "zones" ? "bg-brand text-white" : "text-mute hover:text-white"
                }`}
              >
                Zones & Lines ({localZones.length + localLines.length})
              </button>
            </div>

            {sidebarTab === "live" ? (
              <>
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
              </>
            ) : (
              <div className="flex flex-1 flex-col gap-3 overflow-y-auto">
                <div className="flex flex-col gap-2 rounded-xl border border-white/10 bg-white/[0.03] p-3">
                  <div className="text-xs font-semibold text-white">Draw on live video</div>
                  <p className="text-[11.5px] leading-relaxed text-mute">
                    Pick a field type below and click directly on the camera feed to place polygon corners or counting lines. Changes apply live.
                  </p>
                  <div className="mt-1 grid grid-cols-1 gap-1.5">
                    <Button
                      variant={tool === "intrusion" ? "primary" : "default"}
                      className="justify-center !py-1.5 text-xs"
                      onClick={() => selectTool("intrusion")}
                    >
                      <ShieldAlert size={14} className="text-bad" /> Draw Intrusion Zone
                    </Button>
                    <Button
                      variant={tool === "loitering" ? "primary" : "default"}
                      className="justify-center !py-1.5 text-xs"
                      onClick={() => selectTool("loitering")}
                    >
                      <Hourglass size={14} className="text-warn" /> Draw Loitering Zone
                    </Button>
                    <Button
                      variant={tool === "line" ? "primary" : "default"}
                      className="justify-center !py-1.5 text-xs"
                      onClick={() => selectTool("line")}
                    >
                      <Slash size={14} className="text-sky2" /> Draw Crossing Line
                    </Button>
                  </div>
                </div>

                {saveZones.isError && <Alert>{(saveZones.error as Error).message}</Alert>}

                <div className="flex items-center justify-between text-[11.5px] font-semibold uppercase tracking-wider text-mute">
                  <span>Configured Zones ({localZones.length})</span>
                  {(localZones.length > 0 || localLines.length > 0) && (
                    <button
                      onClick={clearAllZones}
                      className="cursor-pointer text-[11px] font-normal text-bad hover:underline"
                    >
                      Clear all
                    </button>
                  )}
                </div>

                {localZones.length === 0 ? (
                  <div className="rounded-xl border border-white/5 bg-white/[0.02] py-4 text-center text-xs text-mute">
                    No intrusion or loitering zones configured
                  </div>
                ) : (
                  <ul className="m-0 flex list-none flex-col gap-2 p-0">
                    {localZones.map((z) => {
                      const isIntrusion = z.rules.includes("intrusion");
                      const isLoitering = z.rules.includes("loitering");
                      return (
                        <li key={z.id} className="flex flex-col gap-1.5 rounded-xl border border-white/10 bg-white/5 p-2.5 text-xs">
                          <div className="flex items-center justify-between gap-2">
                            <div className="flex items-center gap-2 truncate">
                              <span
                                className={`size-2.5 shrink-0 rounded-full ${
                                  isIntrusion ? "bg-bad" : "bg-warn"
                                }`}
                              />
                              <strong className="truncate text-white">{z.name}</strong>
                            </div>
                            <button
                              onClick={() => deleteZone(z.id)}
                              className="cursor-pointer text-mute hover:text-bad"
                              title="Delete zone"
                            >
                              <Trash2 size={13} />
                            </button>
                          </div>
                          <div className="flex flex-wrap items-center gap-2 text-[11px] text-mute">
                            <span className="rounded bg-white/10 px-1.5 py-0.5 uppercase text-ink">
                              {z.rules.join(" + ")}
                            </span>
                            <span>{z.points.length} vertices</span>
                            {isLoitering && <span>· {z.loiter_seconds}s threshold</span>}
                          </div>
                        </li>
                      );
                    })}
                  </ul>
                )}

                <div className="mt-1 text-[11.5px] font-semibold uppercase tracking-wider text-mute">
                  Counting Lines ({localLines.length})
                </div>

                {localLines.length === 0 ? (
                  <div className="rounded-xl border border-white/5 bg-white/[0.02] py-4 text-center text-xs text-mute">
                    No counting lines configured
                  </div>
                ) : (
                  <ul className="m-0 flex list-none flex-col gap-2 p-0">
                    {localLines.map((ln) => (
                      <li key={ln.id} className="flex items-center justify-between gap-2 rounded-xl border border-white/10 bg-white/5 p-2.5 text-xs">
                        <div className="flex items-center gap-2 truncate">
                          <span className="size-2.5 shrink-0 rounded-full bg-sky2" />
                          <strong className="truncate text-white">{ln.name}</strong>
                        </div>
                        <button
                          onClick={() => deleteLine(ln.id)}
                          className="cursor-pointer text-mute hover:text-bad"
                          title="Delete line"
                        >
                          <Trash2 size={13} />
                        </button>
                      </li>
                    ))}
                  </ul>
                )}

                {saveZones.isPending && (
                  <div className="text-center text-xs text-brand">Saving & reloading rules…</div>
                )}
              </div>
            )}
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
