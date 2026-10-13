"""Smoke test: the wizard's transfer-plan step and the Accounts summary list all four
accounts even when a planned balance is zero (empty ones muted with a reason, no Copy)."""
import os, sys, tempfile, time
from datetime import date, timedelta

tmp = tempfile.mkdtemp(prefix="budget_acct_")
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
app = bg.BudgetApp(); app.state.onboarding_complete = True; app.state.tutorial_complete = True
app.geometry("1366x768+0+0"); app.update(); time.sleep(0.4); app.update(); app.focus_force(); app.update()
if getattr(app, "_setup_wizard_scrim", None): app._setup_wizard_scrim.destroy(); app._setup_wizard_scrim = None
app._celebrate = lambda *a, **k: None
st = app.state
# the reported profile: no bills, two funds, one goal, nothing entered on the money step
st.funds.append(bg.Fund("Holiday", 2000.0, today + timedelta(days=120), "important", 0.0, "auto", 0.0, "fund"))
st.goals.append(bg.Goal("Emergency", 5000.0, None, 1, 0.0, "percent_surplus", 20.0))
app._show_setup_wizard(); app.update()
sc = app._setup_wizard_scrim
for _ in range(10):
    nb = [w for w in all_w(sc) if isinstance(w, (bg.ttk.Button, tk.Button)) and str(w.cget("text")).startswith(("Next", "Skip for now"))]
    if not nb or btn(sc, "Finish  ✓"):
        break
    nb[0].invoke(); app.update()
assert btn(sc, "Finish  ✓"), "should reach the transfer-plan step"
tt = texts(sc)
for name in ("Everyday Account", "Bills Account", "Savings Account", "Investment Account"):
    assert any(t == f"in  {name}" for t in tt), (name, [t for t in tt if t.startswith("in  ")])
assert sum(1 for t in tt if t.startswith("nothing to hold yet")) == 3, [t for t in tt if "hold" in t]
assert len(btn(sc, "Copy")) == 1, "only the funded account gets a Copy button"
btn(sc, "Finish later")[0].invoke(); app.update()
# Accounts-tab summary names every account too
st.account_balances = {"spending": 120.0}; st.starting_position_set = True
summ = app._starting_position_summary()
assert "Bills Account" in summ and "Savings Account" in summ, summ
app.destroy()
print("SMOKE TEST 25 PASSED")
