import { render } from "solid-js/web";
import "./settings.css";
import { loadConfig } from "../core/config";
import { Settings } from "./Settings";

async function main(): Promise<void> {
  await loadConfig();
  render(() => <Settings />, document.getElementById("root")!);
}

void main();
