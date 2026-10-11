"""Smoke test: Phase C part 1 — monthly event banner, seasonal card sets (in-season only,
+8 Gems on completion), double-XP pay weekend, daily Perk Shop deal, while-you-were-away
recap, and Gerald's letters (unlock per Pulse day, choice letters grant a cosmetic)."""
import os, sys, tempfile, time, json
from datetime import date, timedelta, datetime
from pathlib import Path

tmp = tempfile.mkdtemp(prefix="budget_c1_")
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
season = bg.season_for_month(today.month)
# ── Engine ───────────────────────────────────────────────────────────────────
st = bg.AppState(); eng = bg.BudgetGameEngine(st); g = st.game
ev = eng.current_event()
assert ev["name"] == bg.MONTHLY_EVENTS[today.month][0] and ev["season"] == season and ev["set_total"] == 4 and ev["set_have"] == 0
# seasonal cards: only this season's are drawable; the other three seasons never appear
g.total_score = 10 ** 6
for _ in range(80):
    eng.open_pack("standard")
off_season = {c[0] for s, (_n, cards) in bg.EVENT_CARD_SETS.items() if s != season for c in cards}
assert not (off_season & set(g.cards_owned)), "off-season cards must not drop"
# completing the in-season set pays 8 Gems once
g.cards_owned = [c[0] for c in bg.EVENT_CARD_SETS[season][1]]
g.event_sets_claimed = []; g.achievements = [a for a in g.achievements if "Collector" not in a]   # the packs above may have claimed it already
gems0 = g.gems
assert eng.check_event_set() == bg.EVENT_CARD_SETS[season][0] and g.gems == gems0 + 8 and season in g.event_sets_claimed
assert eng.check_event_set() == "" and any("Collector" in a for a in g.achievements)
# double XP only on a pay-week weekend
st.pay_frequency = "fortnightly"
sat = today + timedelta(days=(5 - today.weekday()) % 7)
st.incomes.append(bg.IncomeEntry(2000.0, sat - timedelta(days=16), "Pay"))      # expected pay lands Thu that week (16 days before Sat + 14)
assert eng.xp_window_active(sat) and eng.xp_window_active(sat + timedelta(days=1)) and not eng.xp_window_active(sat - timedelta(days=1))
st.incomes[0] = bg.IncomeEntry(2000.0, sat - timedelta(days=3), "Pay")            # next pay is 11 days away → no window
assert not eng.xp_window_active(sat)
# daily deal: 30% off one perk, stable within a day, applied by buy_perk
pid, disc = eng.featured_perk(today)
perk = next(p_ for p_ in bg.PERK_SHOP_ITEMS if p_[0] == pid)
assert disc == max(1, round(perk[3] * 0.7)) and eng.featured_perk(today) == (pid, disc) and eng.featured_perk(today + timedelta(days=1))[0] != pid
g.gems = disc; ok, msg = eng.buy_perk(pid); assert ok and g.gems == 0, msg
# weekly xp tracking via add_season_xp
w0 = g.weekly_xp; eng.add_season_xp(20); assert g.weekly_xp >= w0 + 20 and g.weekly_xp_week == today.strftime("%G-W%V")
# letters
assert not eng.letter_waiting() and eng.read_next_letter() is None
g.pulse_days_total = 2
assert eng.letters_available() == 2 and eng.letter_waiting()
l1 = eng.read_next_letter(); assert l1["index"] == 0 and l1["title"] == "Welcome to the valley" and g.letters_read == 1
l2 = eng.read_next_letter(); assert l2["index"] == 1 and not eng.letter_waiting() and eng.read_next_letter() is None
g.pulse_days_total = 12
for _ in range(10):
    l = eng.read_next_letter()
assert l["index"] == 11 and l.get("choice")
assert not eng.choose_letter_gift(11, "acc_headband")[0]
ok, msg = eng.choose_letter_gift(11, "acc_glasses"); assert ok and "acc_glasses" in g.character_items_owned and g.letter_choices["11"] == "acc_glasses"
assert not eng.choose_letter_gift(11, "acc_scarf")[0]
g.pulse_days_total = 500; assert eng.letters_available() == len(bg.GERALD_LETTERS) == 40
s2 = bg.AppState.from_dict(json.loads(json.dumps(st.to_dict()))); assert s2.game.letters_read == 12 and s2.game.letter_choices == {"11": "acc_glasses"} and s2.game.event_sets_claimed == [season]
print("engine OK")

# ── UI ───────────────────────────────────────────────────────────────────────
app = bg.BudgetApp(); app.state.onboarding_complete = True; app.state.tutorial_complete = True; app.state.starting_position_set = True
app.geometry("1366x768+0+0"); app.update(); time.sleep(0.4); app.update()
if getattr(app, "_setup_wizard_scrim", None): app._setup_wizard_scrim.destroy(); app._setup_wizard_scrim = None
app._startup_progression_migration(); app.refresh_today_tab(); app.update()
app._celebrate = lambda *a, **k: None
app._show_tier_up_card = lambda *a, **k: None   # the Rent bill below earns tier 1; its card would land mid-test
st = app.state; g = st.game; eng = app.game_engine
# event banner on Today
tt = texts(app._event_host)
assert any("THIS MONTH" == t for t in tt) and any(bg.MONTHLY_EVENTS[today.month][0] == t for t in tt) and any("Today's deal" in t for t in tt), tt
# welcome back: needs ≥6h away and something to say
st.ui_prefs["last_close"] = (datetime.now() - timedelta(hours=3)).isoformat(timespec="minutes")
app._maybe_welcome_back(); app.update(); assert not scrims(app)
st.ui_prefs["last_close"] = (datetime.now() - timedelta(hours=30)).isoformat(timespec="minutes")
g.mill_last_collected = (datetime.now() - timedelta(hours=9)).isoformat(timespec="minutes")
st.bills.append(bg.Bill("Rent", 800.0, today + timedelta(days=1), "monthly", "essential", "bill", 100.0))
g.pulse_days_total = 3
app._maybe_welcome_back(); app.update()
sc = scrims(app)[-1]
tt = texts(sc)
assert any("WHILE YOU WERE AWAY" == t for t in tt) and any("Gone 1 day" in t for t in tt), tt[:4]
kinds = [icon for icon, _t, _p in app._welcome_back_lines_shown]
assert "🌾" in kinds and "📅" in kinds and "✉" in kinds and "🔥" in kinds, kinds
btn(sc, "Start the Pulse  →")[0].invoke(); app.update()
assert not scrims(app) and app.current_page_key == "today"
# letters on the Homestead page
app._show_page("homestead"); app.update()
assert btn(app._letters_host, "Open the letter") and "a letter is waiting" in app._letters_summary.get()
assert any(t[0] == "Letter waiting ✉" for t in app._next_up_items())
btn(app._letters_host, "Open the letter")[0].invoke(); app.update()
sc = scrims(app)[-1]
assert any("LETTER 1 OF 40" == t for t in texts(sc)) and any("Welcome to the valley" == t for t in texts(sc))
btn(sc, "Keep it")[0].invoke(); app.update()
assert g.letters_read == 1 and not scrims(app)
# choice letter via UI
g.letters_read = 11; g.pulse_days_total = 12; app._render_letters_card(); app.update()
btn(app._letters_host, "Open the letter")[0].invoke(); app.update(); sc = scrims(app)[-1]
assert btn(sc, "The wrap scarf")
btn(sc, "The wrap scarf")[0].invoke(); app.update()
assert "acc_scarf" in g.character_items_owned and not scrims(app), ("acc_scarf" in g.character_items_owned, g.letter_choices, [texts(s_)[:3] for s_ in scrims(app)])
# perk shop shows the deal
app._open_perk_shop(); app.update()
tops = [w for w in app.winfo_children() if isinstance(w, tk.Toplevel)]
assert tops and any("today's deal" in t for t in texts(tops[-1])), [t for t in texts(tops[-1]) if "Cost" in t]
for w in tops: w.destroy()
app.destroy()
print("SMOKE TEST 19 PASSED")
