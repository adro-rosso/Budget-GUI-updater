"""Layout audit: find widgets that are clipped (requested width > allocated
width of their container) and grid cells where two widgets overlap."""
import os, sys, tempfile, time
from datetime import date, timedelta

tmp = tempfile.mkdtemp(prefix="budget_audit_")
os.chdir(tmp)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import tkinter as tk
import budget_gui as bg

W, H = int(sys.argv[1]) if len(sys.argv) > 1 else 1366, int(sys.argv[2]) if len(sys.argv) > 2 else 768
findings = []


def label_of(w):
    try:
        t = str(w.cget("text"))
        if t:
            return t[:40]
    except tk.TclError:
        pass
    kids = []
    for ch in w.winfo_children()[:4]:
        try:
            tt = str(ch.cget("text"))
            if tt: kids.append(tt[:14])
        except tk.TclError:
            kids.append(ch.winfo_class())
    return w.winfo_class() + "{" + "|".join(kids) + "}"


def audit(root, where):
    seen = set()
    def walk(w):
        for ch in w.winfo_children():
            walk(ch)
        try:
            if not w.winfo_ismapped() or w.winfo_class() == 'Treeview' or any(ch.winfo_class() == 'Treeview' for ch in w.winfo_children()):
                return
            mgr = w.winfo_manager()
            if mgr not in ("pack", "grid"):
                return
            master = w.master
            req_w = w.winfo_reqwidth()
            alloc_w = w.winfo_width()
            # Clipped: Tk gave it less than it asked for
            if req_w - alloc_w > 3 and alloc_w > 1:
                findings.append((where, "clipped", f"{label_of(w)} [{w.winfo_class()}] needs {req_w}px, got {alloc_w}px (parent {label_of(master)} {master.winfo_width()}px)"))
            # Off the right edge of its master
            if w.winfo_x() + req_w > master.winfo_width() + 3 and master.winfo_width() > 1:
                key = (str(w), "edge")
                if key not in seen:
                    seen.add(key)
                    findings.append((where, "off-edge", f"{label_of(w)} [{w.winfo_class()}] ends at {w.winfo_x() + req_w}px in a {master.winfo_width()}px parent ({label_of(master)})"))
        except tk.TclError:
            pass
        # Grid cell sharing
        try:
            cells = {}
            for ch in w.winfo_children():
                if ch.winfo_manager() == "grid" and ch.winfo_ismapped():
                    gi = ch.grid_info()
                    cells.setdefault((gi.get("row"), gi.get("column")), []).append(ch)
            for (r, c), kids in cells.items():
                if len(kids) > 1:
                    total = sum(k.winfo_reqwidth() for k in kids)
                    col_w = w.grid_bbox(c, r)[2] if w.grid_bbox(c, r) else w.winfo_width()
                    if total > col_w + 3:
                        findings.append((where, "overlap", f"cell r{r}c{c} of {label_of(w)}: " + " + ".join(label_of(k) for k in kids) + f" need {total}px in {col_w}px"))
        except tk.TclError:
            pass
    walk(root)


def scrims(app):
    return [w for w in app.winfo_children() if isinstance(w, tk.Frame) and str(w.cget("bg")) == bg.UI_HERO and w.winfo_manager() == "place"]


def btn(root, text):
    out = []
    def walk(w):
        if isinstance(w, (bg.ttk.Button, tk.Button)) and str(w.cget("text")) == text: out.append(w)
        for ch in w.winfo_children(): walk(ch)
    walk(root); return out


app = bg.BudgetApp(); app.state.onboarding_complete = True; app.state.tutorial_complete = True
app.geometry(f"{W}x{H}+0+0"); app.update(); time.sleep(0.4); app.update()
if getattr(app, "_setup_wizard_scrim", None): app._setup_wizard_scrim.destroy(); app._setup_wizard_scrim = None
today = date.today()
app.state.bills = [bg.Bill("Rent", 800.0, today + timedelta(days=5), "monthly", "essential", "bill", 0.0),
                   bg.Bill("Electricity", 518.0, today + timedelta(days=20), "quarterly", "essential", "bill", 0.0)]
app.state.funds = [bg.Fund("Holiday", 1000.0, today + timedelta(days=100), "important", 200.0, "auto", 0.0, "fund")]
app.state.goals = [bg.Goal("Emergency", 5000.0, None, 1, 500.0, "fixed", 50.0)]
app.refresh_all_views(); app.update()

# Pages
for page in ("today", "income", "transactions", "score", "setup", "collection", "character", "review", "homestead", "gerald", "settings"):
    app._show_page(page); app.update(); audit(app.page_frames[page], f"page:{page}")
for sub in ("plan", "bills", "funds", "goals", "investments", "rules", "accounts"):
    app._show_page("setup"); app._show_setup_sub(sub); app.update(); audit(app.setup_tab, f"setup:{sub}")

# Wizard steps
app._show_setup_wizard(); app.update()
for i in range(7):
    sc = app._setup_wizard_scrim; audit(sc, f"wizard:step{i + 1}")
    nb = btn(sc, "Next  →") or btn(sc, "Skip for now  →")
    if i < 6 and nb: nb[0].invoke(); app.update()
btn(app._setup_wizard_scrim, "Finish later")[0].invoke(); app.update()

# Sort card with bills + funds present, recurring-bill form open, flagged
def tx(d, desc, out): return bg.TransactionRecord(tx_date=d, description=desc, money_out=out, fingerprint=f"{d}|{desc}|{out}")
app.latest_import = [app.matcher.match(tx(today - timedelta(days=1), "ADOBE CREATIVE CLOUD 3", 29.99)), app.matcher.match(tx(today - timedelta(days=2), "COLES 123", 50.0))]
app.open_review_queue(); app.update(); rq = app._review_queue_scrim; audit(rq, "sort:overview")
btn(rq, "Start sorting  →")[0].invoke(); app.update(); audit(rq, "sort:card")
btn(rq, "Make it a recurring bill")[0].invoke(); app.update(); audit(rq, "sort:card+billform")
btn(rq, "Finish later")[0].invoke(); app.update()

# Allocation editor
app._show_allocation_editor(2000.0, today, "Pay"); app.update(); audit(app._allocation_editor_scrim, "alloc-editor")
btn(app._allocation_editor_scrim, "Cancel")[0].invoke(); app.update()

# Cost guide with rego selected
app._show_cost_guide("bill"); app.update(); sc = scrims(app)[-1]
lbl = [w for w in sc.winfo_children()]
def all_w(root):
    out = []
    def walk(w):
        out.append(w)
        for ch in w.winfo_children(): walk(ch)
    walk(root); return out
rl = [w for w in all_w(sc) if isinstance(w, tk.Label) and str(w.cget("text")) == "Car registration (QLD)"]
if rl: rl[0].event_generate("<Button-1>"); app.update()
audit(sc, "cost-guide"); btn(sc, "Close")[0].invoke(); app.update()

# Quick add overlay (each kind)
for k in ("bill", "fund", "goal"):
    app._show_quick_add(k); app.update(); sc = scrims(app)[-1]; audit(sc, f"quick-add:{k}"); btn(sc, "Cancel")[0].invoke(); app.update()

# Homestead decor section
app._show_page("homestead"); app.update(); app._expand_section("homestead.shop"); app.update(); audit(app.homestead_tab, "page:homestead+shop")

# Tier-up card
app._show_tier_up_card(2, ["comp_cat"]); app.update(); sc = scrims(app)[-1]; audit(sc, "tier-up"); btn(sc, "Later")[0].invoke(); app.update()

# Custom period overlay (Analysis)
app._show_page("review"); app.update(); app._show_review_custom_range(); app.update(); sc = scrims(app)[-1]; audit(sc, "review-custom"); btn(sc, "Cancel")[0].invoke(); app.update()
for _k in ("qtr", "fy"):
    app._review_set_period(_k); app.update(); audit(app.review_tab, "page:review:" + _k)

# Set up from statement (history mode)
from datetime import date as _d, timedelta as _td
_t = _d.today()
for n_, desc, out_, inn_, mt, cat in [(38, "ACME PAY", 0.0, 2400.0, "income", "Income"), (24, "ACME PAY", 0.0, 2400.0, "income", "Income"),
                                      (35, "NETFLIX.COM", 22.99, 0.0, "discretionary", "Subscription"), (5, "NETFLIX.COM", 22.99, 0.0, "discretionary", "Subscription"),
                                      (33, "COLES", 120.0, 0.0, "discretionary", "Groceries"), (31, "SHELL", 70.0, 0.0, "discretionary", "Fuel")]:
    app.state.transactions.append(bg.TransactionRecord(tx_date=_t - _td(days=n_), description=desc, money_out=out_, money_in=inn_, fingerprint=f"a{n_}{desc}", matched_type=mt, category=cat, user_verified=True, needs_review=False))
app.state.incomes.append(bg.IncomeEntry(2400.0, _t - _td(days=38), "Acme")); app.state.incomes.append(bg.IncomeEntry(2400.0, _t - _td(days=24), "Acme"))
app._show_statement_setup(); app.update(); sc = scrims(app)[-1]; audit(sc, "statement-setup"); btn(sc, "Done")[0].invoke(); app.update()

# Bank links editor
app.state.bank_links = [{"name": "CommBank", "url": "https://www.my.commbank.com.au/netbank/Logon/Logon.aspx", "every_days": 14, "last_opened": ""}]
app._show_bank_links_editor(); app.update(); sc = scrims(app)[-1]; audit(sc, "bank-links"); btn(sc, "Done")[0].invoke(); app.update()
app._show_page("transactions"); app.update(); audit(app.transactions_tab, "page:transactions+bank")

# Pact maker + savings challenges (Phase B)
app.state.game.gems = max(app.state.game.gems, 3); app.state.game.active_pact = {}
app._show_pact_maker(); app.update(); sc = scrims(app)[-1]; audit(sc, "pact-maker:reserve")
for kind_label in ("Keep a category under a cap this week", "Get a fund or goal to a number by a date", "No-spend days this week"):
    for w in all_w(sc):
        if isinstance(w, tk.Label) and str(w.cget("text")) == kind_label: w.event_generate("<Button-1>"); app.update(); break
    audit(sc, "pact-maker:" + kind_label[:12])
btn(sc, "Not today")[0].invoke(); app.update()
app._show_savings_challenges(); app.update(); sc = scrims(app)[-1]; audit(sc, "savings-challenges"); btn(sc, "Close")[0].invoke(); app.update()

# Bulk contribute + shortcuts
app._show_bulk_contribute(); app.update(); sc = scrims(app)[-1]; audit(sc, "bulk-contribute"); btn(sc, "Cancel")[0].invoke(); app.update()
app._show_shortcuts(); app.update(); sc = scrims(app)[-1]; audit(sc, "shortcuts"); btn(sc, "Close")[0].invoke(); app.update()

# Invest helper
app._show_invest_helper(); app.update(); sc = scrims(app)[-1]; audit(sc, "invest-helper"); btn(sc, "Close")[0].invoke(); app.update()

# Monthly report (needs last-month data)
prev = (today.replace(day=1) - timedelta(days=1)).replace(day=10)
app.state.incomes.append(bg.IncomeEntry(3000.0, prev, "Pay"))
app.state.transactions.append(bg.TransactionRecord(prev, "WOOLWORTHS", money_out=120.0, fingerprint="m1", matched_type="discretionary", category="Groceries", user_verified=True, needs_review=False))
app._show_monthly_report(prev.year, prev.month); app.update(); sc = scrims(app)[-1]; audit(sc, "monthly-report"); btn(sc, "Done  ✓")[0].invoke(); app.update()

# Pay-day ritual
alloc = app.engine.allocate_pay(2000.0, apply=False)
app._show_pay_day_ritual(2000.0, today, "Pay", alloc, {"points": 40, "level_up": False, "breakdown": ["x"], "gems_earned": 1, "completed_challenges": []}, bg.FORTUNE_CARDS[0] if isinstance(bg.FORTUNE_CARDS[0], dict) else {"title": "t", "text": "x", "symbol": "◆", "effect_type": "none"})
app.update(); sc = scrims(app)[-1]
for i in range(4):
    audit(sc, f"ritual:step{i + 1}")
    nb = btn(sc, "Next  →")
    if nb: nb[0].invoke(); app.update()
app.destroy()

seen = set()
for where, kind, msg in findings:
    key = (where, kind, msg[:60])
    if key in seen: continue
    seen.add(key)
    print(f"{where:22} {kind:9} {msg}")
print(f"--- {len(seen)} finding(s) at {W}x{H}")
