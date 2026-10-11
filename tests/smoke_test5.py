"""Smoke test: Daily Vault, Next Up strip, streak risk, celebrations, pack pity."""
import os, sys, tempfile, time, random
from datetime import date, timedelta

tmp = tempfile.mkdtemp(prefix="budget_hooks_")
os.chdir(tmp)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import tkinter as tk
import budget_gui as bg

# ── Pulse / Vault engine ─────────────────────────────────────────────────────
st = bg.AppState(); eng = bg.BudgetGameEngine(st); g = st.game
today = date.today()
s = eng.vault_status()
assert not s["opened_today"] and s["day"] == 1 and not s["bonus"] and not s["ready"]
eng.pulse_mark_beat("spend"); eng.pulse_mark_beat("sort")
assert eng.vault_status()["ready"]
r = eng.open_vault(force_tier="silver")
assert r["gold"] == 12 and r["day"] == 1 and r["streak"] == 1 and g.total_score == 12 and r["tier"] == "silver"
assert eng.open_vault() is None
s = eng.vault_status(); assert s["opened_today"] and s["day"] == 1 and s["last_tier"] == "silver"
# yesterday was day 6 → today is day 7: Gold+ guaranteed, real action doubles, freeze earned
g.pulse_last_date = (today - timedelta(days=1)).isoformat(); g.pulse_streak = 6
eng.mark_real_action(); eng.pulse_mark_beat("spend"); eng.pulse_mark_beat("sort")
s = eng.vault_status(); assert s["day"] == 7 and s["guaranteed"] and s["odds"]["bronze"] == 0 and s["bonus"], s
r = eng.open_vault(); assert r["tier"] in ("gold", "mythic") and r["gold"] in (40, 80) and r["streak"] == 7 and r["freeze_earned"] and g.pulse_freezes == 1
# missed one day with a freeze banked → freeze consumed, run intact
g.pulse_last_date = (today - timedelta(days=2)).isoformat(); g.pulse_streak = 7
s = eng.vault_status(); assert s["streak"] == 7 and g.pulse_freezes == 0 and s["day"] == 8, s
# missed again with no freeze → broken, repairable for gems
g.pulse_last_date = (today - timedelta(days=3)).isoformat(); g.pulse_streak = 9
s = eng.vault_status(); assert s["streak"] == 0 and s["day"] == 1 and s["repair"]["length"] == 9 and s["repair"]["cost"] == 3, s
g.gems = 2; ok, _ = eng.repair_pulse(); assert not ok
g.gems = 5; ok, _ = eng.repair_pulse(); assert ok and g.pulse_streak == 9 and g.gems == 2 and eng.vault_status()["repair"] is None
print("pulse OK")

# ── Pack pity ────────────────────────────────────────────────────────────────
st = bg.AppState(); eng = bg.BudgetGameEngine(st); g = st.game
g.total_score = 100000
random.seed(1)
orig = random.choices
random.choices = lambda pop, weights=None, k=1: ["common"] * k   # force dry packs
try:
    for i in range(4):
        res = eng.open_pack("standard")
        assert all(c[2] == "common" for c in res["cards"]) and not res["pity_used"]
    assert g.packs_since_epic == 4
    res = eng.open_pack("standard")
    assert res["pity_used"] and any(c[2] in ("epic", "legendary") for c in res["cards"]), res["cards"]
    assert g.packs_since_epic == 0
finally:
    random.choices = orig
print("pity OK")

# ── Live app: Today row, next-up, streak risk, celebrate ─────────────────────
app = bg.BudgetApp(); app.state.onboarding_complete = True; app.state.tutorial_complete = True
app.update(); time.sleep(0.4); app.update()
if getattr(app, "_setup_wizard_scrim", None): app._setup_wizard_scrim.destroy(); app._setup_wizard_scrim = None
app._startup_progression_migration(); app.refresh_today_tab(); app.update()   # the saved file in prod already has onboarding_complete
app._show_page("today"); app.update()
def texts(root):
    out = []
    def walk(w):
        try: out.append(str(w.cget("text")))
        except tk.TclError: pass
        for ch in w.winfo_children(): walk(ch)
    walk(root); return out
vt = texts(app._vault_host)
assert any("DAILY PULSE" in t for t in vt) and any("Yesterday" in t for t in vt), vt
nt = texts(app._next_up_host)
assert any("NEXT UP" in t for t in nt) and any(t.startswith("Level 2") for t in nt) and any("Streak 3" in t for t in nt), nt
# existing profile: migration pre-did the two beats and forced a Gold chest → open from the UI
btn = [w for w in all_w(app._vault_host) if isinstance(w, bg.ttk.Button)] if "all_w" in dir() else []
def _buttons(root):
    out = []
    def walk(w):
        if isinstance(w, bg.ttk.Button): out.append(w)
        for ch in w.winfo_children(): walk(ch)
    walk(root); return out
btn = [b for b in _buttons(app._vault_host) if str(b.cget("text")) == "OPEN THE VAULT"]
assert btn, vt
btn[0].invoke(); app.update()
assert app.state.game.pulse_streak == 1 and app.state.game.vault_last_tier == "gold" and app.state.game.total_score >= 20
assert any("Gold chest opened" in t for t in texts(app._vault_host)), texts(app._vault_host)
top = getattr(app, "_celebration_top", None)
assert top is not None and top.winfo_exists()
time.sleep(0.5); app.update()
assert not [b for b in _buttons(app._vault_host) if str(b.cget("text")) == "OPEN THE VAULT"]
# streak risk banner
app.state.game.streak_pays = 4
app.state.incomes.append(bg.IncomeEntry(2000.0, today - timedelta(days=20), "Pay"))   # fortnightly → 6 days late
app.refresh_today_tab(); app.update()
risk = app._streak_risk(); assert risk and risk[1] == bg.UI_RUBY and "6 days ago" in risk[0], risk
assert any("Streak at risk" in t for t in texts(app._next_up_host))
app.state.incomes[-1] = bg.IncomeEntry(2000.0, today - timedelta(days=13), "Pay")     # due tomorrow
risk = app._streak_risk(); assert risk and risk[1] == bg.UI_GOLD, risk
# next-up ordering: closest first, max 4, and homestead entry present
items = app._next_up_items()
assert 1 <= len(items) <= 4 and all(items[i][1] >= items[i + 1][1] for i in range(len(items) - 1))
assert all(len(it) == 5 for it in items)   # (homestead at 0% is legitimately outside the top 4 on a fresh profile)
# collection pity label
app._show_page("collection"); app.update()
assert "guaranteed within 5 packs" in app._pack_pity_var.get(), app._pack_pity_var.get()
app.state.game.packs_since_epic = 4; app.refresh_collection(); app.update()
assert "Next pack has a guaranteed Epic" in app._pack_pity_var.get()
# celebrate variants render and self-destroy
app._celebrate("Level 9!", "subtitle here", bg.UI_EMERALD, duration_ms=300); app.update()
time.sleep(0.6); app.update()
# round trip
s2 = bg.AppState.from_dict(app.state.to_dict())
assert s2.game.vault_visit_streak == 1 and s2.game.packs_since_epic == 4
app.destroy()
print("SMOKE TEST 5 PASSED")
