import { createResource, createSignal, Show, type Component } from "solid-js";
import { config } from "../core/config";
import { autoSave, Group, Icon, NumberField, Page, Row, showToast } from "./ui";

interface Ap { active: boolean; ssid?: string | null; password?: string | null; url: string }

export const Place: Component = () => {
  const loc = (config() as { location?: { lat?: number; lon?: number } }).location ?? {};
  const [lat, setLat] = createSignal(loc.lat ?? 40.4862);
  const [lon, setLon] = createSignal(loc.lon ?? -74.4518);
  const save = autoSave("location");
  const commit = () => save({ lat: lat(), lon: lon() }, 0);

  const [ap] = createResource<Ap | null>(async () => {
    const s = await (await fetch("/api/snapshot?pattern=net.ap")).json();
    return s["net.ap"] ?? null;
  });

  const useGps = async () => {
    const s = await (await fetch("/api/snapshot?pattern=gps.position")).json();
    const fix = s["gps.position"];
    if (!fix) {
      showToast("No GPS fix yet. Connect the GPS receiver and give it a minute outdoors.", true);
      return;
    }
    setLat(Math.round(fix.lat * 1e4) / 1e4);
    setLon(Math.round(fix.lon * 1e4) / 1e4);
    commit();
  };

  return (
    <Page title="Location & Wi-Fi" back>
      <Group title="Home location" note="Used for weather, and for speed limits until the GPS has a fix.">
        <Row label="Latitude" for="lat">
          <NumberField id="lat" wide step={0.0001} min={-90} max={90} value={lat()}
            onChange={(v) => { setLat(v); commit(); }} />
        </Row>
        <Row label="Longitude" for="lon">
          <NumberField id="lon" wide step={0.0001} min={-180} max={180} value={lon()}
            onChange={(v) => { setLon(v); commit(); }} />
        </Row>
        <button type="button" class="row action" onClick={() => void useGps()}>
          <Icon name="pin" /><span>Use the car's current position</span>
        </button>
      </Group>

      <Group
        title="Settings in the car"
        note="When no known Wi-Fi is in range at startup, the HUD makes its own network so your phone can reach this page."
      >
        <Show
          when={ap()?.ssid}
          fallback={
            <p class="empty">
              The HUD's own network isn't set up on this device. Run the installer on the Pi to create it.
            </p>
          }
        >
          <Row label="Join Wi-Fi">
            <span class="mono">{ap()!.ssid}</span>
          </Row>
          <Row label="Password">
            <span class="mono">{ap()!.password}</span>
          </Row>
          <Row label="Then open">
            <span class="mono">10.42.0.1:8000/settings</span>
          </Row>
          <Row label="Right now">
            <span class="row-value">{ap()!.active ? "Using its own network" : "On your Wi-Fi"}</span>
          </Row>
        </Show>
      </Group>
    </Page>
  );
};
