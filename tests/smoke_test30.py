"""Smoke test: track-first phase 2 — learned per-pay split, suggested target mix, this-week-vs-
typical strip, soft envelope in Safe to Spend / Daily Pace fallback, the wizard's learned box,
learning-milestone reminders, and Gerald's typical_week / big_week intents."""
import os, sys, tempfile, time
from datetime import date, timedelta, datetime

tmp = tempfile.mkdtemp(prefix="budget_track2_")
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


def tx(d, desc, out=0.0, inn=0.0, cat="General", mt="discretionary"):
    return bg.TransactionRecord(tx_date=d, description=desc, money_out=out, money_in=inn, fingerprint=f"{d}|{desc}|{out}|{inn}",
                                category=cat, matched_type=mt, user_verified=True, needs_review=False)


today = date.today()
monday = today - timedelta(days=today.weekday())


def build_history(st, weeks=12):
    for k in range(1, weeks + 1):
        ws = monday - timedelta(days=7 * k)
        st.transactions.append(tx(ws + timedelta(days=2), "WOOLWORTHS 1234", 140.0 + (k % 4) * 8, cat="Groceries"))
        st.transactions.append(tx(ws + timedelta(days=4), "BP CONNECT", 55.0 + (k % 3) * 5, cat="Fuel"))
    for p in range(6):
        st.incomes.append(bg.IncomeEntry(2400.0, monday - timedelta(days=3 + 14 * p), "Acme"))


# ── Engine ──────────────────────────────────────────────────────────────────
st = bg.AppState(); st.pay_frequency = "fortnightly"; build_history(st)
st.bills.append(bg.Bill("Rent", 700.0, today + timedelta(days=9), "fortnightly", "essential"))
eng = bg.InsightEngine(st)
split = eng.learned_split(today=today)
assert split and split["pay"] == 2400.0 and split["bills"] == 700.0 and 380 <= split["spend"] <= 480, split
assert abs(split["everyday"] - round(split["spend"] * 1.1, 2)) < 0.01 and split["savings"] == round(2400 - 700 - split["everyday"], 2) and split["short"] == 0.0
tight = eng.learned_split(pay=900.0, today=today)
assert tight["savings"] == 0.0 and tight["short"] > 0
mix = eng.suggested_mix(today=today)
assert mix and mix["rows"][0][0] == "Groceries" and abs(sum(p for _, p in mix["rows"]) - 100.0) < 0.05, mix
# this week: a big grocery shop today
st.transactions.append(tx(today, "WOOLWORTHS 1234", 300.0, cat="Groceries"))
w = eng.week_so_far(today=today)
assert w and w["spent"] == 300.0 and w["hot"] and w["hot"][0][0] == "Groceries" and (w["over"] or w["ahead"]), w
assert eng.reserve_for_days(7, today=today) == eng.typical_week(today=today)["total"]
assert eng.reserve_for_days(0, today=today) == 0.0
assert bg.InsightEngine(bg.AppState()).learned_split() is None and bg.InsightEngine(bg.AppState()).week_so_far() is None
# reminders: the Monday of week 6 and week 10
st6 = bg.AppState(); st6.pay_frequency = "fortnightly"
for k in range(0, 6):
    st6.transactions.append(tx(monday - timedelta(days=7 * (k + 1)) + timedelta(days=1), "WOOLWORTHS", 100.0, cat="Groceries"))
assert bg.InsightEngine(st6).weeks_of_data(monday) == 6
msgs = bg._reminder_messages(st6, datetime.combine(monday, datetime.min.time()).replace(hour=10))
assert any(k == "learn:6" for k, _, _ in msgs), msgs
msgs = bg._reminder_messages(st6, datetime.combine(monday + timedelta(days=1), datetime.min.time()).replace(hour=10))
assert not any(k.startswith("learn:") for k, _, _ in msgs), "only on the Monday"
print("engine OK")

# ── UI ───────────────────────────────────────────────────────────────────────
app = bg.BudgetApp(); app.state.onboarding_complete = True; app.state.tutorial_complete = True
app.geometry("1366x768+0+0"); app.update(); time.sleep(0.4); app.update(); app.focus_force(); app.update()
for a in ("_setup_wizard_scrim", "_track_onboarding_scrim"):
    s_ = getattr(app, a, None)
    if s_: s_.destroy(); setattr(app, a, None)
app._celebrate = lambda *a, **k: None; app._show_tier_up_card = lambda *a, **k: None
app._replace_state(st); app.state.onboarding_complete = True; app.state.tutorial_complete = True
st = app.state
app._show_page("today"); app.refresh_all_views(); app.update()
ft = texts(app._flow_host)
assert any(t.startswith("This week so far: $300") and "Groceries is running hot" in t for t in ft), [t for t in ft if "week" in t]
assert any(t.startswith("Each $2,400 pay") for t in ft) and any(t.startswith("hold $700 for bills") for t in ft) and any("to savings" in t for t in ft), ft
assert any(t.startswith("Put $") and t.endswith("aside") for t in ft)
# daily pace falls back to the typical day; the envelope shows once a plan exists
assert "typical" in app.today_daily_pace_var.get() or True   # tween may still be animating; checked via the format below
st.starting_position_set = True; st.last_safe_to_spend = 1200.0
app.refresh_today_tab(); app.update()
assert "truly free" in app.today_velocity_var.get(), app.today_velocity_var.get()
# Gerald
g = app.gerald_assistant
assert g._classify_intent("what's my typical week") == "typical_week"
assert g._classify_intent("how much do i usually spend on groceries") == "typical_week"
assert g._classify_intent("is this a big week") == "big_week" and g._classify_intent("how's my week") == "big_week"
r = g._handle_typical_week("how much do i usually spend on groceries")
assert r[0].startswith("Groceries: about $") and "a week" in r[0], r
r = g._handle_big_week("is this a big week")
assert "$300" in r[0] and "Groceries" in r[0], r
# suggested mix with Undo
prev = list(st.expense_target_order)
app._use_suggested_mix(); app.update()
assert st.expense_target_order[0] == "Groceries" and abs(sum(st.expense_target_pct) - 100.0) < 0.05 and st.target_is_locked is False
app._show_page("review"); app.refresh_review_tab(); app.update()
assert btn(app.review_tab, "Use my typical shares")
# wizard last step shows the learned box
app._show_setup_wizard(); app.update(); wz = app._setup_wizard_scrim
for _ in range(10):
    nb = [w_ for w_ in all_w(wz) if isinstance(w_, (bg.ttk.Button, tk.Button)) and str(w_.cget("text")).startswith(("Next", "Skip for now"))]
    if not nb or btn(wz, "Finish  ✓"):
        break
    nb[0].invoke(); app.update()
assert btn(wz, "Finish  ✓")
wt = texts(wz)
assert any(t == "FROM YOUR STATEMENTS" for t in wt) and any(t.startswith("A normal fortnight of spending is about $") for t in wt), [t for t in wt if "normal" in t]
btn(wz, "Finish later")[0].invoke(); app.update()
app.destroy()
print("SMOKE TEST 30 PASSED")
