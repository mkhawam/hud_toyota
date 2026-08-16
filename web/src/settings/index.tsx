import { render } from "solid-js/web";
import "./settings.css";
import { loadConfig } from "../core/config";
import { installPanelNav } from "./kbnav";
import { Settings } from "./Settings";

async function main(): Promise<void> {
  await loadConfig(); // units for the chart axes + current values for forms

  // Opened from the HUD (OK button on the panel): enable arrow/OK
  // navigation and remember where to go back to.
  const params = new URLSearchParams(location.search);
  const fromHud = params.get("hud") === "1";
  const returnUrl = fromHud ? "/" + (params.get("return") ?? "") : null;
  installPanelNav(returnUrl);

  render(() => <Settings backUrl={returnUrl} />, document.getElementById("root")!);
}

void main();
