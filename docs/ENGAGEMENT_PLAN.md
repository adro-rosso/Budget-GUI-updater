# Engagement Plan — making the app something you *want* to open

Written 8 Oct 2026. Companion to `HOMESTEAD_PLAN.md`.

**Status (9 Oct 2026): Phase A built** — items 1, 2, 3, 5, 6 and 13 (Daily Pulse, freezes/repair, Windows reminders, any-day + weekly challenges, day-one head start, variable vault, level curve). **Phase B built (9 Oct)** — items 4, 7, 8 and 9 (Homestead idle accrual, money milestones + records + final-stretch bonus, Pacts with Gerald, savings challenges). Phase C is open.

## 1. Diagnosis — why the current loop can't be habit-forming

The app already has a lot of game: Gold, Gems, levels, a pay streak, season pass, daily challenges, fortune cards, a vault, cards and packs, 105 avatar items, Homestead tiers, celebrations, a pity timer. What it lacks is a **daily unit of real behaviour** and **triggers from outside the app**. Specifically:

| Problem | Evidence in the code | Why it matters |
|---|---|---|
| The only scored real action is a **pay**, which is fortnightly | `score_pay` is the only Gold source tied to money; fortune card, season XP and streak all hang off it | 13 of every 14 days there is nothing financially real to do. Habits form on a daily cadence (Duolingo: 7 consecutive days → 2.4× retention). |
| **Half the daily challenges are impossible on most days** | `CHALLENGE_POOL`: `pay`, `pay_40`, `pay_35`, `streak` need a pay; 3 are drawn from 8 | A "daily" list with items you cannot do today teaches people to ignore it. |
| The **daily vault is fixed and unforgiving** | `VAULT_REWARDS` is a flat 7-step ladder; `vault_visit_streak` resets to 0 on one missed day; no freeze | Fixed rewards stop being interesting after a week; a harsh reset is the exact pattern Duolingo found *reduces* retention (two freezes → +0.38% DAU). |
| **Pay-streak milestones are months away** | 3 / 7 / 14 / 30 pays at fortnightly pay = 6 / 14 / 28 / 60 weeks | Goal-gradient effect needs a visible next step within days, not quarters. |
| **No external trigger** | Desktop Tkinter app; alerts only fire inside `_gerald_startup_alert` | Duolingo's single biggest retention win was the streak-saver notification. A closed app can't pull anyone back. |
| **No appointment mechanics** | Nothing accrues or ripens while the app is closed | Finch (54% D1 / 37% D7, better than Royal Match) runs on 6-hour pet adventures you come back to collect. |
| **Nothing time-limited** | Season pass is the same 6 tiers every month; Perk Shop stock never changes | Novelty + urgency is what live-ops games lean on between content drops. |
| **Celebrations are for game events, not money** | `_celebrate` fires on vault, level, streak, homestead, card set | The thing we actually want them obsessed with — the balance going up — is the quietest moment in the app. |
| **Flat level curve** | 250 Gold per level, level 1 → 10 | First levels should come fast (endowed progress), later ones slow. |
| **First session ends empty-handed** | `_run_onboarding` → wizard → Today. No pack, no card, no first streak day | The real data file shows a user who finished setup and never logged a pay. Day-1 is where this is lost. |
| No **social or comparative** layer | Single profile, no leaderboards | Leagues were Duolingo's second-biggest win. We can't do real multiplayer, but we can do rivals. |

### Design rules (these make hooks *stronger*, not just safer)

1. **Every reward hangs off a real financial action** (a verified transaction, a logged spend, a contribution, a confirmed no-spend day, a pay). Pure clicking earns pocket change at most. The scoring integrity caps already in `score_pay` stay.
2. **Slack beats strictness.** Earned freezes, a repair window, and "weekend doesn't count against you" options. Research (Duolingo, Penn/UCLA) says flexible streaks retain better; Octalysis warns loss-aversion in finance churns people through anxiety.
3. **Bounded sessions.** One Pulse per day, one harvest per cycle. Wordle's lesson: scarcity makes the session matter.
4. **Never punish the money.** Game penalties only touch Gold/Gems/streaks; nothing ever moves a dollar or nags about spending in a shaming tone (Gerald roasts, he doesn't scold).
5. **No real-money purchases, ever.** Everything is earned.

---

## 2. The plan, ranked by expected impact

Effort: **S** = under a day, **M** = 1–3 days, **L** = a week. "Hooks into" names the existing code to extend.

### Tier 1 — build the daily loop (do these first, together)

**1. Daily Pulse — a 60-second real check-in that *is* the daily streak** (M)
Replaces "open the vault" with a three-beat ritual on Today:
1. **Yesterday** — "Any cash or card spending not on a statement?" One-tap chips: *No spend ✓* / *Groceries* / *Eating out* / *Fuel* / *Other* + amount. A *No spend* day feeds a separate **no-spend run** (its own streak with its own milestones). Logged spends become `TransactionRecord`s (source `pulse`) so they count in Analysis and the month report.
2. **One card to sort** — if any imported row is unverified, show one (the same card UI as Sort Unrecognised, single item). None pending → "All sorted" with a tiny bonus.
3. **Open the vault** — now a *variable* chest (see item 13) that only opens after beats 1–2.
Finishing the Pulse marks the day for the **daily streak** (`GameStats.daily_streak`, `daily_streak_best`, `pulse_dates`). The pay streak stays as the long chain. Gerald comments on the run (3, 7, 14, 30, 60, 100 days; new celebration tiers).
Hooks into: `_render_daily_vault`, `vault_status/open_vault`, `mark_real_action`, `_celebrate`, `TransactionRecord`.

**2. Freezes, repair and amnesty for the daily streak** (S)
- Earn 1 **freeze** per 7-day run (bank max 2). A missed day auto-consumes one (Duolingo's +0.38% DAU change).
- **Repair** a broken run within 48 h for Gems (price scales with run length; cap at 6 Gems).
- Setting: *Weekends don't count* (default off).
- The streak-risk banner (`_streak_risk`) gains a daily variant: "Pulse not done yet today — 4 h left".
Hooks into: `GameStats`, `_streak_risk`, Settings page.

**3. Outside-the-app triggers** (M)
A tiny `reminder.pyw` (read-only on `budget_data.json`) registered in Windows Task Scheduler from Settings (*Remind me* toggle, writes/removes the task via `schtasks`). It fires native toasts through PowerShell (no extra dependency; `winotify` optional) with a *Open Budget* action:
- 7 pm: "Daily Pulse not done — your 12-day run ends at midnight."
- Pay day −1: "Pay lands tomorrow. 2 min to log it = +Gold, streak 6 → 7."
- Bill due −2 and overdue.
- Harvest ready (item 4).
- Month closed → report ready.
Rate-limited to one toast per trigger per day, quiet hours configurable. This is the single highest-leverage item on the list.
Hooks into: Settings tab, `_pending_report_month`, `_streak_risk`, data file (read-only).

**4. Homestead idle accrual — the appointment mechanic** (M)
While the app is closed, the Homestead works:
- **Windmill** mills Gold at a rate set by Homestead tier × (bills on track ? 1 : 0.25). Caps at 8 h of production → a *Collect* button in the Today hero card and on the Homestead page. (Clash Royale chest / Finch adventure pattern.)
- **Plots ripen**: a contribution to a fund starts a 12 h timer; harvesting yields a *pack fragment* (5 fragments = a Standard Pack). Harvest also plays the plot animation.
- **Mailbox**: once a day a letter arrives (see item 9).
Stored as timestamps in `GameStats` (`mill_last_collected`, `plot_timers`), computed on open, so no background process is needed. Show "ready in 3 h 12 m" in Next Up.
Hooks into: `HomesteadEngine.snapshot`, `draw_homestead`, `_next_up_items`, `_render_daily_vault` row.

**5. Fix the daily challenges** (S)
Split `CHALLENGE_POOL` into an *any-day* set (pulse, no-spend day, sort 1 / 3 rows, add $ to a fund, open the Homestead, play one arcade round, beat a PB, read Gerald's letter) and a *pay-day* set. Draw 3 from any-day; on a pay day swap one for a pay-day challenge. Add a **weekly** trio (import a statement, 5 Pulses, reserve ≥25% on a pay) worth a Gem Pack. Daily missions are the most reliable ritual-builder in puzzle games; weekly ones feed the season pass.
Hooks into: `generate_daily_challenges`, `complete_challenge`, Score tab row 2.

**6. Endowed progress on day one** (S)
- Finishing the wizard hatches the avatar (a 3-second "hatch" animation using the existing idle rig) and awards a free Standard Pack + a *Founder* card (collection reads 1 / 12 immediately).
- Season tier 1 pre-credited (progress bar starts at 50 / 150, not 0).
- The first Pulse is pre-done ("Day 1 ✓ — come back tomorrow for Day 2").
- Welcome checklist shows 2 of 7 already ticked.
- Level curve: 100 / 150 / 200 / 250 … so Level 2 lands in the first session.
Hooks into: `_run_onboarding`, `_show_setup_wizard` finish, `level`/`rank` thresholds, `_render_today_get_started`.

### Tier 2 — stakes and variable reward tied to money

**7. Money milestones + personal records** (S/M)
Celebrate the dollars: first $100 / $500 / $1k / $5k in any fund or goal, 25 / 50 / 75 / 100%, every $1k of total reserved, savings-rate PB, best month net, longest no-spend run, biggest single contribution. A **Records** panel on Score (Strava-style PB board) and a `_celebrate` with the amount in the headline. Add the **final-stretch bonus**: contributions to an item ≥80% full earn 2× Gold (goal-gradient: people accelerate near the finish, so reward that).
Hooks into: `_commit_pay`, `_plan_row` Add $, `_show_bulk_contribute`, `score_pay`, new `RECORD_DEFS`.

**8. Pacts with Gerald — commitment contracts** (M)
"I promise to … and I'm staking 4 Gems on it." Measurable pacts only, verified from real data: reserve ≥ X% on the next pay; keep *Eating out* under $Y this week (from imported rows); get fund X to $Y by a date; 5 no-spend days in 7. Win: stake ×2 plus an exclusive *Pact* card set (4 cards). Lose: stake gone, Gerald offers a smaller pact. Deposit contracts are the strongest behaviour-change incentive in the physical-activity RCTs, and here the deposit is game currency so the downside is bounded. One active pact at a time; pact card on Today with a countdown.
Hooks into: Gerald intents, `GameStats.active_pact`, month/weekly evaluators, `CARD_SETS`.

**9. Savings challenges, prebuilt** (M)
A catalogue on Setup → Plan: **52-week** ($1 → $52), **No-spend month**, **Round-up jar** (Pulse spends round up to the next $5 into a jar fund), **$5 note challenge**, **Pay-yourself-first 10%**. Each creates a Fund with a schedule, a calendar grid you tick, and its own reward track (badge + card at 25 / 50 / 100%). Commitment + structure removes decision paralysis.
Hooks into: `Fund` (new `schedule` field), Plan tab, cost guide overlay pattern.

**10. Monthly live event** (M)
One theme a month (Frugal Feb, No-spend November, Tax-time Tune-up in July): an **event card set** (4 cards, gone when the month ends), one 2× XP window on the pay-day weekend, a **rotating Perk Shop** (one featured item per day at a discount, countdown), and an event banner on Today. Uses `ensure_season()` for the roll-over. Time-limited exclusives are the strongest FOMO lever that doesn't involve money.
Hooks into: `ensure_season`, `SEASON_TIERS`, `PERK_SHOP_ITEMS`, Collection tab.

### Tier 3 — attachment and curiosity

**11. "While you were away"** (S)
On launch after ≥ 6 h away: a one-screen recap — Gold milled, plots ready, a letter waiting, a bill moved closer, what Gerald noticed. Curiosity gap + Zeigarnik (open loops pull people back). Also doubles as the hand-off to the Do-this-now strip.
Hooks into: startup sequence after `_maybe_prompt_monthly_report`.

**12. Gerald's letters — a serialized story** (S content, M writing)
30–60 short letters unlocked one per Pulse day (not per launch), read at the Homestead mailbox. A gentle serial about the village, with occasional choices that unlock a cosmetic. Narrative drip is the cheapest novelty engine there is; it also makes the mailbox flag mean something.
Hooks into: Homestead mailbox, `GameStats.letters_read`.

**13. Variable vault** (S)
Chest tiers Bronze / Silver / Gold / Mythic rolled daily with weights that improve along the run (day 7 guarantees Gold+), plus a visible *next three days* preview (people value a reward they've already "seen"). Keep the pity logic from packs. Replaces the flat `VAULT_REWARDS`.

**14. Homestead neighbours — NPC rivals** (M)
A weekly XP race against four **clearly fictional villagers** (named, drawn with the avatar rig, with their own "pace" curves that adapt to yours so the race stays close). Promotion / relegation across three leagues; top finish = exclusive badge + items. This is the single-player answer to Duolingo leagues. Must be labelled as villagers, never implied to be real people.
Hooks into: season XP, new `NEIGHBOURS` constant, Score tab.

**15. Wrapped — "Your Month" and "Your Year" share cards** (M)
Extend the month report with PBs and one surprising stat ("you spent 31% less on takeaway than in August"), and add *Your Year* in January. Export the card as an HTML file that opens in the browser (no new dependencies) so it can be screenshotted and shared. Spotify Wrapped works on pride + self-insight; finance has the same material.
Hooks into: `_show_monthly_report`, `_monthly_report_data`.

### Tier 4 — economy and curve tuning (do alongside Tier 1)

- **Collection nudges**: "1 card from completing Momentum" surfaces in Next Up and on the pack screen; duplicate protection when a set is ≥ 80% complete.
- **Rank titles everywhere** (nav rail, profile card, letters).
- **Gem sinks**: freeze purchases, repairs, pact stakes and the rotating shop give Gems a reason to be wanted.
- **Engagement log**: append `(date, action)` to a local `engagement.jsonl` so you can see day-1 / day-7 / day-30 return rates and which hooks are used. Without this, tuning is guesswork.

---

## 3. Suggested build order

| Phase | Items | Why this grouping |
|---|---|---|
| **A — the loop** | 1 Pulse · 2 freezes · 5 challenges fix · 13 variable vault · 6 day-one · 3 triggers | Creates a daily real action, makes it forgiving, makes it variable, and pulls people back from outside. Everything else multiplies this. |
| **B — stakes** | 4 Homestead accrual · 7 milestones & records · 8 pacts · 9 challenges catalogue | Appointment timers plus money-anchored celebrations and commitment. |
| **C — world** | 10 live events · 11 while-you-were-away · 12 letters · 14 neighbours · 15 wrapped | Novelty, story and rivalry on top of a working loop. |

Phase A is roughly a week of work and is where nearly all the retention upside sits.

---

## 4. Sources consulted

- Duolingo streak research (milestone animations +1.7% D7 retention; two freezes +0.38% DAU; 7-day streak → 3.6× completion): https://blog.duolingo.com/duolingo-streak-research/
- How Duolingo reignited growth (streak-saver notification and leagues were the biggest wins): https://www.lennysnewsletter.com/p/how-duolingo-reignited-user-growth
- Duolingo retention strategy overview (7+ day streak users retain 2.4×): https://www.trypropel.ai/resources/blogs/duolingo-customer-retention-strategy
- Finch retention teardown (6-hour adventures, widgets, 54% D1 / 37% D7): https://www.deconstructoroffun.com/blog/x0hd2ssr80y5n7gv0w967pg7hwd7tl
- Finch onboarding (hatching first, feature list later): https://screensdesign.com/articles/finch-app-onboarding-design/
- Fortune City (expense categories → buildings): https://sparkful.app/fortune-city
- Gamification can help consumers reach saving goals (field experiment): https://cepr.org/system/files/2022-08/Hashim%20-%20Gamification_Can_Help_Consumers_Reach_Their_Saving_Goals.pdf
- Deposit contracts vs rewards for behaviour change (RCT): https://www.ncbi.nlm.nih.gov/pmc/articles/PMC11042509/
- Octalysis on finance apps (loss aversion is the drive most likely to churn users): https://yukaichou.com/gamification-examples/top-10-finance-apps-for-2017-from-an-octalysis-gamification-perspective/
- Why daily limits work (Wordle): https://dinogame.gg/blog/why-daily-limits-work-in-games/
- Daily missions in puzzle games: https://deconstructoroffun.com/blog/2024/9/23/daily-missions-in-puzzles-why-should-we-see-them-more-often
- Battle pass psychology: https://pmplayground.substack.com/p/the-science-behind-battle-passes
- Endowed progress effect (Nunes & Drèze): https://msbfile03.usc.edu/digitalmeasures/jnunes/intellcont/Endowed%20Progress%20Effect-1.pdf
- Goal-gradient effect: https://sketchplanations.com/goal-gradient-effect
- Zeigarnik effect: https://lawsofux.com/zeigarnik-effect/
- Cleo's habit loop (daily chat with personality; Roast Mode 20% day-one uptake): https://sacra.com/chat/h/15171560-6e43-42ff-af61-030f30a5c668/
- Spotify Wrapped psychology: https://www.idomoo.com/blog/why-spotify-wrapped-works-and-how-you-can-do-it-too/
- Dark side of gamification / streak anxiety: https://uxmag.com/articles/gamification-or-manipulation-understanding-the-ethics-of-engagement-loops
- Savings challenges as commitment devices: https://www.westernsouthern.com/personal-finance/savings-challenges
- winotify (Windows toasts from Python via PowerShell): https://pypi.org/project/winotify/
