"use client";

import React from "react";
import { Compass, Sun, Moon } from "lucide-react";
import { ThemeMode } from "./types";

interface TopBarProps {
  theme: ThemeMode;
  onToggleTheme: () => void;
}

export default function TopBar({ theme, onToggleTheme }: TopBarProps) {
  return (
    <header className="top-bar">
      <div className="top-bar-inner">
        <div className="flex items-center gap-2.5 min-w-0">
          <div className="w-8 h-8 shrink-0 rounded bg-[#E11D48] flex items-center justify-center">
            <Compass size={19} className="text-white" aria-hidden="true" />
          </div>
          <div className="leading-tight min-w-0">
            <p className="text-sm font-bold tracking-tight">OptiCompromise</p>
            <p className="text-xs text-slate-600 dark:text-slate-300 truncate">
              Programación de Compromiso Multiobjetivo · UNAL
            </p>
          </div>
        </div>
        <button
          type="button"
          onClick={onToggleTheme}
          aria-label={theme === "dark" ? "Cambiar a tema claro" : "Cambiar a tema oscuro"}
          className="workspace-button top-bar-theme"
        >
          {theme === "dark" ? <Sun size={17} aria-hidden="true" /> : <Moon size={17} aria-hidden="true" />}
        </button>
      </div>
    </header>
  );
}
