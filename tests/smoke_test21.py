"""Smoke test: the calm pass — progressive unlock with locked lines and the Settings override,
compact Pulse line once done (details on demand), pacts/event folded into a collapsed Today
section with a summary and Next Up rows, one quick-action row with a More menu holding every
old button, race/letters collapsed by default, toast coalescing, celebration queue."""
import os, sys, tempfile, time
from datetime import date, timedelta, datetime

tmp = tempfile.mkdtemp(prefix="budget_calm_")
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


today = date.today()
app = bg.BudgetApp(); app.state.onboarding_complete = True; app.state.tutorial_complete = True; app.state.starting_position_set = True
app.geometry("1366x768+0+0"); app.update(); time.sleep(0.4); app.update(); app.focus_force(); app.update()
if getattr(app, "_setup_wizard_scrim", None): app._setup_wizard_scrim.destroy(); app._setup_wizard_scrim = None
app._startup_progression_migration(); app.refresh_today_tab(); app.update()
st = app.state; g = st.game; eng = app.game_engine

# ── Progressive unlock on a fresh profile ────────────────────────────────────
assert not app._feature_unlocked("pacts") and not app._feature_unlocked("race") and not app._feature_unlocked("weekly") and not app._feature_unlocked("decor")
assert any("🔒 Pacts with Gerald" in t for t in texts(app._pact_host)), texts(app._pact_host)
app._show_page("score"); app.refresh_daily_challenges(); app.refresh_season_pass(); app.update()
assert any("🔒 Weekly challenges" in t for t in texts(app._weekly_host)) and any("🔒 Weekly race" in t for t in texts(app._rivals_host))
assert app._rivals_summary_var.get().startswith("locked")
# progress unlocks naturally
g.pulse_days_total = 5; g.total_pays_processed = 1; g.level = 3
assert app._feature_unlocked("pacts") and app._feature_unlocked("race") and app._feature_unlocked("weekly") and app._feature_unlocked("decor")
app.refresh_season_pass(); app.update()
assert any("LEAGUE" in t for t in texts(app._rivals_host))
# the override shows everything regardless
g.pulse_days_total = 0; g.total_pays_processed = 0; g.level = 1
app._show_page("settings"); app.update()
assert btn(app.settings_tab, "Show everything now")
btn(app.settings_tab, "Show everything now")[0].invoke(); app.update()
assert st.ui_prefs["unlock_all"] is True and app._feature_unlocked("race") and btn(app.settings_tab, "Reveal systems as I go")
app._show_page("today"); app.update()
assert btn(app._pact_host, "Make a pact")

# ── Today: extras collapsed with a summary; More menu holds the old buttons ─
assert not st.ui_prefs.get("today.extras", False)
summ = app._today_extras_summary.get()
assert "no pact" in summ and bg.MONTHLY_EVENTS[today.month][0] in summ and "deal:" in summ, summ
labels = [app._today_more_menu.entrycget(i, "label") for i in range(app._today_more_menu.index("end") + 1) if app._today_more_menu.type(i) == "command"]
for want in ("Sort unrecognised", "Commit reviewed", "Open Perk Shop", "Make a pact with Gerald", "Savings challenges…", "Set up from my statement"):
    assert want in labels, (want, labels)
assert btn(app.today_tab, "Log Pay") and btn(app.today_tab, "Import statement") and btn(app.today_tab, "Setup")
assert not btn(app.today_tab, "Open Perk Shop"), "moved into More"

# ── Pulse compact once done ──────────────────────────────────────────────────
eng.pulse_mark_beat("spend"); eng.pulse_mark_beat("sort"); eng.open_vault(force_tier="gold")
app._expand_section("today.progress"); app.refresh_today_tab(); app.update()
tt = texts(app._vault_host)
assert any(t.startswith("✓ Done · 1-day run") and "Gold" in t for t in tt), tt
assert not any("Next:" == t for t in tt), "full done-state should be hidden until 'details'"
compact = [w for w in all_w(app._vault_host) if isinstance(w, tk.Label) and str(w.cget("text")).startswith("✓ Done")][0]
compact.event_generate("<Button-1>"); app.update()
tt = texts(app._vault_host)
assert any("Next:" == t for t in tt) and any("less" == t for t in tt), tt
[w for w in all_w(app._vault_host) if isinstance(w, tk.Label) and str(w.cget("text")) == "less"][0].event_generate("<Button-1>"); app.update()
assert any(t.startswith("✓ Done") for t in texts(app._vault_host))

# ── Next Up rows for an active pact and the seasonal set ─────────────────────
g.gems = 4; eng.make_pact("nospend", {"n": 3}, 1)
g.no_spend_dates = [today.isoformat(), (today + timedelta(days=1)).isoformat()]   # 2 of 3 → near the top of Next Up
season = bg.season_for_month(today.month); g.cards_owned.append(bg.EVENT_CARD_SETS[season][1][0][0])
titles = [it[0] for it in app._next_up_items()]
assert any(t.startswith("Pact:") for t in titles), titles
app.refresh_today_tab(); app.update()
assert "Pact:" in app._today_extras_summary.get()

# ── Toast coalescing: three quick successes become one toast ─────────────────
app._toast_stack.clear()
app._show_toast("Challenge done: A", "success"); app._show_toast("Milestone: B", "success"); app._show_toast("Record: C", "success"); app.update()
live = [t for t in app._toast_stack if t.winfo_exists()]
assert len(live) == 1 and str(live[0]._msg_lbl.cget("text")).count("\n") == 2, [str(t._msg_lbl.cget("text")) for t in live]
app._show_toast("With undo", "success", action_label="Undo", action_cb=lambda: None); app.update()
assert len([t for t in app._toast_stack if t.winfo_exists()]) == 2, "an actionable toast never merges"

# ── Celebrations queue instead of overlapping ────────────────────────────────
app._celebrate("One", "first"); app.update()
first = app._celebration_top
app._celebrate("Two", "second"); app.update()
assert app._celebration_top is first, "second celebration should wait, not replace"
for _ in range(110):            # pump the Tk loop so the first burst plays out (~1.7 s of 40 ms frames)
    app.update(); time.sleep(0.03)
assert app._celebration_top is not first, "queued celebration should have started"
for w in list(app.winfo_children()):
    if isinstance(w, tk.Toplevel): w.destroy()
app.update()

# ── Race and letters collapsed by default; letters open when one waits ───────
assert not st.ui_prefs.get("score.rivals", False)
g.letters_read = g.pulse_days_total          # nothing waiting yet → the section stays closed
app._show_page("homestead"); app.update()
assert not st.ui_prefs.get("homestead.letters", False)
g.pulse_days_total = 2; g.letters_read = 0
app._render_letters_card(); app.update()
assert st.ui_prefs.get("homestead.letters") is True
app.destroy()
print("SMOKE TEST 21 PASSED")
