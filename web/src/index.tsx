import { render } from "solid-js/web";
import "./hud.css";
import "./widgets"; // side effect: registers all widgets
import { connect } from "./core/socket";
import { loadConfig, watchConfigUpdates } from "./core/config";
import { Hud } from "./Hud";

async function main(): Promise<void> {
  await loadConfig();
  connect();
  watchConfigUpdates();
  render(() => <Hud />, document.getElementById("root")!);
}

void main();
