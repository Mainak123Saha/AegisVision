import { Plus } from "lucide-react";
import { useState } from "react";
import AddCameraForm from "../components/cameras/AddCameraForm";
import CameraCard from "../components/cameras/CameraCard";
import { Button, EmptyState, ErrorState, Spinner } from "../components/common/ui";
import { useCameraStatuses, useCameras } from "../hooks/queries";

export default function Cameras() {
  const [adding, setAdding] = useState(false);
  const cameras = useCameras();
  const statuses = useCameraStatuses(cameras.data);

  return (
    <div className="flex flex-col gap-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-mute">A camera record is not a running stream — start monitoring to process it.</p>
        {!adding && <Button variant="primary" onClick={() => setAdding(true)}><Plus size={14} /> Add camera</Button>}
      </div>
      {adding && <AddCameraForm onDone={() => setAdding(false)} />}

      {cameras.isLoading ? <Spinner label="Loading cameras…" />
        : cameras.isError ? <ErrorState error={cameras.error} onRetry={() => cameras.refetch()} />
        : !cameras.data?.length ? <EmptyState title="No cameras yet" hint="Add a camera to start monitoring." />
        : <div className="grid grid-cols-[repeat(auto-fill,minmax(300px,1fr))] gap-5">
            {cameras.data.map((c) => <CameraCard key={c.id} camera={c} status={statuses[c.id]} />)}
          </div>}
    </div>
  );
}
