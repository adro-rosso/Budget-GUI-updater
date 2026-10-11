"""Smoke test: Phase C part 2 — weekly race standings and settlement (promotion, rewards,
relegation), the Score tab panel + Next Up row, and share cards for a month and the year
(canvas poster, HTML export, PNG export with ImageGrab stubbed)."""
import os, sys, tempfile, time, json
from datetime import date, timedelta, datetime
from pathlib import Path

tmp = tempfile.mkdtemp(prefix="budget_c2_")
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
week = today.strftime("%G-W%V")
# ── Engine: standings + settlement ───────────────────────────────────────────
st = bg.AppState(); eng = bg.BudgetGameEngine(st); g = st.game
assert eng.ensure_rival_week() is None and g.rival_week == week and g.rival_seed
rows = eng.rival_standings()
assert len(rows) == 5 and [r["place"] for r in rows] == [1, 2, 3, 4, 5] and sum(1 for r in rows if r["you"]) == 1
assert eng.rival_standings() == rows, "standings are deterministic within a week"
# a huge week wins: simulate last week with lots of XP
g.rival_week = "2020-W01"; g.weekly_xp_week = "2020-W01"; g.weekly_xp = 5000
res = eng.ensure_rival_week()
assert res and res["place"] == 1 and res["reward"] == "+4 Gems" and "promoted to silver" in res["moved"] and g.rival_league == "silver" and g.gems == 4
assert g.weekly_xp == 0 and g.weekly_xp_week == week and g.rival_prev_user_xp == 5000 and g.rival_last["place"] == 1
assert eng.ensure_rival_week() is None
# a dead week relegates
g.rival_week = "2020-W02"; g.weekly_xp_week = "2020-W02"; g.weekly_xp = 0
res = eng.ensure_rival_week(); assert res["place"] == 5 and "relegated to bronze" in res["moved"] and g.rival_league == "bronze"
# baseline follows the user's previous week, bounded
g.rival_prev_user_xp = 0; assert eng._rival_baseline() == 120.0
g.rival_prev_user_xp = 10 ** 6; assert eng._rival_baseline() == 900.0
# round trip
s2 = bg.AppState.from_dict(json.loads(json.dumps(st.to_dict()))); assert s2.game.rival_league == "bronze" and s2.game.rival_last["place"] == 5
print("engine OK")

# ── UI ───────────────────────────────────────────────────────────────────────
app = bg.BudgetApp(); app.state.onboarding_complete = True; app.state.tutorial_complete = True; app.state.starting_position_set = True
app.geometry("1366x768+0+0"); app.update(); time.sleep(0.4); app.update()
if getattr(app, "_setup_wizard_scrim", None): app._setup_wizard_scrim.destroy(); app._setup_wizard_scrim = None
app._startup_progression_migration(); app.refresh_today_tab(); app.update()
app._celebrate = lambda *a, **k: None
st = app.state; g = st.game; eng = app.game_engine
g.weekly_xp = 30; g.weekly_xp_week = week
app._show_page("score"); app.refresh_season_pass(); app.update()
tt = texts(app._rivals_host)
assert any("LEAGUE" in t for t in tt) and any("★ You" == t for t in tt) and any("Hazel Thorne" in t for t in tt), tt[:8]
assert "league" in app._rivals_summary_var.get()
assert any(t[0].startswith("Weekly race") for t in app._next_up_items()) or next(r for r in eng.rival_standings() if r["you"])["place"] == 1

# share card: month with data
for n, desc, out, cat in [(3, "COLES", 120.0, "Groceries"), (5, "SHELL", 70.0, "Fuel"), (9, "NETFLIX", 22.99, "Subscription")]:
    st.transactions.append(bg.TransactionRecord(today - timedelta(days=n), desc, money_out=out, category=cat, fingerprint=desc, user_verified=True, needs_review=False))
st.incomes.append(bg.IncomeEntry(2400.0, today - timedelta(days=4), "Acme"))
d = eng.share_card_data(today.year, today.month, app)
assert d["income"] == 2400.0 and abs(d["spent"] - 212.99) < 0.01 and d["top"][0][0] == "Groceries" and d["biggest"][0].lower().startswith("coles")
dy = eng.share_card_data(today.year, None, app)
assert dy["label"].endswith("so far") and dy["spent"] >= d["spent"]
app._show_share_card(today.year, today.month); app.update()
sc = scrims(app)[-1]
assert btn(sc, "Save as image") and btn(sc, "Save as web page") and len(app._share_card_canvas.find_all()) > 30
html = app._share_card_html(d)
assert "<!doctype html>" in html and "Groceries" in html and "$2,400" in html
import tkinter.filedialog as fd
out_html = str(Path(tmp) / "card.html"); fd.asksaveasfilename = lambda *a, **k: out_html
btn(sc, "Save as web page")[0].invoke(); app.update()
assert Path(out_html).exists() and "Budget Planner" in Path(out_html).read_text(encoding="utf-8")
# PNG with ImageGrab stubbed
import types, PIL
class _Img:
    def convert(self, *_a): return self
    def resize(self, *_a): return self
    def getdata(self): return [120] * 256
    def save(self, path): Path(path).write_bytes(b"PNG")
fake = types.SimpleNamespace(grab=lambda bbox=None: _Img()); PIL.ImageGrab = fake; sys.modules["PIL.ImageGrab"] = fake
out_png = str(Path(tmp) / "card.png"); fd.asksaveasfilename = lambda *a, **k: out_png
btn(sc, "Save as image")[0].invoke(); app.update()
assert Path(out_png).exists()
btn(sc, "Close")[0].invoke(); app.update()
# year card from Settings
app._show_page("settings"); app.update()
btn(app.settings_tab, "Your year card ↗")[0].invoke(); app.update()
assert scrims(app) and any("so far" in t for t in [app._share_card_data_last["label"]])
btn(scrims(app)[-1], "Close")[0].invoke(); app.update()
app.destroy()
print("SMOKE TEST 20 PASSED")
