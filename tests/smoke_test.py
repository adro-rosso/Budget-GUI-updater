"""Scripted smoke test of the Sort Unrecognised overlay. Runs with cwd = a temp
dir so the real budget_data.json is never touched."""
import os, sys, tempfile
from datetime import date

tmp = tempfile.mkdtemp(prefix="budget_rq_")
os.chdir(tmp)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import tkinter as tk
import budget_gui as bg

app = bg.BudgetApp()
app.state.onboarding_complete = True; app.state.tutorial_complete = True
app.update()
import time; time.sleep(0.4); app.update()
if getattr(app, '_setup_wizard_scrim', None) is not None:
    app._setup_wizard_scrim.destroy(); app._setup_wizard_scrim = None

app.register_expense_category("Groceries")
app.register_expense_category("Fuel")

def tx(d, desc, out=0.0, inn=0.0):
    t = bg.TransactionRecord(tx_date=d, description=desc, money_in=inn, money_out=out,
                             fingerprint=f"{d}|{desc}|{out}|{inn}")
    return t

rows = [
    tx(date(2026, 9, 3), "VISA PURCHASE ACME WIDGETS 1234 SYDNEY", 42.10),
    tx(date(2026, 9, 17), "VISA PURCHASE ACME WIDGETS 9981 SYDNEY", 18.50),
    tx(date(2026, 9, 5), "COLES 0412 PARRAMATTA", 88.20),
    tx(date(2026, 9, 9), "MYSTERY SHOP 77", 12.00),
    tx(date(2026, 9, 12), "SALARY ACME CORP", inn=2500.0),
]
app.latest_import = [app.matcher.match(t) for t in rows]
groups = app._review_queue_groups()
print("groups:", [(g["name"], len(g["indexes"]), g["confident"]) for g in groups])
assert len(groups) == 3, groups
assert groups[0]["confident"] is False and groups[-1]["name"].lower().startswith("coles")

app.open_review_queue(after_import=True)
app.update()
scrim = app._review_queue_scrim
assert scrim is not None and scrim.winfo_exists()


def find_widgets(root, cls, text=None):
    out = []
    stack = [root]
    while stack:
        w = stack.pop()
        try:
            if isinstance(w, cls) and (text is None or str(w.cget("text")) == text):
                out.append(w)
        except tk.TclError:
            pass
        stack.extend(w.winfo_children())
    return out


def texts(root):
    return [str(w.cget("text")) for w in find_widgets(root, (tk.Label,))]


# Overview screen
assert any("transactions imported" in t for t in texts(scrim)), texts(scrim)
start = find_widgets(scrim, bg.ttk.Button, "Start sorting  →")
assert start, "no start button"
start[0].invoke(); app.update()

# Card 1: an unknown merchant -> click the Groceries chip
labels = texts(scrim)
assert any("NOT RECOGNISED" in t for t in labels), labels
chip = find_widgets(scrim, tk.Button, "Groceries")
assert chip, "no Groceries chip"
chip[0].invoke(); app.update()

# Card 2: second unknown merchant -> new category via entry
labels = texts(scrim)
assert any("NOT RECOGNISED" in t for t in labels), labels
entries = find_widgets(scrim, bg.ttk.Entry)
assert entries
entries[0].insert(0, "Hobbies")
add_btn = find_widgets(scrim, bg.ttk.Button, "Add & use")
add_btn[0].invoke(); app.update()

# Card 3: suggested (Coles -> Groceries) -> press Enter on the scrim
labels = texts(scrim)
assert any("SUGGESTED MATCH" in t for t in labels), labels
assert any("Suggested:  Groceries" in t for t in labels), labels
scrim.event_generate("<Return>"); app.update()

# Done screen
labels = texts(scrim)
assert any("Everything is sorted" in t for t in labels), labels
assert find_widgets(scrim, bg.ttk.Button, "Commit now  ✓")
back = find_widgets(scrim, bg.ttk.Button, "Back to table")
back[0].invoke(); app.update()
assert app._review_queue_scrim is None

# State checks
out_rows = [t for t in app.latest_import if t.direction() == "out"]
assert all(t.user_verified for t in out_rows), [(t.description, t.user_verified) for t in out_rows]
acme = [t for t in app.latest_import if "ACME WIDGETS" in t.description]
assert all(t.category == "Groceries" for t in acme), [t.category for t in acme]
assert "Hobbies" in app.state.expense_categories
rules = [(r.rule_type, r.keyword, r.category) for r in app.state.advanced_match_rules]
print("rules:", rules)
assert any(k == "acme widgets sydney" and c == "Groceries" for _, k, c in rules), rules
assert "visa purchase acme widgets 1234 sydney" in app.state.merchant_memory
assert app.tx_sort_btn_var.get() == "Sort Unrecognised", app.tx_sort_btn_var.get()

# Re-import a new ACME variant: the rule should auto-sort it
new = app.matcher.match(tx(date(2026, 10, 2), "VISA PURCHASE ACME WIDGETS 5555 SYDNEY", 30.0))
assert new.user_verified and new.category == "Groceries" and new.confidence == "manual", new

# Opening the queue with nothing left just toasts
app.open_review_queue()
app.update()
assert app._review_queue_scrim is None

# Accept-all path
app.latest_import = [app.matcher.match(tx(date(2026, 9, 20), "WOOLWORTHS 123 METRO", 20.0)),
                     app.matcher.match(tx(date(2026, 9, 21), "ZZZ UNKNOWN 1", 5.0))]
app.open_review_queue(); app.update()
scrim = app._review_queue_scrim
acc = [b for b in find_widgets(scrim, bg.ttk.Button) if str(b.cget("text")).startswith("Accept 1 suggestion")]
assert acc, [str(b.cget("text")) for b in find_widgets(scrim, bg.ttk.Button)]
acc[0].invoke(); app.update()
labels = texts(scrim)
assert any("NOT RECOGNISED" in t for t in labels), labels
assert app.tx_sort_btn_var.get() == "Sort Unrecognised"  # not refreshed until finish
skip = find_widgets(scrim, bg.ttk.Button, "Skip  →")
skip[0].invoke(); app.update()
labels = texts(scrim)
assert any("still unsorted" in t for t in labels), labels
assert find_widgets(scrim, bg.ttk.Button, "Sort the rest  →")
scrim.event_generate("<Escape>"); app.update()
assert app._review_queue_scrim is None
assert app.tx_sort_btn_var.get() == "Sort Unrecognised (1)", app.tx_sort_btn_var.get()

app.destroy()
print("SMOKE TEST PASSED")
