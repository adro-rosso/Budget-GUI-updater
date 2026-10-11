# The Homestead — incentive design plan

A living scene that grows out of real financial behaviour. Not a login streak, not a points
multiplier: a place that visibly thrives when the money is handled and quietly overgrows when
it isn't. The pull to come back is the same one that makes people water a plant.

## Why this, and not another challenge list

The app already rewards *actions* (Gold, Gems, challenges, season pass, cards, avatar items).
What it lacks is a **persistent, glanceable state that you feel responsible for**. Every existing
reward is a number or an unlock; none of them *change* when you stop. The Homestead adds:

- **Loss aversion without punishment.** Nothing is ever destroyed. Neglect shows as weeds, dim
  lanterns, a raised mailbox flag. One good pay day clears it. The cost of ignoring the app is
  visible but always recoverable, which is the honest message about money too.
- **Progress you can show someone.** A scene is a screenshot; a score is not.
- **A Gold sink.** Gold currently buys avatar items and packs and then piles up. Homestead decor
  (fences, ponds, lanterns, a greenhouse) gives Gold somewhere to go for the long tail of players.
- **Ties to the real plan.** Every plot on the land *is* a fund or goal. Watching the orchard fill
  in is watching the sinking funds fill in.

## The scene

One canvas (same draw-op system as the avatar, so it animates and scales). Lives on its own page
"Homestead" in the nav, with a small live thumbnail on Today's hero row that opens it.

| Layer | Driven by | Visual |
|---|---|---|
| Sky | Real clock + streak health | Day/evening/night palette by local time. Clear skies at streak ≥ 3, light cloud at 1–2, overcast at 0, rain after a broken streak (clears on the next good pay). |
| Land | Prestige level | Land size grows a notch per prestige (more plots, a second field). |
| House | Level (score) | 5 house stages: tent → cabin → cottage → farmhouse → manor. Lit windows at night only when no bill is overdue. |
| Garden plots | One per fund | Plant grows through 4 stages by % funded. Open-ended funds (ongoing/buffer) grow by balance milestones ($100 / $500 / $1k / $2.5k) and show a "harvest" animation when you record spending from them. |
| Orchard trees | One per goal | Sapling → tree → fruiting by % to target; open-ended goals fruit on every $1k milestone. |
| Fence line | Bills paid on time | Each bill marked paid before its due date adds a fence segment; an overdue bill leaves a gap with a leaning post. |
| Path to the gate | Statement imports | Flagstones laid per committed import (max 12 visible). Overgrown by weeds after 45 days with no import. |
| Mailbox | Flagged follow-ups | Flag raised while any 🚩 merchant is unresolved. |
| Windmill | Daily pace | Blades turn when spending is under the daily pace; stop when over. |
| Well | Emergency fund (largest goal named "emergency") | Water level = % funded. |
| Weeds | Pays not logged | After 1.5 pay cycles without a pay logged, weeds appear in two plots; after 3 cycles, across the path too. Clear instantly on the next logged pay. |
| Weather events | Season pass | Monthly palette shift (season themes) so the scene never looks the same two months running. |

Everything derives from existing state. No new tracking for the first version.

## Tiers and rewards

Homestead Tier (0–5) is computed, not purchased:

```
tier = number of these that are true:
  house stage ≥ 3 (Level 10+)
  ≥ 4 plots at stage 3+
  fence complete for the last 3 pay cycles (no overdue bills)
  path ≥ 6 stones (6 imports committed)
  mailbox flag down (no unresolved follow-ups) for 30 days
```

Each tier unlocks one exclusive avatar item in a new slot **"companion"** (a creature that sits
on the shoulder or by the feet — hen, cat, fox, owl, dragonet) and a Gerald line. Tier 5 unlocks
a Legendary background "Your Homestead" that renders the actual scene behind the avatar.

Gold/Gem decor shop (cosmetic only, so no pay-to-win on the finances): fence styles, pond,
lanterns, flower beds, a greenhouse, a hammock for the avatar. 8–10 items at launch.

## Decay rules (the honest part)

- Decay is **visual only**. No Gold, Gems, items or streaks are ever removed by the Homestead.
- Decay is **fast to reverse**. Any single positive action clears the related decay the same day.
- Decay is **never triggered by not opening the app**. Only by not doing the real thing (no pay
  logged when a pay cycle has passed, bills overdue, follow-ups ignored). If the user has no
  pay due yet, nothing decays.

## Data model

```python
# GameStats (new fields, defaults keep old saves loading)
homestead_tier: int = 0
homestead_decor: List[str] = []          # purchased decor ids
homestead_last_tended: Optional[str]     # ISO date of last positive action (for Gerald quips)
homestead_claimed_tiers: List[int] = []  # companion items awarded
```

Scene state is computed on demand by `HomesteadEngine.snapshot(state) -> dict` (pure function,
stateless like the other engines), then drawn by `draw_homestead(canvas, snapshot, w, h, frame)`.

## Implementation phases

| Phase | Scope | Effort |
|---|---|---|
| 1. Static scene — **DONE 2026-10-07** (plus windmill/cloud/star animation, weeds, day/night pulled forward from phase 2) | `HomesteadEngine.snapshot`, `draw_homestead` with sky/land/house/plots/orchard/fence/path/mailbox, Homestead page + Today thumbnail. Tier computation and the 5 companion items. | 1 session |
| 2. Life | Windmill, weeds, weather, day/night, harvest animation on spend-from-fund, Gerald quips reacting to the scene ("your orchard's looking thin"), tier-up celebration overlay (reuse the Pay Day Ritual card). | 1 session |
| 3. Ownership | Decor shop (Gold/Gem sink), seasonal palettes tied to the season pass, "Your Homestead" legendary background, share-to-PNG button using the rasteriser from this session. | 1 session |

## Risks and how they are handled

- **Scene feels like nagging.** Decay is subtle (weeds, dim lights) and the fix is one action.
  Gerald never scolds; he notices and suggests.
- **Too many bills/funds to draw.** Cap visible plots at 8 and trees at 6, chosen by priority;
  the rest are summarised as a "distant field" silhouette.
- **Performance.** Same canvas approach as the avatar (100–300 items, 90 ms tick) — already
  proven on the Avatar tab.

## Ideas considered and parked

- *Weekly expeditions / quests*: overlaps with daily challenges; adds grind, not attachment.
- *Evolving pet only*: cute, but a single creature can't represent bills vs funds vs goals.
- *Net-worth museum*: good for milestones, no reason to return between them.
