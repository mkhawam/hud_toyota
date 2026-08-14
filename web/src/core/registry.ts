/**
 * Widget registry. A widget is just a Solid component registered under the
 * name the layout config refers to — adding a widget means one .tsx file
 * plus one register call in widgets/index.ts.
 */
import type { Component } from "solid-js";

const registry = new Map<string, Component>();

export function registerWidget(name: string, component: Component): void {
  registry.set(name, component);
}

export function getWidget(name: string): Component | undefined {
  const w = registry.get(name);
  if (!w) console.warn(`layout references unknown widget: ${name}`);
  return w;
}
