import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus } from "lucide-react";
import { useState, type FormEvent } from "react";
import { createCamera } from "../../api/cameras";
import type { SourceType } from "../../types/camera";
import { Alert, Button, Card, inputCls, labelCls } from "../common/ui";

const PLACEHOLDER: Record<SourceType, string> = {
  mp4: "assets/videos/surveillance_clip.mp4",
  webcam: "0",
  rtsp: "rtsp://user:pass@192.168.1.10/stream",
};

export default function AddCameraForm({ onDone }: { onDone: () => void }) {
  const qc = useQueryClient();
  const [name, setName] = useState("");
  const [type, setType] = useState<SourceType>("mp4");
  const [uri, setUri] = useState("");
  const [location, setLocation] = useState("");

  const create = useMutation({
    mutationFn: () => createCamera({ name, source_type: type, source_uri: uri, location: location || null }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["cameras"] }); onDone(); },
  });

  const submit = (e: FormEvent) => { e.preventDefault(); create.mutate(); };

  return (
    <Card>
      <form className="flex flex-col gap-4" onSubmit={submit}>
        <h3 className="text-base font-semibold">Add camera</h3>
        <div className="grid grid-cols-[repeat(auto-fit,minmax(240px,1fr))] gap-3.5">
          <label className={labelCls}>Name<input className={inputCls} required value={name} onChange={(e) => setName(e.target.value)} placeholder="Front entrance" /></label>
          <label className={labelCls}>Source type
            <select className={inputCls} value={type} onChange={(e) => setType(e.target.value as SourceType)}>
              <option value="mp4">MP4 file</option>
              <option value="webcam">Webcam</option>
              <option value="rtsp">RTSP / HTTP stream</option>
            </select>
          </label>
          <label className={labelCls}>Source (file path, device index or URL)
            <input className={inputCls} required value={uri} onChange={(e) => setUri(e.target.value)} placeholder={PLACEHOLDER[type]} />
          </label>
          <label className={labelCls}>Location (optional)<input className={inputCls} value={location} onChange={(e) => setLocation(e.target.value)} placeholder="Lobby" /></label>
        </div>
        {create.error && <Alert>{(create.error as Error).message}</Alert>}
        <div className="flex justify-end gap-2.5">
          <Button type="button" onClick={onDone}>Cancel</Button>
          <Button variant="primary" disabled={create.isPending}><Plus size={14} /> {create.isPending ? "Adding…" : "Add camera"}</Button>
        </div>
        <p className="text-[12.5px] text-mute">Adding a camera only saves its record. Press “Start monitoring” to begin processing.</p>
      </form>
    </Card>
  );
}
