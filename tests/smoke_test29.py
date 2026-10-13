"""Smoke test: track first, plan later — the InsightEngine (weekly baselines, outlier weeks,
recurring-bill candidates, savings picture, money flow, learning level), the two-card first run
(no wizard), the rewritten welcome checklist, Today's 'Where your money goes' panel and 'Looks
like regular bills' card (Yes → bill + rule + relabelled rows, Undo; Not a bill → dismissed),
the learned line in the allocation editor, and Analysis 'Typical week & big weeks'."""
import os, sys, tempfile, time
from datetime import date, timedelta

tmp = tempfile.mkdtemp(prefix="budget_track_")
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


def tx(d, desc, out=0.0, inn=0.0, cat="General", mt="discretionary"):
    return bg.TransactionRecord(tx_date=d, description=desc, money_out=out, money_in=inn, fingerprint=f"{d}|{desc}|{out}|{inn}",
                                category=cat, matched_type=mt, user_verified=True, needs_review=False)


today = date.today()
monday = today - timedelta(days=today.weekday())


def build_history(st):
    """12 complete weeks: groceries ~150 (one 420 week), fuel ~60, Netflix monthly, pays fortnightly."""
    for k in range(1, 13):
        ws = monday - timedelta(days=7 * k)
        g = 420.0 if k == 3 else 140.0 + (k % 4) * 8
        st.transactions.append(tx(ws + timedelta(days=2), "WOOLWORTHS 1234", g, cat="Groceries"))
        st.transactions.append(tx(ws + timedelta(days=4), "BP CONNECT", 55.0 + (k % 3) * 5, cat="Fuel"))
    for m in range(3):
        st.transactions.append(tx(monday - timedelta(days=10 + 30 * m), "NETFLIX.COM", 20.99, cat="Subscription"))
    for p in range(6):
        st.incomes.append(bg.IncomeEntry(2400.0, monday - timedelta(days=3 + 14 * p), "Acme"))


# ── Engine ──────────────────────────────────────────────────────────────────
st = bg.AppState(); st.pay_frequency = "fortnightly"
build_history(st)
eng = bg.InsightEngine(st)
lvl = eng.data_level(today)
assert lvl["weeks"] >= 12 and lvl["level"] == "solid", lvl
b = eng.category_baseline("Groceries", today=today)
assert b["weeks"] == 12 and 140 <= b["typical"] <= 170, b
assert any(v == 420.0 for _, v in b["outliers"]), b["outliers"]
assert b["confidence"] > 0.5
tw = eng.typical_week(today=today)
assert [c for c, _ in tw["rows"]][:2] == ["Groceries", "Fuel"], tw["rows"]
assert 190 <= tw["total"] <= 240, tw["total"]
big = eng.big_weeks(today=today)
assert len(big) == 1 and big[0]["driver"] == "Groceries" and big[0]["total"] >= 420, big
cands = eng.recurring_candidates(today)
assert len(cands) == 1 and cands[0]["name"].lower().startswith("netflix") and cands[0]["frequency"] == "monthly" and cands[0]["amount"] == 20.99, cands
assert cands[0]["next_due"] > today
pic = eng.savings_picture(today)
assert pic["pay"] == 2400.0 and 380 <= pic["spend"] <= 480 and pic["could_save"] and pic["could_save"] > 1500, pic
flow = eng.money_flow(today - timedelta(days=29), today)
assert flow["income"] > 0 and flow["categories"].get("Groceries", 0) > 0 and abs(flow["saved"] - (flow["income"] - flow["out"])) < 0.01, flow
st.recurring_dismissed.append(cands[0]["key"])
assert eng.recurring_candidates(today) == []
st.recurring_dismissed.clear()
empty = bg.InsightEngine(bg.AppState())
assert empty.data_level()["level"] == "none" and empty.typical_week()["rows"] == [] and empty.savings_picture()["could_save"] is None
print("engine OK")

# ── First run: two cards, no wizard ─────────────────────────────────────────
app = bg.BudgetApp(); app.state.tutorial_complete = True
app._celebrate = lambda *a, **k: None
app._open_pack_animation = lambda *a, **k: None   # the day-one free pack would open a grabbing Toplevel 2.3 s later
app.geometry("1366x768+0+0"); app.update(); time.sleep(0.5); app.update(); app.focus_force(); app.update()
assert getattr(app, "_setup_wizard_scrim", None) is None, "the full wizard must not open on first run any more"
sc = app._track_onboarding_scrim; ob = app._track_onboarding
assert sc is not None and sc.winfo_exists()
assert any("Let's see where your money goes." == t for t in texts(sc))
btn(sc, "Monthly")[0].invoke(); app.update()
ents = [w for w in all_w(sc) if isinstance(w, bg.ttk.Entry)]
ents[0].insert(0, "5200"); app.update()
btn(sc, "Next  →")[0].invoke(); app.update()
assert any("Bring in a statement" == t for t in texts(sc)) and btn(sc, "Set up a full money plan instead →", tk.Label)
btn(sc, "I'll log things as I go")[0].invoke(); app.update()
st = app.state
assert st.onboarding_complete and st.setup_mode == "track" and st.pay_frequency == "monthly" and st.income_baseline == 5200.0
assert st.starting_position_date == today.isoformat() and not st.starting_position_set
assert app._track_onboarding_scrim is None
# day-one head start opened the free pack reveal (a grabbing Toplevel) — close it like a user would
time.sleep(0.3); app.update()
for w_ in list(app.winfo_children()):
    if isinstance(w_, tk.Toplevel):
        w_.destroy()
try:
    app.grab_release()
except tk.TclError:
    pass
app.update()
# welcome checklist: statement first, hides once there is data
app._show_page("today"); app.refresh_today_tab(); app.update()
ov = app._today_get_started_overlay
assert ov.winfo_ismapped()
tt = texts(app._today_get_started_steps_host)
assert tt and any("Bring in a statement" == t for t in tt) and any("Optional: a full money plan" == t for t in tt), tt
assert not any("Add your bills" in t for t in tt)
st.pay_frequency = "fortnightly"
build_history(st)
app.refresh_all_views(); app.update()
assert not ov.winfo_ismapped(), "any data hides the checklist"
# money flow panel
ft = texts(app._flow_host)
assert any("WHERE YOUR MONEY GOES" == t for t in ft), ft
assert any(t.startswith("In $") for t in ft) and any(t.startswith("Groceries $") for t in ft), ft
assert any(t.startswith("Typical week:") and "Groceries" in t for t in ft), ft
assert any("weeks of data" in t for t in ft)
assert any(t.startswith("Put $") and t.endswith("aside") for t in ft), ft
# recurring card: Yes → bill + rule + rows linked; Undo reverses
rt = texts(app._recurring_host)
assert any("LOOKS LIKE REGULAR BILLS · 1" == t for t in rt), rt
app._toast_stack.clear()
btn(app._recurring_host, "Yes, it's a bill  ✓")[0].invoke(); app.update()
nf = next(b_ for b_ in st.bills if b_.name.lower().startswith("netflix"))
assert nf.amount == 20.99 and nf.frequency == "monthly" and nf.due_date > today and nf.keywords
assert any(r.matched_type == "linked_bill" and r.matched_target == nf.name for r in st.advanced_match_rules)
assert all(t_.matched_type == "linked_bill" for t_ in st.transactions if "NETFLIX" in t_.description)
assert app._recurring_host.winfo_manager() == "", "answered → card hidden"
# the matcher now links a fresh Netflix charge straight to the bill
m = app.matcher.match(bg.TransactionRecord(tx_date=today, description="NETFLIX.COM", money_out=20.99, fingerprint="nf-new"))
assert m.matched_type == "linked_bill" and m.matched_target == nf.name
# undo via the toast action
labels = [w for t_ in app._toast_stack if t_.winfo_exists() for w in all_w(t_) if isinstance(w, tk.Label) and str(w.cget("text")) == "Undo"]
assert labels, "toast should carry Undo"
labels[-1].event_generate("<Button-1>"); app.update(); app.update()
assert not any(b_.name.lower().startswith("netflix") for b_ in st.bills)
assert all(t_.matched_type == "discretionary" for t_ in st.transactions if "NETFLIX" in t_.description)
app.refresh_today_tab(); app.update()
assert app._recurring_host.winfo_manager() != ""
# Not a bill → dismissed, never suggested again
btn(app._recurring_host, "Not a bill")[0].invoke(); app.update()
assert st.recurring_dismissed and app._recurring_host.winfo_manager() == ""
# Do-this-now candidate exists only while something is unconfirmed
st.recurring_dismissed.clear()
assert any(c["title"].startswith("Confirm 1 regular bill") for c in app._do_now_candidates([])), [c["title"] for c in app._do_now_candidates([])]
# put aside creates the Savings pot
app._put_aside(100.0); app.update()
pot = next(g for g in st.goals if g.name == "Savings")
assert pot.current_saved == 100.0 and st.account_balances["savings"] == 100.0
# allocation editor shows the learned line
app._show_allocation_editor(2400.0, today, "Acme"); app.update()
ed = app._allocation_editor_scrim
assert any(t.startswith("Learned from") and "typical fortnight" in t for t in texts(ed)), [t for t in texts(ed) if "Learned" in t]
btn(ed, "Cancel")[0].invoke(); app.update()
# Safe to Spend fallback for a track-only profile (no plan, no pays)
st2 = bg.AppState(); st2.transactions.append(tx(today - timedelta(days=2), "KMART", 50.0)); st2.transactions.append(tx(today - timedelta(days=1), "ACME PAYROLL", inn=900.0, cat="Income", mt="income"))
app._replace_state(st2); app.state.onboarding_complete = True; app._show_page("today"); app.refresh_today_tab(); app.update()
assert "over the last 30 days" in app.today_velocity_var.get(), app.today_velocity_var.get()
# Analysis typical week section
app._replace_state(st); app.refresh_all_views(); app._show_page("review"); app.refresh_review_tab(); app.update()
at = texts(app._review_typical_frame)
assert any(t == "Groceries" for t in at) and any(t.startswith("Big weeks overall") for t in at), at
assert "Groceries $" in app.review_typical_summary_var.get()
app.destroy()
print("SMOKE TEST 29 PASSED")
