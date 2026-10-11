"""Smoke test: history mode — a first statement reaching back a month records past pays
without allocating, confirms only pays on/after the cutoff, never auto-pays bills from
history, offers 'Set up from your statement' (rhythm / bills / mix), undo removes the
history pays, Analysis shows a partial-month label, existing profiles keep their cutoff."""
import os, sys, tempfile, time, json
from datetime import date, timedelta, datetime
from pathlib import Path

tmp = tempfile.mkdtemp(prefix="budget_hist_")
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


def tx(d, desc, out=0.0, inn=0.0, **kw):
    kw.setdefault("user_verified", True); kw.setdefault("needs_review", False)
    return bg.TransactionRecord(tx_date=d, description=desc, money_out=out, money_in=inn, fingerprint=f"{d}|{desc}|{out}|{inn}", **kw)


today = date.today()
app = bg.BudgetApp(); app.state.onboarding_complete = True; app.state.tutorial_complete = True
app.state.starting_position_set = True; app.state.starting_position_date = today.isoformat()
app.geometry("1366x768+0+0"); app.update(); time.sleep(0.4); app.update()
if getattr(app, "_setup_wizard_scrim", None): app._setup_wizard_scrim.destroy(); app._setup_wizard_scrim = None
app._startup_progression_migration(); app.refresh_today_tab(); app.update()
app._celebrate = lambda *a, **k: None
st = app.state; g = st.game
assert app._history_cutoff() == today

# A fund set up in the wizard with today's balance; a bill due soon
st.funds.append(bg.Fund("Holiday", 2000.0, today + timedelta(days=120), "important", 500.0, "auto", 0.0, "fund"))
st.bills.append(bg.Bill("Rent", 800.0, today + timedelta(days=2), "fortnightly", "essential", "bill", 800.0))
rent_due = st.bills[0].due_date

# First statement: last month + this month up to yesterday, plus a pay today
d = lambda n: today - timedelta(days=n)
batch = [tx(d(38), "ACME PTY LTD PAY", inn=2400.0, matched_type="income", category="Income"),
         tx(d(24), "ACME PTY LTD PAY", inn=2400.0, matched_type="income", category="Income"),
         tx(d(10), "ACME PTY LTD PAY", inn=2400.0, matched_type="income", category="Income"),
         tx(d(37), "RENT REAL ESTATE", 800.0, matched_type="linked_bill", matched_target="Rent", category="Bill"),
         tx(d(23), "RENT REAL ESTATE", 800.0, matched_type="linked_bill", matched_target="Rent", category="Bill"),
         tx(d(9), "RENT REAL ESTATE", 800.0, matched_type="linked_bill", matched_target="Rent", category="Bill"),
         tx(d(35), "NETFLIX.COM", 22.99, matched_type="discretionary", category="Subscription"),
         tx(d(5), "NETFLIX.COM", 22.99, matched_type="discretionary", category="Subscription"),
         tx(d(33), "COLES 1234", 120.0, matched_type="discretionary", category="Groceries"),
         tx(d(31), "SHELL COLES EXPRESS", 70.0, matched_type="discretionary", category="Fuel"),
         tx(d(34), "GUZMAN Y GOMEZ", 18.5, matched_type="discretionary", category="Food"),
         tx(d(30), "COLES 1234", 95.0, matched_type="discretionary", category="Groceries"),
         tx(today, "ACME PTY LTD PAY", inn=2400.0, matched_type="income", category="Income")]
app.latest_import = list(batch)
app._show_page("transactions"); app.update()
score0, holiday0, gems0 = g.total_score, st.funds[0].current_saved, g.gems
app.commit_imported_transactions(); app.update()
# history pays recorded, nothing allocated; only today's pay is up for confirmation
assert len(st.incomes) == 3 and all(i.received_on < today for i in st.incomes), [(i.received_on, i.amount) for i in st.incomes]
assert st.funds[0].current_saved == holiday0 and g.streak_pays == 0 and g.total_pays_processed == 0
assert len(st.pending_income_confirmations) == 1 and st.pending_income_confirmations[0] == batch[-1].fingerprint
assert st.bills[0].due_date == rent_due and st.bills[0].current_saved == 800.0, "history must not pay the bill"
assert st.income_baseline > 0
assert app._history_cutoff() == today   # last logged pay is before today
# the offer appears
time.sleep(0.9); app.update()
sc = scrims(app)[-1]
tt = texts(sc)
assert any("SET UP FROM YOUR STATEMENT" == t for t in tt), tt[:5]
w = app._statement_setup_widgets
assert w["rhythm"]["count"] == 3 and w["rhythm"]["freq"] == "fortnightly" and w["rhythm"]["typical"] == 2400.0
names = [b["name"].lower() for b in w["bills"]]
assert any("netflix" in n for n in names) and not any("rent" == n for n in names), names   # Rent exists already; Netflix is new
assert w["mix"] and w["mix"]["rows"] and abs(sum(p for _, p in w["mix"]["rows"]) - 100.0) < 0.2, w["mix"]
st.pay_frequency = "weekly"
btn(sc, "Use this rhythm  ✓")[0].invoke(); app.update()
assert st.pay_frequency == "fortnightly" and st.income_baseline == 2400.0
nb = len(st.bills)
btn(sc, "Add the ticked ones as bills  ✓")[0].invoke(); app.update()
assert len(st.bills) > nb and any("netflix" in b.name.lower() for b in st.bills)
assert any("netflix" in r.keyword for r in st.advanced_match_rules), [r.keyword for r in st.advanced_match_rules]
mix_btn = [b for b in all_w(sc) if isinstance(b, bg.ttk.Button) and str(b.cget("text")).startswith("Start my target from")]
mix_btn[0].invoke(); app.update()
assert st.expense_target_order and abs(sum(st.expense_target_pct) - 100.0) < 0.2 and not st.target_is_locked
btn(sc, "Done")[0].invoke(); app.update()
assert st.ui_prefs["statement_setup.done"] and not scrims(app)

# Confirming today's pay still allocates (it is new)
st.ui_prefs["pay.review_allocation"] = False
app._confirm_income_log(batch[-1].fingerprint); app.update()
for w_ in list(app.winfo_children()):
    if isinstance(w_, (tk.Toplevel,)): w_.destroy()
    elif isinstance(w_, tk.Frame) and str(w_.cget("bg")) == bg.UI_HERO and w_.winfo_manager() == "place": w_.destroy()
app.update()
assert len(st.incomes) == 4 and g.total_pays_processed == 1 and not st.pending_income_confirmations
assert app._history_cutoff() == today

# Undo the import removes the three history pays and the batch
st_before = len(st.transactions)
app._undo_last_commit(); app.update()
assert len(st.transactions) == 0 and sum(1 for i in st.incomes if i.received_on < today) == 0, [(i.received_on) for i in st.incomes]
app.latest_import = []

# Analysis: partial-month label on the current month (unless today is the last day)
app._show_page("review"); app.update()
import calendar
lbl = app._review_month_label.cget("text")
if today.day < calendar.monthrange(today.year, today.month)[1]:
    assert f"day {today.day}/" in lbl, lbl
app.save_state()
s2 = bg.AppState.from_dict(json.loads(bg.DATA_FILE.read_text(encoding="utf-8")))
assert s2.starting_position_date == today.isoformat() and s2.first_launch_date
app.destroy()

# ── Existing profile: cutoff follows the last logged pay, not the update date ──
tmp2 = tempfile.mkdtemp(prefix="budget_hist2_"); os.chdir(tmp2); bg.DATA_FILE = Path("budget_data.json")
s3 = bg.AppState(); s3.onboarding_complete = True; s3.tutorial_complete = True; s3.starting_position_set = True
s3.incomes.append(bg.IncomeEntry(2000.0, today - timedelta(days=20), "Pay"))
Path("budget_data.json").write_text(json.dumps(s3.to_dict()), encoding="utf-8")
app2 = bg.BudgetApp(); app2.update(); time.sleep(0.3); app2.update()
assert app2._history_cutoff() == today - timedelta(days=20)
# a pay 5 days ago is after the cutoff → it is a real new pay to confirm
app2.latest_import = [tx(today - timedelta(days=5), "EMPLOYER PAY", inn=2000.0, matched_type="income", category="Income")]
app2.commit_imported_transactions(); app2.update()
assert len(app2.state.pending_income_confirmations) == 1 and len(app2.state.incomes) == 1
app2.destroy()
print("SMOKE TEST 15 PASSED")
