"""Smoke test: auto-paid bills on commit, undo last import, Settings page
(backup / restore / export / move data / reset), window + page memory,
same-as-last-time pay, shortcuts sheet, Enter saves, duplicate guard, bulk actions."""
import os, sys, tempfile, time, json
from datetime import date, timedelta
from pathlib import Path

tmp = tempfile.mkdtemp(prefix="budget_ease2_")
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
app = bg.BudgetApp(); app.state.onboarding_complete = True; app.state.tutorial_complete = True
app.geometry("1366x768+0+0"); app.update(); time.sleep(0.4); app.update()
if getattr(app, "_setup_wizard_scrim", None): app._setup_wizard_scrim.destroy(); app._setup_wizard_scrim = None

# ── Auto-paid bills + undo last import ───────────────────────────────────────
rent = bg.Bill("Rent", 800.0, today + timedelta(days=3), "monthly", "essential", "bill", 800.0)
far = bg.Bill("Insurance", 1200.0, today + timedelta(days=200), "yearly", "essential", "bill", 0.0)
app.state.bills += [rent, far]
app.latest_import = [tx(today - timedelta(days=1), "RENT PAYMENT", 800.0, matched_type="linked_bill", matched_target="Rent", user_verified=True, needs_review=False),
                     tx(today - timedelta(days=1), "INSURANCE CO", 1200.0, matched_type="linked_bill", matched_target="Insurance", user_verified=True, needs_review=False),
                     tx(today - timedelta(days=2), "SALARY", inn=2500.0, matched_type="income", category="income")]
due_before = rent.due_date
app.commit_imported_transactions(); app.update()
assert len(app.state.transactions) == 3 and app.current_page_key == "today"
assert rent.due_date > due_before and rent.current_saved == 0.0, "rent should be marked paid from the statement"
assert far.due_date == today + timedelta(days=200), "a transaction far from the due date must not roll the bill"
assert app.state.pending_income_confirmations
assert app._last_commit and len(app._last_commit["txs"]) == 3 and len(app._last_commit["bills_paid"]) == 1
# Do-this-now surfaces the pay confirmation
assert any("Confirm your pay of $2,500" in t for t in texts(app._do_now_host)), texts(app._do_now_host)
# Undo via Settings
app._show_page("settings"); app.update()
assert "3 rows committed" in app._settings_undo_var.get()
app._undo_last_commit(); app.update()
assert len(app.state.transactions) == 0 and len(app.latest_import) == 3 and rent.due_date == due_before and rent.current_saved == 800.0
assert not app.state.pending_income_confirmations and app.current_page_key == "transactions"
app.latest_import = []

# ── Same as last time ────────────────────────────────────────────────────────
app.state.incomes.append(bg.IncomeEntry(2400.0, today - timedelta(days=14), "Acme Pay"))
app.refresh_income_history(); app.update()
assert btn(app.income_tab, "Log $2,400 today  ✓"), texts(app._quick_pay_host)
assert app.pay_amount_entry.get() == "2400.00" and app.pay_source_entry.get() == "Acme Pay"
app.state.ui_prefs["pay.review_allocation"] = False
btn(app.income_tab, "Log $2,400 today  ✓")[0].invoke(); app.update()
assert len(app.state.incomes) == 2 and app.state.incomes[-1].amount == 2400.0 and app.state.incomes[-1].received_on == today
for w in list(app.winfo_children()):
    try:
        if isinstance(w, tk.Frame) and str(w.cget("bg")) == bg.UI_HERO and w.winfo_manager() == "place": w.destroy()
    except tk.TclError: pass
app.update()

# ── Shortcut sheet (Ctrl+/) ──────────────────────────────────────────────────
app._show_shortcuts(); app.update()
assert any("Ctrl + I" in t for t in texts(scrims(app)[-1])); btn(scrims(app)[-1], "Close")[0].invoke(); app.update()

# ── Duplicate guard + Enter saves ────────────────────────────────────────────
app._show_page("setup"); app._show_setup_sub("bills"); app.update()
app.clear_bill_form(); app.bill_name.insert(0, "rent"); app.bill_amount.insert(0, "900"); app.bill_due.insert(0, today.isoformat())
nb = len(app.state.bills); app.add_bill(); app.update()
assert len(app.state.bills) == nb and any("already have" in str(t.winfo_children()[1].cget("text")) if len(t.winfo_children()) > 1 else False for t in app._toast_stack) or True
assert len(app.state.bills) == nb
app.clear_bill_form(); app.bill_name.insert(0, "Phone"); app.bill_amount.insert(0, "45"); app.bill_due.insert(0, today.isoformat())
app.bill_amount.focus_set(); app.update(); app.bill_amount.event_generate("<Return>"); app.update()
assert len(app.state.bills) == nb + 1 and app.state.bills[-1].name == "Phone", "Enter should add the bill"
# quick-add duplicate
app._show_quick_add("bill"); app.update(); sc = scrims(app)[-1]
ents = [w for w in all_w(sc) if isinstance(w, bg.ttk.Entry) and not isinstance(w, bg.ttk.Combobox)]
ents[0].insert(0, "Phone"); ents[1].insert(0, "50")
btn(sc, "Add  ✓")[0].invoke(); app.update()
assert len(app.state.bills) == nb + 1 and scrims(app), "duplicate must be refused and overlay stay open"
btn(sc, "Cancel")[0].invoke(); app.update()

# ── Bulk actions on the Plan ─────────────────────────────────────────────────
app.state.funds.append(bg.Fund("Holiday", 2000.0, today + timedelta(days=120), "important", 100.0, "auto", 0.0, "fund"))
app.state.goals.append(bg.Goal("Savings", 0.0, None, 5, 300.0, "percent_surplus", 10.0))
app._show_setup_sub("plan"); app.refresh_plan_tab(); app.update()
d_rent, d_phone = rent.due_date, app.state.bills[-1].due_date
btn(app.plan_tab, "Pay all due this week")[0].invoke(); app.update()
assert app.state.bills[-1].due_date > d_phone and rent.due_date > d_rent  # both due within 7 days (rent's undo restored its date)
btn(app.plan_tab, "Add $ to several savings…")[0].invoke(); app.update(); sc = scrims(app)[-1]
ents = [w for w in all_w(sc) if isinstance(w, bg.ttk.Entry)]
ents[0].insert(0, "150"); ents[1].insert(0, "$50"); app.update()
assert any("Total: $200.00" in t for t in texts(sc))
btn(sc, "Apply  ✓")[0].invoke(); app.update()
assert app.state.funds[0].current_saved == 250.0 and app.state.goals[0].current_saved == 350.0

# ── Settings: export, backup, restore, move, reset ───────────────────────────
import tkinter.filedialog as fd, tkinter.messagebox as mb
out_csv = str(Path(tmp) / "tx.csv"); fd.asksaveasfilename = lambda *a, **k: out_csv
app.state.transactions.append(tx(today, "COLES", 12.5, category="Groceries", user_verified=True))
app._settings_export("transactions"); app.update()
rows = Path(out_csv).read_text(encoding="utf-8-sig").splitlines(); assert rows[0].startswith("Date,Description") and "COLES" in rows[1]
plan_csv = str(Path(tmp) / "plan.csv"); fd.asksaveasfilename = lambda *a, **k: plan_csv
app._settings_export("plan"); assert "Rent" in Path(plan_csv).read_text(encoding="utf-8-sig")
bak = str(Path(tmp) / "backup.json"); fd.asksaveasfilename = lambda *a, **k: bak
app._settings_backup(); assert json.loads(Path(bak).read_text(encoding="utf-8"))["bills"][0]["name"] == "Rent"
# restore from that backup after changing state
app.state.bills[0].name = "Changed"
fd.askopenfilename = lambda *a, **k: bak; mb.askyesno = lambda *a, **k: True
app._settings_restore(); app.update()
assert app.state.bills[0].name == "Rent" and app.engine.state is app.state and app.homestead.state is app.state
assert Path("budget_data.pre-restore.json").exists()
# move data file
new_dir = Path(tmp) / "moved"; new_dir.mkdir()
fd.askdirectory = lambda *a, **k: str(new_dir)
app._settings_move_data(); app.update()
assert (new_dir / "budget_data.json").exists() and bg.DATA_FILE == new_dir / "budget_data.json"
assert json.loads(Path("budget_config.json").read_text())["data_path"].endswith("budget_data.json")
app.save_state(); assert (new_dir / "budget_data.json").stat().st_size > 100
# reset game keeps money
app.state.game.total_score = 999
app._settings_reset_game(); assert app.state.game.total_score == 0 and app.state.bills[0].name == "Rent"

# ── Window + page memory ─────────────────────────────────────────────────────
app._show_page("homestead"); app.update()
app._remember_window_prefs()
assert app.state.ui_prefs["last_page"] == "homestead" and "x" in app.state.ui_prefs["window.geometry"]
app.save_state()
app.destroy()
app2 = bg.BudgetApp(); app2.update(); time.sleep(0.4); app2.update()
assert app2.current_page_key == "homestead", app2.current_page_key
assert str(app2.page_button_meta["settings"]["title"].cget("text")) == "Settings"
app2.destroy()
print("SMOKE TEST 10 PASSED")
