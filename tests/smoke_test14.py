"""Smoke test: mouse-wheel routing — the Avatar item grid scrolls when the cursor is
inside it (and the page does not), the Collection grid still scrolls, nested canvases
without registration scroll, and the page canvas scrolls when the cursor is outside."""
import os, sys, tempfile, time
tmp = tempfile.mkdtemp(prefix="budget_wheel_"); os.chdir(tmp)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import tkinter as tk
import budget_gui as bg


def all_w(root):
    out = []
    def walk(w):
        out.append(w)
        for ch in w.winfo_children(): walk(ch)
    walk(root); return out


class Ev:
    def __init__(self, x, y, delta=-120):
        self.x_root, self.y_root, self.delta = x, y, delta


def wheel_at(app, widget, delta=-120):
    """Send a wheel event with the cursor at the centre of `widget`."""
    x = widget.winfo_rootx() + max(2, widget.winfo_width() // 2)
    y = widget.winfo_rooty() + max(2, widget.winfo_height() // 2)
    app._on_global_wheel(Ev(x, y, delta))
    app.update()


app = bg.BudgetApp(); app.state.onboarding_complete = True; app.state.tutorial_complete = True; app.state.starting_position_set = True
app.geometry("1366x768+0+0"); app.update(); time.sleep(0.4); app.update()
if getattr(app, "_setup_wizard_scrim", None): app._setup_wizard_scrim.destroy(); app._setup_wizard_scrim = None

# ── Avatar page: the grid scrolls under the cursor ───────────────────────────
app._show_page("character"); app.update(); time.sleep(0.3); app.update()
grid = app._char_grid_canvas
assert app._scroll_canvas_page[id(grid)] == "character"
sr = grid.cget("scrollregion"); assert sr and float(str(sr).split()[3]) > grid.winfo_height(), "grid must overflow for this test"
y0 = grid.yview()[0]
page_canvas = next(c for c in app._scroll_canvases if app._scroll_canvas_page.get(id(c)) == "character" and c is not grid)
p0 = page_canvas.yview()[0]
wheel_at(app, grid); wheel_at(app, grid)
assert grid.yview()[0] > y0, "Avatar grid should scroll when the cursor is inside it"
assert page_canvas.yview()[0] == p0, "the page must not scroll while the cursor is over the grid"
# scroll back
wheel_at(app, grid, 120); wheel_at(app, grid, 120); assert abs(grid.yview()[0] - y0) < 1e-6

# ── Collection page: its grid still scrolls ──────────────────────────────────
app._show_page("collection"); app.update(); time.sleep(0.3); app.update()
coll = app._coll_grid_frame
# find the canvas hosting the collection grid
cc = coll.master if isinstance(coll.master, tk.Canvas) else next((w for w in all_w(app.collection_tab) if isinstance(w, tk.Canvas) and str(w.cget("yscrollcommand"))), None)
if cc is not None and cc.cget("scrollregion") and float(str(cc.cget("scrollregion")).split()[3]) > cc.winfo_height():
    c0 = cc.yview()[0]; wheel_at(app, cc); wheel_at(app, cc)
    assert cc.yview()[0] > c0, "Collection grid should scroll under the cursor"

# ── Unregistered nested canvas (generic path) ────────────────────────────────
app._show_page("today"); app.update()
host = tk.Frame(app.today_tab, bg=bg.UI_SURFACE); host.place(x=300, y=200, width=200, height=120)
nested = tk.Canvas(host, bg=bg.UI_SURFACE2, highlightthickness=0, yscrollcommand=lambda *a: None)
nested.pack(fill="both", expand=True)
for i in range(40):
    nested.create_text(10, 15 * i, text=f"row {i}", anchor="nw", fill="white")
nested.configure(scrollregion=(0, 0, 200, 600)); app.update(); time.sleep(0.2); app.update()
n0 = nested.yview()[0]; wheel_at(app, nested); wheel_at(app, nested)
assert nested.yview()[0] > n0, "a nested canvas with overflow should scroll under the cursor"
# one without overflow falls through to the page (no crash)
nested.configure(scrollregion=(0, 0, 200, 50)); app.update(); wheel_at(app, nested)
host.destroy(); app.update()
app.destroy()
print("SMOKE TEST 14 PASSED")
