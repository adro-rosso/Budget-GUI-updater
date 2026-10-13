"""Smoke test: track-first follow-ups — confirming a bill is not a 'contribute' challenge, merchant
labels are cleaned ('Netflix', not 'Netflix Com'), track mode has no Setup badge and a tracking-
shaped completeness list, and a pay with nothing in the plan offers the learned split."""
import os, sys, tempfile, time
from datetime import date, timedelta

tmp = tempfile.mkdtemp(prefix="budget_track3_")
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


def btn(root, text, cls=None):
    cls = cls or (bg.ttk.Button, tk.Button)
    return [w for w in all_w(root) if isinstance(w, cls) and str(w.cget("text")) == text]


def tx(d, desc, out=0.0, inn=0.0, cat="General", mt="discretionary"):
    return bg.TransactionRecord(tx_date=d, description=desc, money_out=out, money_in=inn, fingerprint=f"{d}|{desc}|{out}|{inn}",
                                category=cat, matched_type=mt, user_verified=True, needs_review=False)


today = date.today()
monday = today - timedelta(days=today.weekday())
assert bg.clean_merchant_label("Netflix Com") == "Netflix" and bg.clean_merchant_label("Optus Mobile Pty") == "Optus Mobile" and bg.clean_merchant_label("Bp Connect") == "Bp Connect"

app = bg.BudgetApp(); app.state.onboarding_complete = True; app.state.tutorial_complete = True
app.geometry("1366x768+0+0"); app.update(); time.sleep(0.4); app.update(); app.focus_force(); app.update()
app._celebrate = lambda *a, **k: None; app._show_tier_up_card = lambda *a, **k: None
app._show_pay_day_ritual = lambda *a, **k: None
st = app.state; st.setup_mode = "track"; st.pay_frequency = "fortnightly"
for k in range(1, 13):
    ws = monday - timedelta(days=7 * k)
    st.transactions.append(tx(ws + timedelta(days=2), "WOOLWORTHS 1234", 140.0 + (k % 4) * 8, cat="Groceries"))
for m in range(3):
    st.transactions.append(tx(monday - timedelta(days=10 + 30 * m), "NETFLIX.COM", 20.99, cat="Subscription"))
for p in range(4):
    st.incomes.append(bg.IncomeEntry(2400.0, monday - timedelta(days=3 + 14 * p), "Acme"))
app._show_page("today"); app.refresh_all_views(); app.update()
# no Setup nag in track mode; tracking-shaped completeness
assert "setup" not in app._nav_badge_counts(), app._nav_badge_counts()
labels = [l for l, _ in app._setup_completeness_steps()]
assert "First statement in" in labels and "Starting position set" not in labels, labels
assert app.today_health_summary_var.get().startswith("Tracking"), app.today_health_summary_var.get()
# the suggestion is named cleanly and confirming it completes no 'contribute' challenge
cands = bg.InsightEngine(st).recurring_candidates()
assert cands and cands[0]["name"] == "Netflix", cands
g = st.game
g.daily_challenges = [{"id": "contribute", "description": "Add money to a fund or goal", "trigger": "contribute", "reward_type": "gold", "reward_amount": 20, "completed": False}]
g.daily_challenges_date = today.isoformat()
gold0 = g.total_score
btn(app._recurring_host, "Yes, it's a bill  ✓")[0].invoke(); app.update()
assert any(b.name == "Netflix" for b in st.bills)
assert g.total_score == gold0 and not g.daily_challenges[0].get("completed"), (g.total_score, gold0, g.daily_challenges)
# a pay with nothing in the plan to absorb it → learned-split offer with 'Put $ aside'
app._toast_stack.clear()
app._commit_pay(2400.0, today, "Acme"); app.update()
time.sleep(2.0); app.update()
labels = [str(w.cget("text")) for t_ in app._toast_stack if t_.winfo_exists() for w in all_w(t_) if isinstance(w, tk.Label)]
assert any(l.startswith("From what you actually do: keep $") for l in labels), labels
put = [w for t_ in app._toast_stack if t_.winfo_exists() for w in all_w(t_) if isinstance(w, tk.Label) and str(w.cget("text")).startswith("Put $")]
assert put
put[-1].event_generate("<Button-1>"); app.update(); app.update()
pot = next((g_ for g_ in st.goals if g_.name == "Savings"), None)
assert pot is not None and pot.current_saved > 0, [g_.name for g_ in st.goals]
# once a goal in the plan absorbs part of the pay there is no offer
pot.value = 300.0   # fixed $300 per pay into Savings
app._toast_stack.clear()
app._commit_pay(2400.0, today, "Acme"); app.update(); time.sleep(2.0); app.update()
assert app.last_allocation["goal_total"] > 0
labels = [str(w.cget("text")) for t_ in app._toast_stack if t_.winfo_exists() for w in all_w(t_) if isinstance(w, tk.Label)]
assert not any(l.startswith("From what you actually do") for l in labels), labels
app.destroy()
print("SMOKE TEST 31 PASSED")
