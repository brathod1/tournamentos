import React, { createContext, useContext, useEffect, useState, useCallback } from "react";
import { api, getToken, setToken, setUnauthorizedHandler } from "./api";
import { toast } from "sonner";

/** Auth state for the whole app.
 *  Signed out is a valid state — the app stays usable in read-only mode so
 *  players and parents can follow the schedule without an account. */
const AuthCtx = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [ready, setReady] = useState(false);
  const [initialized, setInitialized] = useState(true);   // has any account been created?

  const signOut = useCallback((quiet) => {
    setToken(null);
    setUser(null);
    if (!quiet) toast.success("Signed out");
  }, []);

  useEffect(() => {
    setUnauthorizedHandler(() => {
      setUser(null);
      toast.warning("Your session expired — sign in again to make changes");
    });
  }, []);

  useEffect(() => {
    (async () => {
      try {
        const st = await api.authStatus();
        setInitialized(st.initialized);
      } catch { /* backend unreachable; surfaced elsewhere */ }
      if (getToken()) {
        try { setUser(await api.me()); }
        catch { setToken(null); }
      }
      setReady(true);
    })();
  }, []);

  const signIn = async (email, password) => {
    const r = await api.login({ email, password });
    setToken(r.access_token);
    setUser(r.user);
    setInitialized(true);
    return r.user;
  };

  const bootstrap = async (payload) => {
    const r = await api.bootstrap(payload);
    setToken(r.access_token);
    setUser(r.user);
    setInitialized(true);
    return r.user;
  };

  return (
    <AuthCtx.Provider value={{
      user, ready, initialized, signIn, bootstrap, signOut,
      canEdit: !!user, isAdmin: user?.role === "admin",
    }}>
      {children}
    </AuthCtx.Provider>
  );
}

export const useAuth = () => useContext(AuthCtx) || { user: null, canEdit: false, ready: true };

/** Wrap any editing control: renders nothing for signed-out visitors. */
export const CanEdit = ({ children }) => (useAuth().canEdit ? <>{children}</> : null);
