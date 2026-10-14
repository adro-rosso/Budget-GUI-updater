"""Smoke test: Phase B UI — Today harvest line + one-click collect, Homestead harvest strip,
pact card + pact maker overlay + settlement, records section on Score, savings challenges
overlay + Plan strip + round-up, money milestones on contribution, Gerald 'make a pact'."""
import os, sys, tempfile, time
from datetime import date, timedelta, datetime
from pathlib import Path

tmp = tempfile.mkdtemp(prefix="budget_phaseb_")
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


def close_tops(app):
    for w in list(app.winfo_children()):
        if isinstance(w, tk.Toplevel):
            try: w.destroy()
            except tk.TclError: pass
    app.update()


today = date.today()
app = bg.BudgetApp(); app.state.onboarding_complete = True; app.state.tutorial_complete = True
app.geometry("1366x768+0+0"); app.update(); time.sleep(0.4); app.update(); app.focus_force(); app.update()
if getattr(app, "_setup_wizard_scrim", None): app._setup_wizard_scrim.destroy(); app._setup_wizard_scrim = None
app._startup_progression_migration(); app.state.ui_prefs["unlock_all"] = True; app.refresh_today_tab(); app.update()
g = app.state.game; eng = app.game_engine

# ── Today harvest line: nothing yet → after 9 h of milling → collect ─────────
assert "windmill" in app._today_harvest_var.get().lower(), app._today_harvest_var.get()
g.mill_last_collected = (datetime.now() - timedelta(hours=9)).isoformat(timespec="minutes")
app.refresh_today_tab(); app.update()
assert "16 Gold milled (full)" in app._today_harvest_var.get(), app._today_harvest_var.get()
assert any(t.startswith("Harvest ready") for t, *_ in app._next_up_items())
score0 = g.total_score
app._today_harvest_lbl.event_generate("<Button-1>"); app.update()
assert g.total_score == score0 + 16 and g.mill_gold_total == 16
close_tops(app)

# ── Contribution plants a plot, triggers milestones, records ─────────────────
app.state.funds.append(bg.Fund("Holiday", 2000.0, today + timedelta(days=120), "important", 450.0, "auto", 0.0, "fund"))
app._startup_progression_migration()   # seeds the $100 milestone silently (existing savings)
assert "fund:Holiday:$100" in g.money_milestones
import tkinter.simpledialog as sd
sd.askfloat = lambda *a, **k: 100.0
app.refresh_plan_tab(); app.update()
score0 = g.total_score
app._contribute_to_target("fund", 0); app.update()
assert app.state.funds[0].current_saved == 550.0
assert "fund:Holiday:$500" in g.money_milestones and "fund:Holiday:pct25" in g.money_milestones
assert g.total_score >= score0 + 25 + 15
assert "fund:Holiday" in g.plot_timers and g.records["biggest_contribution"]["value"] == 100.0
close_tops(app)

# ── Homestead page strip ─────────────────────────────────────────────────────
app._show_page("homestead"); app.update()
ht = texts(app._homestead_harvest_host)
assert any("HARVEST" == t for t in ht) and any("Holiday — ripens in" in t for t in ht), ht
assert btn(app._homestead_harvest_host, "Nothing ready yet")
g.plot_timers["fund:Holiday"] = (datetime.now() - timedelta(minutes=1)).isoformat(timespec="minutes")
app.refresh_homestead_tab(); app.update()
assert btn(app._homestead_harvest_host, "Collect everything")
btn(app._homestead_harvest_host, "Collect everything")[0].invoke(); app.update()
assert g.pack_fragments == 1 and g.harvests_total == 1 and not g.plot_timers
close_tops(app)

# ── Pact card + maker + settlement ───────────────────────────────────────────
app._show_page("today"); app.update()
assert btn(app._pact_host, "Make a pact")
g.gems = 4
btn(app._pact_host, "Make a pact")[0].invoke(); app.update()
sc = scrims(app)[-1]
assert any("A PACT WITH GERALD" in t for t in texts(sc))
lbl(sc, "No-spend days this week")[0].event_generate("<Button-1>"); app.update()
lbl(sc, "3")[0].event_generate("<Button-1>"); app.update()
lbl(sc, "2 ◇")[0].event_generate("<Button-1>"); app.update()
assert any("3 no-spend days in the next 7" in t and "stake 2 Gems" in t for t in texts(sc)), texts(sc)
btn(sc, "Shake on it  ✓")[0].invoke(); app.update()
assert g.active_pact["kind"] == "nospend" and g.gems == 2 and not scrims(app)
close_tops(app)
pt = texts(app._pact_host)
assert any("ACTIVE PACT" == t for t in pt) and any("0 of 3 no-spend days" in t for t in pt), pt
# win it: three no-spend days inside the window
g.no_spend_dates = [(today + timedelta(days=i)).isoformat() for i in range(3)]
app.refresh_today_tab(); app.update()
assert not g.active_pact and g.pacts_won == 1 and g.gems == 6 and "p_oath_nospend" in g.cards_owned
close_tops(app)
assert btn(app._pact_host, "Make a pact") and any("1 kept" in t for t in texts(app._pact_host))
# Gerald intent
ga = getattr(app, "gerald_assistant", None) or bg.GeraldAssistant(app)
reply = ga._route("make a pact")
assert "stake" in reply[0].lower(); app.update(); time.sleep(0.3); app.update()
assert scrims(app); btn(scrims(app)[-1], "Not today")[0].invoke(); app.update()

# ── Records section on Score ─────────────────────────────────────────────────
app._show_page("score"); app.update()
rt = texts(app._records_host)
assert any("PERSONAL BESTS" == t for t in rt) and any("$100" in t for t in rt) and any("Holiday — passed $500" in t for t in rt), rt
assert "1 milestones" in app._records_summary_var.get() or "milestones" in app._records_summary_var.get()

# ── Savings challenges ───────────────────────────────────────────────────────
app._show_page("setup"); app._show_setup_sub("plan"); app.update()
btn(app.plan_tab, "Savings challenges…")[0].invoke(); app.update()
sc = scrims(app)[-1]
assert len(btn(sc, "Start")) == 5
btn(sc, "Start")[0].invoke(); app.update()   # 52-week
assert not scrims(app) and eng.challenge_active("52week") and app.state.funds[-1].challenge == "52week"
close_tops(app)
rows = texts(app._plan_host)
assert any("52-week challenge" in t and "0 of 52 weeks" in t for t in rows), rows
btn(app.plan_tab, "Savings challenges…")[0].invoke(); app.update(); sc = scrims(app)[-1]
assert len(btn(sc, "Start")) == 4 and lbl(sc, "RUNNING")
# start the round-up jar, then a Pulse spend rounds up into it
[b for b in btn(sc, "Start")][1].invoke(); app.update()
assert eng.challenge_active("roundup")
close_tops(app)
app._show_page("today"); app.update()
g.pulse_progress = {}; g.pulse_last_date = (today - timedelta(days=1)).isoformat(); app.refresh_today_tab(); app.update()
app._expand_section("today.progress"); app.update()   # the Pulse lives in a closed section; clicks need it mapped
lbl(app._vault_host, "Food")[0].event_generate("<Button-1>"); app.update()
app._pulse_amt_entry.insert(0, "7.25"); app.focus_force(); app._pulse_amt_entry.focus_force(); app._pulse_amt_entry.event_generate("<Return>"); app.update()
jar = eng.challenge_fund("roundup"); assert jar.current_saved == 2.75 and jar.challenge_ticks == 1
close_tops(app)
app.save_state()
s2 = bg.AppState.from_dict(__import__("json").loads(bg.DATA_FILE.read_text(encoding="utf-8")))
assert s2.game.pacts_won == 1 and s2.funds[1].challenge == "52week"
app.destroy()
print("SMOKE TEST 12 PASSED")
