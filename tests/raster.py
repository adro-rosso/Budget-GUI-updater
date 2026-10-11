import os
"""Rasterise Tk canvas items into a PIL image (no screen capture needed).
Approximates smoothed polygons as straight polygons."""
import sys, math
import tkinter as tk
from PIL import Image, ImageDraw, ImageFont
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import budget_gui as bg

SCALE = 2  # supersample for nicer output


def _font(size):
    try:
        return ImageFont.truetype("segoeui.ttf", max(6, int(size * SCALE)))
    except Exception:
        return ImageFont.load_default()


def rasterise(canvas, w, h, bgcol="#14161c"):
    img = Image.new("RGB", (w * SCALE, h * SCALE), bgcol)
    d = ImageDraw.Draw(img)
    for item in canvas.find_all():
        typ = canvas.type(item)
        co = [c * SCALE for c in canvas.coords(item)]
        def opt(name, default=""):
            try:
                v = canvas.itemcget(item, name)
                return v if v != "" else default
            except tk.TclError:
                return default
        fill = opt("fill") or None
        outline = opt("outline") or None
        try:
            width = max(1, int(round(float(opt("width", "1")) * SCALE)))
        except ValueError:
            width = SCALE
        if fill and not fill.startswith("#"):
            fill = None if fill == "" else fill
        if outline and not outline.startswith("#"):
            outline = None
        try:
            if typ == "oval":
                x1, y1, x2, y2 = co
                d.ellipse((min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2)), fill=fill, outline=outline, width=width if outline else 0)
            elif typ == "rectangle":
                x1, y1, x2, y2 = co
                d.rectangle((min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2)), fill=fill, outline=outline, width=width if outline else 0)
            elif typ == "arc":
                x1, y1, x2, y2 = co
                box = (min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2))
                start = float(opt("start", "0")); extent = float(opt("extent", "90"))
                style = opt("style", "pieslice")
                # Tk: counter-clockwise from 3 o'clock; PIL: clockwise from 3 o'clock
                a0, a1 = -start - extent, -start
                if extent < 0:
                    a0, a1 = -start, -start - extent
                if style == "arc":
                    d.arc(box, a0, a1, fill=outline or fill, width=width)
                elif style == "chord":
                    d.chord(box, a0, a1, fill=fill, outline=outline, width=width if outline else 0)
                else:
                    d.pieslice(box, a0, a1, fill=fill, outline=outline, width=width if outline else 0)
            elif typ == "polygon":
                pts = list(zip(co[0::2], co[1::2]))
                if len(pts) >= 3:
                    d.polygon(pts, fill=fill, outline=outline)
                    if outline and width > SCALE:
                        d.line(pts + [pts[0]], fill=outline, width=width, joint="curve")
            elif typ == "line":
                pts = list(zip(co[0::2], co[1::2]))
                if len(pts) >= 2:
                    d.line(pts, fill=fill, width=width, joint="curve")
            elif typ == "text":
                x, y = co
                txt = opt("text")
                fnt = opt("font")
                size = 9
                try:
                    parts = fnt.replace("{", "").replace("}", "").split()
                    for p in parts:
                        if p.lstrip("-").isdigit():
                            size = abs(int(p)); break
                except Exception:
                    pass
                f = _font(size)
                bb = d.textbbox((0, 0), txt, font=f)
                d.text((x - (bb[2] - bb[0]) / 2, y - (bb[3] - bb[1]) / 2), txt, fill=fill or "#ffffff", font=f)
        except Exception as e:
            print("skip", typ, e)
    return img.resize((w, h), Image.LANCZOS)


def main():
    out, mode = sys.argv[1], sys.argv[2]
    root = tk.Tk(); root.withdraw()
    tiles = []
    if mode == "gerald":
        for e in ["normal", "wink", "happy", "thinking", "shocked", "proud", "sleepy"]:
            c = tk.Canvas(root, width=180, height=240, bg="#14161c", highlightthickness=0)
            bg._draw_gerald(c, 180, 240, expression=e)
            tiles.append((rasterise(c, 180, 240), e))
        for (w, h, e, blink) in [(60, 80, "normal", False), (60, 80, "normal", True), (120, 150, "wink", False), (44, 58, "happy", False)]:
            c = tk.Canvas(root, width=w, height=h, bg="#14161c", highlightthickness=0)
            bg._draw_gerald(c, w, h, expression=e, blink=blink)
            im = rasterise(c, w, h)
            pad = Image.new("RGB", (180, 240), "#14161c"); pad.paste(im, (0, 0))
            tiles.append((pad, f"{w}x{h} {e}{' blink' if blink else ''}"))
        tw, th = 180, 240
    else:
        looks = [
            ({"hair": "hair_starfall_mane", "eyes": "eyes_eclipse", "outfit": "outfit_astronaut", "background": "background_golden_hour", "aura": "aura_nebula_veil", "accessory": "acc_coin_crown"}, "proud", 30),
            ({"hair": "hair_neon_undercut", "eyes": "eyes_prism", "outfit": "outfit_kimono_dawn", "background": "background_rainy_window", "aura": "aura_frost_halo", "accessory": "acc_headphones"}, "happy", 10),
            ({"hair": "hair_afro_halo", "eyes": "eyes_rose_quartz", "outfit": "outfit_pinstripe", "background": "background_library", "aura": "aura_ledger_lines", "accessory": "acc_monocle"}, "neutral", 0),
            ({"hair": "hair_silver_fox", "eyes": "eyes_storm_grey", "outfit": "outfit_hi_vis", "background": "background_skyline_dawn", "aura": "aura_coin_rain", "accessory": "acc_gold_chain"}, "worried", 5),
            ({"hair": "hair_top_knot", "eyes": "eyes_dreamer", "outfit": "outfit_chef_whites", "background": "background_beach_dusk", "aura": "aura_ember_drift", "accessory": "acc_flower_crown"}, "happy", 46),
            ({"hair": "hair_short_dark", "eyes": "eyes_focused_brown", "outfit": "outfit_starter_hoodie", "background": "", "aura": "", "accessory": ""}, "neutral", 1),
            ({"hair": "hair_long_flow", "eyes": "eyes_round_hazel", "outfit": "outfit_business", "background": "background_cityscape", "aura": "aura_soft_glow", "accessory": "acc_glasses"}, "happy", 3),
            ({"hair": "hair_twin_tails", "eyes": "eyes_cool_shades", "outfit": "outfit_leather_jacket", "background": "background_mountain", "aura": "aura_cosmic", "accessory": "acc_dragon_horns"}, "proud", 12),
        ]
        for eq, mood, frame in looks:
            c = tk.Canvas(root, width=260, height=340, bg="#14161c", highlightthickness=0)
            bg.draw_avatar(c, eq, 260, 340, frame, mood=mood)
            tiles.append((rasterise(c, 260, 340), f"{mood} f{frame}"))
        tw, th = 260, 340
    cols = 4
    rows = (len(tiles) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * (tw + 10), rows * (th + 26)), "#0c0d11")
    d = ImageDraw.Draw(sheet)
    for i, (im, label) in enumerate(tiles):
        x, y = (i % cols) * (tw + 10), (i // cols) * (th + 26)
        sheet.paste(im, (x + 5, y))
        d.text((x + 8, y + th + 4), label, fill="#dee0e4", font=_font(5))
    sheet.save(out); print("saved", out, sheet.size)
    root.destroy()


if __name__ == "__main__":
    main()
