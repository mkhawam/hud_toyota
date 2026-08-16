/** Panel navigation: drive the whole settings page with arrows + OK.
 *
 * Built for a small in-car button panel that emulates a keyboard
 * (Up/Down/Left/Right + Enter), but works with any keyboard.
 *
 * Two modes:
 *  - NAV (default): Up/Down (and Left/Right) move focus between controls;
 *    OK activates — buttons/switches click, value controls (select, slider,
 *    number, text) enter EDIT mode.
 *  - EDIT: arrows go to the control natively (slider slides, select cycles,
 *    number steps); OK (or Escape) confirms and returns to NAV.
 *
 * Escape in NAV mode returns to the HUD when a return URL is present.
 */

const FOCUSABLE = "button, input, select, a[href]";

function focusables(): HTMLElement[] {
  return [...document.querySelectorAll<HTMLElement>(FOCUSABLE)].filter(
    (el) => el.offsetParent !== null && !el.hasAttribute("disabled"),
  );
}

function isValueControl(el: Element | null): boolean {
  if (el instanceof HTMLSelectElement) return true;
  if (el instanceof HTMLInputElement) {
    if (el.type === "checkbox") return false; // OK toggles directly
    return true; // range, number, text
  }
  return false;
}

export function installPanelNav(returnUrl: string | null): void {
  let editing = false;
  document.body.classList.add("panel-nav");

  const setEditing = (on: boolean) => {
    editing = on;
    document.body.classList.toggle("editing", on);
  };

  const move = (dir: 1 | -1) => {
    const list = focusables();
    if (list.length === 0) return;
    const idx = list.indexOf(document.activeElement as HTMLElement);
    const next = list[idx === -1 ? (dir === 1 ? 0 : list.length - 1) : (idx + dir + list.length) % list.length];
    next.focus({ preventScroll: true });
    next.scrollIntoView({ block: "center", behavior: "smooth" });
  };

  document.addEventListener(
    "keydown",
    (ev) => {
      const active = document.activeElement as HTMLElement | null;

      if (editing) {
        if (ev.key === "Enter" || ev.key === "Escape") {
          setEditing(false);
          ev.preventDefault();
          ev.stopPropagation();
        }
        return; // arrows reach the control natively
      }

      switch (ev.key) {
        case "ArrowDown":
        case "ArrowRight":
          ev.preventDefault();
          move(1);
          break;
        case "ArrowUp":
        case "ArrowLeft":
          ev.preventDefault();
          move(-1);
          break;
        case "Enter":
          ev.preventDefault();
          if (isValueControl(active)) setEditing(true);
          else active?.click();
          break;
        case "Escape":
          if (returnUrl !== null) location.assign(returnUrl);
          break;
      }
    },
    true,
  );
}
