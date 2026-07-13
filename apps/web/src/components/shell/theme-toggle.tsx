"use client";

import { useEffect, useState } from "react";

export function ThemeToggle() {
  const [theme, setTheme] = useState<"aurora-light" | "radar-dark">("aurora-light");

  useEffect(() => {
    const storedTheme = window.localStorage.getItem("bighead-theme");
    const nextTheme = storedTheme === "radar-dark" ? "radar-dark" : "aurora-light";
    document.documentElement.dataset.theme = nextTheme;
    setTheme(nextTheme);
  }, []);

  function toggleTheme() {
    const nextTheme = theme === "aurora-light" ? "radar-dark" : "aurora-light";
    setTheme(nextTheme);
    document.documentElement.dataset.theme = nextTheme;
    window.localStorage.setItem("bighead-theme", nextTheme);
  }

  return (
    <button className="bh-chip" onClick={toggleTheme} type="button">
      {theme === "aurora-light" ? "Tema escuro" : "Tema claro"}
    </button>
  );
}
