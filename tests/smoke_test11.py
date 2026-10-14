"""Smoke test: Daily Pulse card (spend → sort → vault), no-spend run, freeze/repair UI,
weekly trio on Score, Next Up pulse row + evening banner, Do-this-now, Settings reminders
section (no Task Scheduler writes), day-one head start on first run, --remind dry run."""
import os, sys, tempfile, time, json
from datetime import date, timedelta, datetime
from pathlib import Path

tmp = tempfile.mkdtemp(prefix="budget_pulse_")
os.chdir(tmp)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import tkinter as tk
import budget_gui as bg


def all_w(root):
    out = []
    def walk(w):
        out.append(w)
        for ch in w.winfo_children(): walk(ch)
    walk(root); return out


def texts(root):
    out = []
    for w in all_w(root):
        try: out.append(str(w.cget("text")))
        except tk.TclError: pass
    return out


def btn(root, text, cls=None):
    cls = cls or (bg.ttk.Button, tk.Button)
    return [w for w in all_w(root) if isinstance(w, cls) and str(w.cget("text")) == text]


def lbl(root, text):
    return [w for w in all_w(root) if isinstance(w, tk.Label) and str(w.cget("text")) == text]


def scrims(app):
    return [w for w in app.winfo_children() if isinstance(w, tk.Frame) and str(w.cget("bg")) == bg.UI_HERO and w.winfo_manager() == "place"]


def tx(d, desc, out=0.0, inn=0.0, **kw):
    return bg.TransactionRecord(tx_date=d, description=desc, money_out=out, money_in=inn, fingerprint=f"{d}|{desc}|{out}|{inn}", **kw)


# Never touch the real Task Scheduler from a test
bg.install_reminder_task = lambda p: (True, "stubbed")
bg.remove_reminder_task = lambda: (True, "stubbed")
_installed = [False]
bg.reminder_task_installed = lambda: _installed[0]
bg._send_windows_toast = lambda t, b: True

today = date.today(); yesterday = today - timedelta(days=1)
app = bg.BudgetApp(); app.state.onboarding_complete = True; app.state.tutorial_complete = True
app.geometry("1366x768+0+0"); app.update(); time.sleep(0.4); app.update(); app.focus_force(); app.update()
if getattr(app, "_setup_wizard_scrim", None): app._setup_wizard_scrim.destroy(); app._setup_wizard_scrim = None
app._startup_progression_migration(); app.refresh_today_tab(); app.update()   # the saved file in prod already has onboarding_complete
app.state.ui_prefs["unlock_all"] = True   # progressive unlock would hide the weekly panel on a fresh profile
g = app.state.game; eng = app.game_engine

# ── Existing-profile migration: founder card + beats pre-done, gold chest forced ──
assert g.day_one_done and "x_founder" in g.cards_owned and g.vault_force_tier == "gold"
assert g.pulse_progress.get("spend") and g.pulse_progress.get("sort")
# reset to a clean day so the full flow can be exercised
g.pulse_progress = {}; g.vault_force_tier = ""; g.last_real_action_date = ""
app.latest_import = [app.matcher.match(tx(yesterday, "MYSTERY SHOP 42", 18.5))]
app.refresh_today_tab(); app.update()
app._expand_section("today.progress"); app.update()   # the Pulse lives in a closed section; clicks need it mapped
host = app._vault_host
assert any("DAILY PULSE" == t for t in texts(host)) and any("1 Yesterday" in t for t in texts(host)), texts(host)

# Beat 1: pick a category and log $12.50 for yesterday
lbl(host, "Groceries")[0].event_generate("<Button-1>"); app.update()
ent = app._pulse_amt_entry; ent.insert(0, "$12.50"); app.focus_force(); ent.focus_force(); ent.event_generate("<Return>"); app.update()
assert app.state.transactions and app.state.transactions[-1].source_file == "pulse" and app.state.transactions[-1].money_out == 12.5
assert app.state.transactions[-1].tx_date == yesterday and app.state.transactions[-1].category == "Groceries"
assert g.last_real_action_date == today.isoformat()
assert any("Logged $12.50" in t for t in texts(host)), texts(host)
lbl(host, "that's everything →")[0].event_generate("<Button-1>"); app.update()
assert g.pulse_progress.get("spend") and any("2 Sort one" in t for t in texts(host)), texts(host)

# Beat 2: one card to sort, chip assigns + remembers a rule
assert any("mystery shop" in t.lower() for t in texts(host)), texts(host)
chips = [w for w in all_w(host) if isinstance(w, tk.Label) and str(w.cget("text")).lstrip("✓ ") == "Fuel"]
chips[0].event_generate("<Button-1>"); app.update()
assert app.latest_import[0].user_verified and app.latest_import[0].category == "Fuel"
assert any(r.keyword == "mystery shop" for r in app.state.advanced_match_rules), [r.keyword for r in app.state.advanced_match_rules]
assert g.pulse_progress.get("sort") and btn(host, "OPEN THE VAULT"), texts(host)
assert any("×2 Gold" in t for t in texts(host))

# Beat 3: open → gold doubled, run 1, done state with preview
score0 = g.total_score
btn(host, "OPEN THE VAULT")[0].invoke(); app.update()
assert g.pulse_streak == 1 and g.pulse_last_date == today.isoformat() and g.total_score > score0
gold, _, _, label = bg.BudgetGameEngine.VAULT_CHESTS[g.vault_last_tier]
assert any(t.startswith("✓ Done · 1-day run") for t in texts(host)), texts(host)   # compact by default once done
app._toggle_pulse_details(); app.update()                                                  # 'details' shows the full done state
assert g.total_score - score0 >= gold * 2 and any(label + " opened ✓" == t for t in texts(host)), texts(host)
assert any("D7 Gold+" in t for t in texts(host)) or any("D2" in t for t in texts(host))
app._toggle_pulse_details(); app.update()
for w in list(app.winfo_children()):
    if isinstance(w, tk.Toplevel): w.destroy()

# No-spend path on a fresh day (simulate: yesterday's pulse done, today's not)
g.pulse_last_date = yesterday.isoformat(); g.pulse_progress = {}; app.refresh_today_tab(); app.update()
lbl(host, "No spend ✓")[0].event_generate("<Button-1>"); app.update()
assert g.no_spend_streak == 1 and g.no_spend_last == yesterday.isoformat() and g.pulse_progress.get("no_spend")
# sort beat auto-completes when nothing is waiting
assert g.pulse_progress.get("sort") and btn(host, "OPEN THE VAULT")
# daily challenge 'no_spend' completes if drawn
if any(c["trigger"] == "no_spend" for c in g.daily_challenges):
    assert any(c["trigger"] == "no_spend" and c["completed"] for c in g.daily_challenges)

# Broken run → repair button in the card
g.pulse_last_date = (today - timedelta(days=4)).isoformat(); g.pulse_streak = 8; g.pulse_freezes = 0; g.pulse_progress = {}
g.gems = 10; app.refresh_today_tab(); app.update()
assert g.pulse_streak == 0 and btn(host, "Repair"), texts(host)
btn(host, "Repair")[0].invoke(); app.update()
assert g.pulse_streak == 8 and g.gems == 7

# Next Up shows the pulse milestone row; evening banner only after 17:00
titles = [it[0] for it in app._next_up_items()]
assert any(t.startswith("Pulse run") for t in titles), titles
risk = app._pulse_risk()
assert (risk is None) == (datetime.now().hour < 17)

# Do-this-now offers the Pulse when not done
g.pulse_last_date = yesterday.isoformat(); g.pulse_progress = {}; app.refresh_today_tab(); app.update()
cands = app._do_now_candidates(app._next_actions_snapshot()["actions"])
assert any(c["title"] == "Do today's Pulse" for c in cands), [c["title"] for c in cands]

# ── Weekly trio on the Score tab ─────────────────────────────────────────────
app._show_page("score"); app.update()
wk = texts(app._weekly_host)
assert any("THIS WEEK" == t for t in wk) and any("Finish 5 Daily Pulses" in t for t in wk), wk
for ch in g.weekly_challenges: ch["progress"] = ch["goal"]; ch["completed"] = True
app.refresh_daily_challenges(); app.update()
assert btn(app._weekly_host, "Claim the Gem Pack  ✦")
n_cards = len(g.cards_owned)
btn(app._weekly_host, "Claim the Gem Pack  ✦")[0].invoke(); app.update()
assert len(g.cards_owned) == n_cards + 3 and g.weekly_reward_claimed
for w in list(app.winfo_children()):
    if isinstance(w, tk.Toplevel): w.destroy()
app.update()

# Contribute trigger fires from the Plan quick Add $
app.state.funds.append(bg.Fund("Holiday", 2000.0, today + timedelta(days=120), "important", 100.0, "auto", 0.0, "fund"))
g.daily_challenges = [{"id": "contribute", "description": "Add money to a fund or goal", "trigger": "contribute", "reward_type": "gold", "reward_amount": 20, "completed": False}, {"id": "run_mini_game", "description": "Complete an arcade round", "trigger": "mini_game", "reward_type": "gold", "reward_amount": 20, "completed": False}, {"id": "submit_target", "description": "Submit your spending target mix", "trigger": "submit_target", "reward_type": "gems", "reward_amount": 1, "completed": False}]
import tkinter.simpledialog as sd
sd.askfloat = lambda *a, **k: 50.0
app._contribute_to_target("fund", 0); app.update()
assert app.state.funds[0].current_saved == 150.0 and g.daily_challenges[0]["completed"], (app.state.funds[0].current_saved, g.daily_challenges, [f.name for f in app.state.funds])

# Homestead visit trigger
g.daily_challenges = [{"id": "homestead", "description": "Visit your Homestead", "trigger": "homestead", "reward_type": "gold", "reward_amount": 10, "completed": False}, {"id": "run_mini_game", "description": "Complete an arcade round", "trigger": "mini_game", "reward_type": "gold", "reward_amount": 20, "completed": False}, {"id": "submit_target", "description": "Submit your spending target mix", "trigger": "submit_target", "reward_type": "gems", "reward_amount": 1, "completed": False}]
app._show_page("homestead"); app.update()
assert g.daily_challenges[0]["completed"]

# ── Settings: reminders section (stubbed scheduler) ──────────────────────────
app._show_page("settings"); app.update()
assert btn(app.settings_tab, "Turn reminders on") and btn(app.settings_tab, "Weekends count")
btn(app.settings_tab, "Turn reminders on")[0].invoke(); _installed[0] = True; app._refresh_settings_reminders(); app.update()
assert btn(app.settings_tab, "Turn reminders off") and app.state.ui_prefs["reminders.enabled"] is True
btn(app.settings_tab, "Weekends count")[0].invoke(); app.update()
assert app.state.ui_prefs["pulse.skip_weekends"] is True and btn(app.settings_tab, "Weekends don't count ✓")
app._settings_pulse_hour.set("20:00"); app._settings_set_pulse_hour(); assert app.state.ui_prefs["reminders.pulse_hour"] == 20
btn(app.settings_tab, "Send a test notification")[0].invoke(); app.update()
# weekend skip: a Sat+Sun gap with no freezes keeps the run
g.pulse_freezes = 0
mon = today - timedelta(days=today.weekday())  # this week's Monday
fri = mon - timedelta(days=3)
g.pulse_last_date = fri.isoformat(); g.pulse_streak = 5; g.pulse_broken_len = 0
if today == mon:
    assert eng.vault_status()["streak"] == 5, "weekend gap should not break the run"
app.save_state()

# --remind dry run against the saved file
import io, contextlib
g.pulse_last_date = yesterday.isoformat(); app.state.ui_prefs["reminders.quiet_start"] = 0; app.state.ui_prefs["reminders.quiet_end"] = 0; app.save_state()
at = lambda h: datetime.combine(date.today(), datetime.min.time()).replace(hour=h)
buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    n = bg.run_reminder_check(["--remind", "--data", str(bg.DATA_FILE.resolve()), "--dry-run"], now=at(21))
out = buf.getvalue()
assert n >= 1 and "[pulse]" in out and "-day run ends at midnight" in out, out
# quiet hours (default 22–8) silence it; explicit 0/0 does not
app.state.ui_prefs.pop("reminders.quiet_start"); app.state.ui_prefs.pop("reminders.quiet_end"); app.save_state()
assert bg.run_reminder_check(["--remind", "--data", str(bg.DATA_FILE.resolve()), "--dry-run"], now=at(23)) == 0
app.destroy()

# ── First-run day one: wizard finish → founder + free pack + beats pre-done ──
tmp2 = tempfile.mkdtemp(prefix="budget_dayone_"); os.chdir(tmp2)
bg.DATA_FILE = Path("budget_data.json")
app2 = bg.BudgetApp(); app2.focus_force(); app2.update(); time.sleep(0.4); app2.update()
assert not app2.state.game.day_one_done
# first run is the two-card onboarding now; take its link to the full plan so the wizard's Finish drives day one
ob = app2._track_onboarding_scrim; assert ob is not None
[w for w in all_w(ob) if isinstance(w, (bg.ttk.Button, tk.Button)) and str(w.cget("text")).startswith("Next")][0].invoke(); app2.update()
[w for w in all_w(ob) if isinstance(w, tk.Label) and str(w.cget("text")).startswith("Set up a full money plan")][0].event_generate("<Button-1>"); app2.update()
sc = app2._setup_wizard_scrim; assert sc is not None
# jump through the wizard with 'Finish later' is not a finish; drive the real finish: add one bill then go to the last step
ents = [w for w in all_w(sc) if isinstance(w, bg.ttk.Entry) and not isinstance(w, bg.ttk.Combobox)]
for w in all_w(sc):
    if isinstance(w, (bg.ttk.Button, tk.Button)) and str(w.cget("text")).startswith("Next"):
        pass
# Use the wizard's internal state through the public finish path: step to the end
for _ in range(8):
    nb = [w for w in all_w(sc) if isinstance(w, (bg.ttk.Button, tk.Button)) and str(w.cget("text")).startswith(("Next", "Skip for now", "Finish  ✓"))]
    if not nb: break
    t_ = str(nb[0].cget("text")); nb[0].invoke(); app2.update()
    if t_.startswith("Finish  ✓"): break
g2 = app2.state.game
t0 = time.time()   # the head start waits for a quiet screen (overlays closed), then runs
while time.time() - t0 < 6.0 and not g2.day_one_done:
    for w_ in list(app2.winfo_children()):
        if isinstance(w_, tk.Frame) and w_.winfo_manager() == "place" and str(w_.cget("bg")) == bg.UI_HERO:
            w_.destroy()
    app2.update(); time.sleep(0.2)
assert app2.state.onboarding_complete and g2.day_one_done and "x_founder" in g2.cards_owned, (app2.state.onboarding_complete, g2.day_one_done)
assert len(g2.cards_owned) >= 4 and g2.packs_opened == 1 and g2.season_xp >= 30 and g2.vault_force_tier == "gold"
assert g2.pulse_progress.get("spend") and g2.pulse_progress.get("sort")
# the pack waits for a quiet screen (overlays such as the tier-up card are closed by the user), then 2.3 s
t0 = time.time()
while time.time() - t0 < 8.0 and not (getattr(app2, "_pack_win", None) is not None and app2._pack_win.winfo_exists()):
    for w_ in list(app2.winfo_children()):
        if isinstance(w_, tk.Frame) and w_.winfo_manager() == "place" and str(w_.cget("bg")) == bg.UI_HERO:
            w_.destroy()
    app2.update(); time.sleep(0.2)
assert getattr(app2, "_pack_win", None) is not None and app2._pack_win.winfo_exists(), "free pack should be revealing"
app2._pack_win.destroy(); app2.update(); time.sleep(0.7); app2.update()
app2.destroy()
print("SMOKE TEST 11 PASSED")
