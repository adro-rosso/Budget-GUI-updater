"""Smoke test: small frictions — smart dates everywhere (day/month without a year, month
names, bare day numbers, the Analysis custom range), the Plan header's Undo link after a
removal, and the Bills table's merged 'Every · priority' column."""
import os, sys, tempfile, time
from datetime import date, timedelta

tmp = tempfile.mkdtemp(prefix="budget_frictions_")
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


today = date.today()
app = bg.BudgetApp(); app.state.onboarding_complete = True; app.state.tutorial_complete = True; app.state.starting_position_set = True
app.geometry("1366x768+0+0"); app.update(); time.sleep(0.4); app.update(); app.focus_force(); app.update()
if getattr(app, "_setup_wizard_scrim", None): app._setup_wizard_scrim.destroy(); app._setup_wizard_scrim = None
app._celebrate = lambda *a, **k: None
st = app.state
P = app._parse_smart_date
# ── dates ───────────────────────────────────────────────────────────────────
assert P("2026-11-15") == date(2026, 11, 15) and P("15/11/2026") == date(2026, 11, 15) and P("15.11.2026") == date(2026, 11, 15)
assert P("15 Nov 2026") == date(2026, 11, 15) and P("15 November 2026") == date(2026, 11, 15) and P("Nov 15 2026") == date(2026, 11, 15)
# day/month without a year → next occurrence
d = P("27/10")
assert d is not None and d >= today and d.day == 27 and d.month == 10 and d.year in (today.year, today.year + 1), d
d2 = P("1 jan")
assert d2 is not None and d2 >= today and (d2.month, d2.day) == (1, 1), d2
# a bare day: this month if ahead, else next month
d3 = P("28")
assert d3 is not None and d3 >= today and d3.day == 28 and (d3 - today).days < 32, d3
assert P("28th") == d3
assert P("nonsense words") is None and P("") is None and P("31/2") is None
# Analysis custom range accepts the same forms
app._show_page("review"); app.update()
app._show_review_custom_range(); app.update()
scrims = [w for w in app.winfo_children() if isinstance(w, tk.Frame) and str(w.cget("bg")) == bg.UI_HERO and w.winfo_manager() == "place"]
assert scrims
ents = [w for w in all_w(scrims[-1]) if isinstance(w, bg.ttk.Entry) and not isinstance(w, bg.ttk.Combobox)]
assert len(ents) >= 2
ents[0].delete(0, tk.END); ents[0].insert(0, "1 jul 2026"); ents[1].delete(0, tk.END); ents[1].insert(0, "31/7/2026")
apply_btn = [b for b in all_w(scrims[-1]) if isinstance(b, bg.ttk.Button) and str(b.cget("text")).lower().startswith(("apply", "show", "use"))]
assert apply_btn, [str(b.cget("text")) for b in all_w(scrims[-1]) if isinstance(b, bg.ttk.Button)]
apply_btn[0].invoke(); app.update()
assert app._review_custom == (date(2026, 7, 1), date(2026, 7, 31)), getattr(app, "_review_custom", None)
# ── Bills table: merged column ──────────────────────────────────────────────
st.bills.append(bg.Bill("Rent", 800.0, today + timedelta(days=5), "fortnightly", "essential"))
st.funds.append(bg.Fund("Holiday", 2000.0, today + timedelta(days=120), "important", 0.0, "auto", 0.0, "fund"))
app.refresh_bills(); app.update()
assert tuple(app.bill_tree["columns"]) == ("amount", "due", "cycle", "saved", "per_pay"), app.bill_tree["columns"]
vals = app.bill_tree.item(app.bill_tree.get_children()[0])["values"]
assert vals[2] == "fortnightly · essential", vals
# ── Plan: Undo link in the header after a removal ──────────────────────────
app._show_page("setup"); app.refresh_plan_tab(); app.update()
assert app._plan_undo_lbl.cget("text") == ""
app._plan_menus[("fund", 0)].invoke("Remove"); app.update()
assert not st.funds
assert app._plan_undo_lbl.cget("text") == "↶ Undo: Holiday removed", app._plan_undo_lbl.cget("text")
app._plan_undo_last_remove(); app.update()
assert len(st.funds) == 1 and st.funds[0].name == "Holiday"
assert app._plan_undo_lbl.cget("text") == ""
app.destroy()
print("SMOKE TEST 28 PASSED")
