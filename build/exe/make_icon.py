# -*- coding: utf-8 -*-
"""生成应用图标 build\exe\app.ico（多尺寸，蓝紫渐变圆角方块 + 白色「梦」）。"""
import os
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "app.ico")
PREVIEW = os.path.join(HERE, "app_icon_preview.png")

S = 1024                  # 先大图再缩小，边缘干净
R = int(S * 0.225)        # 圆角半径
C1 = (47, 111, 237)       # #2f6fed
C2 = (123, 47, 247)       # #7b2ff7


def gradient(size):
    """对角线性渐变。"""
    w = h = size
    base = Image.new("RGB", (w, h))
    px = base.load()
    for y in range(h):
        for x in range(w):
            t = (x / (w - 1.0) + y / (h - 1.0)) / 2.0
            t = t ** 0.92
            px[x, y] = (
                int(C1[0] + (C2[0] - C1[0]) * t),
                int(C1[1] + (C2[1] - C1[1]) * t),
                int(C1[2] + (C2[2] - C1[2]) * t),
            )
    return base


def rounded_mask(size, radius):
    m = Image.new("L", (size, size), 0)
    d = ImageDraw.Draw(m)
    d.rounded_rectangle([0, 0, size - 1, size - 1], radius=radius, fill=255)
    return m


img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
img.paste(gradient(S), (0, 0), rounded_mask(S, R))

# 顶部高光（垂直渐隐，不留硬边）
gloss_alpha = Image.new("L", (1, S), 0)
for y in range(S):
    t = y / (S - 1.0)
    a = int(34 * max(0.0, 1.0 - (t / 0.55)) ** 1.4) if t < 0.55 else 0
    gloss_alpha.putpixel((0, y), a)
gloss_alpha = gloss_alpha.resize((S, S))
gloss = Image.new("RGBA", (S, S), (255, 255, 255, 0))
gloss.putalpha(gloss_alpha)
gloss.putdata([(255, 255, 255, a) for a in gloss_alpha.getdata()])
gloss = Image.composite(gloss, Image.new("RGBA", (S, S), (0, 0, 0, 0)), rounded_mask(S, R))
img = Image.alpha_composite(img, gloss)

# 内描边
edge = Image.new("RGBA", (S, S), (0, 0, 0, 0))
ed = ImageDraw.Draw(edge)
ed.rounded_rectangle([2, 2, S - 3, S - 3], radius=R - 2, outline=(255, 255, 255, 70), width=4)
img = Image.alpha_composite(img, edge)

# 「梦」字
FONT = r"C:\Windows\Fonts\msyhbd.ttc"
glyph = "梦"
size = int(S * 0.60)
font = ImageFont.truetype(FONT, size, index=0)
# 微调：让字形视觉居中
tmp = Image.new("RGBA", (S, S), (0, 0, 0, 0))
d = ImageDraw.Draw(tmp)
bbox = d.textbbox((0, 0), glyph, font=font)
gw, gh = bbox[2] - bbox[0], bbox[3] - bbox[1]
x = (S - gw) / 2 - bbox[0]
y = (S - gh) / 2 - bbox[1] - int(S * 0.005)
d.text((x, y), glyph, font=font, fill=(255, 255, 255, 255))
# 柔和投影
sh = tmp.filter(__import__("PIL.ImageFilter", fromlist=["ImageFilter"]).GaussianBlur(int(S * 0.012)))
sh_col = Image.new("RGBA", (S, S), (0, 0, 0, 0))
sh_col.paste((20, 10, 60, 110), (0, 0), sh.split()[3])
img = Image.alpha_composite(img, Image.blend(Image.new("RGBA", (S, S), (0, 0, 0, 0)), sh_col, 1.0))
img = Image.alpha_composite(img, tmp)

SIZES = [256, 128, 96, 64, 48, 32, 24, 16]
frames = []
for s in SIZES:
    frames.append(img.resize((s, s), Image.LANCZOS))
frames[0].save(OUT, format="ICO", sizes=[(s, s) for s in SIZES])
img.resize((256, 256), Image.LANCZOS).save(PREVIEW)

print("ico: %s  %d bytes" % (OUT, os.path.getsize(OUT)))
