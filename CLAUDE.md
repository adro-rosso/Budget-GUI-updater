# Budget GUI — Claude Reference

## Project Overview

A personal finance desktop app built with **Python + Tkinter** (single file). Combines budgeting tools with a deep gamification system to make saving feel rewarding.

**Single source file:** `budget_gui.py` (~31,000 lines) · tests in `tests/` (`python tests/run_all.py`)
**Data file:** `budget_data.json` (persists all state)
**Backup file:** `budget_data.bak` (auto-created on every save — atomic write pattern)

---

## Architecture

```
budget_gui.py
├── Progression constants   (after UI_HERO constant)  — SEASON_TIERS, CHALLENGE_POOL, FORTUNE_CARDS, PERK_SHOP_ITEMS, CARD_SETS
├── Utility functions
├── Data Models             — 9 dataclasses (all have to_dict / from_dict)
├── Business Logic Engines  — BudgetEngine, BudgetGameEngine, InsightEngine, PDFTransactionImporter, TransactionMatcher
└── UI Layer                — BudgetApp (Tkinter, 8 tabs)
```

### Data Models

| Class | Purpose |
|---|---|
| `IncomeEntry` | Pay record (amount, date, source) |
| `Bill` | Bill with due_date, frequency, priority, current_saved |
| `Fund` | Sinking fund. `contribution_mode`: `auto` (target by date), `fixed` (fixed_amount per pay, target optional), `ongoing` (fixed_amount forever, no target), `buffer` (keep current_saved topped up to target_amount; fixed_amount caps a pay's top-up). `target_amount <= 0` = open-ended. |
| `Goal` | Savings goal with mode (fixed $/% of surplus). `target_amount <= 0` = open-ended (never full; `goal_remaining` → inf). |
| `GameStats` | Full progression state — see below |
| `AdvancedMatchRule` | Transaction matching rule (exact/contains/amount_contains) |
| `TransactionRecord` | Bank transaction with matched_type, category, user_verified, `flagged` (user flagged for follow-up) |
| `MerchantMemoryEntry` | Cached classification per normalized description |
| *(split)* | `TransactionRecord.splits` = `[{category, amount}]` summing to `money_out` (one receipt, several categories); `category` stays the largest share. `tx_category_amounts(tx)` returns the per-line list (or one line) and is what `outgoing_category_totals`, the Transactions pie, the top-category summary and `_pact_spent_in_cap` aggregate over; `tx_category_label(tx)` renders 'Groceries ⁄ General' in the trees. UI: `_show_split_editor(txs, on_done)` overlay (blank last amount = remainder; wrong totals refused; one line un-splits; duplicate categories merge), reached from the sort card's **Split…** button (advances the queue) and the right-click menu on both transaction trees (`_bind_tx_tree_menus`, also Flag/Unflag). Splits are per receipt and never become merchant rules. |
| *(reimbursement)* | `TransactionRecord.reimburse` ('' / 'pending' / 'done' / 'dismissed') + `reimbursed_amount`; an incoming row that paid expenses back carries `reimburses` = `[{fingerprint, amount, description}]`, `matched_type='reimbursement'`, category 'Reimbursement' (so it is never a pay to confirm). `tx_net_out(tx)` = money_out − reimbursed; `tx_category_amounts` scales lines by net/gross (fully reimbursed → no lines), so Analysis, the pie, the report, pacts and `outgoing_total` all net automatically. `tx_desc_cell` prefixes ↩ / ↩✓ in the trees. UI: sort-card toggle '↩ Getting reimbursed' (`_set_reimburse`), tree right-click items (getting / in full / in part… / not getting / undo; incoming: 'This is a reimbursement for…' → `_show_reimburse_assign([tx])` with prefilled amounts capped by outstanding and by what came in, partial allowed), Today card `_render_reimbursements` (Received ✓ / Partial… / Dismiss) in `_reimb_host`, `_offer_reimbursement_match` toast 1.5 s after a commit with incoming rows while expenses are pending, and 'It's a reimbursement' on the pay-confirmation card. |
| `AppState` | Root aggregate — contains all the above + expense categories, target mix, transfer_accounts, `account_balances` + `starting_position_set` (starting-position wizard), etc. |

### GameStats Fields (expanded)
Core: `total_score`, `level`, `streak_pays`, `best_streak`, `total_pays_processed`, `last_score_gain`, `achievements`, `mini_game_high_score`, `mini_game_rounds_won`

Progression systems: `gems`, `prestige_level`, `score_multiplier`, `streak_shields`, `active_buffs`, `season_year_month`, `season_xp`, `season_claimed_tiers`, `daily_challenges`, `daily_challenges_date`, `perks_unlocked`, `lifetime_gems_earned`

---

## Engine Classes

### `BudgetEngine`
Core allocation logic.
- `allocate_pay(pay_amount, apply, ..., overrides=None)` — distributes pay across bills → funds → goals → investing. `overrides` ({"bill:<idx>"|"fund:<idx>"|"goal:<idx>"|"invest": amount}) replace the calculated line (still capped at what's left) — fed by the allocation editor
- `bill_recommended_allocation(bill)` — per-pay contribution needed
- `fund_recommended_allocation(fund)` — per-pay contribution by mode (see Fund). `has_end_target(item)` tells UI/scoring whether an item can ever be 'full'.
- `mark_bill_paid(bill)` — resets saved, bumps due_date for recurring (uses correct calendar month arithmetic)
- `next_due_date(due_date, frequency)` — handles monthly correctly (no 30-day drift)

### `BudgetGameEngine`
Full progression engine.
- `score_pay(pay_amount, allocation)` — Gold + streak + gems + buffs + multiplier + challenge triggers
- `score_month_end_mix(year, month)` — one-time monthly bonus
- `generate_daily_challenges()` — 3 daily challenges from pool (refreshes each calendar day)
- `complete_challenge(trigger)` — awards reward, called from UI actions
- `draw_fortune_card()` — weighted random reward card drawn after every pay
- `add_season_xp(amount)` — adds XP with Scholar perk bonus; returns claimable tier indices
- `claim_season_tier(tier_idx)` — claims a season pass reward
- `buy_perk(perk_id)` — gem purchase; returns (success, message)
- `prestige()` — resets score/level, increments prestige_level, raises score_multiplier
- `ensure_season()` — resets season if calendar month changed
- `_check_achievements(is_good_pay)` — awards all achievement chains

### `InsightEngine` (track first, plan later — `docs/TRACK_FIRST_PLAN.md`)
Stateless over `state.transactions/incomes/bills`; `today` injectable. `weeks_of_data` / `data_level` (none <2, early 2–5, forming 6–9, solid ≥10) / `learning_line`; `weekly_series(weeks=12, bills=False)` = per-week category totals over the last complete weeks (bill rows = `linked_bill/linked_fund` or category Bill/Fund; weeks with no spending are *no data*, not zero); `category_baseline(cat)` = median + IQR band, outlier weeks > Q3+1.5·IQR (and >1.25×median), trend last-4 vs prior-4, confidence; `typical_week()` (rows with ≥3 active weeks + overall median), `typical_cycle_spend()` (×1/×2/×4.345 by pay_frequency), `big_weeks()` (overall outliers with the driving category); `recurring_candidates()` (merchant groups not yet bills / not in `state.recurring_dismissed`, ≥2 charges, regular gap → weekly…yearly with every gap within 25%, steady amount or ≥3 charges; weekly/fortnightly need a steady amount and spending categories (groceries/fuel/food/general/dining) need monthly+; returns name/key/amount/frequency/next_due/count/confidence); `income_rhythm()`, `bills_per_cycle()`, `savings_picture()` → `could_save` = typical pay − bills − typical cycle spend; `money_flow(start, end)` → income / bills / categories / out / saved.

### `PDFTransactionImporter` (statement importer — PDF, CSV, OFX)
`extract_any(path)` dispatches by extension: `.pdf` → `extract_transactions` (pypdf → pdfminer row grouping), `.csv` → `extract_csv` (header detection by name incl. Time/Settled; explicit Debit/Credit columns beat a generic Amount column; no-header CommBank layout inferred by content; dates in 12 formats; `(x)`, `CR`/`DR` money), `.ofx`/`.qfx` → `extract_ofx` (`<STMTTRN>` blocks, NAME+MEMO, FITID dedup). All three produce the same fingerprint `date|direction|amount|normalized_description`, so cross-format dedup works.
- Requires `pypdf` (lazy import inside method)

### `TransactionMatcher`
Auto-classifies transactions.
- Priority: AdvancedMatchRules → MerchantMemory → Income detection → Bill/Fund linking → heuristic keywords
- `classify_category(desc, direction)` — checks merchant memory first, then expanded keyword lists

---

## Progression System Constants

### `SEASON_TIERS` (6 tiers per month)
`(xp_threshold, reward_type, reward_amount, tier_name)` — alternates Gold/Gems, resets monthly.

### `CHALLENGE_POOL` (8 challenges, 3 drawn daily)
Triggers: `pay`, `pay_40`, `submit_target`, `mini_game`, `pay_35`, `verify_3`, `streak`, `import`

### `FORTUNE_CARDS` (8 cards, weighted random after every pay)
Effects: `gold`, `gems`, `season_xp`, `buff_double_mix`, `buff_streak_shield`, `none`

### `PERK_SHOP_ITEMS` (5 perks, bought with Gems)
`score_boost` (×3 stacks, +10% multiplier each), `streak_shield`, `gem_magnet`, `season_boost`, `fortune_up`

### `CARD_SETS` (4 sets, each rewards an exclusive avatar item)
- **Foundations** (12 common) → Collector's Cloak (outfit)
- **Momentum** (10 rare) → Momentum Rings (aura)
- **Mastery** (8 epic) → Collector's Gaze (eyes)
- **Legends** (5 legendary) → Sovereign Crown (hair)
Auto-claimed on set completion via `check_card_set_completions()`. Items use `unlock_req: {"type": "card_set", ...}`.

---

## UI — BudgetApp (Tkinter, 8 tabs)

| Tab | Purpose |
|---|---|
| **Today** | Merged dashboard — hero cards (Safe to Spend w/ velocity, Daily Pace, Pending Reviews, Homestead mini-scene), quick actions, distribution metrics strip, allocation plan, upcoming payments, snapshot |
| **Income** | Add pay (with date field) → **allocation editor overlay** (`_show_allocation_editor`: every line editable, Safe to Spend live, Reset/Apply) → `_commit_pay`. Checkbox "Review & adjust the split" (ui_prefs `pay.review_allocation`, default on) skips the editor when off. `_log_pay_and_allocate` is the single entry point for all pay-logging paths. |
| **Transactions** | Import PDF → auto-match → **Sort Unrecognised** overlay (one card per merchant) → commit; committed history; expense pie. Advanced per-row classify toolbox stays collapsible. |
| **Score** | Full progression hub — hero panel, daily challenges, season pass, pie charts, mini-game, score breakdown, achievements |
| **Setup** | Bills, Sinking Funds, Goals, Investments, Rules, Accounts — all in one tabbed view |
| **Collection** | Card packs, collection grid, set progress tracker, recycling. "The Vault" branding. |
| **Avatar** | Cosmetic customization (100 items, 6 slots), idle-animated portrait with mood, profile card, set reward badges, equipment panel with rarity. "The Vault" branding. |
| **Analysis** | Monthly review — actual vs target spending |
| **Homestead** | Living scene derived from real state (`HomesteadEngine.snapshot` → `draw_homestead`). Tier 0–5 from five checks (house ≥ cottage, half the plots grown, fence complete, 6 imports, mailbox flag down); each tier auto-awards a companion item (`BudgetGameEngine.check_homestead_tiers`, `HOMESTEAD_COMPANIONS`) for the new `companion` avatar slot. Animates (windmill, clouds, stars) only while shown. Phase 1 of `docs/HOMESTEAD_PLAN.md`. |

### Score Tab Layout (row order)
- Row 0: Hero panel (rank, progress bar, prestige stars, gems, Perk Shop button, PRESTIGE! button)
- Row 1: 6 stats boxes (Level, Streak, Best Streak, Last Gain, Gems, Score Multiplier)
- Row 2: Daily Challenges (left) + Season Pass (right)
- Row 3: Pie charts (actual spending vs target mix)
- Row 4: Mini-game
- Row 5: Score Breakdown + Achievements

### UI Patterns
- **Collapsible sections ("calm by default")**: secondary panels on every tab sit behind `_collapsible_section(parent, title, key, *, default_open, summary_var, on_expand, bg)` — a chevron header that toggles content via grid/grid_remove and shows a one-line summary while collapsed. Open state persists per key in `AppState.ui_prefs` (e.g. `today.health`, `score.charts`, `tx.classify`). `ui_prefs` must stay the LAST AppState field (from_dict passes args positionally). Pass `on_expand` for canvas charts (unmapped canvases report 1px width). `_expand_section(key)` opens programmatically (e.g. Transactions classify toolbox auto-expands on preview-row select).
- **Sort Unrecognised review queue** (`open_review_queue`): scrim overlay opened automatically after a PDF import. Overview screen (recognised / suggested / unknown counts + merchant list) → one card per merchant group (`_review_queue_groups`, keyed by `merchant_group_key`) with category chips, new-category entry, bill/fund link, Transfer/Ignore → done screen with Commit. Choosing a chip calls `_assign_review_group`, which verifies every transaction in the group, writes merchant memory, and (if "Remember" is ticked) saves a `contains` rule keyed on the merchant key via `_ensure_merchant_rule`. `TransactionMatcher.match` tests contains-rules against both the raw description and `merchant_group_key` so number-stripped keywords still hit. Each card also has **"Make it a recurring bill"**: an inline form prefilled by `_infer_recurring_bill` (cadence from the median gap between this merchant's dates in the batch + committed history: weekly/fortnightly/monthly/quarterly/yearly, next due rolled forward past today, last amount); Create appends a `Bill`, links the group as `linked_bill`, and the saved rule auto-links future charges. Enter accepts a suggestion, Esc closes, ←/→ navigate. The card's content is an `_overlay_scroll_area` (`_review_queue_content`; each screen resets to the top), so the overview lists **every** merchant (rows click through to that card) and a card that grows the bill form still shows its fields on a laptop-height window — previously the list was capped at 8 and the form's entries were clipped below the card edge.
- **Money plan setup wizard** (`_show_setup_wizard`, 7 steps; `_show_starting_position` is an alias): rhythm (pay frequency + typical pay) → bills → set-asides (4 fund modes via chips) → goals (fixed / % of surplus, target optional) → account names → **your money now** (`_render_money_now`: a balance entry per account — all four, named from the accounts step, in a 2×2 grid (`wz['bal']`, total = their sum via `_total_now`); below it an amount per bill/fund/goal/invest saying what each dollar is for; 'Suggest a split' spreads the Bills balance across bills in due order, the Savings balance across buffers → dated funds → goals (leftover to the first open-ended one), Investment → invest; with no Bills/Savings balance it falls back to bills due before next pay and buffers to level from the pool; remainder = Safe to Spend in the Everyday account) → transfer plan (all four accounts always listed — an empty one is muted with the reason and has no Copy button; each row shows 'has $X today → add/take out $Y' and a MOVES TO MAKE list from `_moves(now, planned)` (greedy surplus→deficit, Copy per move) or 'nothing to move'; per-pay preview). Earlier the step asked for one total, so the only account names on screen were Everyday and Investing, which read as 'only two accounts can be filled'. `_starting_position_summary` likewise names every account. Bills/funds/goals are written to state as they're added so 'Finish later' keeps them. Finish writes `current_saved`, `account_balances` (derived from the split), `starting_position_set`, and seeds `last_*` totals when no pay is logged. First run: `_run_onboarding` just opens this wizard with `first_run=True` and sets `onboarding_complete` on finish (old 3-step onboarding removed).
- Setup → Funds form has a "How it works" mode combobox (`_FUND_MODE_LABELS`, `_sync_fund_form_mode`, `_fund_from_form`); fund right-click has "Record spending from fund…" (`_spend_from_fund`) so buffers refill.
- **Welcome checklist** (`_render_today_get_started`): steps are (title, desc, done, action-callable). Mandatory = starting position + first bill (logging a pay is optional). Re-rendered on every add/update of bills/funds/goals and whenever Today is shown (`_show_page`).
- **Flag for follow-up**: Sort Unrecognised card has a "🚩 Flag to investigate later" toggle → `_set_transactions_flag` sets `tx.flagged` on the merchant group and creates/dismisses a Gerald reminder (due +3 days, text from `_flag_reminder_text`). Today shows a "Flagged for follow-up" card (`_render_flagged_followups`) with Resolved / Make it a bill. Preview + committed trees prefix 🚩.
- Shared overlay helpers: `_overlay_card(caption, w, h)` (scrim + card + header + btn_row), `_overlay_scroll_area(parent, height)` (canvas list with wheel binding), `_parse_money_field`.
- **Avatar rendering (visual overhaul)**: `_exec_avatar_draw` supports shaded ops — `grad_band` (vertical gradient over a 0..1 rect), `grad_oval` / `grad_poly` (concentric shrink toward a light point, `from`/`to`/`steps`/`light`/`shrink`), `sparkle` (4-point star, twinkles when animated). It also sanitises `#rrggbbaa` colours and `smooth` on ovals (Tk rejects both). `draw_avatar(..., anim_frame, mood)` idles for everyone: breathing bob, blink every 46 frames (items with `no_blink` opt out), rim light, default vignette stage, mood-driven mouth/brows (`_avatar_mood`: worried if a bill is overdue, proud at streak ≥5, happy at streak ≥2). Items may define `draw_back` (drawn behind the head, after the outfit) for long hair/capes. Catalogue is 105 items across 7 slots (`companion` added — anchor on the right shoulder, drawn last with its own bob); the 30 newest cosmetics and the 5 companions live in `AVATAR_ITEMS.update({...})` blocks. Avatar grid cards render a mini `draw_avatar` thumbnail (current look + that item; locked items get a stipple veil) instead of an emoji.
- **Gerald** (`_draw_gerald(canvas, w, h, expression, blink)`): cel-shaded cartoon with ink outlines — tapered jaw (`_ellipse_pts` with taper), swept tousled hair with a side part and three tufts, big almond eyes with heavy lid lines and filled tapered brows, right-side smirk; teal waistcoat (lit/shadow panels), lapels, collar wings, brass buttons, lanyard badge + pocket square (skipped when scale < 0.5). Expressions normal/wink/happy/thinking/shocked/proud/sleepy. Check changes with `tests/raster.py gerald`. `_gerald_blink_tick` blinks the Today commentator and chat portraits every 3–6 s, restoring `_gerald_today_expr` / `_gerald_chat_expr`.
- Visual checks without a screen: `tests/raster.py` rasterises Tk canvas items through PIL (ImageGrab returns black when the session is locked).
- Incentive design for the next feature: `docs/HOMESTEAD_PLAN.md` (living scene driven by real finance state; 3 phases).
- **Visual polish (Oct 2026)**: `Primary.TButton` is a saturated indigo fill with white text (`UI_PRIMARY_BG/HOVER/PRESSED/FG`) — the one bright element on a page; Secondary/Ghost stay grey. Scrollbars are a flat arrowless thumb (`style.layout` override, `gripcount=0`, `lightcolor/darkcolor` = thumb colour). `_gradient_hero` retints any `bg=UI_HERO` descendant to the hero colour (`_retint_hero`, debounced on content `<Configure>`) so titles never sit in boxes. `_dark_titlebar(win)` asks DWM for the immersive dark title bar (main window + pack reveal Toplevel). Entries/combos use `UI_BORDER_LT` hairlines; locked avatar thumbnails use a `gray12` stipple veil. `tests/shoot.py <dir>` screenshots every page with sample data via PIL ImageGrab (celebrations/toasts stubbed) — use it before and after visual changes.
- **Active tab colours**: selected main-nav entry uses `UI_NAV_ACTIVE_BG` (indigo fill) + `UI_NAV_ACTIVE_BAR` (4px left bar) + white title; selected child tabs (Setup sub-nav, Score Progress/Arcade) use `UI_SUBTAB_ACTIVE` (gold) text + 3px underline. Hover checks compare the underline colour to `UI_SUBTAB_ACTIVE`.
- **Layout rules learned from the overflow audit** (`tests/audit_overflow.py <w> <h>` opens every page/overlay and reports clipped or overlapping widgets): give every `tk.Canvas` that is packed `fill="x"` an explicit `width=10` (the default request is ~470px and inflates its parents); never grid a second widget into a cell that already holds a label (use `column=1`); put action buttons on their own row under multi-field quick-add rows; set `wraplength` on any label that can exceed ~200px inside a card; hero cards use `uniform="hero"` columns. Target: zero findings at 1366×768 apart from Treeview column sums.
- Scrollable tabs via Canvas + Frame + mousewheel binding. `_on_global_wheel` (bound with `bind_all`) routes the wheel: Treeview/Text under the cursor → overlay canvases (`_overlay_wheel_canvases`) → **any nested `tk.Canvas` with a `yscrollcommand` whose scrollregion overflows** (grids, chat transcripts, palette results — no registration needed) → the innermost registered page canvas (`_scroll_canvases` + `_scroll_canvas_page[id]`, which must carry the right page key; the Avatar grid was wrongly keyed 'collection' and never scrolled). `tests/smoke_test14.py` checks the routing.
- TreeView rows color-coded via tags: `overdue`, `urgent`, `good`, `matched`, `review`
- Canvas-based interactive pie charts (draggable handles on target mix)
- Form auto-populates when a TreeView row is selected
- `messagebox` for errors/confirmations
- Atomic save: write `.tmp` → rotate to `.bak` → rename to `.json`
- Income history capped at 104 entries on save

---

## Gamification Loop

### Per Pay
1. `allocate_pay()` → Gold (score) with `score_multiplier` applied
2. Streak tracked; shields absorb breaks; gem bonuses at streak milestones (3, 5, 10, 15...)
3. Active buffs consumed (e.g. `double_mix` doubles mix bonus)
4. Daily challenges auto-complete based on what was done
5. Season XP added (+20 base, +10 bonus if good pay)
6. Fortune Card popup — weighted random reward

### Season Pass (monthly)
- XP fills from all scored actions
- 6 claimable tiers with Gold/Gem rewards
- Resets each calendar month; `season_boost` perk gives +25% XP

### Prestige (long-term)
- Unlocks at Level 10 (score ≥ 1,950 under the current curve)
- Resets score to 0 / level to 1
- Each prestige: +×0.1 score multiplier permanently, prestige star shown in hero

### Engagement hooks (Today, above Quick Actions)
- **Daily Pulse** (replaces the flat vault; `docs/ENGAGEMENT_PLAN.md` Phase A): three beats on Today's hook row — (1) *Yesterday*: 'No spend ✓' (`record_no_spend_day`, its own run `no_spend_streak`), or a category chip + amount that appends a `TransactionRecord` with `source_file="pulse"` dated yesterday, or 'nothing to add'; (2) *Sort one*: the first unverified imported row with category chips (`_pulse_sort_one` → `_assign_review_group`, saves a rule), auto-done when nothing is waiting; (3) *Vault*: `open_vault()` rolls a chest (`VAULT_CHESTS` bronze/silver/gold/mythic, odds from `vault_odds(day)`, every 7th day Gold+ guaranteed, Gold ×2 when `last_real_action_date` is today). Finishing extends the **daily run** (`pulse_streak`, `pulse_best`, `pulse_last_date`); `ensure_pulse()` (startup + every `vault_status()`) consumes **freezes** (`pulse_freezes`, +1 every 7 days, cap 2) for missed days or breaks the run and opens a 48 h **repair** window (`pulse_repairable/repair_pulse`, 2–6 Gems). `ui_prefs['pulse.skip_weekends']` ignores Sat/Sun gaps. Milestones (`PULSE_MILESTONES`) celebrate; Next Up shows the next one; `_pulse_risk` adds an evening banner; Do-this-now offers the Pulse. Beat state for today lives in `GameStats.pulse_progress`. `vault_last_opened/vault_visit_streak` are kept in sync for old code.
- **Challenges**: `CHALLENGE_POOL` is any-day only (pulse, no_spend, verify_1, verify_3, contribute, homestead, mini_game, import, submit_target); `generate_daily_challenges` swaps slot 1 for a `PAYDAY_CHALLENGES` entry when `is_pay_day_window()` (expected pay ±1 day). `WEEKLY_CHALLENGES` (ISO week, `ensure_weekly`, `_advance_weekly` from `complete_challenge`, `claim_weekly_reward` → free Gem Pack via `open_pack(..., free=True)`) render under the daily three on Score (`_render_weekly_challenges`). `_fire_trigger(trigger)` is the UI entry point (toasts, refresh, save); it is called on Homestead visit, every contribution path, and single-row sorts.
- **Level curve**: `level_threshold(level)` — 100/150/200 Gold for levels 2–4, 250 after (`LEVEL_STEPS`); Level 10 = 1,950 Gold. `level_from_score` is the only place levels are computed; `_startup_progression_migration` recomputes on launch.
- **Day one** (`day_one_head_start`): Founder card (`FOUNDER_CARD_ID`, in `EXCLUSIVE_CARD_IDS` so packs never draw it), a free Standard Pack, season XP ≥ 30, today's two beats pre-done and `vault_force_tier='gold'`. Fired by `_day_one_head_start_ui` when the first-run wizard finishes (tutorial waits via `_when_pack_closed`), and silently (no pack) for existing profiles on first launch. Welcome checklist has two pre-ticked rows above the old steps.
- **Reminders** (Settings → Reminders & Daily Pulse): `install_reminder_task` registers a Task Scheduler job (`REMINDER_TASK_NAME`, daily 08:00 repeating hourly for 14 h) that runs the app with `--remind --data <path>`; `run_reminder_check` loads the file read-only, honours quiet hours (`reminders.quiet_start/end`, default 22–8), builds `_reminder_messages` (Pulse not done after `reminders.pulse_hour`, pay tomorrow/today/overdue, bills due ≤2 days, month report on days 1–3), shows ≤2 native toasts via `_send_windows_toast` (PowerShell WinRT, PowerShell's AUMID) and logs sent keys in `budget_reminders.json` beside the data file. `--dry-run` prints instead. The frozen exe handles this mode before any Tk is created.
- **Next Up** (`_next_up_items`, `_render_next_up`): the five closest rewards with progress bars — next level (+ items it unlocks), next pay-streak milestone, next Pulse milestone, next season tier, nearest card set, next Homestead tier, harvest/plot timers, the weekly race, a waiting letter — sorted closest first; rows click through to their page. `_streak_risk` (pay) and `_pulse_risk` (evening, run ≥2) add red/gold banners.
- **Celebrations** (`_celebrate(title, subtitle, color)`): transparent-colour topmost Toplevel with confetti + fading headline (~1.7 s, click to dismiss). Fired on vault open, level up, streak milestones (3/5/10/15/20/25/30), Homestead tier up, card set completion.
- **Pack pity timer** (`GameStats.packs_since_epic`): the 5th pack without an Epic+ forces its first card to Epic (20% Legendary); readout under the pack cards (`_pack_pity_var`).

### Ease-of-use layer (Oct 2026)
- **Do this now** (`_render_do_now`, `_do_now_candidates`, `_run_cta`): one strip at the top of Today's quick-actions card with a single button. Candidates = unsorted statement rows (101) > overdue pay (98) > `_next_actions_snapshot()` actions > month report (80) > unopened vault (20). Today's Gerald / health / metrics sections default closed.
- **Setup → Plan** (`_build_plan_tab`, `refresh_plan_tab`, `_plan_row`, `_inline_edit`): default Setup sub-tab; bills and savings (funds + goals) as one list. Click the amount or due date to edit inline (Enter saves, Esc cancels, date chips appear). Row buttons: Paid ✓ / Spent / Add $ and a ⋯ menu with Edit… (jumps to the old form with the row selected) / Remove (Undo in the toast and the header). `+ Add bill` / `+ Add savings` open `_show_quick_add(kind)` — one overlay for bill / set-aside / goal with mode chips, date chips and the cost guide. The three old forms remain for full edits.
- **Parsing**: Setup forms, Income and Rules use `_parse_money_field` (accepts `$`, commas, `(x)`, CR/DR) and toast on error instead of `messagebox`. `_date_chips(parent, entry_or_var)` adds Today · 15th · End of month · +1 wk · +2 wks · Next month under date fields (Bills, Funds, Income, quick add, inline edit).
- **Responsive overlays**: `_overlay_card` caps the card to the window (−32px) and, when capped, makes `content` a scroll area; `_overlay_scroll_area` registers its canvas in `_overlay_wheel_canvases` so `_on_global_wheel` routes the wheel to it. Review-queue card caps the same way. Window default fits the screen; `minsize(1100, 640)` (was 1280×820, taller than a 768px laptop).
- **Naming**: nav shows Statements / Analysis / Log Pay (`nav_compact_labels`). Goal priority is entered/shown as essential / important / optional (`_priority_word`, `_goal_priority_from_word`; stored 1/5/8).
- **Focus mode** (`ui_prefs['focus_mode']`, `_toggle_focus_mode`, `_apply_focus_mode`): toggle at the bottom of the nav rail (+ palette). Hides Score / Cards / Avatar / Homestead nav entries, the vault + Next Up row and the Homestead hero card.
- **Import**: remembers the last folder (`ui_prefs['import.last_dir']`), Ctrl+I imports from anywhere, commit returns to Today, 'unsorted rows' is a toast with a Sort action. Drag-and-drop needs tkinterdnd2 and is not implemented.
- `mark_bill_paid` now always advances a recurring bill one cycle (paying early counts), then past today.

### Ease-of-use round 2
- **Auto-paid bills**: `commit_imported_transactions` → `_auto_pay_bills_from_batch`: a committed `linked_bill` transaction dated no more than half a cycle before (or one cycle after) the bill's due date marks it paid (`mark_bill_paid`). The commit toast lists them and carries **Undo**.
- **Undo last import** (`_undo_last_commit`, `self._last_commit`): removes the batch from history, restores pending pay confirmations and auto-paid bills, and puts the rows back in the preview. The commit confirmation dialog is gone. Also on Settings.
- **Pay confirmation**: the Today card's button is "Looks right — log it ✓" and the Do-this-now strip surfaces a pending pay (priority 97).
- **Same as last time** (`_render_quick_pay`): Income tab card that logs last pay's amount/source today in one click; amount + source fields prefilled.
- **Settings page** (`_build_settings_tab`, nav → Build): backup / restore (`_replace_state` re-points every engine at the new state; writes `budget_data.pre-restore.json` first) / **Move data file** (writes `budget_config.json` → `{"data_path"}`; `_load_data_location()` reads it at import to set `DATA_FILE`) / Open folder / CSV exports (`_settings_export`: transactions, plan) / Undo last import / Focus mode / shortcuts / Reset game progress (`GameStats()` only).
- **Window memory**: `on_close` → `_remember_window_prefs` (ui_prefs `window.geometry`, `last_page`); `_restore_window_prefs` on startup (validated against the screen; focus-hidden pages skipped).
- **Shortcut sheet** `_show_shortcuts` (Ctrl+/); Enter adds/updates in the Bills / Funds / Goals forms (update when a row is selected).
- **Duplicate guard** `_name_exists(kind, name, exclude_idx)` in the Setup forms, quick add and wizard.
- **Plan bulk actions**: `_plan_pay_due_this_week` (bills due within 7 days, one Undo) and `_show_bulk_contribute` (one entry per fund/goal, live total, Undo).

### Engagement Phase B (`docs/ENGAGEMENT_PLAN.md`)
- **Homestead accrual** (`BudgetGameEngine.mill_status/collect_mill/plant/plot_status/harvest/harvest_all`): the windmill mills Gold from `mill_last_collected` at `2 + 2×tier` Gold/h (×0.25 with an overdue bill), capped at 8 h; a contribution to a fund/goal `plant`s `kind:name` in `plot_timers` (ripe after 12 h) and each harvest adds a `pack_fragment` (5 → free Standard Pack via `open_pack(free=True)`). All timestamp-based; `now` is injectable. UI: hero-card line (`_today_harvest_var/_lbl` → `_collect_all_ui` when actionable), Homestead page HARVEST strip (`_render_homestead_harvest`), Next Up row, reminder key `harvest`; `snapshot()['mill_ready']` draws a grain sack by the windmill.
- **Records + money milestones** (`RECORD_DEFS`, `update_record` → 'first'/'new'/None, `record_text`; `check_money_milestones(award)` over `MONEY_DOLLAR_STEPS` / `MONEY_PCT_STEPS` / every $1k of `_reserved_total()`, keys in `GameStats.money_milestones`; `final_stretch_bonus(pre_pay_ratios())` +15 Gold per ≥80%-funded item that received money on a pay, cap 45). `_after_money_change([(kind, obj, amount)])` is the single hook (plants, records, milestones, challenge rewards, pact settlement, celebration) — called from every contribution path and 0.9 s after `_commit_pay`. Startup seeds milestones silently when the list is empty. Score tab: collapsible 'Personal records & money milestones' (`_build_records_section/_render_records`, key `score.records`).
- **Pacts with Gerald** (`PACT_KINDS` reserve/cap/fund/nospend, `make_pact` escrows 1–6 Gems, `pact_progress`, `pact_note_pay` (called in `_commit_pay`), `settle_pacts` → win = stake×2 + 50 Gold + 50 XP + an exclusive `p_oath_*` card; lose/cancel = stake gone). One active pact in `GameStats.active_pact`, history in `pact_history`. UI: Today card `_pact_host` (`_render_pact_card`, 'call it off'), overlay `_show_pact_maker` (chips wrap 2/4 per row — packed chips overflow the card), `_settle_pacts_ui` on every Today refresh; Gerald intent `pact` ('make a pact', 'bet you').
- **Savings challenges** (`SAVINGS_CHALLENGES`: 52week / nospend30 / roundup / fiver / payfirst; `start_challenge`, `challenge_active`, `challenge_filled`, `check_challenge_rewards` 25% +50 Gold / 50% +2 Gems / 100% +5 Gems + `CHAMPION_CARD_ID`, `sync_challenge_funds` sets the 52-week fund's `fixed_amount` to the week numbers due in the next cycle, `roundup_for_spend` from `_pulse_log_spend`). Fund-kind ones are real `Fund`s with `challenge`, `challenge_started`, `challenge_claimed`, `challenge_ticks` (new trailing fields); the no-spend month lives in `GameStats.nospend_challenge` and counts `no_spend_dates`. UI: Plan → 'Savings challenges…' overlay (`_show_savings_challenges`), grid strip under challenge funds in `_plan_row` (`_plan_challenge_strip`, `_draw_challenge_grid`).
- Exclusive cards (never drawn): `EXCLUSIVE_CARD_IDS` = Founder, Champion, four Oaths.

### History mode (first statement reaching back before setup)
- `_history_cutoff()` = max(`AppState.starting_position_date` (stamped by the wizard's Finish), last logged pay date); None when neither exists (then past pays are the legitimate way to build balances and are confirmed as usual). `first_launch_date` is informational only.
- In `commit_imported_transactions`: income rows before the cutoff → `_log_historical_pays` appends `IncomeEntry`s (deduped ±1 day, updates `income_baseline`) **without allocation**, streak or vault; only income rows on/after the cutoff become `pending_income_confirmations`. `_auto_pay_bills_from_batch` skips historical rows. `_last_commit['incomes_added']` lets Undo remove them.
- **Set up from your statement** (`_show_statement_setup`, offered 0.7 s after a commit that contained history unless `ui_prefs['statement_setup.done']`; re-openable from the Statements bank block): three cards — pay rhythm (`_detect_pay_rhythm`: median gap → weekly/fortnightly/monthly, typical = median amount; 'Use this rhythm' sets `pay_frequency` + `income_baseline`), charges that look like bills (`_detect_recurring_bills`: merchant groups with ≥2 steady amounts or `_BILL_WORDS`, prefilled via `_infer_recurring_bill`; ticked ones become `Bill`s + a `linked_bill` rule), spending mix (`_history_mix`: last completed month's category shares → seeds `expense_target_order/pct`, unlocked; plus 'View the <month> report').
- Analysis: the current month's header gets a second line 'partial: d of n days · ~$X projected' (`refresh_review_tab`).

### Bank links (one click to the statement page)
- `AppState.setup_mode` ('' / 'track' / 'plan') and `recurring_dismissed` (merchant keys that are not bills) sit just before `ui_prefs` (added after `first_launch_date`). `AppState.bank_links` ([{name, url, every_days, last_opened}]) and `last_import_date` (set by `_import_statement_path`, the path-based half of `import_pdf_transactions`) sit just before `ui_prefs`. `BANK_PRESETS` = (label, url, note) for the main Australian banks; only an address is stored.
- UI: Statements tab 'YOUR BANK' block under the import controls (`_bank_links_host` at controls row 8 — classify section moved to row 9; `_render_bank_buttons` on every `refresh_transactions_tab`), editor overlay `_show_bank_links_editor` (preset combobox prefills name/url/note; `_add_bank_link` validates + dedups), wizard accounts step 'Where do you download statements?', Setup → Accounts 'BANK LINKS' row with `_bank_links_summary_var`.
- `_open_bank_link(idx)` opens the browser, stamps `last_opened`, then `_watch_downloads()` polls the Downloads folder (`_downloads_dir()` via the known-folder registry key, fallback ~/Downloads) every 3 s for 15 min; a new .pdf/.csv/.ofx/.qfx → `_offer_downloaded_statement` toast with an **Import** action → `_import_statement_path`. The watch token (`_downloads_watch_token`) cancels an older watcher.
- 'Statement time': `_statement_due()` compares days since `last_import_date` with each link's `every_days` (never imported = due once the plan exists). Surfaces as a Do-this-now candidate (priority 60, below unsorted rows), the 'statement due' button style on Statements, and reminder key `statement` (from 9 am). Gerald intent `open_bank` ('open my bank', 'take me to netbank') opens the matching link or the editor.

### Engagement Phase C + economy tuning + Homestead phases 2–3 (Oct 2026)
- **Live events**: `MONTHLY_EVENTS` (theme per month, Today banner `_render_event_banner` in `_event_host`), `EVENT_CARD_SETS` (4 cards per Australian season appended to `CARD_POOL`; `SEASONAL_CARD_SEASON` keeps them out of packs off-season; `check_event_set` pays +8 Gems once, `event_sets_claimed`), `xp_window_active` doubles Season XP on the Sat/Sun of a pay week, `featured_perk/featured_cost` = one perk at 30% off per day (shown in the Perk Shop and the banner).
- **While you were away** (`_maybe_welcome_back` 2.8 s after startup when `ui_prefs['last_close']` is ≥6 h ago; `_welcome_back_lines` → overlay `_show_welcome_back`).
- **Gerald's letters** (`GERALD_LETTERS`, 40; `letters_available` = Pulse days, `read_next_letter`, two choice letters grant a cosmetic via `choose_letter_gift`). Homestead page 'Letters from Gerald' section (`_render_letters_card`, `_show_letter`), Next Up row, Pulse done-state bit.
- **Weekly race** (`RIVALS` = four fictional villagers, `rival_standings` scaled to the user's previous week × league multiplier with per-week seeded jitter; `ensure_rival_week` settles on the first launch of a new ISO week: 1st +4 Gems/promote, 2nd +2/promote, 3rd +40 Gold, 4th–5th relegate; `GameStats.rival_*`, `weekly_xp` tracked in `add_season_xp`). Score tab row 5 (`_build_rivals_section/_render_rivals`, refreshed with the season pass), Next Up row. The panel states the rivals are characters.
- **Share cards** (`share_card_data(year, month|None, app)`, overlay `_show_share_card` draws a poster on a canvas; `_save_canvas_png` via ImageGrab, `_share_card_html` standalone page). Buttons: month report 'Share card ↗', Settings → Export 'Your year card ↗'.
- **Economy**: `_log_engagement(action)` → `engagement.jsonl` beside the data file (launch/pulse/pay/import/commit/pact/letter/decor/share); `_engagement_stats` → Settings 'Your habit'. `_nearest_set_nudge` under the pack cards; `open_pack` rerolls a duplicate once toward a set that is ≥80% complete. Rank title in the nav rail (`_nav_rank_lbl`) and the Homestead badge.
- **Homestead phase 2**: `_homestead_burst` sparkle on spend/contribute (plot anchors `0.40 + c*0.085, 0.76 + r*0.1`), `_show_tier_up_card` (defers while another overlay/Toplevel is open), `_scene_quips` feed Gerald's Today commentary.
- **Homestead phase 3**: `HOMESTEAD_DECOR` (10 items, Gold/Gem sink, drawn by `_draw_homestead_decor` at fixed anchors; `GameStats.homestead_decor`), `HOMESTEAD_PALETTES` (sky/land per season; `season_for_month`; unlocked by claiming the top season tier in that season via `unlock_season_palette`; `homestead_palette/homestead_palettes`), 'Your Homestead' legendary background awarded with tier 5, `_share_homestead_png` (ImageGrab). Homestead page sections 'Decor & palettes' (row 4) and 'Letters from Gerald' (row 5).
- **Analysis periods**: Month / Quarter (calendar) / FY (Jul–Jun) / YTD / Custom… (`_resolve_review_period`, `_review_step`, `_show_review_custom_range`); `_review_month_offset` is the generic offset.
- **Settings**: Text size (`apply_text_scale` scales `FONT_*` + `TREE_ROWHEIGHT` before the UI is built; `_restart_app`), Sample data (`_build_sample_state`, backup to `budget_data.before-sample.json`, nav banner `_sample_banner`, welcome-overlay link), Your habit readout.
- **Bank presets** verified live on 11 Oct 2026 (all resolve); CommBank uses the new `netbank.web.commbank.com.au` address.
- **History cutoff** = max(starting_position_date, last logged pay); no position and no pays = no cutoff.

### Calm pass (Oct 2026) — show less at once, remove nothing
- **Progressive unlock** (`_feature_unlocked(key)`; keys weekly / pacts / race / decor / events with thresholds in `_UNLOCKS`): a gated panel renders `_locked_line` (one muted line + 'show everything now'). `ui_prefs['unlock_all']` (Settings → Display & game 'Show everything now' / `_settings_toggle_unlock_all`) bypasses all gates. Tests that drive gated UI set `unlock_all`.
- **Today**: once the Pulse is done the card collapses to one line (`_pulse_compact_line`; click → `_toggle_pulse_details`) and `_layout_hook_row(compact)` makes it a full-width strip with Next Up below. Pact card + event banner live in the collapsed 'Pacts & this month' section (`today.extras`, summary from `_update_today_extras_summary`); an active pact and the seasonal set also appear as Next Up rows. Quick actions are one row (Log Pay / Import statement / Setup) plus a **More ▾** menubutton (`_today_more_menu`: sort, commit, perk shop, pact, challenges, set up from statement, shortcuts).
- **Score / Homestead**: weekly race and letters sections default closed; letters auto-expand when one is waiting (`_expand_section('homestead.letters')`).
- **Toasts coalesce**: a plain toast within 1 s of the previous joins it (max 4 lines); actionable toasts never merge (`toast._msg_lbl/_shown_at/_has_action`). **Celebrations queue**: `_celebrate` polls every 300 ms until the current burst ends. `_show_tier_up_card` sizes to its items and waits while another overlay is open.

### Quiet pass (Oct 2026) — professional, not busy
- **One border everywhere**: the `glow = tk.Frame(parent, bg=<colour>, padx=1, pady=1)` wrapper pattern (hero cards, Analysis cards, pack cards, Today panels, alert cards) is always `UI_BORDER` now; meaning stays in the value/title colour. Don't reintroduce coloured card outlines — if something must stand out, colour its number or caption.
- **No decorative rules**: the 3px accent strips above section titles (`tk.Frame(x, bg=UI_ACCENT, height=3).grid(row=0…)`) are gone; the sub-tab underline (`underline`) and `_personality_stripe` remain.
- **Top bar**: flat `UI_HERO`, 13pt brand, borderless status pill, `Save` is a Ghost button, a 1px `UI_BORDER` hairline replaces the gradient glow line. **Hero band** (`UI_GRADIENT_TOP/BOT`) is flat page colour.
- **Nav rail**: title-only entries (subtitle labels exist in `page_button_meta` but are not gridded), tighter rows so all 11 pages fit at 768px; a 56px spacer at the bottom keeps the rank line clear of the floating Add button. Badges are neutral (`UI_SURFACE3`/`UI_TEXT`) except Statements (ruby = rows to sort). Focus toggle reads '◎ Focus mode'.
- **Tables**: `_apply_tree_tags` sets foreground colours only (no tinted row fills); `_priority_pill` / `_frequency_pill` return plain words (no emoji dots). Progress-bar styles set `bordercolor/lightcolor/darkcolor` to the trough so no bright outline.
- **Plan rows**: Edit… / Remove live in a `⋯` Menubutton per row (`self._plan_menus[(kind, idx)]`, reset in `refresh_plan_tab`); Paid ✓ / Spent / Add $ stay visible. Statements' Sort button is Secondary (only Import is Primary). Chat rows, confirm cards and owned collection cards use hairlines. Homestead tier badge is outlined text.
- Check with `tests/shoot.py <dir>` before/after any visual change; the audit baseline is still the 12 Treeview findings.
- **Fewer words (v1.0.21)**: explanatory subtitles under page titles are gone (Log Pay, Statements, Settings, Gerald, Collection, Season Pass, Homestead's long intro → one line), as are per-row 'click to edit' hints (the Plan subtitle says it once), the 'Bulk:' label, 'Tip:' lines, the Today workflow-summary line and 'closest rewards first'. Labels are nouns: Name / Amount / Date / Already saved / Target / Per pay / Frequency; form titles are Bill / Set-aside / Goal; tables are Bills / Set-asides / Goals; Statements buttons are Import statement / Sort Unrecognised / Commit / Clear and the preview is 'Preview' with the empty state 'No statement loaded'. The Pending Reviews subtitle is blank unless something needs sorting. Keep new copy to one short line and prefer no line at all.
- **Small frictions (v1.0.17)**: `_parse_smart_date` also takes `27/10` (next occurrence), `15 Nov`, `15 Nov 2026`, `15.11.2026`, `Nov 15 2026` and a bare `28` / `28th` (this month if ahead, else next); the Analysis custom range uses it too. Plan header shows `↶ Undo: X removed` for two minutes after a removal (`_plan_last_removed`, `_render_plan_undo`, `_plan_undo_last_remove`) alongside the toast. The Bills table has one `cycle` column ('fortnightly · essential') instead of Priority + Frequency.

### Cost guide + investing helper
- `COST_GUIDE` (module constant, ~26 entries, Queensland/Australian typical figures 2025–27 with `low`/`high`/`note`; `REGO_ESTIMATES_QLD` by cylinders; `monthly_equivalent(amount, freq)`; `_guide_lookup(text)` keyword match). Update the numbers here when they date — each note says where to verify.
- `_show_cost_guide(kind, on_pick)`: searchable overlay with Bills / Set-asides / Goals filter; selecting shows the note, a cylinder picker for rego, the computed emergency-fund target (`_emergency_fund_suggestion` = 3 × essential monthly bills, floor $2,000), and an editable amount. "Use this" fills the Setup form (`_apply_guide_to_setup_form`: name, amount, frequency, priority, sensible date/mode) or, from the wizard, calls `on_pick(entry, amount, extras)` to prefill the quick-add row. Buttons: "Not sure? Cost guide" on the Bills/Funds/Goals forms and in wizard steps 2–4.
- `_show_invest_helper()`: four questions (buffer size, high-interest debt, horizon, drawdown comfort) → `_invest_recommendation` → % of surplus (0/5/10/15/20) + minimum buffer (≈ a week of essentials) with reasoning; Apply sets mode=percent and saves. Button on Setup → Investments.
- Investing rules now persist (`AppState.investment_rules`, loaded into `rule_settings` at startup, saved in `apply_investment_rules`). Previously they reset every launch.
- Bills support `quarterly` (next_due_date adds 3 calendar months; frequency combos, pill icon, Gerald patterns).
- Gerald intents `cost_guide` ("how much is rego?") and `invest_help` ("how much should I invest?" → opens the helper).

### Track first, plan later (Oct 2026 restructure — `docs/TRACK_FIRST_PLAN.md`)
- **First run** = `_show_track_first_onboarding(on_done)` (two cards: pay frequency chips + optional typical pay → Import now / Open my bank's page / I'll log as I go; link 'Set up a full money plan instead' opens the old wizard with `first_run=True`, `setup_mode='plan'`). Finish sets `pay_frequency`, `income_baseline` (if typed and no pays), `setup_mode='track'`, stamps `starting_position_date` (so a first statement's older pays are history), then `_run_onboarding`'s `_after` (day-one head start, tutorial). `self._track_onboarding` exposes `step/render/finish/freq/pay` for tests; tests that build a fresh app must stub `_open_pack_animation` (the free pack opens a grabbing Toplevel 2.3 s after onboarding) or set `onboarding_complete` first.
- **Welcome checklist** (`_render_today_get_started`): hides as soon as there is *any* data (statement rows, a pay, a bill or a finished plan); steps = Bring in a statement → Sort what it found → Confirm your pay → Optional: a full money plan. The welcome card anchors to the top of the overlay.
- **Today → 'Where your money goes'** (`_flow_host`, packed above the hook row; `_render_money_flow`): last-30-day flow bar on a canvas (Bills · top 5 categories · Other · Saved, or a dashed 'over by' tail), legend chips (click → Analysis), 'Typical week: Groceries ~$152/wk · …', the latest big week (≤3 weeks old), the learning line, and 'about $X of each pay is free to save' with **Put $X aside** → `_put_aside(amount)` into the one open-ended `Savings` goal (`_savings_pot`, created on first use; moves account_balances spending→savings; Undo).
- **Today → 'Looks like regular bills'** (`_recurring_host`, `_render_recurring_suggestions`): up to 4 `recurring_candidates` rows with **Yes, it's a bill ✓** (`_confirm_recurring_bill`: `Bill(amount=median, due=next_due, freq, 'important', 'Bill', keywords=[key])`, `_ensure_merchant_rule(linked_bill)`, past rows relabelled `linked_bill`, toast with Undo that reverses all three, fires the `contribute` trigger) and **Not a bill** (`_dismiss_recurring` → `recurring_dismissed`). Do-this-now candidate 'Confirm N regular bills I spotted' (priority 70).
- **Safe to Spend fallback**: with no plan (`starting_position_set` False, `last_safe_to_spend` 0) and statement rows, the hero shows max(0, in − out) over the last 30 days and the subtitle 'in $X · out $Y over the last 30 days'.
- **Allocation editor**: a learned line under the totals ('Learned from N weeks…: a typical fortnight of spending is about $S. After this split and a normal fortnight, roughly $Z is free to save' / '…about $Z short').
- **Analysis → 'Typical week & big weeks'** (`review.typical`, row 5, `_render_typical_week`, `review_typical_summary_var`): per-category typical $/wk, usual band, trend, outlier weeks; 'Big weeks overall' line.
- **First-run sequencing (v1.0.22)**: `_screen_busy()` = any overlay scrim (place-managed `bg=UI_HERO` frame at the root), any Toplevel that is not a toast, the tour, `_followup_pending` (set by `commit_imported_transactions` for the 0.7 s until `_statement_setup_offer` runs), an open review queue or unsorted import rows. `_when_quiet(cb)` polls every 400 ms. `_run_onboarding._after` waits for quiet before `_day_one_head_start_ui`; the pack animation and `_run_tutorial` are quiet-gated too (`_run_tutorial` re-waits if busy), so nothing pops over the sort queue or the confirmation step. The tier-up card is a real overlay in that chain (tests stub it).
- **Performance (v1.0.23)**: resizes were ~2–5 s and `refresh_all_views` ~4 s. Causes and fixes: `_draw_sparkline` and the top-bar `_tb_content_resize` forced `update_idletasks()` on every resize (removed; sizes come from `winfo_width/reqwidth`); `_draw_gradient` returns early for a flat fill; **only the current page is grid-managed** (`_show_page` `grid_remove`s the others, so hidden pages take no part in layout — keep it that way); `refresh_all_views` runs the cheap refreshers and marks `character` / `collection` dirty (`_LAZY_PAGES`, `_dirty_pages`, `_refresh_if_dirty` in `_show_page`); Homestead refreshes only when opened; `_refresh_char_grid` rebuilds only when its signature (owned, equipped, filter, Gold/Gems) changes (`force=True` to override). Measure with a cProfile of `app.update()` after `app.geometry(...)`; Python time should be ~20 ms per resize. Tests that inspect the Avatar or Cards page after `refresh_all_views` must `_show_page` it first.
- **Dialog guard**: `import_pdf_transactions` counts `_dialog_open` around the native file dialog and `_import_statement_path` sets `_followup_pending` until `open_review_queue` runs (or the 'nothing new' toast), so `_screen_busy` covers the folder window and statement parsing — the welcome pack/celebration cannot open over them.
- **Confirm what I found** (`_show_statement_setup`, `_statement_setup_scrim`): opens after the first commit with history. Cards: IS THIS YOUR PAY? ('$2,400.00 fortnightly from Acme', count/gap/last/next; **Yes, that's my pay ✓** sets `pay_frequency` + `income_baseline`; **No** just marks `statement_setup.rhythm_done`), YOUR BALANCE (`_statement_closing_balance()` from the latest imported row with a `balance`; **Yes, use it ✓** sets `account_balances['spending']` + `last_safe_to_spend`; only while `starting_position_set` is False), CHARGES THAT LOOK LIKE BILLS, YOUR SPENDING MIX; Done ✓ is Primary. `_detect_pay_rhythm` returns `source`. The onboarding no longer asks for a pay figure.
- **Sort queue polish**: overview says 'N pays found — I'll ask you to confirm your pay after commit' (history) or splits history/to-confirm; card chips exclude Income/Transfer/Bill/Fund/Ignore (those have their own buttons); bill names from `_infer_recurring_bill` / `_detect_recurring_bills` go through `clean_merchant_label` (also drops Australian capitals/state codes, BPAY/DIRECT DEBIT); toast 'Accepted N suggestions.'. **Split editor**: `NEW_CATEGORY_CHOICE` ('+ New category…') is the last combobox value; choosing it calls `_ask_new_category()` (askstring → `register_expense_category`). Tour copy is track-first.
- **Phase 2**: `learned_split(pay)` (bills per cycle, spend×1.1 → everyday, rest → savings, `short`), `suggested_mix()`, `week_so_far()` (spent / expected / `over` / `ahead` / `hot` categories), `reserve_for_days(days_left)`. Today flow panel: 'This week so far…' line (`_week_so_far_text`) and 'Each $P pay, from what you actually do: hold $B for bills · keep $E for a normal fortnight · $S to savings' chips (click → `_copy_amount_to_clipboard`; `_learned_split_last`) with **Put $S aside**; falls back to the savings_picture line without 3 weeks of data. Hero: Safe to Spend subtitle appends '· ~$R for a normal Nd → $F truly free'; Daily Pace shows '~$X / day typical' when the plan gives 0. Wizard transfer step: 'FROM YOUR STATEMENTS' box. Analysis: 'Use my typical shares' (`_use_suggested_mix`, Undo). Reminders `learn:6` / `learn:10` on the Monday of that week. Gerald intents `typical_week` / `big_week` (`_handle_typical_week`, `_handle_big_week`); 'am I overspending' still goes to `pace`.
- **Follow-ups (v1.0.20)**: confirming a suggested bill fires no challenge trigger; suggestion names go through `clean_merchant_label` ('Netflix Com' → 'Netflix'); in track mode (`setup_mode == 'track'` and no starting position) the nav shows no Setup '!' badge and `_setup_completeness_steps` is tracking-shaped (pay frequency, first statement, sorted, first pay, a bill confirmed, three weeks of data; the health summary reads 'Tracking n/6'); `_commit_pay` schedules `_offer_learned_split(amount)` 1.8 s after the ritual — when no fund/goal absorbed the pay and `learned_split` has savings > 0, a 12 s toast offers **Put $Z aside** (`_put_aside`).
- Plan empty state says the app spots regular charges on statements. The wizard, Setup forms, funds, goals, cost guide, interview and the game loop are unchanged and optional.

### Today, rebuilt calm (v1.0.24)
- **Hero** = Safe to Spend (value + velocity subtitle + the pace line `today_daily_pace_var` underneath; no sparklines — `_safe_sparkline_canvas` / `_pace_sparkline_canvas` are None) · **This week** (`today_week_var` = spent since Monday, `today_week_sub_var` = on track / ahead of pace / past a typical week · hot category, from `InsightEngine.week_so_far`; falls back to a plain since-Monday sum) · **Accounts** (`_accounts_card_host`, `_render_accounts_card`: the four balances from `account_balances` with 'update →', or 'Enter what's in your accounts →') · Homestead (unchanged, hidden in focus mode). `today_pending_reviews_var` / `today_actions_summary_var` are still set but no longer have a card.
- **Quick card order**: Do-this-now strip → 'Where your money goes' (bar + legend only; `details ▸` toggle = `ui_prefs['today.flow_details']` reveals typical week, learning line, per-pay chips and Put aside — tests that read those set the pref) → the needs-you hosts (pay overdue, confirm pay, flagged, reimbursements, pending bills, recurring) → **'Daily Pulse & rewards'** collapsed section (`today.progress`, summary `_today_progress_summary` = 'Pulse done ✓ · n-day run'; the hook row with `_vault_host` + `_next_up_host` lives inside; focus mode hides `_today_progress_wrap`) → 'Pacts & this month' → quick action buttons. The 'This week so far' line left the flow panel (it is the hero card now).
- **Row 5** ('Your Pay Distribution Plan' + 'Due soon') is one closed section 'Plan & upcoming' (`today.plan`, summary `today_plan_summary_var` = 'n due soon').
- **Your accounts now** (`_show_accounts_now(on_done)`, `_accounts_now_scrim`, `self._accounts_now = {vars: {key: (name_var, bal_var)}, save}`): four name + balance rows (Everyday prefilled from `_statement_closing_balance()` when empty); Save writes `transfer_accounts` names, `account_balances`, `last_safe_to_spend` = Everyday, `last_reserved_total` = Bills, stamps `starting_position_date` if unset (never sets `starting_position_set`, so track mode stays). Entry points: hero Accounts card, the confirmation step's YOUR BALANCE card ('Enter my accounts ✓' replaced the one-click balance), Do-this-now 'Enter what's in your accounts' (priority 72 while `account_balances` is empty and there are transactions), Today More ▾ 'Update my accounts'.
- `Unknown` is a default expense category (merged into existing profiles by `AppState.from_dict`), for small amounts that fit nowhere.

### Fixes v1.0.25
- **'Verify N transactions' phantom**: incoming rows committed from a statement (history pays and the one pending confirmation) kept `needs_review=True`, so the Today action counted them forever and clicking it found nothing. `commit_imported_transactions` now marks every incoming row verified; `pending_review` (both `_next_actions_snapshot` sites) counts outgoing rows only; `_startup_progression_migration` verifies old incoming rows.
- **Coin Catcher**: the first ← / → (or A / D) press starts the round (`_cc_set_pressed` → `start_cc_round`); keys are also routed from the root (`bind_all` → `_cc_global_key`) while the Score page shows the coin game and no entry has focus, so the canvas no longer needs a click first. Status text says so.

### Bill interview (Gerald asks what you pay for)
- `BILL_INTERVIEW` (24 questions in groups Home / Getting around / Insurance / Subscriptions / Family & other; `interview_item_defaults(item)` merges a `guide` COST_GUIDE entry for frequency/priority/category/typical/note; `options` = multi-pick questions such as streaming/music/software/gaming/news, one bill per ticked option with its typical price; `keywords` = how the charge reads on a statement).
- `Bill` trailing fields: `amount_pending` ('' / `statement` / `revisit`), `amount_pending_since` (ISO), `keywords` (list). A pending bill has `amount = 0` and allocates nothing; `TransactionMatcher` links a charge to a bill by name **or** `_keyword_match` (whole-word/phrase), and the amount±$2 heuristic is skipped when `amount <= 0`.
- `_show_bill_interview(on_done)`: overlay (820×640), one question per card — Yes opens the detail panel (amount prefilled with the typical, every/next due/priority, date chips) with three outcomes: **Add with this amount** / **It'll be on my statement** (`amount_pending='statement'`) / **Not sure — remind me** (`revisit`); No / Enter = Yes / Esc closes / Skip the rest → done screen summarising known / from-statement / to-come-back-to. Already-present bills are shown as 'Already in your plan'. `self._bill_interview` exposes `idx/open/render/yes/no/commit_fn/mode_vars` for tests. Entry points: wizard bills step 'Ask me what I pay for' (re-renders the step on done), Setup → Plan 'Find my bills', Today More ▾, palette, Gerald intent `bill_interview` ('find my bills', 'ask me what I pay for').
- Follow-through: Today card `_render_pending_bills` (`_pending_bills_host`: Set amount… via `_ask_bill_amount` / Remove), Plan row shows `amount?` in gold with the reason (inline edit clears the flag), Setup → Bills tree shows `amount?`, Do-this-now 'Set the amount for X' (revisit ≥2 days, statement ≥7 days, priority 75), reminder key `bill_amount` (≥3 days). Sort card: `_pending_bill_for_group` → gold banner 'Looks like your Gym bill — its amount isn't set yet' with **Use $X and link** (`_set_bill_amount` + `_choose('linked_bill')`, saves the merchant rule). Commit: `_fill_pending_amounts_from_batch` sets a pending bill's amount from the latest linked charge (toast 'Amount set from the statement', `_last_commit['amounts_filled']` restored by Undo).

### End-of-month report
`_pending_report_month()` returns the previous calendar month if it had any income or transactions and `AppState.last_month_report_seen` ≠ that month. On startup (after onboarding) `_maybe_prompt_monthly_report` shows a toast with a View action; Today also shows a "Month closed" card (`_render_month_report_card`) with View / Skip. `_show_monthly_report(y, m)` is an overlay: Gerald quip (`_month_report_quip`), income/spent/net/savings-rate tiles, spend vs previous month, top-5 categories with bars and ±pts vs target mix, and a "what stood out" list (over/under target, anomalies, flagged merchants, overdue bills, level/streak/homestead). Done or "Open full analysis" (jumps the Analysis tab to that month via `_review_month_offset`) marks the month seen. Data comes from `_monthly_report_data` → `_current_month_review_data(for_date=...)`. `last_month_report_seen` sits just before `ui_prefs` in AppState.

### Daily Challenges
- 3 randomly drawn each day from pool of 8
- Trigger automatically during normal app use
- Reward Gold or Gems; completion also grants +15 Season XP

---

## Data File (`budget_data.json`) — Key Fields

- `pay_frequency`: `"weekly"` | `"fortnightly"` | `"monthly"`
- `incomes`, `bills`, `funds`, `goals`: lists of model dicts
- `game`: full GameStats dict (includes all progression fields)
- `transactions`: list of committed TransactionRecord dicts
- `advanced_match_rules`: list of rule dicts
- `merchant_memory`: `{normalized_desc: MerchantMemoryEntry}`
- `expense_target_order` / `expense_target_pct`: target spending mix
- `target_is_locked`: bool
- `last_safe_to_spend`, `last_reserved_total`, etc.: cached from last allocation

---

## Development Notes

- No external dependencies beyond Python stdlib + tkinter (`pypdf` optional for PDF import; `pdfminer.six` is the fallback for PDFs pypdf rejects, e.g. "Trailer cannot be read")
- **PDF fallback path uses coordinate row grouping** (`PDFTransactionImporter._pdfminer_rows`): pdfminer's plain `extract_text` dumps bank tables column-by-column, so text lines are grouped by y-position and sorted by x to rebuild `"dd Mon yyyy  DESC  -$amt  $balance"` rows that the existing parser expects. Within one statement, dedup is keyed on (fingerprint, balance) so identical same-day purchases survive.
- **Building the exe**: `python release.py --build-only` rebuilds `dist/BudgetPlanner.exe` without bumping/publishing. The build must pass `--collect-all charset_normalizer` plus `--hidden-import <hash>__mypyc` for the hashed mypyc helper .pyd files in site-packages (`mypyc_hidden_imports()` finds them). Without that, the frozen app's pdfminer import fails and the dialog says "Install the fallback parser". A running exe can be renamed aside (`BudgetPlanner.old.exe`) so a rebuild can proceed.
- All state lives in `AppState`; engines are stateless (take state as arg)
- `apply=True` param on `allocate_pay()` is what actually mutates state
- Deduplication: never import same transaction twice (fingerprint check)
- Monthly due dates use proper calendar arithmetic (no 30-day drift)
- Pay date field on Income tab defaults to today but is user-editable
- `classify_category()` checks merchant memory first before keyword matching
- Mini-game uses shuffle queue (no repeated questions until all 20 seen)
