import { ChevronLeft, ChevronRight, FilterX } from "lucide-react";
import { useState } from "react";
import { Button, Card, EmptyState, ErrorState, Spinner, inputCls, labelCls } from "../components/common/ui";
import EventsTable from "../components/events/EventsTable";
import { useCameras, useEvents } from "../hooks/queries";
import { EVENT_TYPES, SEVERITIES, type EventType, type Severity } from "../types/event";
import { EVENT_LABEL } from "../utils";

const PAGE_SIZE = 20;

export default function Events() {
  const [type, setType] = useState<EventType | "">("");
  const [severity, setSeverity] = useState<Severity | "">("");
  const [camera, setCamera] = useState<number | "">("");
  const [page, setPage] = useState(0);

  const cameras = useCameras();
  const events = useEvents({ event_type: type, severity, camera_id: camera, limit: PAGE_SIZE, offset: page * PAGE_SIZE });

  const total = events.data?.total ?? 0;
  const pages = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const filtered = type !== "" || severity !== "" || camera !== "";
  // Changing any filter returns to the first page.
  const change = <T,>(set: (v: T) => void) => (v: T) => { set(v); setPage(0); };

  return (
    <div className="flex flex-col gap-5">
      <Card>
        <div className="flex flex-wrap items-end gap-3.5">
          <label className={`${labelCls} min-w-[170px]`}>Type
            <select className={inputCls} value={type} onChange={(e) => change(setType)(e.target.value as EventType | "")}>
              <option value="">All types</option>
              {EVENT_TYPES.map((t) => <option key={t} value={t}>{EVENT_LABEL[t]}</option>)}
            </select>
          </label>
          <label className={`${labelCls} min-w-[170px]`}>Severity
            <select className={inputCls} value={severity} onChange={(e) => change(setSeverity)(e.target.value as Severity | "")}>
              <option value="">All severities</option>
              {SEVERITIES.map((s) => <option key={s} value={s}>{s}</option>)}
            </select>
          </label>
          <label className={`${labelCls} min-w-[170px]`}>Camera
            <select className={inputCls} value={camera} onChange={(e) => change(setCamera)(e.target.value === "" ? "" : Number(e.target.value))}>
              <option value="">All cameras</option>
              {(cameras.data ?? []).map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
            </select>
          </label>
          {filtered && (
            <Button onClick={() => { setType(""); setSeverity(""); setCamera(""); setPage(0); }}>
              <FilterX size={14} /> Clear
            </Button>
          )}
          <span className="flex-1" />
          <span className="text-[12.5px] text-mute">{events.data ? `${total} event${total === 1 ? "" : "s"}` : ""}</span>
        </div>
      </Card>

      <Card>
        {events.isLoading ? <Spinner label="Loading events…" />
          : events.isError ? <ErrorState error={events.error} onRetry={() => events.refetch()} />
          : !events.data?.items.length
            ? <EmptyState title={filtered ? "No events match these filters" : "No events recorded yet"}
                hint={filtered ? "Try clearing a filter." : "Start a camera to generate events."} />
            : <>
                <EventsTable events={events.data.items} cameras={cameras.data} />
                <div className="flex items-center justify-between pt-4">
                  <Button disabled={page === 0} onClick={() => setPage(page - 1)}><ChevronLeft size={14} /> Prev</Button>
                  <span className="text-[12.5px] text-mute">Page {page + 1} of {pages}</span>
                  <Button disabled={page + 1 >= pages} onClick={() => setPage(page + 1)}>Next <ChevronRight size={14} /></Button>
                </div>
              </>}
      </Card>
    </div>
  );
}
