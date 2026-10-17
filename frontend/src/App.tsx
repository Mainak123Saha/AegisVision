import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import Header from "./components/layout/Header";
import Sidebar from "./components/layout/Sidebar";
import Analytics from "./pages/Analytics";
import CameraLive from "./pages/CameraLive";
import Cameras from "./pages/Cameras";
import Dashboard from "./pages/Dashboard";
import Events from "./pages/Events";

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: 1, staleTime: 2000, refetchOnWindowFocus: true } },
});

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <div className="flex min-h-full max-md:flex-col">
          <Sidebar />
          <div className="flex min-w-0 flex-1 flex-col">
            <Header />
            <main className="mx-auto w-full max-w-[1400px] px-8 pb-10 pt-2 max-md:px-4">
              <Routes>
                <Route path="/" element={<Dashboard />} />
                <Route path="/cameras" element={<Cameras />} />
                <Route path="/cameras/:cameraName" element={<CameraLive />} />
                <Route path="/events" element={<Events />} />
                <Route path="/analytics" element={<Analytics />} />
                <Route path="*" element={<Navigate to="/" replace />} />
              </Routes>
            </main>
          </div>
        </div>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
