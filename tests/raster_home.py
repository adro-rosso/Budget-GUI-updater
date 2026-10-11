import os
"""Rasterise Homestead scenes (day / evening / night, rich and empty) and an
avatar with a companion, for visual inspection."""
import sys
from datetime import date, timedelta, datetime
import tkinter as tk
from PIL import Image, ImageDraw
sys.path.insert(0, r"C:\Users\User\AppData\Local\Temp\claude\c--Users-User-Desktop-Budget-GUI\188ef1a1-32b3-46d3-9733-0b178a5b0b38\scratchpad")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from raster import rasterise, _font
import budget_gui as bg

out = sys.argv[1]
st = bg.AppState(); today = date.today()
st.bills = [bg.Bill("Rent", 800.0, today + timedelta(days=5), "monthly", "essential", "bill", 800.0),
            bg.Bill("Power", 120.0, today - timedelta(days=3), "monthly", "essential", "bill", 0.0),
            bg.Bill("Phone", 60.0, today + timedelta(days=12), "monthly", "important", "bill", 60.0),
            bg.Bill("Internet", 80.0, today + timedelta(days=20), "monthly", "important", "bill", 40.0)]
st.funds = [bg.Fund("Holiday", 1000.0, today + timedelta(days=100), "important", 700.0, "auto", 0.0, "fund"),
            bg.Fund("Gifts", 0.0, None, "important", 520.0, "ongoing", 20.0, "fund"),
            bg.Fund("Car", 600.0, None, "important", 600.0, "buffer", 0.0, "fund"),
            bg.Fund("Clothes", 300.0, None, "optional", 0.0, "fixed", 30.0, "fund"),
            bg.Fund("Vet", 400.0, None, "important", 150.0, "buffer", 0.0, "fund")]
st.goals = [bg.Goal("Emergency", 5000.0, None, 1, 5000.0, "fixed", 50.0), bg.Goal("Savings", 0.0, None, 3, 2600.0, "percent_surplus", 10.0),
            bg.Goal("House", 30000.0, None, 2, 4000.0, "fixed", 100.0)]
for i in range(7):
    st.transactions.append(bg.TransactionRecord(today - timedelta(days=i), f"TX {i}", money_out=5.0, source_file=f"s{i}.pdf", fingerprint=f"fp{i}"))
st.transactions[0].flagged = True
st.game.level = 11; st.game.streak_pays = 4
st.incomes.append(bg.IncomeEntry(2000.0, today - timedelta(days=40), "Pay"))
eng = bg.HomesteadEngine(st)

root = tk.Tk(); root.withdraw()
tiles = []
for label, hour, streak in (("day", 10, 4), ("evening cloudy", 18, 1), ("night overcast", 22, 0)):
    st.game.streak_pays = streak
    sn = eng.snapshot(datetime(2026, 10, 7, hour, 0))
    c = tk.Canvas(root, width=640, height=320, bg="#14161c", highlightthickness=0)
    bg.draw_homestead(c, sn, 640, 320, 12)
    tiles.append((rasterise(c, 640, 320), f"{label} · tier {sn['tier']}"))
sn0 = bg.HomesteadEngine(bg.AppState()).snapshot(datetime(2026, 10, 7, 10, 0))
c = tk.Canvas(root, width=640, height=320, bg="#14161c", highlightthickness=0)
bg.draw_homestead(c, sn0, 640, 320, 0)
tiles.append((rasterise(c, 640, 320), "fresh profile"))
# mini + avatar with companion
c = tk.Canvas(root, width=220, height=58, bg="#14161c", highlightthickness=0)
st.game.streak_pays = 4
bg.draw_homestead(c, eng.snapshot(datetime(2026, 10, 7, 10, 0)), 220, 58, 0, mini=True)
mini = rasterise(c, 220, 58)
pad = Image.new("RGB", (640, 320), "#14161c"); pad.paste(mini, (10, 10))
x = 250
for comp in ("comp_hen", "comp_cat", "comp_fox", "comp_owl", "comp_dragonet"):
    cc = tk.Canvas(root, width=130, height=168, bg="#14161c", highlightthickness=0)
    eq = {"hair": "hair_short_dark", "eyes": "eyes_focused_brown", "outfit": "outfit_starter_hoodie", "background": "", "companion": comp}
    bg.draw_avatar(cc, eq, 130, 168, 0)
    im = rasterise(cc, 130, 168)
    pad.paste(im, (x if x + 130 <= 640 else 10, 80 if x + 130 <= 640 else 150)); x += 135
    if x + 130 > 640 and x < 700: x = 1000
tiles.append((pad, "today mini + companions"))
cols = 2; tw, th = 640, 320
rows = (len(tiles) + cols - 1) // cols
sheet = Image.new("RGB", (cols * (tw + 10), rows * (th + 26)), "#0c0d11")
d = ImageDraw.Draw(sheet)
for i, (im, label) in enumerate(tiles):
    xx, yy = (i % cols) * (tw + 10), (i // cols) * (th + 26)
    sheet.paste(im, (xx + 5, yy)); d.text((xx + 8, yy + th + 4), label, fill="#dee0e4", font=_font(5))
sheet.save(out); print("saved", out, sheet.size)
root.destroy()
