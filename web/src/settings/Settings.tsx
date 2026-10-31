/** Phone settings app: a hub with drill-in sections (hash routes). */
import { createSignal, Match, onCleanup, Switch, type Component } from "solid-js";
import { Advanced } from "./Advanced";
import { Alerts } from "./Alerts";
import { Home } from "./Home";
import { Layout } from "./Layout";
import { Look } from "./Look";
import { Place } from "./Place";
import { Toast } from "./ui";
import { Vehicle } from "./Vehicle";

const route = () => location.hash.replace(/^#\/?/, "") || "home";

export const Settings: Component = () => {
  const [view, setView] = createSignal(route());
  const onHash = () => {
    setView(route());
    window.scrollTo({ top: 0 });
  };
  window.addEventListener("hashchange", onHash);
  onCleanup(() => window.removeEventListener("hashchange", onHash));

  return (
    <>
      <Switch fallback={<Home />}>
        <Match when={view() === "look"}><Look /></Match>
        <Match when={view() === "layout"}><Layout /></Match>
        <Match when={view() === "alerts"}><Alerts /></Match>
        <Match when={view() === "vehicle"}><Vehicle /></Match>
        <Match when={view() === "place"}><Place /></Match>
        <Match when={view() === "advanced"}><Advanced /></Match>
      </Switch>
      <Toast />
    </>
  );
};
