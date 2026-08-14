import { type Component } from "solid-js";
import { useTopic, type Topics } from "../core/topics";
import { tempUnit } from "../core/config";
import { ThermoIcon } from "./icons";

function tempStat(topic: keyof Topics & `vehicle.${string}`, label: string, warnAboveC: number): Component {
  return () => {
    const c = useTopic(topic);
    const v = () => c() as number | undefined;
    const display = () => {
      if (v() === undefined) return "--°";
      return tempUnit() === "f" ? `${Math.round(v()! * 1.8 + 32)}°` : `${Math.round(v()!)}°`;
    };
    return (
      <div class="widget stat" classList={{ warn: (v() ?? 0) >= warnAboveC }}>
        <ThermoIcon />
        <div class="stat-body">
          <div class="stat-value">{display()}</div>
          <div class="stat-label">{label}</div>
        </div>
      </div>
    );
  };
}

export const TransTemp = tempStat("vehicle.trans_temp_c", "TRANS", 110);
export const IntakeTemp = tempStat("vehicle.intake_temp_c", "INTAKE", 70);
