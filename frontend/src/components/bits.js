import React from "react";
import {
  AlertDialog, AlertDialogTrigger, AlertDialogContent, AlertDialogHeader, AlertDialogTitle,
  AlertDialogDescription, AlertDialogFooter, AlertDialogCancel, AlertDialogAction,
} from "./ui/alert-dialog";

/** Wraps any trigger element in a destructive-action confirmation dialog. */
export const ConfirmDelete = ({ title, description, onConfirm, children, testId }) => (
  <AlertDialog>
    <AlertDialogTrigger asChild>{children}</AlertDialogTrigger>
    <AlertDialogContent className="bg-zinc-900 border-zinc-800 text-zinc-50 rounded-none">
      <AlertDialogHeader>
        <AlertDialogTitle className="font-display uppercase">{title}</AlertDialogTitle>
        <AlertDialogDescription className="text-zinc-400">{description}</AlertDialogDescription>
      </AlertDialogHeader>
      <AlertDialogFooter>
        <AlertDialogCancel className="rounded-none bg-zinc-800 border-zinc-700 hover:bg-zinc-700">Cancel</AlertDialogCancel>
        <AlertDialogAction data-testid={testId} onClick={onConfirm}
          className="rounded-none bg-red-600 text-white hover:bg-red-700 font-bold uppercase">Delete</AlertDialogAction>
      </AlertDialogFooter>
    </AlertDialogContent>
  </AlertDialog>
);

export const Overline = ({ children, className = "" }) => (
  <div className={`text-[10px] uppercase tracking-[0.25em] text-zinc-500 font-semibold ${className}`}>{children}</div>
);

export const Panel = ({ children, className = "" }) => (
  <div className={`border border-zinc-800 bg-zinc-900/50 ${className}`}>{children}</div>
);

export const SectionTitle = ({ title, sub, right }) => (
  <div className="flex items-end justify-between gap-4 mb-6 flex-wrap">
    <div>
      {sub && <Overline className="mb-2">{sub}</Overline>}
      <h2 className="font-display text-3xl sm:text-4xl font-bold uppercase tracking-tight leading-none text-zinc-50">{title}</h2>
    </div>
    {right}
  </div>
);

export const Empty = ({ icon: Icon, title, hint, action }) => (
  <div className="border border-dashed border-zinc-800 bg-zinc-900/30 py-16 px-6 text-center flex flex-col items-center">
    {Icon && <Icon className="w-10 h-10 text-zinc-700 mb-4" strokeWidth={1.4} />}
    <p className="font-display text-xl uppercase tracking-wide text-zinc-300">{title}</p>
    {hint && <p className="text-sm text-zinc-500 mt-2 max-w-md">{hint}</p>}
    {action && <div className="mt-6">{action}</div>}
  </div>
);

export const Stat = ({ label, value, accent }) => (
  <div className="border border-zinc-800 bg-zinc-900/50 p-5">
    <Overline>{label}</Overline>
    <div className={`font-display text-4xl font-bold mt-2 leading-none ${accent ? "text-lime-400" : "text-zinc-50"}`}>{value}</div>
  </div>
);

export const groundLabel = (name) => {
  const s = (name ?? "").toString().trim();
  return /^\d+$/.test(s) ? `Ground ${s}` : s;
};

export const Labeled = ({ label, children }) => (
  <div className="space-y-1.5">
    <label className="text-xs uppercase tracking-wider text-zinc-400 font-semibold">{label}</label>
    {children}
  </div>
);
