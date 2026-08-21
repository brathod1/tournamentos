import "./App.css";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { Toaster } from "./components/ui/sonner";
import Dashboard from "./pages/Dashboard";
import TournamentDetail from "./pages/TournamentDetail";

function App() {
  return (
    <div className="App grain bg-zinc-950 min-h-screen text-zinc-50">
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/t/:id" element={<TournamentDetail />} />
        </Routes>
      </BrowserRouter>
      <Toaster position="top-right" theme="dark" richColors />
    </div>
  );
}

export default App;
