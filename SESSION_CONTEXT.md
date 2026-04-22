# Budget GUI — Session Context (2026-04-13, Session 4)

Hand this file to Claude at the start of the next session to resume immediately.

---

## Project Location
- **Main file:** `c:\Users\User\Desktop\Budget GUI\budget_gui.py` (4508 lines)
- **Data file:** `budget_data.json`
- **Memory files:** `C:\Users\User\.claude\projects\c--Users-User-Desktop-Budget-GUI\memory\`

---

## What This App Is

A personal finance desktop app (Python + Tkinter, stdlib only) that functions as a **distribution calculator + spending tracker**. Users import their bank statement PDF; the app reads their spending and tells them how to split each pay across bank accounts. They execute the transfers manually. The app tracks whether they stayed on plan and rewards consistency via gamification.

---

## Core Workflow (frequently misunderstood)
1. Pay arrives in main bank account
2. User logs pay in app → app shows: "Transfer $X to bills account, $Y to savings, $Z stays for spending"
3. User physically makes those transfers in their bank
4. At month end → import bank statement PDF on Transactions tab
5. App reads actual spending, scores accuracy, awards Gold + Gems

---

## Current State — STABLE & COMPLETE (Session 4)

Compiles cleanly: `python -m py_compile budget_gui.py` → no errors.

### What was added this session

**Phase A — Onboarding wizard**
- `AppState.onboarding_complete`, `AppState.income_baseline` fields
- `_run_onboarding()` — 3-step modal wizard (frequency/income → savings objectives → review/confirm)
- Creates initial Bills/Funds/Goals from user input; sets income_baseline
- Existing users auto-complete the flag without seeing the wizard

**Phase B — Integrity**
- `GameStats.last_pay_scored_date` — prevents same-day multi-scoring farming
- Daily cap: 2nd scored pay on same calendar day capped at 10 pts
- `_update_income_baseline()` — EMA 80/20, called on each pay
- Scoring is ratio-based throughout (% of pay reserved = score, not dollar amount)

**Phase C — Identity & Appeal**
- Rank names redesigned: The Recruit → The Builder → The Architect → The Sovereign (prestige: The Legend → The Immortal → The Ascended)
- **Streak hero**: left column of Score tab now shows 🔥 + big streak number + "PAY STREAK" as primary hero element
- `_share_score_card()` — text-based privacy-safe score card, copied to clipboard
- Help tab completely rewritten to explain the distribution calculator concept
- Dashboard allocation text rewritten as "TRANSFER THESE AMOUNTS" with bank instructions

---

## Architecture
```
budget_gui.py
├── Color constants + Progression constants (SEASON_TIERS, CHALLENGE_POOL, FORTUNE_CARDS, PERK_SHOP_ITEMS)
├── Card collection constants (CARD_POOL 35 cards, CARD_BY_ID, PACK_TYPES 3 types, RARITY_CONFIG)
├── Utility functions
├── 9 Dataclasses (all have to_dict/from_dict): IncomeEntry, Bill, Fund, Goal, GameStats, AdvancedMatchRule, TransactionRecord, MerchantMemoryEntry, AppState
├── Engine classes: BudgetEngine, BudgetGameEngine, PDFTransactionImporter, TransactionMatcher
└── BudgetApp (Tkinter UI, 12 tabs)
```

---

## Critical Variable Names (Score Tab)

**Live vars (DO NOT remove):**
- Stat cards: `level_var`, `streak_var`, `best_streak_var`, `last_gain_var`, `total_gold_var`, `prestige_var`
- Streak hero (Session 4): `streak_hero_var`, `best_streak_hero_var`
- Hero center: `rank_icon_var`, `rank_name_var`, `rank_desc_var`, `rank_progress_var`, `rank_next_var`
- Hero right: `prestige_stars_var`, `prestige_goal_var`, `gems_hero_var`
- Gems strip: `gems_strip_var`
- Topbar: `topbar_rank_var`, `topbar_gold_var`, `topbar_gem_var`

**DEAD — do NOT re-add:** `gems_var`, `multiplier_var`, `rank_header_var`, `rank_score_need_var`

---

## Rank System
- No prestige (L1-10): The Recruit, The Consistent, The Tracker, The Planner, The Builder, The Analyst, The Strategist, The Accumulator, The Architect, The Sovereign
- P1: The Legend · P2: The Immortal · P3+: The Ascended
- `rank_name_for_level(level, prestige)` — takes both args

---

## Possible Next Work (not started)
1. **Dark mode** — `colour_theme` field exists in AppState but no style wiring yet
2. **Card unlock animations tied to achievements** — auto-award specific cards on achievement
3. **Community/leaderboard** — requires server, out of scope for local app
4. **Export to PDF/CSV**
5. **Packs-opened counter** in Collection tab hero

---

## Notes for Claude
- All work in `budget_gui.py` — no new files
- Python stdlib only — no pip installs (pypdf optional)
- `apply=True` on `allocate_pay()` is what mutates state
- Windows: use `encoding='utf-8'` in Bash file operations
- Curly/smart quotes in string literals cause SyntaxError — always use straight quotes
- Memory files auto-load for Claude at session start
