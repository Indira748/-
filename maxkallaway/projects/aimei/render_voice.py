# Ai Mei — дауыс жазбасы (src/voice.m4a) бойынша edu-reels. 1080x1920, 30fps.
# Расшифровка: src/words.json (faster-whisper large-v3-turbo), мәтін төменде қолмен түзетілген.
# Іске қосу: python3 render_voice.py  ->  out/aimei_voice_reels.mp4
import json, math, os, subprocess, sys, wave
from functools import lru_cache
from multiprocessing import Pool
import numpy as np
from PIL import Image, ImageDraw
import render as R
from render import (W, H, FPS, PURPLE, LIME, WHITE, BLACK, GRAY, F_BLACK, F_XB, F_INTER, F_CJK, APPEAR,
                    clamp, ease_out, back_out, pop, bounce, font, emoji, text_img, pill_img, place, shadowed,
                    gradient, arrow_img, card_mask)

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, 'src')
OUT = os.path.join(HERE, 'out')

# ---------------------------------------------------------------- паузаларды кесу (source секундтары)
KEEP = [(1.55, 13.18), (13.40, 26.84), (27.08, 40.62), (40.78, 45.37), (45.55, 48.60)]
TAIL = 1.0   # соңғы сөзден кейін CTA ұсталады (концовка кесілмейді)


def m(s):
    """source уақыты -> монтаж уақыты"""
    acc = 0.0
    for a, b in KEEP:
        if s < a: return acc
        if s <= b: return acc + s - a
        acc += b - a
    return acc


VOICE_LEN = sum(b - a for a, b in KEEP)
DUR = VOICE_LEN + TAIL

# ---------------------------------------------------------------- түзетілген мәтін
FIX = {'дәрлер': 'дәрілер', 'төбірінен': 'түбірінен', 'диагнозі': 'диагнозы', 'тиабеті': 'диабеті,',
       'оламауыңыз': 'уламаңыз,', 'таңданыз': 'таңдаңыз.', 'денсаулыңызды': 'Денсаулығыңызды',
       'береді': 'береді.', 'емдейді': 'емдейді.', 'тиімді': 'тиімді?', 'біріншіден': 'Біріншіден,',
       'таңдалады': 'таңдалады.', 'екіншіден': 'Екіншіден,', 'қоймай': 'қоймай,', 'келтіреді': 'келтіреді.',
       'қысымы': 'қысымы,', 'ма': 'ма?', 'тапсырыңыз': 'тапсырыңыз.', 'келіп': 'келіп,',
       'жазылыңыз': 'жазылыңыз.', 'химиялық': 'Химиялық', 'ал': 'Ал', 'неге': 'Неге', 'химия': 'Химиямен'}
KEYS = {'химиялық', 'уақытша', 'түбірінен', 'шөптеріміз', 'жеке', 'диагнозы', 'табиғи', 'қабынуды',
        'алмасуды', 'диабеті', 'қысымы', 'аурулары', 'емді', 'сенімді', 'ai', 'mei', 'дәрігердің', 'жазылыңыз'}


def load_words():
    raw = json.load(open(os.path.join(SRC, 'words.json')))
    out, i = [], 0
    while i < len(raw):
        w, s, e = raw[i]['w'], raw[i]['s'], raw[i]['e']
        nxt = raw[i + 1]['w'] if i + 1 < len(raw) else ''
        if w == 'сон' and nxt == 'жалықта':
            out.append(('соншалықты', s, raw[i + 1]['e'])); i += 2; continue
        if w == 'д' and nxt == 'әриердің':
            out.append(('дәрігердің', raw[i + 1]['s'] - 0.1, raw[i + 1]['e'])); i += 2; continue
        if w == 'мен' and out and out[-1][0] == 'Химиямен':
            i += 1; continue
        if w == 'қан' and nxt == 'тиабеті': w = 'Қант'
        if w == 'қан' and nxt == 'қысымы': w = 'қан'
        if w == 'аймей':
            mid = (s + e) / 2; out += [('Ai', s, mid), ('Mei', mid, e)]; i += 1; continue
        if w == 'әйелдердерді':
            mid = s + (e - s) * 0.45; out += [('әйелдер', s, mid), ('аурулары', mid, e)]; i += 1; continue
        out.append((FIX.get(w, w), s, e)); i += 1
    return [(w, m(s), m(e)) for w, s, e in out]


WORDS = load_words()


def nk(w): return ''.join(ch for ch in w.lower() if ch.isalnum())


def chunks():
    res, cur = [], []
    for k, (w, s, e) in enumerate(WORDS):
        cur.append(k)
        if w[-1] in '.,?' or len(cur) >= 6:
            res.append(cur); cur = []
    if cur: res.append(cur)
    return res


CHUNKS = chunks()

# ---------------------------------------------------------------- сценарий (уақыттар source-та, m() арқылы)
T = lambda s: round(m(s), 3)
SCENES = [  # (басы, соңы, фото, zoom_from, zoom_to, фокус_y)
    (0.0, T(4.42), 'p2_product_close', 1.12, 1.00, 0.55),
    (T(4.42), T(9.88), 'p1_product_wide', 1.00, 1.10, 0.62),
    (T(9.88), T(13.04), 'p2_product_close', 1.00, 1.06, 0.50),     # бренд (карточкада)
    (T(13.04), T(21.04), 'd1_pulse', 1.00, 1.04, 0.0),              # дәрігер тамыр ұстайды
    (T(21.04), T(30.54), 'p1_product_wide', 1.05, 1.18, 0.66),
    (T(30.54), T(36.00), 'p2_product_close', 1.00, 1.10, 0.48),
    (T(36.00), T(40.52), 'vid', 1.0, 1.0, 0.0),                     # видео: шөп іріктеу
    (T(40.52), T(43.50), 'd2_pulse', 1.00, 1.06, 0.0),
    (T(43.50), DUR, 'p3_sign', 1.00, 1.10, 0.45),
]
R.SCENES = SCENES
HOOK = ('ХИМИЯ', 'ТАБИҒИ ЕМ', 'pill', 'herb', T(4.30))
KEYWORD = (T(6.06), T(9.85), 'шығыс медицинасы ағзаны', ['ТҮБІРІНЕН', 'ЕМДЕЙДІ'])
BRAND = (T(9.88), T(13.04), 'AI MEI', '爱美', ('Қытай шөптерімен емдеу', 'leaf'))
STEPS_LABEL = 'СЕБЕП'
STEPS = [(T(13.04), 'Жеке таңдалады', 'target'), (T(21.04), 'Табиғи шөптер', 'herb')]
STEPS_END = T(30.50)
# (пайда болу, мәтін, эмодзи, фон, түс, бұрыш, cx, cy, жоғалу)
PILLS = [
    (T(4.42), 'Уақытша жеңілдік', 'hourglass', WHITE, BLACK, -5, 540, 1080, T(6.0)),
    (T(17.10), 'Жеке диагноз', 'stetho', LIME, BLACK, 4, 600, 1570, T(21.0)),
    (T(25.10), 'Қабынуды басады', 'shield', WHITE, BLACK, -5, 450, 1000, T(30.5)),
    (T(28.66), 'Зат алмасу', 'cycle', LIME, BLACK, 4, 640, 1130, T(30.5)),
    (T(36.00), 'Химиямен уламаңыз', 'noentry', WHITE, BLACK, -5, 520, 1000, T(40.5)),
    (T(38.54), 'Табиғи ем', 'herb', LIME, BLACK, 4, 620, 1125, T(40.5)),
    (T(41.82), 'Сенімді қолдар', 'handshake', LIME, BLACK, -4, 540, 1580, T(43.5)),
]
LIST = [(T(30.54), 'Қант диабеті', 'blood', LIME, BLACK, -4),
        (T(31.82), 'Қан қысымы', 'heart', WHITE, BLACK, 4),
        (T(32.66), 'Ішкі ағзалар', 'lungs', PURPLE, WHITE, -3),
        (T(34.18), 'Әйелдер аурулары', 'blossom', LIME, BLACK, 3)]
LIST_END = T(35.95)
CTA = (T(43.50), 'Сізді де мазалай ма?', ('ДӘРІГЕРГЕ', 'ЖАЗЫЛЫҢЫЗ'))


def sfx_events():
    ev = [(0.0, 'whoosh')]
    w1, w2 = HOOK[0], HOOK[1].replace(' ', '')
    ev += [(0.15 + i * 0.07, 'tick') for i in range(len(w1))]
    ev += [(0.95 + i * 0.07, 'tick') for i in range(len(w2))]
    ev += [(0.45, 'pop'), (1.25, 'pop')]
    ev += [(s[0] - 0.05, 'whoosh') for s in SCENES[1:]]
    ev += [(KEYWORD[0] + 0.1, 'pop'), (KEYWORD[0] + 0.3, 'pop2'), (KEYWORD[0] + 0.7, 'pop')]
    ev += [(BRAND[0] + d, 'pop') for d in (0.25, 0.4, 0.6, 0.85)]
    ev += [(t + 0.05, 'pop2') for t, *_ in STEPS]
    ev += [(p[0], 'pop') for p in PILLS] + [(l[0], 'pop') for l in LIST]
    ev += [(CTA[0] + d, k) for d, k in ((0.3, 'pop'), (0.5, 'pop2'), (0.75, 'pop2'), (1.1, 'pop'))]
    return ev


# ---------------------------------------------------------------- блоктар
def draw_hook(c, t):
    w1, w2, e1, e2, end = HOOK
    if t >= end: return
    fade = 1 - clamp((t - end + 0.2) / 0.2)
    c.alpha_composite(gradient(PURPLE, 0.92 * fade, 980))
    for word, col, y, t0 in ((w1, WHITE, 270, 0.15), (w2, LIME, 575, 0.95)):
        size = 190
        while font(F_BLACK, size).getlength(word) > 900: size -= 6
        f = font(F_BLACK, size)
        x = W / 2 - f.getlength(word) / 2
        k = 0
        for ch in word:
            gw = f.getlength(ch)
            if ch != ' ':
                lt = t - (t0 + k * 0.07); k += 1
                if lt > 0:
                    place(c, text_img(ch, F_BLACK, size, col), x + gw / 2, y + 50 * (1 - back_out(lt / APPEAR)),
                          scale=pop(lt / APPEAR), alpha=fade)
            x += gw
    if t > 0.7:
        place(c, arrow_img(WHITE), W // 2, 425 + bounce(t, 1.2, 8), scale=pop((t - 0.7) / APPEAR), alpha=fade)
    for key, x, y, t0, rot in ((e1, 175, 370, 0.45, 12), (e2, 905, 370, 1.25, -8)):
        lt = t - t0
        if lt > 0:
            place(c, shadowed(emoji(key, 180), 8, 12, 0.35), x, y + 60 + bounce(lt, 1.4, 20),
                  scale=pop(lt / APPEAR), rot=rot, alpha=fade)


def draw_keyword(c, t):
    a, b, small, big = KEYWORD
    if not (a <= t < b): return
    lt, out = t - a, clamp((b - t) / 0.2)
    c.alpha_composite(gradient(BLACK, 0.6 * ease_out(lt / 0.3) * out, 950))
    if lt > 0.1:
        place(c, text_img(small, F_INTER, 52, WHITE), W // 2, 300, pop((lt - 0.1) / APPEAR), alpha=out)
    for i, w in enumerate(big):
        x = lt - 0.3 - i * 0.18
        if x > 0:
            sz = 190 if i == 0 else 130
            col = LIME if i == 0 else WHITE
            place(c, text_img(w, F_BLACK, sz, col, True, 900), W // 2, (470, 640)[i] + 40 * (1 - back_out(x / APPEAR)),
                  pop(x / APPEAR), alpha=out)
    x = lt - 0.7
    if x > 0:
        tw = 0.8 + 0.25 * (0.5 + 0.5 * math.sin(t * 9))
        place(c, emoji('sparkles', 120), 960, 330, pop(x / APPEAR) * tw, rot=12 * math.sin(t * 4),
              alpha=out * (0.65 + 0.35 * abs(math.sin(t * 7))))
        place(c, emoji('sparkles', 80), 95, 560, pop(x / APPEAR) * (1.9 - tw), rot=-10 * math.sin(t * 5), alpha=out * 0.9)


def brand_screen(bg, t):
    a, b, name, cjk, (desc, dkey) = BRAND
    if not (a <= t < b): return bg
    lt, rt = t - a, b - t
    k = back_out(lt / 0.38, 1.6) if lt < rt else back_out(rt / 0.32, 1.2)
    k = clamp(k, 0, 1.08)
    c = Image.new('RGBA', (W, H), LIME + (255,))
    sc, rot = 1 - 0.44 * k, -5 * k
    cw, ch = int(W * sc), int(H * sc)
    card = bg.resize((cw, ch), Image.BILINEAR)
    r = int(40 + 20 * k)
    card.putalpha(card_mask(cw, ch, r))
    cy, cx = H / 2 + (1090 - H / 2) * clamp(k), W / 2 + 30 * clamp(k)
    if k > 0.05:
        from PIL import ImageFilter
        sh = Image.new('RGBA', (cw + 120, ch + 120), (0, 0, 0, 0))
        ImageDraw.Draw(sh).rounded_rectangle((60, 60, 60 + cw, 60 + ch), radius=r, fill=(0, 0, 0, int(110 * clamp(k))))
        sh = sh.resize((sh.width // 4, sh.height // 4)).filter(ImageFilter.GaussianBlur(7)).resize(sh.size)
        place(c, sh, cx + 18, cy + 30, rot=rot)
    place(c, card, cx, cy, rot=rot)
    vis = clamp(rt / 0.25)
    items = ((0.25, lambda s: place(c, text_img(name, F_BLACK, 160, BLACK, False), 70, 205, s, 0, vis, 'l')),
             (0.40, lambda s: place(c, text_img(cjk, F_CJK, 140, BLACK, False), 735, 210, s, 0, vis, 'l')),
             (0.60, lambda s: place(c, pill_img(desc, dkey, BLACK, WHITE, 42), 62, 375, s, -2, vis, 'l')),
             (0.85, lambda s: place(c, shadowed(emoji('rocket', 170), 8, 12, .35), 905, 600 + bounce(t, 1.3, 22), s, 0, vis)))
    for t0, fn in items:
        if lt - t0 > 0: fn(pop((lt - t0) / APPEAR))
    return c


def draw_steps(c, t):
    a, b = STEPS[0][0], STEPS_END
    if not (a <= t < b): return
    lt = t - a
    slide = back_out(lt / 0.4, 1.3) if lt < b - t else back_out((b - t) / 0.3, 1.0)
    n = len(STEPS)
    cur = max(i for i, s in enumerate(STEPS) if t >= s[0])
    s_t, title, ekey = STEPS[cur]
    card = Image.new('RGBA', (960, 310), (0, 0, 0, 0))
    d = ImageDraw.Draw(card)
    d.rounded_rectangle((0, 0, 959, 309), radius=44, fill=PURPLE + (255,))
    d.text((44, 34), f'{STEPS_LABEL} {cur + 1} / {n}', font=font(F_INTER, 36), fill=(255, 255, 255, 190))
    sx = t - s_t
    ti = text_img(title, F_XB, 76, WHITE, False, 700)
    tsc = pop(sx / APPEAR) if cur else 1
    ti2 = ti.resize((max(1, int(ti.width * tsc)), max(1, int(ti.height * tsc))), Image.BICUBIC)
    card.alpha_composite(ti2, (44 + (ti.width - ti2.width) // 2, 95 + (ti.height - ti2.height) // 2))
    es = pop(sx / APPEAR)
    em = emoji(ekey, 150).rotate(8 * math.sin(t * 3), Image.BICUBIC)
    em = em.resize((max(1, int(150 * es)), max(1, int(150 * es))))
    card.alpha_composite(em, (860 - em.width // 2, 70 - em.height // 2 + int(bounce(t, 1.2, 8))))
    gap, x0, x1, y = 16, 44, 916, 248
    sw = (x1 - x0 - gap * (n - 1)) / n
    for i in range(n):
        xa = x0 + i * (sw + gap)
        d.rounded_rectangle((xa, y, xa + sw, y + 22), radius=11, fill=(255, 255, 255, 70))
        if i <= cur:
            fill = ease_out((t - STEPS[i][0]) / 0.45)
            if fill > 0.02: d.rounded_rectangle((xa, y, xa + sw * fill, y + 22), radius=11, fill=LIME + (255,))
    place(c, shadowed(card, off=10, blur=16, alpha=0.35), W // 2, 315 - 520 * (1 - clamp(slide, 0, 1.2)))


def draw_pills(c, t):
    for t0, txt, ek, bg, fg, rot, cx, cy, t1 in PILLS:
        if t0 <= t < t1:
            x = t - t0
            place(c, pill_img(txt, ek, bg, fg), cx, cy, pop(x / APPEAR), rot, clamp((t1 - t) / 0.18))


def draw_list(c, t):
    if not (LIST[0][0] <= t < LIST_END): return
    out = clamp((LIST_END - t) / 0.2)
    for i, (t0, txt, ek, bg, fg, rot) in enumerate(LIST):
        x = t - t0
        if x > 0:
            im = pill_img(txt, ek, bg, fg)
            place(c, im, 40 + im.width // 2, 200 + i * 128 - 30 * (1 - back_out(x / APPEAR)), pop(x / APPEAR), rot, out)


def draw_cta(c, t):
    a, q, (l1, l2) = CTA
    if t < a: return
    lt = t - a
    c.alpha_composite(gradient(BLACK, 0.9 * ease_out(lt / 0.3), 1300))
    if lt > 0.3: place(c, text_img(q, F_INTER, 54, WHITE), W // 2, 250, pop((lt - 0.3) / APPEAR))
    for i, (w, col, y) in enumerate(((l1, LIME, 420), (l2, WHITE, 590))):
        x = lt - 0.5 - i * 0.25
        if x > 0:
            place(c, text_img(w, F_BLACK, 150, col, True, 980), W // 2, y + 40 * (1 - back_out(x / APPEAR)), pop(x / APPEAR))
    x = lt - 1.1
    if x > 0:
        for i, ax in enumerate((350, 540, 730)):
            place(c, arrow_img(LIME, 84, 96), ax, 1620 + 22 * abs(math.sin(math.pi * (t * 2.2 - i * 0.18))),
                  pop((x - i * 0.08) / APPEAR))
        place(c, shadowed(emoji('down', 130), 6, 10, .35), 900, 1625 + bounce(t, 1.1, 14), pop((x - 0.3) / APPEAR))


# ---------------------------------------------------------------- субтитр (караоке, нақты сөз уақыттары)
SUB_FONT, SUB_Y, SUB_MAXW = 44, 1350, 900


@lru_cache(None)
def sub_lines(ci):
    idx = CHUNKS[ci]
    f = font(F_INTER, SUB_FONT); sp = f.getlength(' ')
    text = ' '.join(WORDS[k][0] for k in idx)
    if f.getlength(text) <= 560 or len(idx) < 4: return [idx]
    half, acc = f.getlength(text) / 2, 0
    for j, k in enumerate(idx):
        acc += f.getlength(WORDS[k][0]) + sp
        if acc >= half: return [idx[:j + 1], idx[j + 1:]] if idx[j + 1:] else [idx]
    return [idx]


def draw_subs(c, t):
    ci = None
    for i, idx in enumerate(CHUNKS):
        a = WORDS[idx[0]][1] - 0.08
        b = WORDS[CHUNKS[i + 1][0]][1] - 0.08 if i + 1 < len(CHUNKS) else WORDS[idx[-1]][2] + 0.4
        if a <= t < b: ci = i; break
    if ci is None: return
    lines = sub_lines(ci)
    f = font(F_INTER, SUB_FONT); sp = f.getlength(' '); lh = 62
    widths = [sum(f.getlength(WORDS[k][0]) for k in ln) + sp * (len(ln) - 1) for ln in lines]
    bw, bh = int(max(widths) + 64), int(lh * len(lines) + 40)
    k = back_out((t - a) / 0.22, 1.4)
    plate = Image.new('RGBA', (bw, bh), (0, 0, 0, 0))
    d = ImageDraw.Draw(plate)
    d.rounded_rectangle((0, 0, bw - 1, bh - 1), radius=30, fill=(0, 0, 0, 115))
    for li, ln in enumerate(lines):
        x = (bw - widths[li]) / 2
        for kk in ln:
            w, s, e = WORDS[kk]
            said = t >= s - 0.03
            d.text((x, 24 + li * lh), w, font=f, fill=((LIME if nk(w) in KEYS else WHITE) if said else GRAY))
            x += f.getlength(w) + sp
    place(c, plate, W // 2, SUB_Y, scale=0.85 + 0.15 * clamp(k, 0, 1.1), alpha=clamp(k))


VID_DIR = os.path.join(SRC, 'vidframes')


def bg_frame(t):
    for a, b, name, *_ in SCENES:
        if a <= t < b and name == 'vid':
            files = sorted(os.listdir(VID_DIR))
            i = min(len(files) - 1, int((t - a) * FPS))
            return Image.open(os.path.join(VID_DIR, files[i])).convert('RGBA')
    return R.bg_frame(t)


def frame(n):
    t = n / FPS
    bg = bg_frame(t)
    c = brand_screen(bg, t)
    draw_hook(c, t); draw_keyword(c, t); draw_steps(c, t)
    draw_pills(c, t); draw_list(c, t); draw_cta(c, t); draw_subs(c, t)
    return c.convert('RGB').tobytes()


# ---------------------------------------------------------------- дыбыс
SR = 44100


def make_audio(path):
    raw = subprocess.run(['ffmpeg', '-loglevel', 'error', '-i', os.path.join(SRC, 'voice.m4a'), '-ac', '1', '-ar', str(SR),
                          '-f', 'f32le', '-'], capture_output=True).stdout
    v = np.frombuffer(raw, np.float32).astype(np.float64)
    parts = []
    for a, b in KEEP:
        seg = v[int(a * SR):int(b * SR)].copy()
        fl = int(0.012 * SR); seg[:fl] *= np.linspace(0, 1, fl); seg[-fl:] *= np.linspace(1, 0, fl)
        parts.append(seg)
    voice = np.concatenate(parts)
    N = int(DUR * SR)
    voice = np.pad(voice, (0, max(0, N - len(voice))))[:N]
    voice *= 10 ** (-1.5 / 20) / max(1e-6, np.abs(voice).max())
    # музыка (render.py-дағы бит) — беру арқылы бөлек генерациялаймыз
    R.DUR = DUR
    tmp = os.path.join(OUT, '_music.wav')
    R.sfx_events = lambda: []
    R.make_audio(tmp)
    with wave.open(tmp) as w:
        mus = np.frombuffer(w.readframes(w.getnframes()), np.int16)[::2].astype(np.float64) / 32767
    os.remove(tmp)
    mus = np.pad(mus, (0, max(0, N - len(mus))))[:N]
    mus /= max(1e-6, np.sqrt(np.mean(mus ** 2)))
    vr = np.sqrt(np.mean(voice[np.abs(voice) > 0.02] ** 2))
    # ducking: сөйлеу кезінде −20 dB, үзілісте/соңында −12 dB
    win = int(0.05 * SR)
    envv = np.sqrt(np.convolve(voice ** 2, np.ones(win) / win, 'same'))
    speaking = (envv > vr * 0.15).astype(np.float64)
    sm = int(0.25 * SR)
    speaking = np.minimum(1, np.convolve(speaking, np.ones(sm) / sm * 3, 'same'))
    gain_db = -20 * speaking + -12 * (1 - speaking)
    mus = mus * vr * 10 ** (gain_db / 20)
    fx = np.zeros(N); rng = np.random.default_rng(3)
    def add(buf, sig, t):
        i = int(t * SR); j = min(len(buf), i + len(sig))
        if 0 <= i < len(buf): buf[i:j] += sig[:j - i]
    for t, kind in sfx_events():
        if kind == 'whoosh':
            L = int(0.35 * SR); sm2 = np.convolve(rng.standard_normal(L), np.ones(12) / 12, 'same')
            add(fx, sm2 * np.sin(np.pi * np.linspace(0, 1, L)) ** 2 * 0.5, max(0, t - 0.12))
        else:
            L = int(0.09 * SR); x = np.arange(L) / SR
            f0 = {'pop': 900, 'pop2': 1250, 'tick': 1600}[kind]
            add(fx, np.sin(2 * np.pi * f0 * np.exp(-x * 18) * x) * np.exp(-x * 45) * (0.18 if kind == 'tick' else 0.3), t)
    mix = voice + mus + fx * vr * 0.9
    mix = np.tanh(mix * 1.05) / 1.05
    st = (np.stack([mix, mix], 1) * 32767 * 0.97).astype(np.int16)
    with wave.open(path, 'wb') as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes(st.tobytes())


if __name__ == '__main__':
    os.makedirs(OUT, exist_ok=True)
    if len(sys.argv) > 1 and sys.argv[1] == 'still':
        for s in sys.argv[2:]:
            Image.frombytes('RGB', (W, H), frame(int(float(s) * FPS))).save(os.path.join(OUT, f'v_still_{s}.jpg'), quality=85)
        sys.exit()
    if len(sys.argv) > 1 and sys.argv[1] == 'text':
        for idx in CHUNKS: print(f'{WORDS[idx[0]][1]:6.2f}', ' '.join(WORDS[k][0] for k in idx))
        print('DUR', DUR); sys.exit()
    wav = os.path.join(OUT, 'voice_mix.wav'); make_audio(wav)
    dst = os.path.join(OUT, 'aimei_voice_reels.mp4')
    ff = subprocess.Popen(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}',
                           '-r', str(FPS), '-i', '-', '-i', wav, '-c:v', 'libx264', '-preset', 'medium', '-crf', '18',
                           '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '192k', '-movflags', '+faststart', '-shortest', dst],
                          stdin=subprocess.PIPE)
    total = int(DUR * FPS)
    with Pool(4) as pool:
        for i, buf in enumerate(pool.imap(frame, range(total), chunksize=8)):
            ff.stdin.write(buf)
            if i % 300 == 0: print(f'{i}/{total}', flush=True)
    ff.stdin.close(); ff.wait()
    print('OK', dst)
