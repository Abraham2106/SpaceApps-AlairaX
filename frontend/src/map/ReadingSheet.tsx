import { translate } from "../lib/i18n";
import { useEffect, useRef, useState, type KeyboardEvent, type PointerEvent, type ReactNode } from "react";
import { isMobile } from "../lib/viewport";
import type { Lang } from "../lib/types";

const SNAP_NAMES = ["readingSheet.short", "readingSheet.medium", "readingSheet.tall"] as const;

/** Tres alturas de la hoja inferior, medidas contra el escenario (la hoja no tapa todo el mapa). */
function snapHeights(sheet: HTMLElement | null): [number, number, number] {
  const room = (sheet?.offsetParent as HTMLElement | null)?.clientHeight ?? window.innerHeight;
  const tall = Math.round(room * 0.7);
  const short = Math.min(196, Math.round(room * 0.35));
  return [short, Math.round((short + tall) / 2), tall];
}

export function ReadingSheet({ children, title, lang }: { children: ReactNode; title: string; lang: Lang }) {
  const [open, setOpen] = useState(true);
  const sheetRef = useRef<HTMLElement>(null);
  const [snap, setSnap] = useState(0);

  // La altura de la hoja es una de tres: corta, media o alta. Arrastrar la sigue y al soltar ajusta a la más cercana.
  useEffect(() => {
    const apply = () => document.documentElement.style.setProperty("--sheet", `${snapHeights(sheetRef.current)[snap]}px`);
    apply();
    window.addEventListener("resize", apply);
    return () => window.removeEventListener("resize", apply);
  }, [snap]);

  function onHandleKey(event: KeyboardEvent) {
    if (event.key === "ArrowUp" || event.key === "ArrowRight") setSnap((value) => Math.min(2, value + 1));
    else if (event.key === "ArrowDown" || event.key === "ArrowLeft") setSnap((value) => Math.max(0, value - 1));
    else if (event.key === "Home") setSnap(0);
    else if (event.key === "End") setSnap(2);
    else if (event.key === "Enter" || event.key === " ") setSnap((value) => (value + 1) % 3);
    else return;
    event.preventDefault();
  }

  function onHandleDown(event: PointerEvent) {
    if (!isMobile()) return;
    const heights = snapHeights(sheetRef.current);
    const startY = event.clientY;
    const start = sheetRef.current?.getBoundingClientRect().height ?? heights[snap];
    let moved = 0;
    let current = start;
    const move = (pointer: globalThis.PointerEvent) => {
      moved = Math.max(moved, Math.abs(startY - pointer.clientY));
      current = Math.min(heights[2], Math.max(heights[0], start + (startY - pointer.clientY)));
      document.documentElement.style.setProperty("--sheet", `${current}px`);
    };
    const up = () => {
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", up);
      // Un toque sin arrastre pasa a la altura siguiente: alternativa al gesto para quien no arrastra.
      const next = moved < 6
        ? (snap + 1) % 3
        : heights.reduce((best, height, index) => (Math.abs(height - current) < Math.abs(heights[best] - current) ? index : best), 0);
      document.documentElement.style.setProperty("--sheet", `${heights[next]}px`);
      setSnap(next);
    };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", up);
  }

  return (
    <aside ref={sheetRef} className={`left-hud ${open ? "" : "is-collapsed"}`}>
      <section className="glass stack" aria-label={translate(lang, "common.reading")}>
        {open ? <div
          className="sheet-handle"
          role="slider"
          tabIndex={0}
          aria-orientation="vertical"
          aria-valuemin={0}
          aria-valuemax={2}
          aria-valuenow={snap}
          aria-valuetext={translate(lang, SNAP_NAMES[snap])}
          aria-label={translate(lang, "readingSheet.cardHeight")}
          onPointerDown={onHandleDown}
          onKeyDown={onHandleKey}
        /> : null}
        <div className="glass-top">
          {open ? <h1>{title}</h1> : null}
          <button type="button" className="text-btn" aria-expanded={open} onClick={() => setOpen((value) => !value)}>
            {open ? (translate(lang, "readingSheet.hide")) : (translate(lang, "common.reading"))}
          </button>
        </div>
        {open ? children : null}
      </section>
    </aside>
  );
}
