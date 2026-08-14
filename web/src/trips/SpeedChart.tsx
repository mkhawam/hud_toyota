import { createMemo, createSignal, For, Show, type Component } from "solid-js";
import { speedUnit } from "../core/config";
import type { Sample } from "./Trips";

// Palette validated with the dataviz six-checks validator on surface #0b0f12
// (dark band, CVD ΔE 18.4, contrast ≥3:1). Limit is additionally dashed so
// identity never rides on color alone.
const SPEED_COLOR = "#0090ad";
const LIMIT_COLOR = "#b57b00";

const W = 720;
const H = 260;
const PAD = { l: 44, r: 84, t: 12, b: 28 };

const KPH_TO_MPH = 0.621371;

export const SpeedChart: Component<{ samples: Sample[] }> = (props) => {
  const [hover, setHover] = createSignal<number | null>(null); // sample index

  const unit = () => (speedUnit() === "mph" ? "mph" : "km/h");
  const conv = (kph: number) => (speedUnit() === "mph" ? kph * KPH_TO_MPH : kph);

  const model = createMemo(() => {
    const s = props.samples;
    if (s.length < 2) return null;
    const t0 = s[0].ts;
    const dur = Math.max(1, s[s.length - 1].ts - t0);
    const maxSpeed = Math.max(
      10,
      ...s.map((p) => conv(p.speed_kph ?? 0)),
      ...s.map((p) => conv(p.limit_kph ?? 0)),
    );
    const x = (ts: number) => PAD.l + ((ts - t0) / dur) * (W - PAD.l - PAD.r);
    const y = (v: number) => H - PAD.b - (v / maxSpeed) * (H - PAD.t - PAD.b);
    const path = (get: (p: Sample) => number | null) => {
      let d = "";
      let pen = false;
      for (const p of s) {
        const v = get(p);
        if (v == null) {
          pen = false;
          continue;
        }
        d += `${pen ? "L" : "M"}${x(p.ts).toFixed(1)},${y(conv(v)).toFixed(1)}`;
        pen = true;
      }
      return d;
    };
    // round y ticks to a nice step
    const step = maxSpeed > 90 ? 30 : maxSpeed > 40 ? 20 : 10;
    const ticks: number[] = [];
    for (let v = step; v <= maxSpeed; v += step) ticks.push(v);
    return { t0, dur, maxSpeed, x, y, ticks, speedPath: path((p) => p.speed_kph), limitPath: path((p) => p.limit_kph) };
  });

  const onMove = (ev: MouseEvent) => {
    const m = model();
    if (!m) return;
    const svg = ev.currentTarget as SVGSVGElement;
    const rect = svg.getBoundingClientRect();
    const px = ((ev.clientX - rect.left) / rect.width) * W;
    const ts = m.t0 + ((px - PAD.l) / (W - PAD.l - PAD.r)) * m.dur;
    let best = 0;
    let bestDist = Infinity;
    props.samples.forEach((p, i) => {
      const d = Math.abs(p.ts - ts);
      if (d < bestDist) {
        bestDist = d;
        best = i;
      }
    });
    setHover(best);
  };

  const minutes = (ts: number) => {
    const m = model()!;
    return `${Math.round((ts - m.t0) / 60)}m`;
  };

  return (
    <Show when={model()} fallback={<p class="empty">Not enough samples to chart.</p>}>
      {(m) => (
        <div class="chart-wrap">
          <svg
            viewBox={`0 0 ${W} ${H}`}
            class="chart"
            role="img"
            aria-label={`Speed over time in ${unit()}`}
            onMouseMove={onMove}
            onMouseLeave={() => setHover(null)}
          >
            {/* recessive grid + y labels */}
            <For each={m().ticks}>
              {(v) => (
                <>
                  <line x1={PAD.l} x2={W - PAD.r} y1={m().y(v)} y2={m().y(v)} class="grid" />
                  <text x={PAD.l - 6} y={m().y(v) + 4} class="tick" text-anchor="end">
                    {v}
                  </text>
                </>
              )}
            </For>
            <line x1={PAD.l} x2={W - PAD.r} y1={H - PAD.b} y2={H - PAD.b} class="axis" />
            <text x={PAD.l} y={H - 8} class="tick">0m</text>
            <text x={W - PAD.r} y={H - 8} class="tick" text-anchor="end">
              {minutes(props.samples[props.samples.length - 1].ts)}
            </text>

            {/* series */}
            <Show when={m().limitPath}>
              <path d={m().limitPath} class="line limit" />
            </Show>
            <path d={m().speedPath} class="line speed" />

            {/* direct labels at line end (text tokens + colored chip) */}
            <g class="series-label" transform={`translate(${W - PAD.r + 8}, ${PAD.t + 10})`}>
              <rect width="10" height="10" rx="2" fill={SPEED_COLOR} />
              <text x="14" y="9">speed</text>
            </g>
            <Show when={m().limitPath}>
              <g class="series-label" transform={`translate(${W - PAD.r + 8}, ${PAD.t + 30})`}>
                <rect width="10" height="10" rx="2" fill={LIMIT_COLOR} />
                <text x="14" y="9">limit</text>
              </g>
            </Show>

            {/* crosshair + hovered point */}
            <Show when={hover() !== null}>
              {(_) => {
                const p = props.samples[hover()!];
                return (
                  <>
                    <line x1={m().x(p.ts)} x2={m().x(p.ts)} y1={PAD.t} y2={H - PAD.b} class="crosshair" />
                    <Show when={p.speed_kph != null}>
                      <circle cx={m().x(p.ts)} cy={m().y(conv(p.speed_kph!))} r="5" class="dot" />
                    </Show>
                  </>
                );
              }}
            </Show>
          </svg>

          <Show when={hover() !== null}>
            <div class="tooltip">
              <b>{minutes(props.samples[hover()!].ts)}</b>
              {" · "}
              {props.samples[hover()!].speed_kph != null
                ? `${Math.round(conv(props.samples[hover()!].speed_kph!))} ${unit()}`
                : "--"}
              {props.samples[hover()!].limit_kph != null &&
                ` · limit ${Math.round(conv(props.samples[hover()!].limit_kph!))}`}
              {props.samples[hover()!].rpm != null && ` · ${Math.round(props.samples[hover()!].rpm!)} rpm`}
            </div>
          </Show>
        </div>
      )}
    </Show>
  );
};
