# Ai Mei — 中药液 (шөп тұнбасы) ақпараттық рилс. 1080x1920, 30fps.
# Іске қосу: python3 render.py  ->  out/aimei_reels.mp4
import math, os, re, subprocess, sys, wave
from functools import lru_cache
from multiprocessing import Pool
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
A = lambda *p: os.path.join(HERE, 'assets', *p)
OUT = os.path.join(HERE, 'out')
W, H, FPS = 1080, 1920, 30
DUR = 26.0

PURPLE, LIME, WHITE, BLACK = (108, 59, 255), (198, 244, 50), (255, 255, 255), (0, 0, 0)
GRAY = (150, 150, 150)
F_BLACK = A('Montserrat-Black.ttf')
F_XB = A('Montserrat-ExtraBold.ttf')
F_INTER = '/usr/share/fonts/opentype/inter/Inter-SemiBold.otf'
F_CJK = '/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc'

# ---------------------------------------------------------------- сценарий
# (басы, соңы, фото, zoom_from, zoom_to, фокус_y 0..1)
SCENES = [
    (0.0, 3.0, 'p2_product_close', 1.12, 1.00, 0.55),   # хук
    (3.0, 6.5, 'p3_sign', 1.00, 1.08, 0.40),            # бренд-экран (карточкада)
    (6.5, 10.0, 'p2_product_close', 1.00, 1.10, 0.45),  # кілт сөз
    (10.0, 16.0, 'p3_sign', 1.00, 1.08, 0.50),          # қадамдар
    (16.0, 20.5, 'p1_product_wide', 1.18, 1.05, 0.62),  # тізім
    (20.5, DUR, 'p1_product_wide', 1.00, 1.10, 0.70),   # CTA
]
SUBS = [
    (0.3, 2.9, 'Қытай шөптерінен — дайын тұнба', ['шөптерінен', 'тұнба']),
    (3.2, 6.3, 'Ai Mei — қытай дәстүрлі медицина орталығы', ['ai', 'mei']),
    (6.6, 9.8, 'Біздегі жаңалық — дәстүрлі шөп тұнбасы', ['жаңалық', 'тұнбасы']),
    (10.1, 11.9, 'Алдымен шөптер мұқият іріктеледі', ['іріктеледі']),
    (12.1, 13.9, 'Содан кейін ұзақ қайнатылады', ['қайнатылады']),
    (14.1, 15.9, 'Соңында ыңғайлы пакетке құйылады', ['пакетке']),
    (16.2, 18.2, 'Ішуге ыңғайлы, құрамы табиғи шөптен', ['ыңғайлы', 'табиғи']),
    (18.3, 20.4, 'Сөмкеге салып, кез келген жерде ішесіз', ['кез', 'келген', 'жерде']),
    (20.7, 23.0, 'Сізге қай тұнба сәйкес келеді?', ['сәйкес']),
    (23.1, 25.4, 'Ai Mei орталығында маманнан кеңес алыңыз', ['маманнан', 'кеңес']),
]
STEPS = [(10.0, 'Шөпті іріктеу', 'herb'), (12.0, 'Ұзақ қайнату', 'fire'), (14.0, 'Пакетке құю', 'package')]
LIST = [(16.35, 'Ішуге ыңғайлы', 'tea', LIME, BLACK, -4),
        (17.35, 'Табиғи құрам', 'seedling', WHITE, BLACK, 4),
        (18.45, 'Әрқашан қасыңызда', 'backpack', PURPLE, WHITE, -3)]
BRAND = (3.0, 6.5)
HOOK_W1, HOOK_W2 = 'ШӨП', 'ТҰНБА'
SFX = []  # (уақыт, түрі) — төменде толтырылады


def sfx_events():
    ev = [(0.0, 'whoosh')]
    for i in range(len(HOOK_W1)): ev.append((0.15 + i * 0.07, 'tick'))
    ev.append((0.75, 'whoosh'))
    for i in range(len(HOOK_W2)): ev.append((0.95 + i * 0.07, 'tick'))
    ev += [(0.45, 'pop'), (1.25, 'pop')]
    for s in SCENES[1:]: ev.append((s[0] - 0.05, 'whoosh'))
    ev += [(3.45, 'pop'), (3.6, 'pop'), (3.85, 'pop'), (6.75, 'pop'), (6.95, 'pop2'), (8.0, 'pop')]
    ev += [(t + 0.05, 'pop2') for t, *_ in STEPS]
    ev += [(t, 'pop') for t, *_ in LIST]
    ev += [(20.8, 'pop'), (21.0, 'pop2'), (21.25, 'pop2'), (21.6, 'pop')]
    return ev


# ---------------------------------------------------------------- easing
def clamp(x, a=0.0, b=1.0): return max(a, min(b, x))
def ease_out(x): x = clamp(x); return 1 - (1 - x) ** 3
def back_out(x, s=2.0): x = clamp(x); return 1 + (s + 1) * (x - 1) ** 3 + s * (x - 1) ** 2
def pop(x):
    """scale 0 -> 110 -> 100%"""
    x = clamp(x)
    if x < 0.62: return 1.1 * ease_out(x / 0.62)
    return 1.1 - 0.1 * ease_out((x - 0.62) / 0.38)
APPEAR = 0.28


# ---------------------------------------------------------------- графика
@lru_cache(None)
def font(path, size): return ImageFont.truetype(path, size)


@lru_cache(None)
def emoji(key, size):
    return Image.open(A('emoji', key + '.png')).convert('RGBA').resize((size, size), Image.LANCZOS)


@lru_cache(None)
def photo(name):
    im = Image.open(A('photos', name + '.jpg')).convert('RGB')
    return im.resize((int(W * 1.2), int(H * 1.2)), Image.LANCZOS)  # 9:16, zoom-ға қор


def bg_frame(t):
    for i, (a, b, name, z0, z1, fy) in enumerate(SCENES):
        if a <= t < b or i == len(SCENES) - 1:
            break
    p = (t - a) / (b - a)
    z = z0 + (z1 - z0) * (p * p * (3 - 2 * p))
    z *= 1 + 0.06 * (1 - ease_out((t - a) / 0.35)) if i else 1  # кесуде жеңіл «punch»
    src = photo(name)
    sw, sh = src.size
    cw, ch = sw / 1.2 / z, sh / 1.2 / z
    cx = sw / 2
    cy = clamp(fy * sh, ch / 2, sh - ch / 2)
    box = (cx - cw / 2, cy - ch / 2, cx + cw / 2, cy + ch / 2)
    return src.resize((W, H), Image.BILINEAR, box=box).convert('RGBA')


def shadowed(im, off=6, blur=10, alpha=0.55):
    pad = blur * 2 + off
    out = Image.new('RGBA', (im.width + pad * 2, im.height + pad * 2), (0, 0, 0, 0))
    sh = Image.new('RGBA', out.size, (0, 0, 0, 0))
    a = im.split()[3].point(lambda v: int(v * alpha))
    sh.paste((0, 0, 0, 255), (pad, pad + off), a)
    sh = sh.filter(ImageFilter.GaussianBlur(blur))
    out.alpha_composite(sh)
    out.alpha_composite(im, (pad, pad))
    return out


@lru_cache(None)
def text_img(text, path, size, color, shadow=True, maxw=None):
    f = font(path, size)
    if maxw:
        while f.getlength(text) > maxw and size > 20:
            size -= 4; f = font(path, size)
    l, t, r, b = f.getbbox(text)
    im = Image.new('RGBA', (r - l + 8, b - t + 8), (0, 0, 0, 0))
    ImageDraw.Draw(im).text((4 - l, 4 - t), text, font=f, fill=color)
    return shadowed(im) if shadow else im


@lru_cache(None)
def pill_img(text, ekey, bg, fg, size=46, eh=78):
    f = font(F_INTER, size)
    tw = int(f.getlength(text))
    h = 104
    w = 28 + eh + 16 + tw + 36
    im = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((0, 0, w - 1, h - 1), radius=h // 2, fill=bg + (255,))
    im.alpha_composite(emoji(ekey, eh), (24, (h - eh) // 2))
    l, t, r, b = f.getbbox(text)
    d.text((28 + eh + 16, (h - (b - t)) // 2 - t), text, font=f, fill=fg)
    return shadowed(im, off=8, blur=14, alpha=0.35)


def place(canvas, im, cx, cy, scale=1.0, rot=0.0, alpha=1.0, anchor='c'):
    if scale <= 0.01 or alpha <= 0.01: return
    if scale != 1.0:
        im = im.resize((max(1, int(im.width * scale)), max(1, int(im.height * scale))), Image.BICUBIC)
    if rot: im = im.rotate(rot, Image.BICUBIC, expand=True)
    if alpha < 1: im = im.copy(); im.putalpha(im.split()[3].point(lambda v: int(v * alpha)))
    x = cx - im.width // 2 if anchor == 'c' else cx
    canvas.alpha_composite(im, (int(x), int(cy - im.height // 2))) if 0 else _paste(canvas, im, int(x), int(cy - im.height // 2))


def _paste(canvas, im, x, y):
    # шекарадан шыққанда да қауіпсіз
    x0, y0 = max(0, x), max(0, y)
    x1, y1 = min(W, x + im.width), min(H, y + im.height)
    if x1 <= x0 or y1 <= y0: return
    canvas.alpha_composite(im.crop((x0 - x, y0 - y, x1 - x, y1 - y)), (x0, y0))


@lru_cache(None)
def gradient(color, a0, h):
    g = np.zeros((h, W, 4), np.uint8)
    g[..., :3] = color
    g[..., 3] = (a0 * 255 * (1 - np.linspace(0, 1, h)) ** 1.4)[:, None]
    return Image.fromarray(g, 'RGBA')


@lru_cache(None)
def arrow_img(color, w=56, h=64):
    im = Image.new('RGBA', (w + 16, h + 16), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    s = w // 3
    d.rounded_rectangle((8 + w // 2 - s // 2, 8, 8 + w // 2 + s // 2, 8 + h * 0.55), radius=6, fill=color)
    d.polygon([(8, 8 + h * 0.45), (8 + w, 8 + h * 0.45), (8 + w // 2, 8 + h)], fill=color)
    return shadowed(im, off=4, blur=6, alpha=0.4)


def bounce(t, f=1.6, amp=16): return -abs(math.sin(2 * math.pi * f * t)) * amp


# ---------------------------------------------------------------- субтитр (караоке)
SUB_FONT, SUB_Y, SUB_MAXW = 44, 1350, 900


def norm(w): return re.sub(r'[^\w-]', '', w.lower())


@lru_cache(None)
def sub_layout(i):
    a, b, text, keys = SUBS[i]
    words = text.split()
    f = font(F_INTER, SUB_FONT)
    sp = f.getlength(' ')
    lines, cur, cw = [], [], 0
    for wd in words:
        ww = f.getlength(wd)
        if cur and cw + sp + ww > SUB_MAXW:
            lines.append(cur); cur, cw = [], 0
        cur.append(wd); cw += (sp if cw else 0) + ww
    lines.append(cur)
    if len(lines) == 1 and len(words) > 4 and f.getlength(text) > 620:  # 2 жолға теңдеп бөлу
        half = f.getlength(text) / 2; acc = 0
        for k, wd in enumerate(words):
            acc += f.getlength(wd) + sp
            if acc >= half: lines = [words[:k + 1], words[k + 1:]]; break
    # сөз уақыттары — әріп санына пропорционал
    lens = [len(w) + 2 for w in words]
    tot = sum(lens); span = (b - a) * 0.88
    starts, acc = [], a
    for L in lens: starts.append(acc); acc += span * L / tot
    return lines, starts, [norm(w) in keys for w in words]


def draw_subs(canvas, t):
    for i, (a, b, *_rest) in enumerate(SUBS):
        if a - 0.05 <= t < b + 0.1: break
    else:
        return
    lines, starts, iskey = sub_layout(i)
    f = font(F_INTER, SUB_FONT)
    sp = f.getlength(' ')
    lh = 62
    widths = [sum(f.getlength(w) for w in ln) + sp * (len(ln) - 1) for ln in lines]
    bw, bh = int(max(widths) + 64), int(lh * len(lines) + 40)
    k = back_out((t - a + 0.05) / 0.25, 1.4)
    plate = Image.new('RGBA', (bw, bh), (0, 0, 0, 0))
    d = ImageDraw.Draw(plate)
    d.rounded_rectangle((0, 0, bw - 1, bh - 1), radius=30, fill=(0, 0, 0, 115))  # чёрный 45%
    wi = 0
    for li, ln in enumerate(lines):
        x = (bw - widths[li]) / 2
        y = 20 + li * lh + 4
        for wd in ln:
            said = t >= starts[wi]
            col = (LIME if iskey[wi] else WHITE) if said else GRAY
            d.text((x, y), wd, font=f, fill=col)
            x += f.getlength(wd) + sp; wi += 1
    place(canvas, plate, W // 2, SUB_Y, scale=0.85 + 0.15 * k, alpha=clamp(k))


# ---------------------------------------------------------------- блоктар
def draw_hook(c, t):
    if t >= 3.0: return
    fade = 1 - clamp((t - 2.8) / 0.2)
    c.alpha_composite(gradient(PURPLE, 0.92 * fade, 980))
    for word, col, y, t0 in ((HOOK_W1, WHITE, 270, 0.15), (HOOK_W2, LIME, 575, 0.95)):
        f = font(F_BLACK, 190)
        total = f.getlength(word)
        x = W / 2 - total / 2
        for i, ch in enumerate(word):
            lt = t - (t0 + i * 0.07)
            gw = f.getlength(ch)
            if lt > 0:
                im = text_img(ch, F_BLACK, 190, col)
                place(c, im, x + gw / 2, y + 50 * (1 - back_out(lt / APPEAR)), scale=pop(lt / APPEAR), alpha=fade)
            x += gw
    lt = t - 0.7
    if lt > 0:
        place(c, arrow_img(WHITE), W // 2, 425 + bounce(t, 1.2, 8), scale=pop(lt / APPEAR), alpha=fade)
    for key, x, y, t0, rot in (('herb', 150, 250, 0.45, 10), ('tea', 930, 790, 1.25, -8)):
        lt = t - t0
        if lt > 0:
            place(c, shadowed(emoji(key, 190), 8, 12, 0.35), x, y + bounce(lt, 1.4, 20),
                  scale=pop(lt / APPEAR), rot=rot, alpha=fade)


@lru_cache(None)
def card_mask(w, h, r):
    m = Image.new('L', (w, h), 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, w - 1, h - 1), radius=r, fill=255)
    return m


def brand_screen(bg, t):
    a, b = BRAND
    if not (a <= t < b): return bg
    lt, rt = t - a, b - t
    k = back_out(lt / 0.38, 1.6) if lt < rt else back_out(rt / 0.32, 1.2)
    k = clamp(k, 0, 1.08)
    c = Image.new('RGBA', (W, H), LIME + (255,))
    sc = 1 - 0.44 * k
    rot = -5 * k
    cw, ch = int(W * sc), int(H * sc)
    card = bg.resize((cw, ch), Image.BILINEAR)
    r = int(40 + 20 * k)
    card.putalpha(card_mask(cw, ch, r))
    cy = H / 2 + (1090 - H / 2) * clamp(k)
    cx = W / 2 + 30 * clamp(k)
    if k > 0.05:
        sh = Image.new('RGBA', (cw + 120, ch + 120), (0, 0, 0, 0))
        ImageDraw.Draw(sh).rounded_rectangle((60, 60, 60 + cw, 60 + ch), radius=r, fill=(0, 0, 0, int(110 * clamp(k))))
        sh = sh.resize((sh.width // 4, sh.height // 4)).filter(ImageFilter.GaussianBlur(7)).resize(sh.size)
        place(c, sh, cx + 18, cy + 30, rot=rot)
    place(c, card, cx, cy, rot=rot)
    # заголовок + таблетка
    vis = clamp(rt / 0.25)
    for t0, fn in ((0.25, lambda s, al: place(c, text_img('AI MEI', F_BLACK, 160, BLACK, False), 70, 205, s, 0, al, 'l')),
                   (0.40, lambda s, al: place(c, text_img('爱美', F_CJK, 140, BLACK, False), 735, 210, s, 0, al, 'l')),
                   (0.60, lambda s, al: place(c, pill_img('Қытай медицинасы орталығы', 'leaf', BLACK, WHITE, 42), 62, 375, s, -2, al, 'l')),
                   (0.85, lambda s, al: place(c, shadowed(emoji('rocket', 170), 8, 12, .35), 905 + 0 * s, 600 + bounce(t, 1.3, 22), s, 0, al))):
        x = lt - t0
        if x > 0: fn(pop(x / APPEAR), vis)
    return c


def draw_keyword(c, t):
    a, b = 6.5, 10.0
    if not (a <= t < b): return
    lt = t - a
    out = clamp((b - t) / 0.2)
    c.alpha_composite(gradient(BLACK, 0.6 * ease_out(lt / 0.3) * out, 900))
    if lt > 0.1:
        place(c, text_img('біздегі жаңалық', F_INTER, 52, WHITE), W // 2, 300, pop((lt - 0.1) / APPEAR), alpha=out)
    for i, (w, y) in enumerate((('ШӨП', 470), ('ТҰНБАСЫ', 650))):
        x = lt - 0.3 - i * 0.18
        if x > 0:
            place(c, text_img(w, F_BLACK, 200, LIME, True, 980), W // 2, y + 40 * (1 - back_out(x / APPEAR)),
                  pop(x / APPEAR), alpha=out)
    x = lt - 0.7
    if x > 0:
        tw = 0.8 + 0.25 * (0.5 + 0.5 * math.sin(t * 9))
        place(c, emoji('sparkles', 130), 960, 395, pop(x / APPEAR) * tw, rot=12 * math.sin(t * 4),
              alpha=out * (0.65 + 0.35 * abs(math.sin(t * 7))))
        place(c, emoji('sparkles', 80), 110, 560, pop(x / APPEAR) * (1.9 - tw), rot=-10 * math.sin(t * 5), alpha=out * 0.9)
    x = t - 8.0
    if x > 0:
        place(c, pill_img('Дәстүрлі рецепт', 'scroll', WHITE, BLACK), 330, 1080, pop(x / APPEAR), rot=-5, alpha=out)


def draw_steps(c, t):
    a, b = 10.0, 16.0
    if not (a <= t < b): return
    lt = t - a
    slide = back_out(lt / 0.4, 1.3) if lt < b - t else back_out((b - t) / 0.3, 1.0)
    n = len(STEPS)
    cur = max(i for i, s in enumerate(STEPS) if t >= s[0])
    s_t, title, ekey = STEPS[cur]
    card = Image.new('RGBA', (960, 310), (0, 0, 0, 0))
    d = ImageDraw.Draw(card)
    d.rounded_rectangle((0, 0, 959, 309), radius=44, fill=PURPLE + (255,))
    d.text((44, 34), f'ҚАДАМ {cur + 1} / {n}', font=font(F_INTER, 36), fill=(255, 255, 255, 190))
    sx = t - s_t
    ti = text_img(title, F_XB, 76, WHITE, False, 700)
    tsc = pop(sx / APPEAR) if cur else 1
    ti2 = ti.resize((max(1, int(ti.width * tsc)), max(1, int(ti.height * tsc))), Image.BICUBIC)
    card.alpha_composite(ti2, (44 + (ti.width - ti2.width) // 2, 95 + (ti.height - ti2.height) // 2))
    em = emoji(ekey, 150).rotate(8 * math.sin(t * 3), Image.BICUBIC)
    es = pop(sx / APPEAR)
    em = em.resize((max(1, int(150 * es)), max(1, int(150 * es))))
    card.alpha_composite(em, (860 - em.width // 2, 70 - em.height // 2 + int(bounce(t, 1.2, 8))))
    gap, x0, x1, y = 16, 44, 916, 248
    sw = (x1 - x0 - gap * (n - 1)) / n
    for i in range(n):
        xa = x0 + i * (sw + gap)
        d.rounded_rectangle((xa, y, xa + sw, y + 22), radius=11, fill=(255, 255, 255, 70))
        if i <= cur:
            fill = ease_out((t - STEPS[i][0]) / 0.45)
            if fill > 0.02:
                d.rounded_rectangle((xa, y, xa + sw * fill, y + 22), radius=11, fill=LIME + (255,))
    card = shadowed(card, off=10, blur=16, alpha=0.35)
    place(c, card, W // 2, 315 - 520 * (1 - clamp(slide, 0, 1.2)))


def draw_list(c, t):
    a, b = 16.0, 20.5
    if not (a <= t < b): return
    out = clamp((b - t) / 0.2)
    for i, (t0, txt, ek, bg, fg, rot) in enumerate(LIST):
        x = t - t0
        if x > 0:
            im = pill_img(txt, ek, bg, fg)
            place(c, im, 40 + im.width // 2, 200 + i * 128 - 30 * (1 - back_out(x / APPEAR)), pop(x / APPEAR), rot, out)


def draw_cta(c, t):
    a = 20.5
    if t < a: return
    lt = t - a
    c.alpha_composite(gradient(BLACK, 0.85 * ease_out(lt / 0.3), 1050))
    x = lt - 0.3
    if x > 0: place(c, text_img('Сізге қай тұнба сәйкес?', F_INTER, 54, WHITE), W // 2, 250, pop(x / APPEAR))
    for i, (w, col, y) in enumerate((('МАМАНҒА', LIME, 420), ('ЖАЗЫЛЫҢЫЗ', WHITE, 590))):
        x = lt - 0.5 - i * 0.25
        if x > 0:
            place(c, text_img(w, F_BLACK, 150, col, True, 980), W // 2, y + 40 * (1 - back_out(x / APPEAR)), pop(x / APPEAR))
    x = lt - 1.1
    if x > 0:
        for i, ax in enumerate((350, 540, 730)):
            ph = t * 2.2 - i * 0.18
            place(c, arrow_img(LIME, 84, 96), ax, 1620 + 22 * abs(math.sin(math.pi * ph)), pop((x - i * 0.08) / APPEAR))
        place(c, shadowed(emoji('down', 130), 6, 10, .35), 900, 1625 + bounce(t, 1.1, 14), pop((x - 0.3) / APPEAR))


def frame(n):
    t = n / FPS
    bg = bg_frame(t)
    c = brand_screen(bg, t)
    draw_hook(c, t)
    draw_keyword(c, t)
    draw_steps(c, t)
    draw_list(c, t)
    draw_cta(c, t)
    draw_subs(c, t)
    return c.convert('RGB').tobytes()


# ---------------------------------------------------------------- дыбыс
SR = 44100


def env(n, a, d):
    e = np.exp(-np.arange(n) / (d * SR)); e[:int(a * SR)] *= np.linspace(0, 1, int(a * SR)); return e


def make_audio(path):
    rng = np.random.default_rng(7)
    N = int(DUR * SR)
    mus = np.zeros(N)
    bpm = 100; beat = 60 / bpm
    def add(buf, sig, t):
        i = int(t * SR); j = min(len(buf), i + len(sig))
        if i < len(buf): buf[i:j] += sig[:j - i]
    tt = np.arange(int(0.45 * SR)) / SR
    kick = np.sin(2 * np.pi * (45 + 90 * np.exp(-tt * 30)) * tt) * np.exp(-tt * 9)
    noise = rng.standard_normal(int(0.25 * SR))
    clap = np.diff(noise, prepend=0) * env(len(noise), 0.002, 0.06) * 0.35
    hat = np.diff(np.diff(rng.standard_normal(int(0.06 * SR)), prepend=0), prepend=0) * env(int(0.06 * SR), 0.001, 0.012) * 0.07
    chords = [[57, 60, 64], [53, 57, 60], [48, 52, 55], [55, 59, 62]]  # Am F C G
    nb = int(DUR / beat) + 1
    for k in range(nb):
        t = k * beat
        if k % 4 in (0, 2) or (k % 8 == 7): add(mus, kick * 0.9, t if k % 8 != 7 else t + beat / 2)
        if k % 4 in (1, 3): add(mus, clap, t)
        add(mus, hat, t + beat / 2); add(mus, hat * 0.6, t)
        if k % 4 == 0:
            ch = chords[(k // 4) % 4]; L = int(beat * 4 * SR); x = np.arange(L) / SR
            pad = sum(np.sin(2 * np.pi * 440 * 2 ** ((m - 69) / 12) * x) + 0.3 * np.sin(4 * np.pi * 440 * 2 ** ((m - 69) / 12) * x) for m in ch)
            pad *= np.minimum(1, x / 0.05) * np.exp(-x * 0.5) * 0.08
            add(mus, pad, t)
            bass = np.sin(2 * np.pi * 440 * 2 ** ((ch[0] - 12 - 69) / 12) * x[:int(beat * SR)]) * np.exp(-x[:int(beat * SR)] * 3) * 0.35
            for q in (0, 1.5, 2.5): add(mus, bass, t + q * beat)
        if k % 2 == 0:  # пентатоникалық «плак»
            m = [69, 72, 76, 79, 81, 76][(k // 2) % 6]; L = int(0.3 * SR); x = np.arange(L) / SR
            add(mus, np.sin(2 * np.pi * 440 * 2 ** ((m - 69) / 12) * x) * np.exp(-x * 14) * 0.12, t + beat / 2)
    mus /= np.abs(mus).max()
    mus *= 10 ** (-14 / 20)  # дауыс жоқ — бит фон ретінде, тыныш
    fadeout = int(1.2 * SR); mus[-fadeout:] *= np.linspace(1, 0, fadeout)
    mus[:int(0.05 * SR)] *= np.linspace(0, 1, int(0.05 * SR))
    fx = np.zeros(N)
    for t, kind in sfx_events():
        if kind == 'whoosh':
            L = int(0.35 * SR); nz = rng.standard_normal(L)
            sm = np.convolve(nz, np.ones(12) / 12, 'same')
            e = np.sin(np.pi * np.linspace(0, 1, L)) ** 2
            add(fx, sm * e * 0.5, max(0, t - 0.12))
        else:
            L = int(0.09 * SR); x = np.arange(L) / SR
            f0 = {'pop': 900, 'pop2': 1250, 'tick': 1600}[kind]
            sig = np.sin(2 * np.pi * (f0 * np.exp(-x * 18)) * x * (1 + 0)) * np.exp(-x * 45)
            add(fx, sig * (0.18 if kind == 'tick' else 0.3), t)
    mix = mus + fx * 10 ** (-8 / 20)
    mix = np.tanh(mix * 1.1) / 1.1
    st = (np.stack([mix, mix], 1) * 32767 * 0.95).astype(np.int16)
    with wave.open(path, 'wb') as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes(st.tobytes())


if __name__ == '__main__':
    os.makedirs(OUT, exist_ok=True)
    if len(sys.argv) > 1 and sys.argv[1] == 'still':  # тексеру кадрлары
        for s in sys.argv[2:]:
            n = int(float(s) * FPS)
            Image.frombytes('RGB', (W, H), frame(n)).save(os.path.join(OUT, f'still_{s}.jpg'), quality=85)
        sys.exit()
    wav = os.path.join(OUT, 'audio.wav'); make_audio(wav)
    dst = os.path.join(OUT, 'aimei_reels.mp4')
    ff = subprocess.Popen(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}',
                           '-r', str(FPS), '-i', '-', '-i', wav, '-c:v', 'libx264', '-preset', 'medium', '-crf', '18',
                           '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '192k', '-movflags', '+faststart', '-shortest', dst],
                          stdin=subprocess.PIPE)
    total = int(DUR * FPS)
    with Pool(4) as pool:
        for i, buf in enumerate(pool.imap(frame, range(total), chunksize=8)):
            ff.stdin.write(buf)
            if i % 120 == 0: print(f'{i}/{total}', flush=True)
    ff.stdin.close(); ff.wait()
    print('OK', dst)
