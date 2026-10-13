"""Smoke test: the wizard's 'money now' step asks for a balance per account (all four, named
from the accounts step), 'Suggest a split' spreads the Bills balance across bills in due order
and the Savings balance across buffers/dated funds/goals, the transfer step lists the moves
between accounts, and Finish writes the planned balances."""
import os, sys, tempfile, time
from datetime import date, timedelta

tmp = tempfile.mkdtemp(prefix="budget_wizacct_")
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


def entries(root):
    return [w for w in all_w(root) if isinstance(w, bg.ttk.Entry) and not isinstance(w, bg.ttk.Combobox)]


today = date.today()
app = bg.BudgetApp(); app.state.onboarding_complete = True; app.state.tutorial_complete = True
app.geometry("1366x768+0+0"); app.update(); time.sleep(0.4); app.update(); app.focus_force(); app.update()
if getattr(app, "_setup_wizard_scrim", None): app._setup_wizard_scrim.destroy(); app._setup_wizard_scrim = None
app._celebrate = lambda *a, **k: None
st = app.state
st.transfer_accounts = {"spending": {"name": "Up Everyday"}, "bills": {"name": "Up Bills"}, "savings": {"name": "Up Saver"}, "invest": {"name": "Vanguard"}}
st.bills.append(bg.Bill("Rent", 800.0, today + timedelta(days=5), "monthly", "essential"))
st.bills.append(bg.Bill("Car rego", 900.0, today + timedelta(days=200), "yearly", "essential"))   # far away: still gets the Bills balance
st.funds.append(bg.Fund("Car service", 600.0, None, "important", 0.0, "buffer", 0.0, "fund"))
st.funds.append(bg.Fund("Holiday", 2000.0, today + timedelta(days=150), "important", 0.0, "auto", 0.0, "fund"))
st.goals.append(bg.Goal("Emergency", 5000.0, None, 1, 0.0, "percent_surplus", 20.0))
app._show_setup_wizard(); app.update()
sc = app._setup_wizard_scrim
for _ in range(5):
    nb = [w for w in all_w(sc) if isinstance(w, (bg.ttk.Button, tk.Button)) and str(w.cget("text")).startswith(("Next", "Skip for now"))]
    nb[0].invoke(); app.update()
tt = texts(sc)
assert any("What's in each account right now" in t for t in tt), tt[:10]
for name in ("Up Everyday", "Up Bills", "Up Saver", "Vanguard"):
    assert name in tt, (name, [t for t in tt if t.startswith("Up") or t == "Vanguard"])
e = entries(sc)
assert len(e) == 4 + 2 + 2 + 1 + 1, len(e)      # four accounts + bills + funds + goal + invest
for ent, v in zip(e[:4], ("1500", "1000", "3100", "250")):
    ent.delete(0, tk.END); ent.insert(0, v)
app.update()
assert any("Total $5,850.00" in t and "$5,850.00 left as spending money in Up Everyday" in t for t in texts(sc)), [t for t in texts(sc) if "Total" in t]
btn(sc, "Suggest a split")[0].invoke(); app.update()
vals = [x.get() for x in entries(sc)]
# bills balance 1000 → Rent 800 then 200 toward rego; savings 3100 → buffer 600, Holiday 2000, Emergency 500; invest 250
assert vals[4:] == ["800.00", "200.00", "600.00", "2000.00", "500.00", "250.00"], vals
assert any("$1,500.00 left as spending money" in t for t in texts(sc)), [t for t in texts(sc) if "left" in t]
# a bad balance blocks Next; a negative one too
e = entries(sc); e[1].delete(0, tk.END); e[1].insert(0, "abc"); app.update()
assert any("isn't a number" in t for t in texts(sc))
btn(sc, "Next  →")[0].invoke(); app.update(); assert any("What's in each account" in t for t in texts(sc))
e[1].delete(0, tk.END); e[1].insert(0, "1000"); app.update()
# change the plan so money has to move: put only 600 toward bills (rego gets nothing), everything else as suggested
e = entries(sc); e[5].delete(0, tk.END); app.update()
btn(sc, "Next  →")[0].invoke(); app.update()
tt = texts(sc)
assert any("Your set-up transfers" in t for t in tt)
# bills planned 800 vs 1000 held → take out 200; everyday planned 1700 vs 1500 → add 200
assert any("has $1,000.00 today → take out $200.00" in t for t in tt), [t for t in tt if "today" in t]
assert any("has $1,500.00 today → add $200.00" in t for t in tt), [t for t in tt if "today" in t]
assert any(t == "→ Move $200.00 from Up Bills to Up Everyday" for t in tt), [t for t in tt if "Move" in t]
assert any("Safe to Spend starts at $1,700.00" in t for t in tt)
btn(sc, "Finish  ✓")[0].invoke(); app.update()
assert app._setup_wizard_scrim is None and st.starting_position_set
assert st.account_balances == {"spending": 1700.0, "bills": 800.0, "savings": 3100.0, "invest": 250.0}, st.account_balances
assert st.bills[0].current_saved == 800.0 and st.bills[1].current_saved == 0.0
assert st.funds[0].current_saved == 600.0 and st.funds[1].current_saved == 2000.0 and st.goals[0].current_saved == 500.0
# reopen: balances come back per account and nothing needs moving
app._show_setup_wizard(); app.update(); sc = app._setup_wizard_scrim
for _ in range(5):
    nb = [w for w in all_w(sc) if isinstance(w, (bg.ttk.Button, tk.Button)) and str(w.cget("text")).startswith(("Next", "Skip for now"))]
    nb[0].invoke(); app.update()
assert [x.get() for x in entries(sc)[:4]] == ["1700.00", "800.00", "3100.00", "250.00"], [x.get() for x in entries(sc)]
btn(sc, "Next  →")[0].invoke(); app.update()
assert any("nothing to move" in t for t in texts(sc)), [t for t in texts(sc) if "move" in t.lower()]
assert not any(t.startswith("→ Move") for t in texts(sc))
btn(sc, "Finish later")[0].invoke(); app.update()
app.destroy()
print("SMOKE TEST 26 PASSED")
