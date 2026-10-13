"""Smoke test: reimbursements — mark an expense as getting reimbursed (sort card toggle and
right-click), Today's 'Awaiting reimbursement' card with Received / Partial / Dismiss, net
spend in Analysis and the category totals, assigning an incoming row fully or partly to
pending expenses (typed 'reimbursement', never a pay), the post-commit offer, round trip."""
import os, sys, tempfile, time, json
from datetime import date, timedelta

tmp = tempfile.mkdtemp(prefix="budget_reimb_")
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
    return bg.TransactionRecord(tx_date=d, description=desc, money_out=out, money_in=inn, fingerprint=f"{d}|{desc}|{out}|{inn}", **kw)


today = date.today()
# ── Model + net helpers ──────────────────────────────────────────────────────
e = tx(today, "BUNNINGS", 120.0, category="General", matched_type="discretionary", user_verified=True, needs_review=False)
e.reimburse = "pending"; e.reimbursed_amount = 45.0
assert bg.tx_category_amounts(e) == [("General", 75.0)] and bg.tx_net_out(e) == 75.0
e.splits = [{"category": "General", "amount": 80.0}, {"category": "Groceries", "amount": 40.0}]
assert [(c, round(a, 2)) for c, a in bg.tx_category_amounts(e)] == [("General", 50.0), ("Groceries", 25.0)]
e.reimbursed_amount = 120.0; assert bg.tx_category_amounts(e) == [] and bg.tx_net_out(e) == 0.0
r = bg.TransactionRecord.from_dict(json.loads(json.dumps(e.to_dict()))); assert r.reimburse == "pending" and r.reimbursed_amount == 120.0
print("engine OK")

# ── UI ───────────────────────────────────────────────────────────────────────
app = bg.BudgetApp(); app.state.onboarding_complete = True; app.state.tutorial_complete = True; app.state.starting_position_set = True
app.geometry("1366x768+0+0"); app.update(); time.sleep(0.4); app.update(); app.focus_force(); app.update()
if getattr(app, "_setup_wizard_scrim", None): app._setup_wizard_scrim.destroy(); app._setup_wizard_scrim = None
app._celebrate = lambda *a, **k: None
st = app.state
dinner = tx(today - timedelta(days=2), "THE RIVER BISTRO", 140.0, category="Food", matched_type="discretionary", user_verified=True, needs_review=False)
fuel = tx(today - timedelta(days=1), "SHELL COLES EXPRESS", 70.0, category="Fuel", matched_type="discretionary", user_verified=True, needs_review=False)
st.transactions += [dinner, fuel]
app._show_page("transactions"); app.refresh_transactions_tab(); app.update()
assert getattr(app.tx_history_tree, "_split_menu_bound", False)
# mark the dinner as getting reimbursed (the right-click path calls this)
app._set_reimburse([dinner], "pending"); app.update()
assert dinner.reimburse == "pending" and app.pending_reimbursements() == [dinner]
assert any(str(app.tx_history_tree.item(i)["values"][1]).startswith("↩") for i in app.tx_history_tree.get_children())
# Today card
app._show_page("today"); app.refresh_today_tab(); app.update()
tt = texts(app._reimb_host)
assert any("AWAITING REIMBURSEMENT · $140.00" == t for t in tt), tt
# partial receive
import tkinter.simpledialog as sd
sd.askfloat = lambda *a, **k: 40.0
btn(app._reimb_host, "Partial…")[0].invoke(); app.update()
assert dinner.reimbursed_amount == 40.0 and dinner.reimburse == "pending"
assert any("$100.00 of $140.00 still to come" in t for t in texts(app._reimb_host))
# Analysis nets it off
data = app._current_month_review_data(bounds=(today - timedelta(days=3), today))
assert abs(data["outgoing_total"] - (100.0 + 70.0)) < 0.01, data["outgoing_total"]
assert bg.outgoing_category_totals(st.transactions, today - timedelta(days=3), today)["Food"] == 100.0
# an incoming row assigned to the rest (and a bit left over)
rebate = tx(today, "J SMITH TRANSFER", inn=130.0, matched_type="income", category="Income")
st.transactions.append(rebate); st.pending_income_confirmations.append(rebate.fingerprint)
app._show_reimburse_assign([rebate]); app.update()
ra = app._reimb_assign
v = ra["state"]["vars"][dinner.fingerprint]
assert v.get() == "100.00", v.get()     # prefilled with the outstanding amount, capped by what came in
v.set("150"); ra["apply"](); app.update(); assert scrims(app), "more than outstanding must be refused"
v.set("100"); ra["apply"](); app.update()
assert not scrims(app) and dinner.reimburse == "done" and dinner.reimbursed_amount == 140.0
assert rebate.matched_type == "reimbursement" and rebate.category == "Reimbursement" and rebate.reimburses[0]["amount"] == 100.0
assert rebate.fingerprint not in st.pending_income_confirmations, "a reimbursement is never a pay to confirm"
assert bg.tx_net_out(dinner) == 0.0 and app.pending_reimbursements() == []
app.refresh_today_tab(); app.update(); assert app._reimb_host.winfo_manager() == ""
# dismiss path + sort-card toggle
app._set_reimburse([fuel], "pending"); assert fuel in app.pending_reimbursements()
app._set_reimburse([fuel], "dismissed"); assert fuel.reimburse == "dismissed" and fuel not in app.pending_reimbursements()
app.latest_import = [app.matcher.match(tx(today, "OFFICEWORKS 12", 59.0))]
app.open_review_queue(); app.update(); sc = app._review_queue_scrim
btn(sc, "Start sorting  →")[0].invoke(); app.update()
tog = [b for b in all_w(sc) if isinstance(b, tk.Button) and "reimburs" in str(b.cget("text")).lower()]
assert tog, [str(b.cget("text")) for b in all_w(sc) if isinstance(b, tk.Button)]
tog[0].invoke(); app.update()
assert app.latest_import[0].reimburse == "pending"
sc.destroy(); app._review_queue_scrim = None; app.update()
# post-commit offer: an incoming row + a pending expense → toast with Assign
app.latest_import[0].user_verified = True; app.latest_import[0].needs_review = False; app.latest_import[0].matched_type = "discretionary"; app.latest_import[0].category = "General"
app.latest_import.append(app.matcher.match(tx(today, "WORK EXPENSES PAYOUT", inn=59.0)))
app._toast_stack.clear()
app.commit_imported_transactions(); app.update()
labels = [str(w.cget("text")) for t_ in app._toast_stack if t_.winfo_exists() for w in all_w(t_) if isinstance(w, tk.Label)]
assert any("Assign" == l for l in labels), labels
# income confirmation card offers the reimbursement path
app.refresh_today_tab(); app.update()
assert btn(app._confirm_income_host, "It's a reimbursement")
btn(app._confirm_income_host, "It's a reimbursement")[0].invoke(); app.update()
assert scrims(app); ra = app._reimb_assign; ra["apply"](); app.update()
payout = next(t_ for t_ in st.transactions if t_.description == "WORK EXPENSES PAYOUT")
assert payout.matched_type == "reimbursement" and not st.pending_income_confirmations
app.destroy()
print("SMOKE TEST 24 PASSED")
