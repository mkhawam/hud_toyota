"""Declarative alerts engine.

Rules live in config (``alerts.rules``): a topic plus a condition, a level,
and a message. Conditions are a static threshold (``above``/``below``) or a
reference topic (``above_topic``/``below_topic`` + optional ``tolerance``) —
e.g. speed above road.speed_limit_kph + 8. A missing/None reference
deactivates the rule (drive off the map → the overspeed alert retires).

On every change the engine publishes the FULL active set to
``alerts.active`` — last-value semantics mean a client connecting mid-drive
is primed with current alerts instead of replaying a raise/clear stream.

A clear margin (hysteresis band) stops alerts from flapping when a value
hovers at the threshold; dynamic (two-topic) thresholds get a 2-unit floor
so a near-zero reference can't produce a zero-width band.
"""

from __future__ import annotations

from typing import Any

from ..core.provider import DataProvider

CLEAR_MARGIN_FRAC = 0.03  # clear once the value is 3% back inside the threshold
DYNAMIC_MARGIN_MIN = 2.0  # floor for two-topic rules only


class AlertsEngine(DataProvider):
    name = "alerts"

    async def run(self) -> None:
        # Outer loop re-reads the rules whenever the settings page edits them
        # (config.updated on the bus) — no process restart needed.
        while True:
            rules: list[dict[str, Any]] = self.config.get("alerts.rules", []) or []
            for i, rule in enumerate(rules):
                rule["_id"] = f"rule{i}"

            by_topic: dict[str, list[dict[str, Any]]] = {}
            by_ref: dict[str, list[dict[str, Any]]] = {}
            for rule in rules:
                by_topic.setdefault(rule["topic"], []).append(rule)
                ref = rule.get("above_topic") or rule.get("below_topic")
                if ref:
                    by_ref.setdefault(ref, []).append(rule)

            active: dict[str, dict[str, str]] = {}
            self._publish_active(active)  # prime the topic even with no alerts

            watch = set(by_topic) | set(by_ref)
            sub = self.bus.subscribe(*watch, "config.updated")
            try:
                async for msg in sub:
                    if msg.topic == "config.updated":
                        if isinstance(msg.value, dict) and msg.value.get("section") == "alerts.rules":
                            break  # rebuild with the new rules
                        continue
                    changed = False
                    for rule in by_topic.get(msg.topic, []):
                        changed |= self._evaluate(rule, msg.value, active)
                    # a reference update (e.g. the limit changed) re-evaluates
                    # its rules against the cached primary value
                    for rule in by_ref.get(msg.topic, []):
                        primary = self._cached(rule["topic"])
                        if primary is not None:
                            changed |= self._evaluate(rule, primary, active)
                    if changed:
                        self._publish_active(active)
            finally:
                self.bus.unsubscribe(sub)

    def _cached(self, topic: str) -> float | None:
        msg = self.bus.snapshot(topic).get(topic)
        if msg is None or not isinstance(msg.value, (int, float)):
            return None
        return float(msg.value)

    def _threshold(self, rule: dict[str, Any]) -> tuple[float | None, bool, bool]:
        """(threshold, is_above, is_dynamic) — threshold None = rule inactive."""
        if "above" in rule:
            return float(rule["above"]), True, False
        if "below" in rule:
            return float(rule["below"]), False, False
        if "above_topic" in rule:
            ref = self._cached(rule["above_topic"])
            return (None if ref is None else ref + float(rule.get("tolerance", 0))), True, True
        if "below_topic" in rule:
            ref = self._cached(rule["below_topic"])
            return (None if ref is None else ref - float(rule.get("tolerance", 0))), False, True
        return None, True, False

    def _evaluate(self, rule: dict[str, Any], value: Any, active: dict) -> bool:
        if not isinstance(value, (int, float)):
            return False
        rid = rule["_id"]
        is_active = rid in active

        threshold, is_above, dynamic = self._threshold(rule)
        if threshold is None:
            # no reference value (off the map) → an active alert retires
            if is_active:
                del active[rid]
                return True
            return False

        margin = abs(threshold) * CLEAR_MARGIN_FRAC
        if dynamic:
            margin = max(DYNAMIC_MARGIN_MIN, margin)
        if is_above:
            triggered = value > threshold if not is_active else value > threshold - margin
        else:
            triggered = value < threshold if not is_active else value < threshold + margin

        if triggered and not is_active:
            active[rid] = {
                "id": rid,
                "level": rule.get("level", "warn"),
                "message": rule.get("message", rule["topic"]),
            }
            return True
        if not triggered and is_active:
            del active[rid]
            return True
        return False

    def _publish_active(self, active: dict) -> None:
        self.bus.publish("alerts.active", list(active.values()))
