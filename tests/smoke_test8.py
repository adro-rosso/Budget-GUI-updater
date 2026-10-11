"""Smoke test: 'Make it a recurring bill' from the sort card."""
import os, sys, tempfile, time
from datetime import date, timedelta

tmp = tempfile.mkdtemp(prefix="budget_recbill_")
os.chdir(tmp)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import tkinter as tk
import budget_gui as bg


def all_widgets(root):
    out = []
    def walk(w):
        out.append(w)
        for ch in w.winfo_children(): walk(ch)
    walk(root); return out


def find_btn(root, text):
    return [w for w in all_widgets(root) if isinstance(w, bg.ttk.Button) and str(w.cget("text")) == text]


def texts(root):
    out = []
    for w in all_widgets(root):
        try: out.append(str(w.cget("text")))
        except tk.TclError: pass
    return out


app = bg.BudgetApp(); app.state.onboarding_complete = True; app.state.tutorial_complete = True
app.update(); time.sleep(0.4); app.update()
if getattr(app, "_setup_wizard_scrim", None): app._setup_wizard_scrim.destroy(); app._setup_wizard_scrim = None
today = date.today()

def tx(d, desc, out):
    return bg.TransactionRecord(tx_date=d, description=desc, money_out=out, fingerprint=f"{d}|{desc}|{out}")

# Inference: three monthly charges (two committed, one in the batch)
app.state.transactions += [app.matcher.match(tx(today - timedelta(days=61), "ADOBE CREATIVE CLOUD 1", 29.99)),
                           app.matcher.match(tx(today - timedelta(days=31), "ADOBE CREATIVE CLOUD 2", 29.99))]
app.latest_import = [app.matcher.match(tx(today - timedelta(days=1), "ADOBE CREATIVE CLOUD 3", 29.99))]
g = app._review_queue_groups()[0]
guess = app._infer_recurring_bill(g, [app.latest_import[0]])
print(guess)
assert guess["frequency"] == "monthly" and guess["amount"] == 29.99 and guess["due"] >= today and "3 charges" in guess["why"]
# weekly inference from the batch alone
batch = [app.matcher.match(tx(today - timedelta(days=d), "GYM CO", 25.0)) for d in (22, 15, 8, 1)]
app.latest_import = batch
gw = app._review_queue_groups()[0]
assert app._infer_recurring_bill(gw, batch)["frequency"] == "weekly"
# single charge → monthly default
app.latest_import = [app.matcher.match(tx(today - timedelta(days=3), "MYSTERY SUB", 9.99))]
assert "assumed monthly" in app._infer_recurring_bill(app._review_queue_groups()[0], app.latest_import)["why"]

# UI flow: open the queue, click Make it a recurring bill, create → bill exists + group linked
app.latest_import = [app.matcher.match(tx(today - timedelta(days=1), "ADOBE CREATIVE CLOUD 3", 29.99))]
app.open_review_queue(); app.update()
rq = app._review_queue_scrim
find_btn(rq, "Start sorting  →")[0].invoke(); app.update()
find_btn(rq, "Make it a recurring bill")[0].invoke(); app.update()
assert any("NEW RECURRING BILL" in t for t in texts(rq))
ents = [w for w in all_widgets(rq) if isinstance(w, bg.ttk.Entry) and not isinstance(w, bg.ttk.Combobox)]
vals = [e.get() for e in ents]
assert "Adobe Creative Cloud" in vals and "29.99" in vals, vals
n_bills = len(app.state.bills)
find_btn(rq, "Create bill & link these  ✓")[0].invoke(); app.update()
assert len(app.state.bills) == n_bills + 1
b = app.state.bills[-1]
assert b.name == "Adobe Creative Cloud" and b.amount == 29.99 and b.frequency == "monthly" and b.due_date >= today
t0 = app.latest_import[0]
assert t0.user_verified and t0.matched_type == "linked_bill" and t0.matched_target == b.name
# the rule saved means a future charge auto-links to the bill
new = app.matcher.match(tx(today + timedelta(days=29), "ADOBE CREATIVE CLOUD 4", 29.99))
assert new.matched_type == "linked_bill" and new.matched_target == b.name and new.user_verified, (new.matched_type, new.matched_target)
# duplicate name is refused
find_btn(rq, "Back to table")[0].invoke(); app.update()
app.latest_import = [app.matcher.match(tx(today - timedelta(days=2), "NETFLIX", 19.99))]
app.state.bills.append(bg.Bill("Netflix", 19.99, today + timedelta(days=10), "monthly", "optional", "Subscription", 0.0))
app.open_review_queue(); app.update(); rq = app._review_queue_scrim
find_btn(rq, "Start sorting  →")[0].invoke(); app.update()
find_btn(rq, "Make it a recurring bill")[0].invoke(); app.update()
n_bills = len(app.state.bills)
find_btn(rq, "Create bill & link these  ✓")[0].invoke(); app.update()
assert len(app.state.bills) == n_bills and any("already exists" in t for t in texts(rq))
find_btn(rq, "Finish later")[0].invoke(); app.update()
app.destroy(); print("SMOKE TEST 8 PASSED")
