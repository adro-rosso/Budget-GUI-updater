"""Smoke test: engagement log + Settings habit readout, set nudge + duplicate protection
in packs, rank title in the nav rail and Homestead badge, harvest burst on spend/contribute,
tier-up card with Equip, Gerald scene quips."""
import os, sys, tempfile, time, json
from datetime import date, timedelta, datetime
from pathlib import Path

tmp = tempfile.mkdtemp(prefix="budget_b3_")
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


def scrims(app):
    return [w for w in app.winfo_children() if isinstance(w, tk.Frame) and str(w.cget("bg")) == bg.UI_HERO and w.winfo_manager() == "place"]


today = date.today()
app = bg.BudgetApp(); app.state.onboarding_complete = True; app.state.tutorial_complete = True; app.state.starting_position_set = True
app.geometry("1366x768+0+0"); app.update(); time.sleep(0.4); app.update()
if getattr(app, "_setup_wizard_scrim", None): app._setup_wizard_scrim.destroy(); app._setup_wizard_scrim = None
app._startup_progression_migration(); app.refresh_today_tab(); app.update()
app._celebrate = lambda *a, **k: None
st = app.state; g = st.game; eng = app.game_engine

# ── Engagement log ───────────────────────────────────────────────────────────
log = Path("engagement.jsonl")
assert log.exists() and json.loads(log.read_text().splitlines()[-1])["action"] == "launch"
app._log_engagement("pulse")
s = app._engagement_stats(); assert s["first"] == today and s["active7"] == 1 and s["d7"] is None
# synthesise an older profile: first seen 40 days ago, back on day 7 and 30
with log.open("a", encoding="utf-8") as f:
    for n in (40, 33, 10):
        f.write(json.dumps({"ts": (datetime.now() - timedelta(days=n)).isoformat(timespec="minutes"), "action": "launch"}) + "\n")
s = app._engagement_stats(); assert s["first"] == today - timedelta(days=40) and s["d7"] is True and s["d30"] is True and s["active30"] == 2, s
app._show_page("settings"); app.update()
assert "came back on day 7: yes" in app._settings_engagement_var.get()

# ── Rank titles ──────────────────────────────────────────────────────────────
app.refresh_game_text(); app.update()
assert app._nav_rank_lbl.cget("text").startswith("★ ") and "Level" in app._nav_rank_lbl.cget("text")
app._show_page("homestead"); app.update()
assert "·" in app._homestead_tier_var.get() and "TIER" in app._homestead_tier_var.get()

# ── Set nudge + duplicate protection ─────────────────────────────────────────
sid, sname, _d, cids, reward = bg.CARD_SETS[0]           # Foundations: 12 commons
g.cards_owned = list(cids[:-1])                          # 11 of 12 owned
assert "1 card from completing Foundations" in app._nearest_set_nudge()
app._show_page("collection"); app.refresh_collection(); app.update()
assert "Foundations" in app._pack_nudge_var.get()
g.total_score = 100000
import random
random.seed(3)
hits = 0
for _ in range(25):
    res = eng.open_pack("standard")
    if cids[-1] in g.cards_owned:
        hits += 1; break
assert cids[-1] in g.cards_owned, "the missing Foundations card should arrive quickly with duplicate protection"

# ── Harvest burst on spend / contribute (no crash, items drawn + cleared) ────
st.funds.append(bg.Fund("Holiday", 2000.0, today + timedelta(days=100), "important", 300.0, "auto", 0.0, "fund"))
app.refresh_all_views(); app._show_page("homestead"); app.update(); time.sleep(0.2); app.update()
app._homestead_burst("fund", "Holiday"); app.update()
assert app._homestead_canvas.find_withtag("burst"), "burst particles should be on the Homestead canvas"
time.sleep(0.7); app.update()
assert not app._homestead_canvas.find_withtag("burst"), "burst should clear itself"
import tkinter.simpledialog as sd
sd.askfloat = lambda *a, **k: 20.0
app._spend_from_fund(0); app.update()
assert st.funds[0].current_saved == 280.0

# ── Tier-up card ─────────────────────────────────────────────────────────────
app._show_tier_up_card(1, ["comp_hen"]); app.update()
sc = scrims(app)[-1]
assert any("Marigold the Hen" == t for t in texts(sc)) and btn(sc, "Equip now  ✓")
g.character_items_owned.append("comp_hen"); g.homestead_tier = 1; g.homestead_claimed_tiers = [1]
btn(sc, "Equip now  ✓")[0].invoke(); app.update()
assert g.character_equipped.get("companion") == "comp_hen"
assert sc not in app.winfo_children(), "the card we clicked should have closed"
for w_ in list(app.winfo_children()):   # the Homestead page may have raised a real tier-up card too
    if isinstance(w_, tk.Frame) and str(w_.cget("bg")) == bg.UI_HERO and w_.winfo_manager() == "place": w_.destroy()
app.update()

# ── Scene quips ──────────────────────────────────────────────────────────────
st.bills.append(bg.Bill("Rent", 800.0, today - timedelta(days=3), "monthly", "essential", "bill", 0.0))
snap = app.homestead.snapshot()
q = app._scene_quips(snap)
assert any("gap in the fence" in txt and "Rent" in txt for _, txt, _e in q), q
g.mill_last_collected = (datetime.now() - timedelta(hours=9)).isoformat(timespec="minutes")
snap = app.homestead.snapshot(); assert snap["mill_ready"]
assert any("Grain sack" in txt for _, txt, _e in app._scene_quips(snap))
app._show_page("today"); app.refresh_today_tab(); app.update()
app.destroy()
print("SMOKE TEST 17 PASSED")
