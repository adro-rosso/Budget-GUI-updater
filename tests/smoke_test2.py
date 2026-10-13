"""Smoke test: welcome checklist refresh, starting-position wizard, allocation
editor with overrides, flag-for-follow-up, and serialisation round trip."""
import os, sys, tempfile
from datetime import date, timedelta

tmp = tempfile.mkdtemp(prefix="budget_setup_")
os.chdir(tmp)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import tkinter as tk
import budget_gui as bg


def find(root, cls, text=None, startswith=None):
    out = []
    def walk(w):
        try:
            if isinstance(w, cls):
                t = str(w.cget("text"))
                if (text is None or t == text) and (startswith is None or t.startswith(startswith)):
                    out.append(w)
        except tk.TclError:
            pass
        for ch in w.winfo_children():
            walk(ch)
    walk(root)
    return out


def texts(root):
    return [str(w.cget("text")) for w in find(root, (tk.Label, tk.Button))]


app = bg.BudgetApp()
app.update()
import time; time.sleep(0.4); app.update()
if getattr(app, "_setup_wizard_scrim", None) is not None:
    find(app._setup_wizard_scrim, bg.ttk.Button, "Finish later")[0].invoke(); app.update()
app._show_page("today"); app.update()

# 1. Welcome overlay visible for a fresh profile, with the new first step
ov = app._today_get_started_overlay
assert ov.winfo_ismapped(), "welcome overlay should show for fresh state"
host = app._today_get_started_steps_host
assert any("Bring in a statement" in t for t in texts(host)), texts(host)

# 2. Adding a bill through the Setup form must tick the checklist immediately
app._show_page("bills"); app.update()
app.clear_bill_form()
app.bill_name.insert(0, "Rent"); app.bill_amount.insert(0, "800")
app.bill_due.insert(0, (date.today() + timedelta(days=10)).isoformat())
app.bill_frequency.set("monthly"); app.bill_priority.set("essential")
app.add_bill(); app.update()
assert len(app.state.bills) == 1
app._show_page("today"); app.update()
assert not ov.winfo_ismapped(), "any data (a bill here) hides the checklist — nothing is mandatory now"

# 3. Setup wizard (bill already exists) — skip through to "money now", place 800 on Rent
app._show_setup_wizard(); app.update()
scrim = app._setup_wizard_scrim
for _ in range(5):
    btn = find(scrim, bg.ttk.Button, "Next  →") or find(scrim, bg.ttk.Button, "Skip for now  →")
    btn[0].invoke(); app.update()
assert any("What's in each account right now" in t for t in texts(scrim)), texts(scrim)[:8]
ents = find(scrim, bg.ttk.Entry)
ents[0].insert(0, "4900"); ents[4].delete(0, tk.END); ents[4].insert(0, "800"); app.update()   # 0-3 = accounts, 4 = Rent
assert any("$4,100.00 left as spending money" in t for t in texts(scrim)), texts(scrim)
find(scrim, bg.ttk.Button, "Next  →")[0].invoke(); app.update()
assert any("Your set-up transfers" in t for t in texts(scrim))
assert any(t.startswith("→ Move $800.00 from") for t in texts(scrim)), [t for t in texts(scrim) if "Move" in t]
find(scrim, bg.ttk.Button, "Finish  ✓")[0].invoke(); app.update()
assert app.state.starting_position_set
assert app.state.account_balances["spending"] == 4100.0 and app.state.account_balances["bills"] == 800.0
assert app.state.bills[0].current_saved == 800.0
assert app.state.last_safe_to_spend == 4100.0
assert not ov.winfo_ismapped(), "overlay should hide once position + bill are set"
assert "4,100" in app._starting_position_summary_var.get(), app._starting_position_summary_var.get()

# 4. Allocation editor with an override
app.state.bills[0].current_saved = 0.0
app._log_pay_and_allocate(2000.0, date.today(), "Test Pay"); app.update()
ed = app._allocation_editor_scrim
assert ed.winfo_exists()
rows_entries = find(ed, bg.ttk.Entry)
assert rows_entries, "editor rows"
suggested = float(rows_entries[0].get())
print("suggested rent allocation:", suggested)
rows_entries[0].delete(0, tk.END); rows_entries[0].insert(0, "123.45"); app.update()
assert "$123.45" in texts(ed)[-30:] or any("$123.45" in t for t in texts(ed)), "totals should update live"
find(ed, bg.ttk.Button, "Apply this split  ✓")[0].invoke(); app.update()
assert len(app.state.incomes) == 1
assert app.last_allocation["bill_total"] == 123.45, app.last_allocation["bill_total"]
assert app.state.bills[0].current_saved == 123.45
# close the pay-day ritual that follows
for w in list(app.winfo_children()):
    try:
        if isinstance(w, tk.Frame) and str(w.cget("bg")) == bg.UI_HERO and w.winfo_manager() == "place":
            w.destroy()
    except tk.TclError:
        pass
app.update()

# 4b. With the review preference off, a pay applies straight away
app.state.ui_prefs["pay.review_allocation"] = False
app._log_pay_and_allocate(500.0, date.today(), "Direct"); app.update()
assert len(app.state.incomes) == 2
assert not getattr(app, "_allocation_editor_scrim", None) or not app._allocation_editor_scrim.winfo_exists()
for w in list(app.winfo_children()):
    try:
        if isinstance(w, tk.Frame) and str(w.cget("bg")) == bg.UI_HERO and w.winfo_manager() == "place":
            w.destroy()
    except tk.TclError:
        pass
app.update()

# 5. Flagging inside the review queue
def tx(d, desc, out):
    return bg.TransactionRecord(tx_date=d, description=desc, money_out=out, fingerprint=f"{d}|{desc}|{out}")
app.latest_import = [app.matcher.match(tx(date.today(), "MYSTERY STREAMING 42", 14.99)),
                     app.matcher.match(tx(date.today() - timedelta(days=30), "MYSTERY STREAMING 41", 14.99))]
app.open_review_queue(); app.update()
rq = app._review_queue_scrim
find(rq, bg.ttk.Button, "Start sorting  →")[0].invoke(); app.update()
flag_btn = find(rq, tk.Button, startswith="🚩 Flag")
assert flag_btn, [str(b.cget("text")) for b in find(rq, tk.Button)]
flag_btn[0].invoke(); app.update()
assert all(t.flagged for t in app.latest_import)
assert any("Investigate Mystery Streaming" in r["text"] and not r["dismissed"] for r in app.state.gerald_reminders)
assert find(rq, tk.Button, startswith="🚩 Flagged")
# still sort it as a subscription
chip = find(rq, tk.Button, "Subscription")
assert chip; chip[0].invoke(); app.update()
labels = texts(rq)
assert any("flagged for follow-up" in t for t in labels), labels
find(rq, bg.ttk.Button, "Back to table")[0].invoke(); app.update()
# Today shows the flagged card
app._show_page("today"); app.update()
fh = app._flagged_host
assert fh.winfo_manager() == "pack", "flagged host should be packed"
assert any("Mystery Streaming" in t for t in texts(fh))
assert app.tx_sort_btn_var.get() == "Sort Unrecognised"
# preview status carries the flag
vals = app.transaction_tree.item("0")["values"]
assert str(vals[-1]).startswith("🚩"), vals
# resolve from Today
find(fh, bg.ttk.Button, "Resolved ✓")[0].invoke(); app.update()
assert not any(t.flagged for t in app.latest_import)
assert all(r["dismissed"] for r in app.state.gerald_reminders if "Mystery Streaming" in r["text"])
assert fh.winfo_manager() == ""

# 6. Serialisation round trip
app.latest_import[0].flagged = True
app.state.transactions.extend(app.latest_import)
d = app.state.to_dict()
s2 = bg.AppState.from_dict(d)
assert s2.starting_position_set and s2.account_balances["spending"] == 4100.0
assert s2.transactions[-2].flagged is True and s2.transactions[-1].flagged is False
assert s2.ui_prefs.get("pay.review_allocation") is False

app.destroy()
print("SMOKE TEST 2 PASSED")
