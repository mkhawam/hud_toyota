import { createSignal, For, Show, type Component } from "solid-js";
import { config, type LayoutItem } from "../core/config";
import { SLOT_LABELS, SLOTS, WIDGET_NAMES, WIDGETS } from "../core/names";
import { autoSave, Group, Icon, Page, Sheet } from "./ui";

const label = (w: string) => WIDGETS[w]?.label ?? w;

/** 3×3 position picker shaped like the strip. */
const SlotPicker: Component<{ value?: string; onPick: (slot: string) => void }> = (props) => (
  <div class="slot-picker" role="radiogroup" aria-label="Position on the windshield">
    <For each={[...SLOTS]}>
      {(s) => (
        <button
          type="button"
          role="radio"
          aria-checked={props.value === s}
          aria-label={SLOT_LABELS[s]}
          classList={{ on: props.value === s }}
          onClick={() => props.onPick(s)}
        >
          <span>{SLOT_LABELS[s]}</span>
        </button>
      )}
    </For>
  </div>
);

export const Layout: Component = () => {
  const [items, setItems] = createSignal<LayoutItem[]>([...(config().layout ?? [])]);
  const [editing, setEditing] = createSignal<number | null>(null);
  const [adding, setAdding] = createSignal<string | null | false>(false); // false=closed, null=choose widget
  const save = autoSave("layout");
  const commit = (next: LayoutItem[]) => {
    setItems(next);
    save(next, 0);
  };

  const inSlot = (slot: string) =>
    items().map((it, i) => ({ ...it, i })).filter((it) => it.slot === slot);
  const unused = () => WIDGET_NAMES.filter((w) => !items().some((it) => it.widget === w));

  const move = (i: number, slot: string) =>
    commit(items().map((it, j) => (j === i ? { ...it, slot } : it)));
  const remove = (i: number) => {
    commit(items().filter((_, j) => j !== i));
    setEditing(null);
  };
  /** Swap with the previous/next widget in the same spot (stacking order). */
  const shift = (i: number, dir: -1 | 1) => {
    const list = items();
    const peers = list.map((it, j) => ({ it, j })).filter((p) => p.it.slot === list[i].slot);
    const pos = peers.findIndex((p) => p.j === i);
    const other = peers[pos + dir];
    if (!other) return;
    const next = [...list];
    [next[i], next[other.j]] = [next[other.j], next[i]];
    commit(next);
    setEditing(other.j);
  };

  const editItem = () => (editing() !== null ? items()[editing()!] : undefined);
  const peerInfo = () => {
    const it = editItem();
    if (!it) return { pos: 0, count: 0 };
    const peers = inSlot(it.slot);
    return { pos: peers.findIndex((p) => p.i === editing()), count: peers.length };
  };

  return (
    <Page title="Layout" back>
      <p class="lede">Where each readout sits on the windshield. Tap a widget to move or remove it.</p>

      <div class="strip" aria-label="Windshield layout">
        <For each={[...SLOTS]}>
          {(slot) => (
            <div class="cell" classList={{ center: slot === "center" }}>
              <For each={inSlot(slot)}>
                {(it) => (
                  <button type="button" class="wchip" onClick={() => setEditing(it.i)}
                    aria-label={`${label(it.widget)}, ${SLOT_LABELS[slot]}`}>
                    {label(it.widget)}
                  </button>
                )}
              </For>
            </div>
          )}
        </For>
      </div>
      <p class="strip-caption">Center column is wider, as on the HUD. Widgets in the same spot stack top to bottom.</p>

      <Group>
        <button type="button" class="row action" onClick={() => setAdding(null)} disabled={unused().length === 0}>
          <Icon name="plus" />
          <span>{unused().length ? "Add widget" : "All widgets are on the HUD"}</span>
        </button>
      </Group>

      <Show when={editItem()}>
        <Sheet title={label(editItem()!.widget)} onClose={() => setEditing(null)}>
          <p class="sheet-lede">{WIDGETS[editItem()!.widget]?.hint}</p>
          <h3 class="sheet-label">Position</h3>
          <SlotPicker value={editItem()!.slot} onPick={(s) => move(editing()!, s)} />
          <Show when={peerInfo().count > 1}>
            <h3 class="sheet-label">Order in this spot</h3>
            <div class="btn-pair">
              <button type="button" class="btn" disabled={peerInfo().pos === 0} onClick={() => shift(editing()!, -1)}>
                Move up
              </button>
              <button type="button" class="btn" disabled={peerInfo().pos === peerInfo().count - 1}
                onClick={() => shift(editing()!, 1)}>
                Move down
              </button>
            </div>
          </Show>
          <button type="button" class="btn danger wide" onClick={() => remove(editing()!)}>
            <Icon name="trash" /> Remove from HUD
          </button>
        </Sheet>
      </Show>

      <Show when={adding() !== false}>
        <Sheet title={adding() ? `Place ${label(adding() as string)}` : "Add widget"} onClose={() => setAdding(false)}>
          <Show
            when={adding()}
            fallback={
              <div class="pick-list">
                <For each={unused()}>
                  {(w) => (
                    <button type="button" class="pick" onClick={() => setAdding(w)}>
                      <span class="pick-name">{label(w)}</span>
                      <span class="pick-hint">{WIDGETS[w].hint}</span>
                    </button>
                  )}
                </For>
              </div>
            }
          >
            <p class="sheet-lede">Choose where it goes.</p>
            <SlotPicker onPick={(s) => { commit([...items(), { widget: adding() as string, slot: s }]); setAdding(false); }} />
          </Show>
        </Sheet>
      </Show>
    </Page>
  );
};
