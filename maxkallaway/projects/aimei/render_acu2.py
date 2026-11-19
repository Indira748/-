# Ai Mei — иглотерапия, ӨЗ ДАУЫСЫМЕН (src/acu_voice/voice.m4a). Сабырлы жасыл/ақ стиль + ұстап тұру (retention) элементтері:
# хук ине кадрымен, прогресс-жолақ, тізімде әр пунктке жеке кадр + белсенді пункт, карточкада сөзбе-сөз караоке.
# Іске қосу: python3 render_acu2.py -> out/aimei_acupuncture_voice.mp4 | still 1 5 ... | text
import json, math, os, subprocess, sys, wave
from functools import lru_cache
from multiprocessing import Pool
import numpy as np
from PIL import Image, ImageDraw
import render_acu as RA
from render_acu import (W, H, FPS, GREEN, LEAF, MINT, CREAM, WHITE, INK, MUTED, F_B, F_XB, F_SB, F_INTER, F_CJK,
                        font, put, txt, rise, smooth, kb, rrect, leaf_icon, num_badge, needles_deco, logo_circle,
                        pill, vgrad, shadowed, card_mask, ease_out, clamp, vid_files, VID, NEEDLE, needle_files, PHONE)

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, 'src', 'acu_voice')
OUT = os.path.join(HERE, 'out')
ADDRESS = '6а шағын ауданы, 11/3'
LIGHT = (176, 186, 178)

# ---------------------------------------------------------------- дауысты монтаждау
SIL = [(0, 2.14), (2.15, 2.47), (5.01, 5.39), (11.59, 11.93), (15.84, 16.32), (17.20, 17.50), (19.61, 19.98),
       (21.39, 21.82), (22.71, 23.08), (26.23, 26.59), (30.71, 35.24),          # 30.7–35.2: қате оқылған бірінші дубль
       (38.67, 39.00), (40.33, 40.93), (43.40, 44.11), (45.88, 46.36), (48.42, 48.90), (51.32, 51.89),
       (56.45, 56.78), (58.98, 59.32), (60.41, 60.71), (62.29, 62.70), (65.02, 66.56)]
PAD = 0.12          # әр үзілістен қалатын тыныштық (екі жағынан)
KEEP = []
_prev = 0.0
for a, b in SIL:
    if a > _prev: KEEP.append((max(0, _prev - (PAD if _prev else 0)), a + PAD))
    _prev = b
KEEP = [(max(0, a), b) for a, b in KEEP]


def m(s):
    acc = 0.0
    for a, b in KEEP:
        if s < a: return acc
        if s <= b: return acc + s - a
        acc += b - a
    return acc


VOICE_LEN = sum(b - a for a, b in KEEP)
DUR = round(VOICE_LEN + 1.8, 2)       # соңы кесілмейді, CTA ұсталады

# ---------------------------------------------------------------- түзетілген сөздер (source уақыттары)
def words():
    raw = [x for x in json.load(open(os.path.join(SRC, 'words.json'))) if not (30.5 <= x['s'] < 35.4)]
    fix = {'жеңішке': 'жіңішке', 'енелері': 'инелер', 'келтіруне': 'келтіруіне', 'мұна': 'мына',
           'дәргердің': 'дәрігердің', 'тәжірбелі': 'тәжірибелі', 'дәргерлері': 'дәрігерлері', 'иқысыздық': 'ұйқысыздық',
           'неврология': 'невралгия', 'мигрен': 'мигрень', 'иглотерапия': 'Иглотерапия', 'әдісі': 'әдісі.', 'ол': 'Ол'}
    out = []
    for x in raw:
        w, s, e = x['w'], x['s'], x['e']
        if w == 'өзін': continue
        if w == '-өзін': w, s = 'өзін-өзі', s - 0.38
        if w == 'ем' and s > 34: s = 35.3
        if w == 'көмектеседі' and s < 5: w = 'көмектеседі?'
        out.append((fix.get(w, w), s, e))
    return out


W_SRC = words()


def ws(a, b):
    """source [a,b) аралығындағы сөздер -> [(сөз, out_start, out_end)]"""
    return [(w, m(s), m(e)) for w, s, e in W_SRC if a <= s < b]


T = lambda s: round(m(s), 3)
# көріністер (out уақыты)
SCENES = [
    ('hook', 0.0, T(5.0)),
    ('what', T(5.0), T(15.75)),
    ('list', T(15.75), T(38.66)),
    ('why', T(38.66), T(48.70)),
    ('cta', T(48.70), DUR),
]
HOOK_T = (T(1.96), T(3.24))
WHAT_WORDS = ws(5.0, 15.75)
WHAT_KEYS = {'белсенді', 'нүктелерге', 'жіңішке', 'стерильді', 'инелер', 'қалпына'}
LIST_T0 = T(15.78)
ITEMS = [('Бел мен мойын ауыруы', T(19.60)), ('Буын ауыруы', T(21.38)), ('Бас ауыруы мен мигрень', T(22.76)),
         ('Ұйқысыздық пен стресс', T(24.46)), ('Невралгия және бет нервісінің қабынуы', T(26.18)), ('Ас қорыту бұзылыстары', T(28.94))]
NOTE_T = T(35.3)
WHY = [('Неге Ai Mei?', T(38.66)), ('Тәжірибелі қытай дәрігерлері', T(40.46)), ('Тамыр арқылы диагностика', T(43.96)),
       ('Иглотерапия және шөп емі', T(46.28))]
CTA_T = dict(title=T(48.74), addr=T(51.68), phone=T(56.56), book=T(62.42))
XF = 0.45


# ---------------------------------------------------------------- медиа көздері (тізімдегі карточкаға)
@lru_cache(None)
def frame_file(d, i):
    return Image.open(os.path.join(d, i)).convert('RGB')


def needle(t):
    f = needle_files(); return frame_file(NEEDLE, f[int(t * FPS) % len(f)])


def herbs(t):
    f = vid_files(); return frame_file(VID, f[min(len(f) - 1, int(t * FPS))])


def photo_full(name, t, z=1.0):
    return kb(name, t, 4.0, 1.0, 1.0, 0.5).convert('RGB')


# әр пункт үшін: (кадр функциясы, қиып алу аймағы x0,y0,x1,y1 — 1080x1920 кадрда)
# әр ауруға иллюстрация-карточка: (негізгі 3D бейне, қосымша, фон түсі)
ILLU = {
    1: ('massage', 'herb', (214, 236, 214)),       # бел мен мойын
    2: ('bone', 'sparkles', (226, 236, 220)),      # буын
    3: ('bandage', 'zap', (232, 238, 218)),        # бас ауыруы, мигрень
    4: ('sleeping', 'moon', (218, 230, 236)),      # ұйқысыздық, стресс
    5: ('brain', 'zap', (230, 226, 238)),          # невралгия, бет нервісі
    6: ('bowl', 'herb', (238, 234, 216)),          # ас қорыту
}


@lru_cache(None)
def illu_bg(col):
    g = np.zeros((600, 960, 3), np.float32)
    yy, xx = np.mgrid[0:600, 0:960]
    r = np.sqrt(((xx - 380) / 520) ** 2 + ((yy - 300) / 420) ** 2)
    k = np.clip(r, 0, 1)[..., None]
    g[:] = np.array(col) * (1 - k) + np.array(CREAM) * k
    im = Image.fromarray(g.astype(np.uint8), 'RGB').convert('RGBA')
    deco = needles_deco(260, 260, LEAF)
    deco.putalpha(deco.split()[3].point(lambda v: int(v * 0.5)))
    im.alpha_composite(deco, (680, 320))
    return im


def illu(k, t):
    main, sub, col = ILLU[k]
    im = illu_bg(col).copy()
    fl = math.sin(t * 2.2) * 10                                        # жұмсақ «қалқу»
    sc = 0.94 + 0.06 * ease_out(t / 0.6)
    e = RA.emoji(main, int(330 * sc))
    halo = Image.new('RGBA', (460, 460), (0, 0, 0, 0))
    ImageDraw.Draw(halo).ellipse((20, 20, 440, 440), fill=(255, 255, 255, 150))
    im.alpha_composite(halo, (380 - 230, 300 - 230))
    im.alpha_composite(shadowed(e, 10, 16, 0.18), (int(380 - e.width / 2 - 26), int(300 - e.height / 2 - 26 + fl)))
    a = 2 * math.pi * (t * 0.18) + k
    e2 = RA.emoji(sub, 140)
    im.alpha_composite(e2, (int(640 + 40 * math.cos(a) - 70), int(150 + 30 * math.sin(a) - 70 - fl * 0.6)))
    return im


MEDIA = [
    (lambda t: photo_full('p3_sign', t), (0, 110, 1080, 785)),          # кіріспе — логотип + «Ai Mei» жазуы
    None, None, None, None, None, None,                                 # 1–6: иллюстрациялар (ILLU)
    (lambda t: photo_full('d1_pulse', t), (0, 380, 1080, 1055)),        # ескерту — дәрігер кеңесі
]
CARD_W, CARD_H = 960, 600


@lru_cache(None)
def sign_card():
    """вывеска: логотип + «Ai Mei» толық көрінеді (биіктігі бойынша сыйғызылып, фонда бұлыңғыр көшірме)"""
    from PIL import ImageFilter
    src = Image.open(os.path.join(HERE, 'assets', 'photos', 'p3b_sign.jpg')).convert('RGB')
    sw, sh = src.size
    reg = src.crop((0, 0, sw, int(sh * 0.44)))                       # логотип + Ai Mei
    bg = reg.resize((CARD_W, int(CARD_W * reg.height / reg.width))).crop((0, 0, CARD_W, CARD_H))
    bg = bg.filter(ImageFilter.GaussianBlur(28)).convert('RGBA')
    bg.alpha_composite(Image.new('RGBA', bg.size, CREAM + (90,)))
    fg = reg.resize((int(CARD_H * reg.width / reg.height), CARD_H), Image.LANCZOS).convert('RGBA')
    bg.alpha_composite(fg, ((CARD_W - fg.width) // 2, 0))
    return bg


def media_card(k, t):
    if k == 0:
        im = sign_card(); z = 1.0 + 0.04 * smooth(t / 3.0)
        w, h = CARD_W / z, CARD_H / z
        return im.resize((CARD_W, CARD_H), Image.BILINEAR, box=((CARD_W - w) / 2, (CARD_H - h) / 2, (CARD_W + w) / 2, (CARD_H + h) / 2))
    if MEDIA[k] is None: return illu(k, t)
    fn, (x0, y0, x1, y1) = MEDIA[k]
    z = 1.0 + (0.0 if k == 0 else 0.06) * smooth(t / 3.0)                # баяу zoom (вывескада жоқ — жазу кесілмесін)
    cx, cy, w, h = (x0 + x1) / 2, (y0 + y1) / 2, (x1 - x0) / z, (y1 - y0) / z
    im = fn(t).resize((CARD_W, CARD_H), Image.BILINEAR, box=(cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2))
    return im.convert('RGBA')


# ---------------------------------------------------------------- көріністер
def progress(c, t):
    k = clamp(t / DUR)
    d = ImageDraw.Draw(c)
    d.rounded_rectangle((60, 46, W - 60, 52), radius=3, fill=(255, 255, 255, 150))
    d.rounded_rectangle((60, 46, 60 + (W - 120) * k, 52), radius=3, fill=LEAF if k < 1 else GREEN)


def sc_hook(lt, dur, t):
    f = needle_files()
    c = Image.open(os.path.join(NEEDLE, f[min(len(f) - 1, int(lt * FPS))])).convert('RGBA')
    z = 1.0 + 0.08 * (1 - ease_out(lt / 0.7))                           # бірінші кадрдағы жеңіл «punch»
    if z > 1.001:
        cw, ch = W / z, H / z
        c = c.resize((W, H), Image.BILINEAR, box=((W - cw) / 2, (H - ch) / 2, (W + cw) / 2, (H + ch) / 2))
    c.alpha_composite(vgrad(CREAM, 1080, 1420, 0.96))
    a, dy = rise(lt, 0.0, 0.45)
    put(c, pill('AI MEI  ·  ҚЫТАЙ МЕДИЦИНАСЫ', 30, GREEN, WHITE), W / 2, 1290 + dy, a)
    a, dy = rise(lt, HOOK_T[0] - 0.25, 0.5)
    put(c, txt('Иглотерапия', F_XB, 128, GREEN), W / 2, 1390 + dy, a)
    a, dy = rise(lt, HOOK_T[1] - 0.15, 0.5)
    put(c, txt('қандай жағдайда көмектеседі?', F_SB, 52, INK), W / 2, 1560 + dy, a)
    a, dy = rise(lt, HOOK_T[1] + 0.9, 0.5)
    put(c, pill('6 жағдай  ·  соңына дейін қараңыз', 34, MINT, GREEN), W / 2, 1680 + dy, a)
    return c


@lru_cache(None)
def what_layout():
    f = font(F_INTER, 40); sp = f.getlength(' ')
    lines, cur, cw = [], [], 0
    for k, (w, s, e) in enumerate(WHAT_WORDS):
        ww = f.getlength(w)
        if cur and cw + sp + ww > 830: lines.append(cur); cur, cw = [], 0
        cur.append(k); cw += (sp if cw else 0) + ww
    return lines + [cur]


BACK = os.path.join(HERE, 'src', 'backframes')


@lru_cache(None)
def back_files(): return sorted(os.listdir(BACK))


def back_frame(t):
    f = back_files()
    return Image.open(os.path.join(BACK, f[min(len(f) - 1, max(0, int(t * FPS)))])).convert('RGBA')


def sc_what(lt, dur, t):
    f = needle_files()
    vstart = SCENES[0][2] - SCENES[0][1]
    vl = len(f) / FPS - vstart                                           # ине видеосының қалғаны
    c = Image.open(os.path.join(NEEDLE, f[min(len(f) - 1, int((lt + vstart) * FPS))])).convert('RGBA')
    if lt > vl - 0.5:
        k = smooth((lt - (vl - 0.5)) / 0.5)
        c = Image.blend(c, back_frame(lt - vl + 0.5), k)               # арқаға ине қою видеосы
    a, dy = rise(lt, 0.25, 0.6)
    put(c, rrect(960, 400, 48, CREAM, 242), W / 2, 1365 + dy, a)
    put(c, leaf_icon(48), 120, 1452 + dy, a, 'l')
    put(c, txt('Иглотерапия деген не?', F_B, 50, GREEN), 184, 1446 + dy, a, 'l')
    fnt = font(F_INTER, 40); sp = fnt.getlength(' ')
    d = ImageDraw.Draw(c)
    for li, ln in enumerate(what_layout()):
        x, y = 120, 1536 + li * 56 + dy
        for k in ln:
            w, s, e = WHAT_WORDS[k]
            said = t >= s - 0.05
            col = (GREEN if w.strip('.,?') in WHAT_KEYS else INK) if said else LIGHT
            if a > 0.5: d.text((x, y), w, font=fnt, fill=col)
            x += fnt.getlength(w) + sp
    return c


def sc_list(lt, dur, t):
    c = Image.new('RGBA', (W, H), CREAM + (255,))
    put(c, needles_deco(300, 300), W - 270, 70, 0.35, 'l')
    a, dy = rise(lt, 0.1)
    put(c, txt('Қандай жағдайда көмектеседі?', F_XB, 62, GREEN, 800, 1.12, 'l'), 70, 110 + dy, a, 'l')
    cur = -1
    for i, (_, st) in enumerate(ITEMS):
        if t >= st - 0.1: cur = i
    if t >= NOTE_T - 0.1: mk = 7
    else: mk = cur + 1
    # медиа карточка: пункт ауысқанда жұмсақ crossfade
    starts = [SCENES[2][1]] + [st for _, st in ITEMS] + [NOTE_T]
    ms = starts[mk] - (0.1 if mk else 0)
    card = media_card(mk, t - ms)
    if mk > 0 and t - ms < 0.35:
        prev = media_card(mk - 1, t - starts[mk - 1])
        card = Image.blend(prev, card, smooth((t - ms) / 0.35))
    card.putalpha(card_mask(CARD_W, CARD_H, 44))
    a, dy = rise(lt, 0.25, 0.6)
    put(c, shadowed(card, 10, 22, 0.18), W / 2, 270 + dy, a)
    if cur >= 0:
        k = ease_out((t - ITEMS[cur][1] + 0.1) / 0.35)
        put(c, pill(f'{cur + 1} / {len(ITEMS)}', 36, GREEN, WHITE), 120, 360 - 10 * (1 - k), k, 'l')
    y0, step = 975, 116
    for i, (item, st) in enumerate(ITEMS):
        a, dy = rise(t, st - 0.12, 0.45)
        if a <= 0: continue
        active = 1.0 if i == cur and mk <= 6 else 0.0
        act = active * ease_out((t - st + 0.1) / 0.3)
        y = y0 + i * step + dy
        bg = tuple(int(WHITE[j] + (GREEN[j] - WHITE[j]) * act) for j in range(3))
        fg = tuple(int(INK[j] + (WHITE[j] - INK[j]) * act) for j in range(3))
        put(c, rrect(920, 100, 50, bg, 255), W / 2, y - 58, a)
        put(c, num_badge(i + 1, 62), 104, y + 19, a, 'l')
        fs = 42
        while font(F_INTER, fs).getlength(item) > 780: fs -= 2
        put(c, txt(item, F_INTER, fs, fg), 192, y + 27 + (42 - fs) // 2, a, 'l')
    a, dy = rise(t, NOTE_T - 0.1, 0.6)
    put(c, pill('Ем дәрігердің тексеруінен кейін жеке тағайындалады', 31, GREEN, WHITE, 'stetho'), W / 2, 1688 + dy, a)
    return c


def sc_why(lt, dur, t):
    c = RA.vid(lt * min(1.0, len(vid_files()) / FPS / dur))
    a, dy = rise(lt, 0.2, 0.6)
    put(c, rrect(960, 450, 48, CREAM, 245), W / 2, 1245 + dy, a)
    for i, (w, st) in enumerate(WHY):
        a, dy = rise(t, st - 0.12, 0.5)
        if i == 0:
            put(c, txt(w, F_B, 56, GREEN), 120, 1360 + dy, a, 'l'); continue
        y = 1468 + (i - 1) * 92
        put(c, leaf_icon(46), 122, y + 4 + dy, a, 'l')
        put(c, txt(w, F_INTER, 44, INK), 190, y + dy, a, 'l')
    return c


def sc_cta(lt, dur, t):
    c = Image.new('RGBA', (W, H), GREEN + (255,))
    put(c, needles_deco(420, 420, (52, 118, 80)), -40, 1460, ease_out(lt / 1.2), 'l')
    put(c, needles_deco(300, 300, (52, 118, 80)), W - 280, 60, ease_out(lt / 1.2), 'l')
    a, dy = rise(lt, 0.15, 0.7)
    put(c, logo_circle(300), W / 2, 300 + dy, a)
    a, dy = rise(t, CTA_T['title'] - 0.1)
    put(c, txt('Ai Mei орталығына келіп емделіңіз', F_XB, 84, WHITE, 900, 1.18), W / 2, 730 + dy, a)
    k = ease_out((t - CTA_T['title'] - 0.5) / 0.8)
    if k > 0:
        ImageDraw.Draw(c).rounded_rectangle((W / 2 - 70 * k, 1080, W / 2 + 70 * k, 1086), radius=3, fill=LEAF)
    a, dy = rise(t, CTA_T['addr'] - 0.1)
    put(c, pill(ADDRESS, 46, WHITE, GREEN, 'pin'), W / 2, 1150 + dy, a)
    a, dy = rise(t, CTA_T['phone'] - 0.1)
    put(c, pill(PHONE, 48, WHITE, GREEN, 'phone'), W / 2, 1280 + dy, a)
    a, dy = rise(t, CTA_T['book'] - 0.1)
    put(c, txt('Алдын ала қабылдауға жазылыңыз', F_INTER, 42, MINT), W / 2, 1450 + dy, a)
    a, dy = rise(t, CTA_T['book'] + 0.6)
    put(c, txt('AI MEI', F_XB, 56, LEAF), W / 2 - 70, 1720 + dy, a)
    put(c, txt('爱美', F_CJK, 56, LEAF), W / 2 + 110, 1720 + dy, a)
    return c


FN = dict(hook=sc_hook, what=sc_what, list=sc_list, why=sc_why, cta=sc_cta)


def frame(n):
    t = n / FPS
    for i, (name, a, b) in enumerate(SCENES):
        if a <= t < b or i == len(SCENES) - 1: break
    c = FN[name](t - a, b - a, t)
    if i + 1 < len(SCENES) and t > b - XF:
        nx, na, nb = SCENES[i + 1]
        c = Image.blend(c, FN[nx](0.0, nb - na, na), smooth((t - (b - XF)) / XF))
    progress(c, t)
    return c.convert('RGB').tobytes()


# ---------------------------------------------------------------- дыбыс
SR = 44100


def make_audio(path):
    raw = subprocess.run(['ffmpeg', '-loglevel', 'error', '-i', os.path.join(SRC, 'voice.m4a'),
                          '-af', 'highpass=f=80,acompressor=threshold=-22dB:ratio=3:attack=8:release=120:makeup=3',
                          '-ac', '1', '-ar', str(SR), '-f', 'f32le', '-'], capture_output=True).stdout
    v = np.frombuffer(raw, np.float32).astype(np.float64)
    parts = []
    for a, b in KEEP:
        seg = v[int(a * SR):int(b * SR)].copy()
        fl = int(0.015 * SR); seg[:fl] *= np.linspace(0, 1, fl); seg[-fl:] *= np.linspace(1, 0, fl)
        parts.append(seg)
    N = int(DUR * SR)
    voice = np.concatenate(parts); voice = np.pad(voice, (0, max(0, N - len(voice))))[:N]
    voice *= 10 ** (-1.5 / 20) / max(1e-6, np.abs(voice).max())
    # музыка — render_acu-дағы тыныш эмбиент
    RA.DUR = DUR; RA.SCENES = []
    tmp = os.path.join(OUT, '_m.wav'); RA.make_audio(tmp, music_only=True)
    with wave.open(tmp) as w:
        mus = np.frombuffer(w.readframes(w.getnframes()), np.int16)[::2].astype(np.float64) / 32767
    os.remove(tmp)
    mus = np.pad(mus, (0, max(0, N - len(mus))))[:N]
    vr = np.sqrt(np.mean(voice[np.abs(voice) > 0.03] ** 2))
    win = int(0.05 * SR)
    env = np.sqrt(np.convolve(voice ** 2, np.ones(win) / win, 'same'))
    sp = (env > vr * 0.2).astype(np.float64)
    sm = int(0.35 * SR); sp = np.minimum(1, np.convolve(sp, np.ones(sm) / sm * 3, 'same'))
    mus = mus / max(1e-6, np.sqrt(np.mean(mus ** 2))) * vr * 10 ** ((-20 * sp - 12 * (1 - sp)) / 20)
    fx = np.zeros(N)
    def add(sig, t0):
        i = int(t0 * SR); j = min(N, i + len(sig))
        if 0 <= i < N: fx[i:j] += sig[:j - i]
    x = np.arange(int(0.25 * SR)) / SR
    tick = np.sin(2 * np.pi * 1320 * x) * np.exp(-x * 30) + 0.4 * np.sin(2 * np.pi * 1980 * x) * np.exp(-x * 40)
    for _, st in ITEMS: add(tick * 0.5, st - 0.1)                       # әр пунктке нәзік «тық»
    x = np.arange(int(1.5 * SR)) / SR
    chime = (np.sin(2 * np.pi * 1175 * x) + 0.5 * np.sin(2 * np.pi * 1760 * x)) * np.exp(-x * 3.5)
    for _, a, _b in SCENES[1:]: add(chime * 0.35, a - XF / 2)
    mix = voice + mus + fx * vr * 0.35
    st = (np.clip(np.stack([mix, mix], 1), -1, 1) * 32767).astype(np.int16)
    with wave.open(path, 'wb') as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes(st.tobytes())


if __name__ == '__main__':
    os.makedirs(OUT, exist_ok=True)
    if len(sys.argv) > 1 and sys.argv[1] == 'text':
        print(SCENES); print('DUR', DUR); print(' '.join(f'{w}' for w, *_ in WHAT_WORDS)); sys.exit()
    if len(sys.argv) > 1 and sys.argv[1] == 'still':
        for s in sys.argv[2:]:
            Image.frombytes('RGB', (W, H), frame(int(float(s) * FPS))).save(os.path.join(OUT, f'b_still_{s}.jpg'), quality=85)
        sys.exit()
    wav = os.path.join(OUT, 'acu_voice_mix.wav'); make_audio(wav)
    dst = os.path.join(OUT, 'aimei_acupuncture_voice.mp4')
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
