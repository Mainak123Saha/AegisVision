import { useIsFetching, useQuery } from "@tanstack/react-query";
import { Activity } from "lucide-react";
import { useLocation } from "react-router-dom";
import { apiGet } from "../../api/client";
import { StatusPill } from "../common/ui";

const TITLES: Record<string, string> = {
  "/": "Dashboard",
  "/cameras": "Cameras",
  "/events": "Events",
  "/analytics": "Analytics",
};

interface Health { status: string; database: string }

export default function Header() {
  const { pathname } = useLocation();
  const fetching = useIsFetching();
  const health = useQuery({
    queryKey: ["health"],
    queryFn: () => apiGet<Health>("/health"),
    refetchInterval: 10000,
    retry: false,
  });

  let tone: "ok" | "degraded" | "down" = "down";
  let text = "API offline";
  if (health.data) {
    tone = health.data.database === "up" ? "ok" : "degraded";
    text = tone === "ok" ? "API online" : "Database down";
  }

  return (
    <header className="mx-auto flex w-full max-w-[1400px] items-center justify-between px-8 pb-4 pt-6 max-md:px-4">
      <h1 className="text-[26px] font-bold tracking-tight">{TITLES[pathname] ?? "AegisVision"}</h1>
      <div className="flex items-center gap-3.5">
        {fetching > 0 && <Activity size={16} className="animate-pulse text-mute" />}
        <StatusPill tone={tone}>{text}</StatusPill>
      </div>
    </header>
  );
}
