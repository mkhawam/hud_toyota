/**
 * Auto-hiding mouse cursor for the kiosk page.
 *
 * The page's default is `cursor: none`. While the mouse is actually moving
 * we show a cursor and hide it again after a short idle. The visible cursor
 * is a custom SVG (not the system theme): the kiosk runs under an invisible
 * Xcursor theme so the compositor's own arrow never appears at boot, which
 * would also blank any theme-based cursor Chromium tried to show.
 */

const IDLE_MS = 2500;

export function installAutoHideCursor(): void {
  let timer: ReturnType<typeof setTimeout> | undefined;
  const hide = () => document.body.classList.remove("cursor-visible");
  const onMove = () => {
    document.body.classList.add("cursor-visible");
    clearTimeout(timer);
    timer = setTimeout(hide, IDLE_MS);
  };
  window.addEventListener("mousemove", onMove, { passive: true });
  window.addEventListener("mousedown", onMove, { passive: true });
}
