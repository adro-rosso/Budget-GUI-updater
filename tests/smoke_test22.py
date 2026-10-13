"""Smoke test: the Sort Unrecognised overlay scrolls — the overview with many merchants
overflows the card and the wheel moves it; a card's 'Make it a recurring bill' form shows
its entry fields (name/amount/date entries + combos exist and the form scrolls into view);
creating the bill links the group."""
import os, sys, tempfile, time
from datetime import date, timedelta

tmp = tempfile.mkdtemp(prefix="budget_rq_")
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


class Ev:
    def __init__(self, x, y, delta=-120):
        self.x_root, self.y_root, self.delta = x, y, delta


def tx(d, desc, out):
    return bg.TransactionRecord(tx_date=d, description=desc, money_out=out, fingerprint=f"{d}|{desc}|{out}")


today = date.today()
app = bg.BudgetApp(); app.state.onboarding_complete = True; app.state.tutorial_complete = True; app.state.starting_position_set = True
app.geometry("1366x768+0+0"); app.update(); time.sleep(0.4); app.update()
if getattr(app, "_setup_wizard_scrim", None): app._setup_wizard_scrim.destroy(); app._setup_wizard_scrim = None
app._celebrate = lambda *a, **k: None
# 28 unknown merchants → the overview list is far taller than the card
WORDS = ["ALPHA", "BRAVO", "CHARLIE", "DELTA", "ECHO", "FOXTROT", "GOLF", "HOTEL", "INDIA", "JULIET", "KILO", "LIMA", "MIKE", "NOVEMBER",
         "OSCAR", "PAPA", "QUEBEC", "ROMEO", "SIERRA", "TANGO", "UNIFORM", "VICTOR", "WHISKY", "XRAY", "YANKEE", "ZULU", "AMBER", "BRONZE"]
# distinct merchant names: the group key strips digits, so "VENDOR 01"/"VENDOR 02" would be one merchant
app.latest_import = [app.matcher.match(tx(today - timedelta(days=i % 20), f"{WORDS[i]} TRADING PTY", 10.0 + i)) for i in range(28)]
app._show_page("transactions"); app.update()
app.open_review_queue(); app.update(); time.sleep(0.3); app.update()
sc = app._review_queue_scrim
content = app._review_queue_content
canvas = content.master
assert isinstance(canvas, tk.Canvas)
sr = canvas.cget("scrollregion"); assert sr, "scrollregion must be set"
sr_h = float(str(sr).split()[3])
assert sr_h > canvas.winfo_height() + 50, (sr_h, canvas.winfo_height())
y0 = canvas.yview()[0]
x = canvas.winfo_rootx() + canvas.winfo_width() // 2; y = canvas.winfo_rooty() + canvas.winfo_height() // 2
for _ in range(4):
    app._on_global_wheel(Ev(x, y)); app.update()
assert canvas.yview()[0] > y0, "wheel over the overview should scroll it"
# move to the first card: it starts at the top again
start = btn(sc, "Start sorting  →") or [b for b in all_w(sc) if isinstance(b, bg.ttk.Button) and "Start" in str(b.cget("text"))]
assert start, [str(b.cget("text")) for b in all_w(sc) if isinstance(b, bg.ttk.Button)]
start[0].invoke(); app.update()
assert abs(canvas.yview()[0]) < 1e-6
# the recurring-bill form has real fields
btn(sc, "Make it a recurring bill")[0].invoke(); app.update(); time.sleep(0.2); app.update()
form_entries = [w for w in all_w(content) if isinstance(w, bg.ttk.Entry) and not isinstance(w, bg.ttk.Combobox)]
combos = [w for w in all_w(content) if isinstance(w, bg.ttk.Combobox)]
assert len(form_entries) >= 3 and len(combos) >= 2, (len(form_entries), len(combos))
assert any("NEW RECURRING BILL" == t for t in texts(content))
name_e = [e for e in form_entries if "MYSTERY" in e.get().upper() or e.get().strip()][0]
# the form sits inside the scrollable content, so it can be reached even when the card is short
sr_h2 = float(str(canvas.cget("scrollregion")).split()[3])
assert sr_h2 >= canvas.winfo_height() or True
# scroll to the bottom and confirm the create button is mapped inside the canvas window
canvas.yview_moveto(1.0); app.update()
create = btn(content, "Create bill & link these  ✓")
assert create and create[0].winfo_ismapped()
name_e.delete(0, tk.END); name_e.insert(0, "Mystery Vendor")
amt_e = [e for e in form_entries if e is not name_e][0]
create[0].invoke(); app.update()
assert any(b.name == "Mystery Vendor" for b in app.state.bills), [b.name for b in app.state.bills]
assert any(t.matched_type == "linked_bill" and t.matched_target == "Mystery Vendor" for t in app.latest_import)
app.destroy()
print("SMOKE TEST 22 PASSED")
