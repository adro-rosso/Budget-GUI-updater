import os, sys, tempfile, time, json
from datetime import date, timedelta, datetime
tmp = tempfile.mkdtemp(prefix="budget_shots_"); os.chdir(tmp)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import tkinter as tk, budget_gui as bg
from PIL import ImageGrab
OUT = sys.argv[1]
app = bg.BudgetApp(); app.state.onboarding_complete = True; app.state.tutorial_complete = True; app.state.starting_position_set = True
app._celebrate = lambda *a, **k: None
app._show_tier_up_card = lambda *a, **k: None
app._show_toast = lambda *a, **k: None
app.geometry("1366x768+40+60"); app.update(); time.sleep(0.4); app.update()
if getattr(app, "_setup_wizard_scrim", None): app._setup_wizard_scrim.destroy(); app._setup_wizard_scrim = None
# realistic data
today = date.today(); st = app.state; g = st.game
st.bills += [bg.Bill("Rent", 800.0, today + timedelta(days=5), "fortnightly", "essential", "bill", 400.0),
             bg.Bill("Electricity", 210.0, today + timedelta(days=12), "quarterly", "essential", "bill", 90.0),
             bg.Bill("Phone", 45.0, today - timedelta(days=1), "monthly", "important", "bill", 10.0)]
st.funds += [bg.Fund("Holiday", 2000.0, today + timedelta(days=120), "important", 850.0, "auto", 0.0, "fund"),
             bg.Fund("Car service", 600.0, None, "important", 600.0, "buffer", 100.0, "fund")]
st.goals += [bg.Goal("Emergency fund", 5000.0, None, 1, 1900.0, "percent_surplus", 20.0)]
st.incomes += [bg.IncomeEntry(2400.0, today - timedelta(days=16), "Acme"), bg.IncomeEntry(2400.0, today - timedelta(days=2), "Acme")]
g.total_score = 720; g.level = app.game_engine.level_from_score(720); g.gems = 9; g.streak_pays = 4; g.best_streak = 6
g.pulse_streak = 5; g.pulse_best = 9; g.pulse_freezes = 1; g.pulse_last_date = (today - timedelta(days=1)).isoformat()
g.season_xp = 220; g.mill_last_collected = (datetime.now() - timedelta(hours=5)).isoformat(timespec="minutes")
for d, desc, out, cat in [(today - timedelta(days=1), "COLES 1234", 86.2, "Groceries"), (today - timedelta(days=2), "SHELL", 71.0, "Fuel"), (today - timedelta(days=3), "NETFLIX", 22.99, "Subscription"), (today - timedelta(days=4), "GUZMAN Y GOMEZ", 18.5, "Food")]:
    st.transactions.append(bg.TransactionRecord(d, desc, money_out=out, category=cat, fingerprint=desc, user_verified=True, needs_review=False, source_file="sept.pdf"))
st.bank_links = [{"name": "CommBank", "url": "https://www.my.commbank.com.au/netbank/Logon/Logon.aspx", "every_days": 14, "last_opened": ""}]; st.last_import_date = (today - timedelta(days=19)).isoformat()
app.state.ui_prefs["unlock_all"] = True
app.game_engine.pulse_mark_beat("spend"); app.game_engine.pulse_mark_beat("sort"); app.game_engine.open_vault(force_tier="gold")
app._startup_progression_migration(); app.refresh_all_views(); app.update()
def shot(name):
    app.update(); time.sleep(0.35); app.update()
    x, y = app.winfo_rootx(), app.winfo_rooty(); w, h = app.winfo_width(), app.winfo_height()
    ImageGrab.grab(bbox=(x - 8, y - 36, x + w + 8, y + h + 8)).save(os.path.join(OUT, name + ".png"))
for page in ["today", "income", "transactions", "score", "setup", "collection", "character", "review", "homestead", "settings"]:
    app._show_page(page); shot(page)
app._show_page("setup"); app._show_setup_sub("bills"); shot("setup_bills")
app._show_page("score"); app._show_score_section("arcade"); shot("score_arcade")
app._show_page("gerald"); shot("gerald")
app._show_page("today"); app.update(); app._show_pact_maker(); shot("overlay_pact")
[w.destroy() for w in app.winfo_children() if isinstance(w, tk.Frame) and str(w.cget("bg")) == bg.UI_HERO and w.winfo_manager() == "place"]
app._show_setup_wizard(); shot("overlay_wizard")
app.destroy()
print("done", OUT)
