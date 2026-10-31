import { createSignal, For, type Component } from "solid-js";
import { config } from "../core/config";
import { ACCENT_PRESETS, FONTS, THEME_PRESETS, type FontKey, type ThemeConfig } from "../core/theme";
import { autoSave, Group, Page, Row, Segmented, Slider, Switch } from "./ui";
import { LivePreview } from "./Home";

type Theme = Required<ThemeConfig>;

function currentTheme(): Theme {
  const t = config().theme ?? {};
  return {
    accent: t.accent ?? "#3ce0ff",
    glow: t.glow ?? 0.85,
    font: t.font ?? "chakra",
    night_mode: t.night_mode ?? "auto",
    night_brightness: t.night_brightness ?? 0.55,
    speed_size: t.speed_size ?? 36,
    rpm_width: t.rpm_width ?? 44,
  };
}

/** A miniature black HUD tile showing the preset's real font, color and glow. */
const PresetTile: Component<{ p: (typeof THEME_PRESETS)[number]; on: boolean; onPick: () => void }> = (props) => {
  const accent = () => props.p.theme.accent ?? "#3ce0ff";
  const glow = () => props.p.theme.glow ?? 0.85;
  return (
    <button type="button" class="preset" classList={{ on: props.on }} aria-pressed={props.on} onClick={props.onPick}>
      <span class="preset-screen" style={{ "--accent": accent() }}>
        <span
          class="preset-digits"
          style={{
            "font-family": FONTS[props.p.theme.font ?? "chakra"].display,
            "text-shadow": `0 0 ${6 * glow()}px ${accent()}aa`,
          }}
        >
          42
        </span>
        <span class="preset-unit">mph</span>
        <span class="preset-bar">
          <For each={[0, 1, 2, 3, 4, 5, 6, 7, 8, 9]}>{(i) => <i classList={{ lit: i < 6 }} />}</For>
        </span>
      </span>
      <span class="preset-name">{props.p.name}</span>
      <span class="preset-hint">{props.p.hint}</span>
    </button>
  );
};

export const Look: Component = () => {
  const [theme, setTheme] = createSignal<Theme>(currentTheme());
  const save = autoSave("theme");
  const patch = (p: Partial<Theme>, delay = 350) => {
    const next = { ...theme(), ...p };
    setTheme(next);
    save(next, delay);
  };
  const [mirror, setMirror] = createSignal(config().mirror !== false);
  const saveMirror = autoSave("mirror");

  const isPreset = (p: (typeof THEME_PRESETS)[number]) =>
    p.theme.accent === theme().accent && p.theme.font === theme().font;
  const pct = (v: number) => `${Math.round(v * 100)}%`;

  return (
    <Page title="Look" back>
      <LivePreview />

      <Group title="Theme">
        <div class="presets">
          <For each={THEME_PRESETS}>
            {(p) => <PresetTile p={p} on={isPreset(p)} onPick={() => patch(p.theme, 0)} />}
          </For>
        </div>
      </Group>

      <Group title="Customize">
        <Row label="Accent color" for="accent-custom" stacked>
          <div class="swatches">
            <For each={[...ACCENT_PRESETS]}>
              {(a) => (
                <button
                  type="button"
                  class="swatch"
                  classList={{ on: theme().accent.toLowerCase() === a.hex }}
                  style={{ background: a.hex }}
                  aria-label={`Accent ${a.name}`}
                  aria-pressed={theme().accent.toLowerCase() === a.hex}
                  onClick={() => patch({ accent: a.hex }, 0)}
                />
              )}
            </For>
            <input
              id="accent-custom"
              class="swatch custom"
              type="color"
              value={theme().accent}
              aria-label="Custom accent color"
              onInput={(e) => patch({ accent: e.currentTarget.value })}
            />
          </div>
        </Row>
        <Row label="Font" for="font">
          <Segmented
            id="font"
            label="Font"
            value={theme().font}
            options={Object.entries(FONTS).map(([value, f]) => ({ value, label: f.name, font: f.display }))}
            onChange={(v) => patch({ font: v as FontKey }, 0)}
          />
        </Row>
        <Slider id="glow" label="Glow" min={0} max={2} step={0.1} value={theme().glow} format={pct}
          onInput={(v) => patch({ glow: v })} />
        <Slider id="speed-size" label="Speed digits" min={24} max={48} step={1} value={theme().speed_size}
          format={(v) => (v === 36 ? "Standard" : v < 36 ? `Smaller (${v})` : `Larger (${v})`)}
          onInput={(v) => patch({ speed_size: v })} />
        <Slider id="gauge-width" label="Gauge width" min={28} max={60} step={1} value={theme().rpm_width}
          format={(v) => `${Math.round((v / 60) * 100)}% of strip`}
          onInput={(v) => patch({ rpm_width: v })} />
      </Group>

      <Group title="Night" note="Auto dims when the headlights come on, or after sunset when the car doesn't report lights.">
        <Row label="Night mode" for="night-mode">
          <Segmented
            id="night-mode"
            label="Night mode"
            value={theme().night_mode}
            options={[{ value: "auto", label: "Auto" }, { value: "on", label: "Always" }, { value: "off", label: "Never" }]}
            onChange={(v) => patch({ night_mode: v as Theme["night_mode"] }, 0)}
          />
        </Row>
        <Slider id="night-brightness" label="Night brightness" min={0.2} max={1} step={0.05}
          value={theme().night_brightness} format={pct}
          onInput={(v) => patch({ night_brightness: v })} />
      </Group>

      <Group title="Projection" note="Position and size of the image are set on the HUD itself: press OK, then Calibrate projection.">
        <Row label="Mirror for windshield" hint="Turn off only when viewing the screen directly" for="mirror">
          <Switch id="mirror" label="Mirror for windshield" checked={mirror()}
            onChange={(v) => { setMirror(v); saveMirror(v, 0); }} />
        </Row>
      </Group>
    </Page>
  );
};
