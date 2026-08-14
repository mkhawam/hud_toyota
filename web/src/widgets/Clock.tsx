import { createSignal, onCleanup, type Component } from "solid-js";

export const Clock: Component = () => {
  const [now, setNow] = createSignal(new Date());
  const timer = setInterval(() => setNow(new Date()), 1000);
  onCleanup(() => clearInterval(timer));

  const time = () =>
    now().toLocaleTimeString([], { hour: "numeric", minute: "2-digit", hour12: true });

  return <div class="widget clock">{time()}</div>;
};
