# Track first, plan later — restructure design

**Problem.** The first run asked for a full money plan: bills, things to set aside for, goals,
four account names, a balance for each, then a transfer plan. That is forethought most people
don't have on day one, and it hid the thing the app is actually good at: showing where money goes.

**Principle.** The app should work from a single statement. Structure (bills, set-asides, goals)
is *discovered* from real transactions and confirmed with one click, not declared up front.
Saving is "what's left after what really goes out", not "save for X". Confidence grows with data,
and the app says how sure it is and what it still needs.

## What the user sees

| Moment | Before | Now |
|---|---|---|
| First run | 7-step wizard | Two cards: how you're paid (optional) → bring in a statement / open your bank / log as you go. A link to the full wizard stays for people who want it. |
| Today, no data | "Set your starting position" | Checklist with one real step: bring in a statement. Sorting and confirming a pay follow from that; the full plan is optional. |
| Today, with data | Safe to Spend from the plan | **Where your money goes** panel: a flow bar (income → bills · categories · saved), typical-week chips, a learning line, and "you could put $X aside". Safe to Spend falls back to in − out when there is no plan. |
| A regular charge shows up | Nothing until you add a bill | **Looks like regular bills** card: "Netflix · $20.99 monthly · seen 3×" → *Yes, it's a bill* (creates the bill, links the charges, saves the rule) / *Not a bill* (never asked again). |
| Pay day | Split across bills/funds/goals | Same editor, plus a learned line: "a typical fortnight of spending is about $S; roughly $Z of this pay could go to savings". |
| Analysis | Actual vs target mix, trend | **Typical week & big weeks**: per-category typical $/wk with a usual range and trend, and the weeks that were outliers with what drove them. |

Nothing was removed: the wizard, Setup forms, funds, goals, the cost guide, Gerald's interview and
the whole game loop are all still there. They are optional now.

## The learning engine — `InsightEngine(state)`

Stateless, derived from `state.transactions`, `state.incomes` and `state.bills` on every call;
`today` is injectable for tests.

- **Weeks of data** = complete ISO weeks since the first outgoing row. Levels: none (<2), early
  (2–5), forming (6–9), solid (≥10). `learning_line()` turns that into one sentence.
- **Weekly series** = per-week category totals over the last 12 complete weeks, bills excluded
  (`linked_bill`/`linked_fund` rows and the Bill/Fund categories). Weeks with no spending at all
  are treated as *no data*, not as zero — a statement that only covers some weeks must not drag
  the median down.
- **Category baseline** = median of the active weeks with the interquartile range as the "usual"
  band. Outlier weeks are above `Q3 + 1.5·IQR` (and at least 25% over the median). Trend is the
  last 4 weeks against the 4 before. Confidence rises with weeks (10 → full) and falls with spread.
- **Typical week** = baselines for every category with ≥3 active weeks, plus the overall weekly
  median; **typical cycle spend** scales it to the pay cycle (×1 / ×2 / ×4.345).
- **Big weeks** = outlier weeks on the overall total, with the category that drove each.
- **Recurring candidates** = merchant groups (not already a bill, not dismissed) with ≥2 charges,
  a regular gap (median gap → weekly / fortnightly / monthly / quarterly / yearly, every gap
  within 25%) and either a steady amount or ≥3 occurrences. Carries the median amount, the next
  due date rolled past today and a confidence score.
- **Savings picture** = typical pay (median of logged pays) − bills per cycle (from the confirmed
  bills) − typical cycle spend → `could_save`.
- **Money flow** over a window = income (logged pays, else income rows), bills, spending by
  category, and saved = income − out.

## Data

`AppState.setup_mode` ("" / "track" / "plan") records which first run the user took, and
`AppState.recurring_dismissed` holds merchant keys the user said are not bills. Both sit before
`ui_prefs`. The new onboarding stamps `starting_position_date` so a first statement's older pays
are recorded as history (not allocated) — the existing history-mode rules apply unchanged.

## Phase 1 (built)

InsightEngine; the two-card first run (`_show_track_first_onboarding`, with the full wizard one
link away); the rewritten welcome checklist (hides as soon as there is any data); Today's
"Where your money goes" panel (`_render_money_flow`) and "Looks like regular bills" card
(`_render_recurring_suggestions`, `_confirm_recurring_bill`, `_dismiss_recurring`); Safe to Spend
fallback to in − out; the learned line in the allocation editor; Analysis "Typical week & big
weeks" (`_render_typical_week`); a Do-this-now candidate for unconfirmed regular bills; Plan
empty-state copy; tests (`smoke_test29`).

## Phase 2 (next)

- Transfer plan from learned data: Bills account = confirmed bills per cycle, Everyday = typical
  cycle spend + a small buffer, Savings = the rest — shown on the wizard's last step and as a
  one-click "move $X" list after each pay.
- Suggested target mix from the baselines (Analysis → "use my typical shares"), replacing the
  hand-set percentages for people who never set them.
- "This week vs typical" strip on Today (`InsightEngine.week_so_far`) with the category that is
  running hot.
- Learning milestones as reminders ("6 weeks in — your typical week is ready") and Gerald
  intents ("what's my typical week", "is this a big week").
- Groceries & co. as soft envelopes: a learned weekly amount per category that Safe to Spend
  reserves for the rest of the cycle, so the number means "free *after* a normal week".
