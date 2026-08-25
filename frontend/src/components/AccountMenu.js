import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "./ui/dialog";
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from "./ui/select";
import { Labeled, Overline, ConfirmDelete } from "./bits";
import { LogIn, LogOut, UserCog, Users, Plus, Trash2, KeyRound, Eye } from "lucide-react";
import { toast } from "sonner";

/** Header control: sign in / account + admin user management. */
export default function AccountMenu() {
  const { user, canEdit, isAdmin, signOut } = useAuth();
  const nav = useNavigate();
  const [open, setOpen] = useState(false);
  const [users, setUsers] = useState([]);
  const [nu, setNu] = useState({ email: "", name: "", password: "", role: "organizer" });
  const [pw, setPw] = useState({ current_password: "", new_password: "" });

  const loadUsers = () => { if (isAdmin) api.listUsers().then(setUsers).catch(() => {}); };
  useEffect(() => { if (open) loadUsers(); /* eslint-disable-next-line */ }, [open, isAdmin]);

  if (!canEdit) {
    return (
      <div className="flex items-center gap-3">
        <span className="hidden sm:flex items-center gap-1.5 text-xs uppercase tracking-widest text-zinc-500">
          <Eye className="w-3.5 h-3.5" />View only
        </span>
        <Button data-testid="signin-btn" onClick={() => nav("/login", { state: { from: window.location.pathname } })}
          className="rounded-none bg-lime-400 text-black hover:bg-lime-500 font-bold uppercase tracking-wider gap-2 h-9 text-xs">
          <LogIn className="w-4 h-4" />Sign In
        </Button>
      </div>
    );
  }

  const addUser = async () => {
    if (!nu.email.trim() || nu.password.length < 8) return toast.error("Email and a password of at least 8 characters are required");
    try { await api.createUser(nu); toast.success("Account created"); setNu({ email: "", name: "", password: "", role: "organizer" }); loadUsers(); }
    catch (e) { toast.error(e.response?.data?.detail || "Could not create account"); }
  };
  const removeUser = async (id) => {
    try { await api.deleteUser(id); toast.success("Account removed"); loadUsers(); }
    catch (e) { toast.error(e.response?.data?.detail || "Could not remove account"); }
  };
  const changePw = async () => {
    if (pw.new_password.length < 8) return toast.error("New password must be at least 8 characters");
    try { await api.changePassword(pw); toast.success("Password updated"); setPw({ current_password: "", new_password: "" }); }
    catch (e) { toast.error(e.response?.data?.detail || "Could not update password"); }
  };

  return (
    <>
      <div className="flex items-center gap-2">
        <button data-testid="account-btn" onClick={() => setOpen(true)}
          className="flex items-center gap-2 text-xs uppercase tracking-wider text-zinc-400 hover:text-lime-400 px-2 py-1.5">
          <UserCog className="w-4 h-4" /><span className="hidden sm:inline">{user.name || user.email}</span>
        </button>
        <button data-testid="signout-btn" onClick={() => signOut()} title="Sign out"
          className="text-zinc-500 hover:text-red-400 p-1.5"><LogOut className="w-4 h-4" /></button>
      </div>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="bg-zinc-900 border-zinc-800 text-zinc-50 rounded-none max-w-2xl max-h-[85vh] overflow-y-auto">
          <DialogHeader><DialogTitle className="font-display text-2xl uppercase tracking-tight">Account</DialogTitle></DialogHeader>

          <div className="text-sm text-zinc-400">
            Signed in as <b className="text-zinc-100">{user.email}</b>
            <span className="ml-2 text-[10px] uppercase tracking-widest px-2 py-0.5 bg-zinc-800 text-lime-400">{user.role}</span>
          </div>

          <div className="border-t border-zinc-800 pt-4">
            <Overline className="mb-3 flex items-center gap-2"><KeyRound className="w-3.5 h-3.5" />Change Password</Overline>
            <div className="grid grid-cols-2 gap-4">
              <Labeled label="Current"><Input type="password" value={pw.current_password}
                onChange={(e) => setPw({ ...pw, current_password: e.target.value })}
                className="rounded-none bg-zinc-950 border-zinc-800 focus:border-lime-400" /></Labeled>
              <Labeled label="New (min 8)"><Input type="password" value={pw.new_password}
                onChange={(e) => setPw({ ...pw, new_password: e.target.value })}
                className="rounded-none bg-zinc-950 border-zinc-800 focus:border-lime-400" /></Labeled>
            </div>
            <Button data-testid="change-password-btn" onClick={changePw}
              className="rounded-none bg-zinc-800 hover:bg-zinc-700 text-zinc-100 uppercase tracking-wider text-xs mt-3">Update Password</Button>
          </div>

          {isAdmin && (
            <div className="border-t border-zinc-800 pt-4">
              <Overline className="mb-3 flex items-center gap-2"><Users className="w-3.5 h-3.5" />Organizer Accounts</Overline>
              <div className="border border-zinc-800 divide-y divide-zinc-800 mb-4">
                {users.map((u) => (
                  <div key={u.id} data-testid={`user-row-${u.id}`} className="flex items-center justify-between px-3 py-2 text-sm">
                    <div className="min-w-0">
                      <div className="font-semibold truncate">{u.name}</div>
                      <div className="text-xs text-zinc-500 truncate">{u.email}</div>
                    </div>
                    <div className="flex items-center gap-3 shrink-0">
                      <span className="text-[10px] uppercase tracking-widest text-zinc-500">{u.role}</span>
                      {u.id !== user.id && (
                        <ConfirmDelete title="Remove account?" testId={`confirm-delete-user-${u.id}`}
                          description={`${u.name} (${u.email}) will no longer be able to sign in. Tournament data is unaffected.`}
                          onConfirm={() => removeUser(u.id)}>
                          <button className="text-zinc-600 hover:text-red-500"><Trash2 className="w-4 h-4" /></button>
                        </ConfirmDelete>
                      )}
                    </div>
                  </div>
                ))}
              </div>
              <div className="grid grid-cols-2 gap-3">
                <Labeled label="Name"><Input data-testid="new-user-name" value={nu.name} onChange={(e) => setNu({ ...nu, name: e.target.value })}
                  className="rounded-none bg-zinc-950 border-zinc-800 focus:border-lime-400" /></Labeled>
                <Labeled label="Email"><Input data-testid="new-user-email" value={nu.email} onChange={(e) => setNu({ ...nu, email: e.target.value })}
                  className="rounded-none bg-zinc-950 border-zinc-800 focus:border-lime-400" /></Labeled>
                <Labeled label="Password (min 8)"><Input data-testid="new-user-password" type="password" value={nu.password}
                  onChange={(e) => setNu({ ...nu, password: e.target.value })}
                  className="rounded-none bg-zinc-950 border-zinc-800 focus:border-lime-400" /></Labeled>
                <Labeled label="Role">
                  <Select value={nu.role} onValueChange={(v) => setNu({ ...nu, role: v })}>
                    <SelectTrigger className="rounded-none bg-zinc-950 border-zinc-800 focus:border-lime-400"><SelectValue /></SelectTrigger>
                    <SelectContent className="bg-zinc-900 border-zinc-800 text-zinc-50 rounded-none">
                      <SelectItem value="organizer">Organizer</SelectItem>
                      <SelectItem value="admin">Admin</SelectItem>
                    </SelectContent>
                  </Select>
                </Labeled>
              </div>
              <Button data-testid="add-user-btn" onClick={addUser}
                className="rounded-none bg-lime-400 text-black hover:bg-lime-500 font-bold uppercase tracking-wider gap-2 mt-3 text-xs h-9">
                <Plus className="w-4 h-4" />Add Account
              </Button>
              <p className="text-xs text-zinc-600 mt-3">Everyone signed in can edit every tournament. Admins can additionally manage accounts.</p>
            </div>
          )}

          <DialogFooter><Button onClick={() => setOpen(false)}
            className="rounded-none bg-zinc-800 hover:bg-zinc-700 text-zinc-100 uppercase tracking-wider w-full">Close</Button></DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
