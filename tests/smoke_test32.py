"""Smoke test: a flawless first run — nothing pops over the sort queue (the welcome pack and the
tour wait until the screen is quiet), the overview says the pays will be confirmed after commit,
sort-card chips exclude Transfer/Bill/Fund/Ignore, bills get clean names, the confirmation step
asks 'Is this your pay?' (with source) and offers the statement's closing balance, the split
editor has '+ New category…', and the tour starts only once everything is closed."""
import os, sys, tempfile, time, csv
from datetime import date, timedelta

tmp = tempfile.mkdtemp(prefix="budget_firstrun_")
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


def toplevels(app):
    return [w for w in app.winfo_children() if isinstance(w, tk.Toplevel) and w.winfo_exists()]


today = date.today()
rows = []
d0 = today - timedelta(days=60)
for k in range(0, 61):
    d = d0 + timedelta(days=k)
    if (today - d).days % 14 == 3: rows.append((d, "ACME PTY LTD PAYROLL 00412", "", "2400.00"))
    if (today - d).days % 14 == 5: rows.append((d, "RENT RAY WHITE ASCOT", "800.00", ""))
    if d.day == 7: rows.append((d, "NETFLIX.COM MELBOURNE", "20.99", ""))
    if d.weekday() == 5: rows.append((d, "WOOLWORTHS 1234 CHERMSIDE", f"{130 + (k % 5) * 9:.2f}", ""))
    if d.weekday() == 2: rows.append((d, "BP CONNECT KEDRON", f"{55 + (k % 3) * 6:.2f}", ""))
rows.sort()
with open("statement.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f); w.writerow(["Date", "Description", "Debit", "Credit", "Balance"])
    bal = 3000.0
    for d, desc, deb, cred in rows:
        bal += float(cred or 0) - float(deb or 0)
        w.writerow([d.strftime("%d/%m/%Y"), desc, deb, cred, f"{bal:.2f}"])
closing = round(bal, 2)
csv_path = os.path.abspath("statement.csv")

app = bg.BudgetApp(); app.geometry("1366x768+0+0"); app.update(); time.sleep(0.5); app.update(); app.focus_force(); app.update()
app._celebrate = lambda *a, **k: None
app._show_tier_up_card = lambda *a, **k: None   # a real overlay the user would close; it would rightly delay the pack
opened = []
app._open_pack_animation = lambda *a, **k: opened.append(time.time())
import tkinter.simpledialog as sd
sd.askstring = lambda *a, **k: "Pets"
app.import_pdf_transactions = lambda: app._import_statement_path(csv_path)
sc = app._track_onboarding_scrim
assert not any("Typical pay" in t for t in texts(sc)), "no pay figure asked up front"
btn(sc, "Next  →")[0].invoke(); app.update()
btn(sc, "Import a statement now  (PDF / CSV / OFX)")[0].invoke(); app.update()
assert app.state.onboarding_complete
# 3 s: the sort queue is open and nothing else appears over it
t0 = time.time()
while time.time() - t0 < 3.2:
    app.update(); time.sleep(0.1)
rq = app._review_queue_scrim
assert rq is not None and rq.winfo_exists(), "sort queue should open after the import"
assert not opened and not toplevels(app) and not getattr(app, "_tutorial_overlay", None), "pack/tour must wait while sorting"
tt = texts(rq)
assert any("found — I'll ask you to confirm your pay after commit" in t for t in tt), [t for t in tt if "incoming" in t or "pay" in t]
assert not any("confirmed on Today after commit" in t for t in tt)
# sort: card chips exclude the structural categories
btn(rq, "Start sorting  →")[0].invoke(); app.update()
chips = [str(b.cget("text")) for b in all_w(rq) if isinstance(b, tk.Button)]
for bad in ("Transfer", "Bill", "Fund", "Ignore", "Income"):
    assert bad not in chips, chips
assert "Groceries" in chips
# rent → recurring bill with a clean name
for _ in range(12):
    tt = texts(rq)
    if any("Commit now" in t for t in tt):
        break
    if any("RENT RAY WHITE" in t for t in tt) and btn(rq, "Make it a recurring bill"):
        btn(rq, "Make it a recurring bill")[0].invoke(); app.update()
        btn(rq, "Create bill & link these  ✓")[0].invoke(); app.update(); continue
    g = [b for b in all_w(rq) if isinstance(b, tk.Button) and str(b.cget("text")) == "General"]
    g[0].invoke(); app.update()
assert any(b.name == "Rent Ray White" for b in app.state.bills), [b.name for b in app.state.bills]
btn(rq, "Commit now  ✓")[0].invoke(); app.update()
# the confirmation step opens; the tour and the pack still wait
t0 = time.time()
while time.time() - t0 < 2.5:
    app.update(); time.sleep(0.1)
ss = getattr(app, "_statement_setup_scrim", None)
assert ss is not None and ss.winfo_exists(), "confirmation step should open after the first commit"
assert not opened and not getattr(app, "_tutorial_overlay", None), "tour must not cover the confirmation step"
tt = texts(ss)
assert any(t == "IS THIS YOUR PAY?" for t in tt) and any(t.startswith("$2,400.00 fortnightly from Acme") for t in tt), [t for t in tt if "$" in t][:5]
assert any(t == "YOUR BALANCE" for t in tt) and any(t.startswith(f"${closing:,.2f} after the last row") for t in tt), [t for t in tt if "after" in t]
assert "Unknown" in app.state.expense_categories
btn(ss, "Yes, that's my pay  ✓")[0].invoke(); app.update()
assert app.state.pay_frequency == "fortnightly" and app.state.income_baseline == 2400.0
btn(ss, "Enter my accounts  ✓")[0].invoke(); app.update()
acc = app._accounts_now
assert acc["vars"]["spending"][1].get() == f"{closing:.2f}", "Everyday is prefilled with the statement's closing balance"
acc["vars"]["bills"][1].set("1200"); acc["vars"]["savings"][1].set("5000"); acc["vars"]["invest"][1].set("")
acc["save"](); app.update()
assert app.state.account_balances == {"spending": closing, "bills": 1200.0, "savings": 5000.0, "invest": 0.0}, app.state.account_balances
assert app.state.last_safe_to_spend == closing and app._accounts_now_scrim is None
app.refresh_today_tab(); app.update()
assert any(t == f"${closing:,.0f}" for t in texts(app._accounts_card_host)), texts(app._accounts_card_host)
assert any("Netflix" == t.split("  ·")[0] for t in tt), [t for t in tt if "Netflix" in t]
btn(ss, "Done  ✓")[0].invoke(); app.update()
# now the screen is quiet: pack first, then (after it closes) the tour
t0 = time.time()
while time.time() - t0 < 4.0 and not opened:
    app.update(); time.sleep(0.1)
assert opened, "welcome pack should come once the screen is quiet"
t0 = time.time()
while time.time() - t0 < 4.5 and not getattr(app, "_tutorial_overlay", None):
    app.update(); time.sleep(0.1)
assert getattr(app, "_tutorial_overlay", None), "tour should start after the pack"
# split editor: a visible '+ New category…' that creates one
t = next(x for x in app.state.transactions if "WOOLWORTHS" in x.description)
app._show_split_editor([t]); app.update()
ed = app._split_editor
assert bg.BudgetApp.NEW_CATEGORY_CHOICE in app._split_category_choices()
ed["rows"][0][0][0].set(bg.BudgetApp.NEW_CATEGORY_CHOICE)
app._ask_new_category()
assert "Pets" in app.state.expense_categories
app.destroy()
print("SMOKE TEST 32 PASSED")
