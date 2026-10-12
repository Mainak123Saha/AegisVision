import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Film, MapPin, Play, Radio, Square, Trash2, Video, Webcam } from "lucide-react";
import { deleteCamera, startCamera, stopCamera } from "../../api/cameras";
import type { Camera, CameraStatus } from "../../types/camera";
import { formatTimeAgo } from "../../utils";
import { Alert, Button, StatusPill } from "../common/ui";

const TYPE_ICON = { mp4: Film, webcam: Webcam, rtsp: Radio } as const;

export default function CameraCard({ camera, status }: { camera: Camera; status: CameraStatus | undefined }) {
  const qc = useQueryClient();
  const refresh = () => {
    qc.invalidateQueries({ queryKey: ["cameras"] });
    qc.invalidateQueries({ queryKey: ["camera-status", camera.id] });
  };
  const start = useMutation({ mutationFn: () => startCamera(camera.id), onSettled: refresh });
  const stop = useMutation({ mutationFn: () => stopCamera(camera.id), onSettled: refresh });
  const remove = useMutation({ mutationFn: () => deleteCamera(camera.id), onSettled: refresh });

  const running = status?.running ?? false;
  const failed = !running && !!status?.last_error;
  const label = !status ? "Checking…" : running ? "Monitoring" : failed ? "Failed" : "Stopped";
  const busy = start.isPending || stop.isPending || remove.isPending;
  const error = (start.error ?? stop.error ?? remove.error) as Error | null;
  const Icon = TYPE_ICON[camera.source_type] ?? Video;

  const border = running
    ? "border-ok/45 shadow-lg shadow-ok/10"
    : failed ? "border-bad/45" : "border-line";

  return (
    <div className={`flex flex-col gap-2 rounded-2xl border bg-gradient-to-b from-[#172044]/75 to-panel/75 p-5 transition hover:-translate-y-0.5 ${border}`}>
      <div className="flex items-center justify-between">
        <div className="grid size-10 place-items-center rounded-xl bg-brand/15 text-brand"><Icon size={20} /></div>
        <StatusPill tone={running ? "ok" : failed ? "down" : "idle"}>{label}</StatusPill>
      </div>
      <h3 className="mt-1 text-[17px] font-semibold">{camera.name}</h3>
      <div className="flex items-center gap-1 text-[12.5px] text-mute"><MapPin size={12} /> {camera.location || "No location"}</div>
      <dl className="my-2 grid grid-cols-[auto_1fr] gap-x-3.5 gap-y-1.5 text-[13px]">
        <dt className="text-mute">Source</dt><dd className="text-right">{camera.source_type.toUpperCase()}</dd>
        <dt className="text-mute">URI</dt>
        <dd className="min-w-0 truncate text-right font-mono text-[12.5px]" title={camera.source_uri}>{camera.source_uri}</dd>
        <dt className="text-mute">Events saved</dt><dd className="text-right">{status?.events_persisted ?? 0}</dd>
        <dt className="text-mute">Started</dt>
        <dd className="text-right">{running && status?.started_at ? formatTimeAgo(status.started_at) : "—"}</dd>
      </dl>
      {failed && <Alert>{status?.last_error}</Alert>}
      {error && <Alert>{error.message}</Alert>}
      <div className="mt-1 flex gap-2">
        {running ? (
          <Button variant="danger" className="flex-1 justify-center" disabled={busy} onClick={() => stop.mutate()}>
            <Square size={14} /> Stop
          </Button>
        ) : (
          <Button variant="primary" className="flex-1 justify-center" disabled={busy} onClick={() => start.mutate()}>
            <Play size={14} /> Start monitoring
          </Button>
        )}
        <Button variant="icon" disabled={busy} title="Delete camera" aria-label="Delete camera"
          onClick={() => { if (confirm(`Delete camera "${camera.name}"? Its events are kept.`)) remove.mutate(); }}>
          <Trash2 size={15} />
        </Button>
      </div>
    </div>
  );
}
