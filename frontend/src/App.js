import "./App.css";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { Toaster } from "./components/ui/sonner";
import { AuthProvider } from "./lib/auth";
import Dashboard from "./pages/Dashboard";
import TournamentDetail from "./pages/TournamentDetail";
import Login from "./pages/Login";

function App() {
  return (
    <div className="App grain bg-zinc-950 min-h-screen text-zinc-50">
      <BrowserRouter>
        <AuthProvider>
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/login" element={<Login />} />
            <Route path="/t/:id" element={<TournamentDetail />} />
          </Routes>
        </AuthProvider>
      </BrowserRouter>
      <Toaster position="top-right" theme="dark" richColors />
    </div>
  );
}

export default App;
