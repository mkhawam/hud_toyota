/**
 * Human-facing names for everything the settings page edits. Internal keys
 * (widget ids, slot ids, bus topics) never appear in the UI; this catalog
 * maps them to the words a driver would use.
 */

export interface WidgetInfo {
  label: string;
  hint: string;
}

export const WIDGETS: Record<string, WidgetInfo> = {
  speed: { label: "Speed", hint: "Big speed readout with the limit chip" },
  rpm: { label: "Tachometer", hint: "Engine RPM gauge with the gear" },
  power: { label: "Hybrid power", hint: "Charge and power meter" },
  clock: { label: "Clock", hint: "Time of day" },
  coolant: { label: "Coolant temp", hint: "Engine coolant temperature" },
  fuel: { label: "Fuel level", hint: "Fuel remaining in percent" },
  alerts: { label: "Alerts", hint: "Warnings from your alert rules" },
  source: { label: "Car link", hint: "Shows whether data comes from CAN, OBD, or nothing" },
  weather: { label: "Weather", hint: "Temperature and conditions" },
  traffic: { label: "Traffic", hint: "Slowdowns on your road" },
  dtc: { label: "Check engine", hint: "Trouble codes when the car reports them" },
  trip: { label: "Trip computer", hint: "Economy, distance and drive time" },
  zerosixty: { label: "0–60 timer", hint: "Your last and best launch" },
  speedlimit: { label: "Limit sign", hint: "Posted speed limit (needs GPS)" },
  lanes: { label: "Lane lines", hint: "From the lane-keeping camera" },
  cruise: { label: "Cruise speed", hint: "Set speed while cruise is on" },
  transtemp: { label: "Trans temp", hint: "Transmission oil temperature" },
  intaketemp: { label: "Intake temp", hint: "Intake air temperature" },
};

export const WIDGET_NAMES = Object.keys(WIDGETS);

/** Grid positions on the windshield strip, in reading order. */
export const SLOTS = [
  "top-left", "top-center", "top-right",
  "center-left", "center", "center-right",
  "bottom-left", "bottom-center", "bottom-right",
] as const;

export const SLOT_LABELS: Record<string, string> = {
  "top-left": "Top left", "top-center": "Top middle", "top-right": "Top right",
  "center-left": "Left", center: "Center", "center-right": "Right",
  "bottom-left": "Bottom left", "bottom-center": "Bottom middle", "bottom-right": "Bottom right",
};

/** What an alert rule can watch, and how its numbers are shown. */
export type MetricKind = "temp" | "speed" | "rpm" | "percent" | "volts";

export interface MetricInfo {
  label: string;
  kind: MetricKind;
}

export const METRICS: Record<string, MetricInfo> = {
  "vehicle.speed_kph": { label: "Speed", kind: "speed" },
  "vehicle.rpm": { label: "Engine RPM", kind: "rpm" },
  "vehicle.coolant_c": { label: "Coolant temp", kind: "temp" },
  "vehicle.trans_temp_c": { label: "Trans temp", kind: "temp" },
  "vehicle.intake_temp_c": { label: "Intake temp", kind: "temp" },
  "vehicle.fuel_pct": { label: "Fuel level", kind: "percent" },
  "vehicle.battery_v": { label: "Battery voltage", kind: "volts" },
  "system.cpu_temp_c": { label: "Pi temperature", kind: "temp" },
};
