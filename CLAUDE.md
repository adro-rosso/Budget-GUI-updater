# Budget GUI — Claude Reference

## Project Overview

A personal finance desktop app built with **Python + Tkinter** (single file). Combines budgeting tools with a deep gamification system to make saving feel rewarding.

**Single source file:** `budget_gui.py` (~10,000 lines)
**Data file:** `budget_data.json` (persists all state)
**Backup file:** `budget_data.bak` (auto-created on every save — atomic write pattern)

---

## Architecture

```
budget_gui.py
├── Progression constants   (after UI_HERO constant)  — SEASON_TIERS, CHALLENGE_POOL, FORTUNE_CARDS, PERK_SHOP_ITEMS, CARD_SETS
├── Utility functions
├── Data Models             — 9 dataclasses (all have to_dict / from_dict)
├── Business Logic Engines  — BudgetEngine, BudgetGameEngine, PDFTransactionImporter, TransactionMatcher
└── UI Layer                — BudgetApp (Tkinter, 8 tabs)
```

### Data Models

| Class | Purpose |
|---|---|
| `IncomeEntry` | Pay record (amount, date, source) |
| `Bill` | Bill with due_date, frequency, priority, current_saved |
| `Fund` | Sinking fund with target_amount, target_date, contribution_mode |
| `Goal` | Savings goal with mode (fixed $/% of surplus) |
| `GameStats` | Full progression state — see below |
| `AdvancedMatchRule` | Transaction matching rule (exact/contains/amount_contains) |
| `TransactionRecord` | Bank transaction with matched_type, category, user_verified |
| `MerchantMemoryEntry` | Cached classification per normalized description |
| `AppState` | Root aggregate — contains all the above + expense categories, target mix, transfer_accounts, etc. |

### GameStats Fields (expanded)
Core: `total_score`, `level`, `streak_pays`, `best_streak`, `total_pays_processed`, `last_score_gain`, `achievements`, `mini_game_high_score`, `mini_game_rounds_won`

Progression systems: `gems`, `prestige_level`, `score_multiplier`, `streak_shields`, `active_buffs`, `season_year_month`, `season_xp`, `season_claimed_tiers`, `daily_challenges`, `daily_challenges_date`, `perks_unlocked`, `lifetime_gems_earned`

---

## Engine Classes

### `BudgetEngine`
Core allocation logic.
- `allocate_pay(pay_amount, apply, ...)` — distributes pay across bills → funds → goals → investing
- `bill_recommended_allocation(bill)` — per-pay contribution needed
- `fund_recommended_allocation(fund)` — auto or fixed contribution
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

### `PDFTransactionImporter`
Parses bank PDF statements into `TransactionRecord` list.
- Requires `pypdf` (lazy import inside method)
- Fingerprint deduplication: `date|direction|amount|normalized_description`

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
| **Today** | Merged dashboard — hero cards (Safe to Spend w/ velocity, Daily Pace, Pending Reviews), quick actions, distribution metrics strip, allocation plan, upcoming payments, snapshot |
| **Income** | Add pay (with date field) + allocate; income history |
| **Transactions** | Import PDF, match/verify, commit; committed history; expense pie |
| **Score** | Full progression hub — hero panel, daily challenges, season pass, pie charts, mini-game, score breakdown, achievements |
| **Setup** | Bills, Sinking Funds, Goals, Investments, Rules, Accounts — all in one tabbed view |
| **Collection** | Card packs, collection grid, set progress tracker, recycling. "The Vault" branding. |
| **Avatar** | Cosmetic customization, profile card, set reward badges, equipment panel with rarity. "The Vault" branding. |
| **Analysis** | Monthly review — actual vs target spending |

### Score Tab Layout (row order)
- Row 0: Hero panel (rank, progress bar, prestige stars, gems, Perk Shop button, PRESTIGE! button)
- Row 1: 6 stats boxes (Level, Streak, Best Streak, Last Gain, Gems, Score Multiplier)
- Row 2: Daily Challenges (left) + Season Pass (right)
- Row 3: Pie charts (actual spending vs target mix)
- Row 4: Mini-game
- Row 5: Score Breakdown + Achievements

### UI Patterns
- Scrollable tabs via Canvas + Frame + mousewheel binding
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
- Unlocks at Level 10 (score ≥ 2250)
- Resets score to 0 / level to 1
- Each prestige: +×0.1 score multiplier permanently, prestige star shown in hero

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

- No external dependencies beyond Python stdlib + tkinter (`pypdf` optional for PDF import)
- All state lives in `AppState`; engines are stateless (take state as arg)
- `apply=True` param on `allocate_pay()` is what actually mutates state
- Deduplication: never import same transaction twice (fingerprint check)
- Monthly due dates use proper calendar arithmetic (no 30-day drift)
- Pay date field on Income tab defaults to today but is user-editable
- `classify_category()` checks merchant memory first before keyword matching
- Mini-game uses shuffle queue (no repeated questions until all 20 seen)
