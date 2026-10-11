"""Smoke test: Homestead engine + scene, tier awards + companions, Homestead
page, Today card, avatar grid thumbnails."""
import os, sys, tempfile, time
from datetime import date, timedelta, datetime

tmp = tempfile.mkdtemp(prefix="budget_home_")
os.chdir(tmp)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import tkinter as tk
import budget_gui as bg

# ── Engine on a hand-built state ─────────────────────────────────────────────
st = bg.AppState()
today = date.today()
st.bills = [bg.Bill("Rent", 800.0, today + timedelta(days=5), "monthly", "essential", "bill", 800.0),
            bg.Bill("Power", 120.0, today - timedelta(days=3), "monthly", "essential", "bill", 0.0)]   # overdue
st.funds = [bg.Fund("Holiday", 1000.0, today + timedelta(days=100), "important", 700.0, "auto", 0.0, "fund"),
            bg.Fund("Gifts", 0.0, None, "important", 520.0, "ongoing", 20.0, "fund"),
            bg.Fund("Car", 600.0, None, "important", 600.0, "buffer", 0.0, "fund")]
st.goals = [bg.Goal("Emergency", 5000.0, None, 1, 5000.0, "fixed", 50.0), bg.Goal("Savings", 0.0, None, 3, 2600.0, "percent_surplus", 10.0)]
for i in range(7):
    st.transactions.append(bg.TransactionRecord(today - timedelta(days=i), f"TX {i}", money_out=5.0, source_file=f"s{i}.pdf", fingerprint=f"fp{i}"))
st.transactions[0].flagged = True
st.game.level = 7; st.game.streak_pays = 4
st.incomes.append(bg.IncomeEntry(2000.0, today - timedelta(days=40), "Pay"))
eng = bg.HomesteadEngine(st)
snap = eng.snapshot(datetime(2026, 10, 7, 21, 0))
print({k: snap[k] for k in ("time_of_day", "weather", "house_stage", "lit_windows", "path_stones", "mailbox_flag", "windmill_spin", "weeds", "tier")})
assert snap["time_of_day"] == "night" and snap["weather"] == "clear" and snap["house_stage"] == 3
assert snap["lit_windows"] is False                         # Power overdue
assert [p["stage"] for p in snap["plots"]] == [3, 2, 4], [p["stage"] for p in snap["plots"]]   # 70%, $520 milestones, full buffer
assert [t["stage"] for t in snap["trees"]] == [4, 2], [t["stage"] for t in snap["trees"]]
assert [f["ok"] for f in snap["fence"]] == [False, True]   # sorted by due date: Power (overdue) then Rent
assert snap["path_stones"] == 7 and snap["mailbox_flag"] and snap["weeds"] and not snap["windmill_spin"]
assert snap["tier"] == 3, snap["checks"]                    # house ✓, plots ✓ (2 of 3 grown), fence ✗, path ✓, mailbox ✗

# Scene renders at all sizes/frames, mini and full, day/evening/night
root = tk.Tk(); root.withdraw(); c = tk.Canvas(root)
n = 0
for hour in (9, 18, 23):
    sn = eng.snapshot(datetime(2026, 10, 7, hour, 0))
    for (w, h, mini) in ((760, 360, False), (220, 58, True), (1200, 360, False), (120, 40, True)):
        for frame in (0, 1, 50):
            bg.draw_homestead(c, sn, w, h, frame, mini=mini); assert len(c.find_all()) > 20; n += 1
empty = bg.HomesteadEngine(bg.AppState()).snapshot()
bg.draw_homestead(c, empty, 760, 360, 0); assert empty["tier"] == 0
print("scene renders:", n)
root.destroy()

# ── Live app: page, tiers, companions, thumbnails ────────────────────────────
app = bg.BudgetApp(); app.state.onboarding_complete = True; app.state.tutorial_complete = True
app.update(); time.sleep(0.4); app.update()
if getattr(app, "_setup_wizard_scrim", None): app._setup_wizard_scrim.destroy(); app._setup_wizard_scrim = None
# copy the rich state in
for attr in ("bills", "funds", "goals", "transactions", "incomes"):
    setattr(app.state, attr, getattr(st, attr))
app.state.game.level = 7; app.state.game.total_score = bg.level_threshold(7); app.state.game.streak_pays = 4   # score must back the level: challenge rewards recompute it
app.refresh_all_views(); app.update()
assert app.today_homestead_var.get() == "Tier 3 of 5", app.today_homestead_var.get()
assert app.state.game.homestead_tier == 3
assert "comp_hen" in app.state.game.character_items_owned and "comp_cat" in app.state.game.character_items_owned and "comp_fox" in app.state.game.character_items_owned
assert sorted(app.state.game.homestead_claimed_tiers) == [1, 2, 3]
assert "comp_owl" not in app.state.game.character_items_owned
# page shows and animates
app._show_page("homestead"); app.update()
assert app._homestead_anim_active
f0 = app._homestead_frame; time.sleep(0.4); app.update(); assert app._homestead_frame > f0
assert len(app._homestead_canvas.find_all()) > 50
texts = [str(w.cget("text")) for w in app._homestead_status_host.winfo_children()[0].winfo_children()]
app._show_page("today"); app.update()
assert not app._homestead_anim_active
# companion equips and draws on the shoulder
ok, msg = app.game_engine.equip_avatar_item("comp_fox"); assert ok, msg
app._show_page("character"); app.update()
assert app.state.game.character_equipped["companion"] == "comp_fox"
assert "companion" in app._char_equip_rows
# unlock text + cannot buy a homestead item
ok, msg = app.game_engine.buy_avatar_item("comp_owl"); assert not ok and "Tier 4" in msg, msg
assert "Tier 4" in app._char_cost_text(bg.AVATAR_ITEMS["comp_owl"])
# grid thumbnails are canvases now, and the rebuild is quick enough
app._char_filter_var.set("all")
t0 = time.time(); app._refresh_char_grid(); app.update(); dt = time.time() - t0
canvases = [w for w in app._char_grid_frame.winfo_children() for ww in w.winfo_children() for www in ww.winfo_children() if isinstance(www, tk.Canvas)]
print(f"grid rebuild {dt:.2f}s, thumbnails: {len(canvases)}")
assert len(canvases) == len(bg.AVATAR_ITEMS)
assert dt < 15.0   # ~2 s alone; generous so a parallel exe build can't flake it
# round trip
s2 = bg.AppState.from_dict(app.state.to_dict())
assert s2.game.homestead_tier == 3 and s2.game.homestead_claimed_tiers == [1, 2, 3]
app._stop_avatar_anim(); app.destroy()
print("SMOKE TEST 4 PASSED")
