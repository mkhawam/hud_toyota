import { render } from "solid-js/web";
import "./trips.css";
import { loadConfig } from "../core/config";
import { Trips } from "./Trips";

async function main(): Promise<void> {
  await loadConfig(); // units for the chart axes
  render(() => <Trips />, document.getElementById("root")!);
}

void main();
