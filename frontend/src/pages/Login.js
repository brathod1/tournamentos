import React, { useState } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { useAuth } from "../lib/auth";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Overline, Labeled } from "../components/bits";
import { Trophy, LogIn, Eye } from "lucide-react";
import { toast } from "sonner";

/** Sign-in screen. Doubles as first-run setup: when no account exists yet it
 *  creates the initial admin instead of asking for credentials that don't exist. */
export default function Login() {
  const { signIn, bootstrap, initialized, ready } = useAuth();
  const nav = useNavigate();
  const loc = useLocation();
  const back = loc.state?.from || "/";
  const [f, setF] = useState({ email: "", password: "", name: "" });
  const [busy, setBusy] = useState(false);
  const setup = ready && !initialized;

  const submit = async (e) => {
    e?.preventDefault();
    if (!f.email.trim() || !f.password) return toast.error("Email and password are required");
    if (setup && f.password.length < 8) return toast.error("Choose a password of at least 8 characters");
    setBusy(true);
    try {
      if (setup) { await bootstrap({ email: f.email, password: f.password, name: f.name || "Admin", role: "admin" }); toast.success("Admin account created"); }
      else { await signIn(f.email, f.password); toast.success("Signed in"); }
      nav(back, { replace: true });
    } catch (err) {
      toast.error(err.response?.data?.detail || "Could not sign in");
    }
    setBusy(false);
  };

  return (
    <div className="relative z-10 min-h-screen flex items-center justify-center px-6">
      <div className="w-full max-w-md">
        <div className="flex items-center gap-3 mb-8">
          <div className="w-10 h-10 bg-lime-400 flex items-center justify-center">
            <Trophy className="w-6 h-6 text-black" strokeWidth={2.2} />
          </div>
          <div>
            <div className="font-display text-2xl font-bold uppercase tracking-tight leading-none">Tournament<span className="text-lime-400">OS</span></div>
            <Overline className="mt-1">{setup ? "First-time setup" : "Organizer sign in"}</Overline>
          </div>
        </div>

        <form onSubmit={submit} className="border border-zinc-800 bg-zinc-900/50 p-6 space-y-4">
          {setup && (
            <p className="text-sm text-zinc-400 border-l-2 border-lime-400 pl-3">
              No accounts exist yet. Create the first admin account — you'll be able to add
              other organizers from the Accounts screen afterwards.
            </p>
          )}
          {setup && (
            <Labeled label="Your Name">
              <Input data-testid="login-name" value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })}
                placeholder="Tournament Director" className="rounded-none bg-zinc-950 border-zinc-800 focus:border-lime-400" />
            </Labeled>
          )}
          <Labeled label="Email">
            <Input data-testid="login-email" type="email" autoComplete="username" value={f.email}
              onChange={(e) => setF({ ...f, email: e.target.value })}
              className="rounded-none bg-zinc-950 border-zinc-800 focus:border-lime-400" />
          </Labeled>
          <Labeled label={setup ? "Password (min 8 characters)" : "Password"}>
            <Input data-testid="login-password" type="password"
              autoComplete={setup ? "new-password" : "current-password"} value={f.password}
              onChange={(e) => setF({ ...f, password: e.target.value })}
              className="rounded-none bg-zinc-950 border-zinc-800 focus:border-lime-400" />
          </Labeled>
          <Button data-testid="login-submit" type="submit" disabled={busy}
            className="rounded-none bg-lime-400 text-black hover:bg-lime-500 font-bold uppercase tracking-wider w-full gap-2">
            <LogIn className="w-4 h-4" />{busy ? "Please wait…" : setup ? "Create Admin Account" : "Sign In"}
          </Button>
        </form>

        <button data-testid="browse-readonly" onClick={() => nav("/")}
          className="mt-4 w-full text-xs uppercase tracking-widest text-zinc-500 hover:text-lime-400 flex items-center justify-center gap-2 py-2">
          <Eye className="w-3.5 h-3.5" />Browse schedules without signing in
        </button>
      </div>
    </div>
  );
}
