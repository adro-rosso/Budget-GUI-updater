"""Smoke test: ease-of-use layer — Do this now, Plan list + inline edit + quick add,
money/date parsing + chips, responsive overlays, nav names, goal priority words,
focus mode, import folder memory, Ctrl+I, commit → Today, toasts instead of dialogs."""
import os, sys, tempfile, time
from datetime import date, timedelta

tmp = tempfile.mkdtemp(prefix="budget_ease_")
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


app = bg.BudgetApp(); app.state.onboarding_complete = True; app.state.tutorial_complete = True
app.geometry("1366x768+0+0"); app.update(); time.sleep(0.4); app.update(); app.focus_force(); app.update()
if getattr(app, "_setup_wizard_scrim", None): app._setup_wizard_scrim.destroy(); app._setup_wizard_scrim = None
today = date.today()

# ── Nav names + focus button present ─────────────────────────────────────────
assert str(app.page_button_meta["transactions"]["title"].cget("text")) == "Statements"
assert str(app.page_button_meta["review"]["title"].cget("text")) == "Analysis"
assert "Focus mode" in str(app._focus_btn.cget("text"))

# ── Do this now: fresh profile → "Log your first pay"; with unsorted rows → sort ─
app._show_page("today"); app.update()
dn = texts(app._do_now_host)
assert any("DO THIS NOW" in t for t in dn) and any("Log your first pay" in t for t in dn), dn
def tx(d, desc, out): return bg.TransactionRecord(tx_date=d, description=desc, money_out=out, fingerprint=f"{d}|{desc}|{out}")
app.latest_import = [app.matcher.match(tx(today - timedelta(days=1), "MYSTERY 1", 10.0))]
app.refresh_today_tab(); app.update()
dn = texts(app._do_now_host)
assert any("Sort 1 unrecognised transaction" in t for t in dn), dn
btn(app._do_now_host, "Sort now  →")[0].invoke(); app.update()
assert app.current_page_key == "transactions" and app._review_queue_scrim is not None
btn(app._review_queue_scrim, "Later")[0].invoke(); app.update()
app.latest_import = []

# Secondary Today sections default closed
for key in ("today.gerald", "today.health", "today.metrics"):
    assert not app.state.ui_prefs.get(key, False)

# ── Setup opens on Plan; quick add a bill with "$1,200" and a date chip ──────
app._show_page("setup"); app.update()
assert app._setup_sub_btns["plan"]["underline"].cget("bg") == bg.UI_SUBTAB_ACTIVE
assert any("No bills yet" in t for t in texts(app._plan_host))
btn(app.plan_tab, "+ Add bill")[0].invoke(); app.update()
sc = scrims(app)[-1]
ents = [w for w in all_w(sc) if isinstance(w, bg.ttk.Entry) and not isinstance(w, bg.ttk.Combobox)]
ents[0].insert(0, "Rent"); ents[1].insert(0, "$1,200")
btn(sc, "15th", tk.Button)[0].invoke(); app.update()
assert ents[2].get().endswith("-15") or ents[2].get().endswith("-15"), ents[2].get()
btn(sc, "Add  ✓")[0].invoke(); app.update()
assert len(app.state.bills) == 1 and app.state.bills[0].amount == 1200.0 and app.state.bills[0].name == "Rent"
assert not scrims(app)
rows = texts(app._plan_host)
assert any("Rent" == t for t in rows) and any("$1,200.00" in t for t in rows), rows

# Quick add a set-aside (buffer) and a goal with word priority
btn(app.plan_tab, "+ Add savings")[0].invoke(); app.update(); sc = scrims(app)[-1]
btn(sc, "Keep a buffer topped up", tk.Button)[0].invoke(); app.update()
ents = [w for w in all_w(sc) if isinstance(w, bg.ttk.Entry) and not isinstance(w, bg.ttk.Combobox)]
ents[0].insert(0, "Car service"); ents[1].insert(0, "600")
btn(sc, "Add  ✓")[0].invoke(); app.update()
assert app.state.funds[0].contribution_mode == "buffer" and app.state.funds[0].target_amount == 600.0
btn(app.plan_tab, "+ Add savings")[0].invoke(); app.update(); sc = scrims(app)[-1]
btn(sc, "Goal", tk.Button)[0].invoke(); app.update()
ents = [w for w in all_w(sc) if isinstance(w, bg.ttk.Entry) and not isinstance(w, bg.ttk.Combobox)]
ents[0].insert(0, "Emergency"); ents[1].insert(0, "50"); ents[2].insert(0, "5000")
combos = [w for w in all_w(sc) if isinstance(w, bg.ttk.Combobox)]
combos[-1].set("essential")
btn(sc, "Add  ✓")[0].invoke(); app.update()
assert app.state.goals[0].priority == 1 and app.state.goals[0].value == 50.0
assert app._priority_word(app.state.goals[0].priority) == "essential"
rows = texts(app._plan_host)
assert any("essential" in t for t in rows) and any("Spent" == t for t in rows) and any("Paid ✓" == t for t in rows)

# Inline edit the rent amount
amt_lbls = [w for w in all_w(app._plan_host) if isinstance(w, tk.Label) and str(w.cget("text")) == "$1,200.00"]
amt_lbls[0].event_generate("<Button-1>"); app.update()
e = [w for w in all_w(app._plan_host) if isinstance(w, bg.ttk.Entry)]
assert e, "inline entry expected"
e[0].delete(0, tk.END); e[0].insert(0, "1,250"); app.focus_force(); e[0].focus_force(); e[0].event_generate("<Return>"); app.update()
assert app.state.bills[0].amount == 1250.0
# Paid from the Plan row rolls the due date forward
due0 = app.state.bills[0].due_date
btn(app._plan_host, "Paid ✓")[0].invoke(); app.update()
assert app.state.bills[0].due_date > due0
# Delete with undo
n = len(app.state.funds)
app._plan_menus[("fund", 0)].invoke("Remove"); app.update()   # the row menu: Car service is the first fund
assert len(app.state.funds) == n - 1
app._toast_stack[-1] if app._toast_stack else None
# undo via the toast action: find the toast's action label
undo = [w for w in all_w(app._toast_stack[-1]) if isinstance(w, tk.Label) and str(w.cget("text")) == "Undo"]
assert undo; undo[0].event_generate("<Button-1>"); app.update()
assert len(app.state.funds) == n

# ── Old forms accept "$" and "," and toast instead of dialogs ────────────────
app._show_setup_sub("bills"); app.update()
app.clear_bill_form(); app.bill_name.insert(0, "Power"); app.bill_amount.insert(0, "$518.00")
btn(app.bills_tab, "End of month", tk.Button)[0].invoke(); app.update()
assert app.bill_due.get() == bg.month_bounds(today)[1].isoformat()
app.bill_frequency.set("quarterly"); app.add_bill(); app.update()
assert app.state.bills[-1].amount == 518.0 and app.state.bills[-1].frequency == "quarterly"
app.clear_bill_form(); app.bill_name.insert(0, "Bad"); app.bill_amount.insert(0, "abc"); app.bill_due.insert(0, today.isoformat())
nb = len(app.state.bills); app.add_bill(); app.update()
assert len(app.state.bills) == nb and app._toast_stack, "should toast, not add"
app._show_setup_sub("goals"); app.update()
assert "essential" in app.goal_priority["values"]
app.goal_tree.selection_set("0"); app.on_goal_select(); assert app.goal_priority.get() == "essential"

# ── Pay amount parsing + chips on the Income tab ─────────────────────────────
app._show_page("income"); app.update()
assert btn(app.income_tab, "Today", tk.Button)
app.pay_amount_entry.delete(0, tk.END); app.pay_amount_entry.insert(0, "oops")
app.add_pay_and_allocate(); app.update(); assert not app.state.incomes

# ── Responsive overlays: small window caps the wizard card and scrolls ───────
app.geometry("1100x640+0+0"); app.update(); time.sleep(0.3); app.update()
app._show_setup_wizard(); app.update()
sc = app._setup_wizard_scrim
card = [w for w in all_w(sc) if isinstance(w, tk.Frame) and str(w.cget("bg")) == bg.UI_SURFACE and w.master.master is sc][0]
assert int(card.cget("height")) <= 640 - 32, card.cget("height")
assert any(isinstance(w, tk.Canvas) for w in all_w(card)), "capped card should scroll its content"
assert btn(sc, "Finish later"), "buttons must remain visible"
btn(sc, "Finish later")[0].invoke(); app.update()
app.geometry("1366x768+0+0"); app.focus_force(); app.update()

# ── Focus mode hides the game layers and restores them ───────────────────────
app._show_page("score"); app.update()
app._toggle_focus_mode(); app.update()
assert app.state.ui_prefs["focus_mode"] is True
assert app.nav_buttons["score"].winfo_manager() == "" and app.nav_buttons["homestead"].winfo_manager() == ""
assert app.current_page_key == "today"
assert app._today_progress_wrap.winfo_manager() == "" and app._today_hero_cards[3].winfo_manager() == ""
assert "on" in str(app._focus_btn.cget("text"))
app._toggle_focus_mode(); app.update()
assert app.nav_buttons["score"].winfo_manager() == "grid" and app._hook_row.winfo_manager() == "pack"

# ── Import memory + commit returns to Today ──────────────────────────────────
assert "<Control-i>" in [b.lower() for b in app.bind_all()] or app.bind_all("<Control-i>")
app.latest_import = [app.matcher.match(tx(today - timedelta(days=1), "COLES 1", 10.0))]
app.latest_import[0].user_verified = True; app.latest_import[0].needs_review = False
app._show_page("transactions"); app.update()
import tkinter.messagebox as mb
mb.askyesno = lambda *a, **k: True
app.commit_imported_transactions(); app.update()
assert app.current_page_key == "today" and len(app.state.transactions) == 1
app.latest_import = [app.matcher.match(tx(today, "NEW 2", 5.0))]
app.commit_imported_transactions(); app.update()
assert len(app.state.transactions) == 1 and app._toast_stack, "unsorted rows should toast, not dialog"

# round trip of prefs
s2 = bg.AppState.from_dict(app.state.to_dict()); assert s2.ui_prefs.get("focus_mode") is False
app.destroy(); print("SMOKE TEST 9 PASSED")
