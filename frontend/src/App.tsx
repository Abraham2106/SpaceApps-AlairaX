import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Route, Routes } from "react-router-dom";
import { Shell } from "./components/Shell";
import { MapScreen } from "./screens/MapScreen";
import { CantonsScreen } from "./screens/CantonsScreen";
import { RotationsScreen } from "./screens/RotationsScreen";
import { SeasonScreen } from "./screens/SeasonScreen";
import { TrustScreen } from "./screens/TrustScreen";

const client = new QueryClient();

export default function App() {
  return (
    <QueryClientProvider client={client}>
      <Routes>
        <Route element={<Shell />}>
          <Route index element={<MapScreen />} />
          <Route path="cantones" element={<CantonsScreen />} />
          <Route path="rotaciones" element={<RotationsScreen />} />
          <Route path="temporada" element={<SeasonScreen />} />
          <Route path="confianza" element={<TrustScreen />} />
        </Route>
      </Routes>
    </QueryClientProvider>
  );
}
