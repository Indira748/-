# -*- coding: utf-8 -*-
"""edu-reels монтаж для video1 (Гранит Дент, kk).

Запуск:  python3 edu_reels.py SRC.mov STT.json ASSETS_DIR OUT_DIR
STT.json — результат faster-whisper large-v3 (segments[].words = [start,end,word]).
ASSETS_DIR: fonts/Montserrat.ttf (variable), emoji/*.png (Fluent 3D).
"""
import sys, os, json, math, subprocess, difflib, wave, re
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

SRC, STT, ASSETS, OUT = sys.argv[1:5]
os.makedirs(OUT, exist_ok=True)
W, H, FPS = 1080, 1920, 30
SR = 44100

PURPLE = (108, 59, 255)
LIME = (198, 244, 50)
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
GRAY = (150, 150, 150)

INTER = '/usr/share/fonts/opentype/inter/Inter-SemiBold.otf'
MONT = os.path.join(ASSETS, 'fonts', 'Montserrat.ttf')

# ---------------------------------------------------------------- текст речи
TEXT = """қайырлы күн, оқырмандар!
бүгін менің қабылдауыма 15 жастағы пациентіміз келді.
пациентіміз ауыздан жағымсыз иістің шығуынан, тамақ жей алуының қиындауынан шағымданып келді.
жалпы тексеру барысында визуалды рентгенге түсіріп қарадық.
рентген түсіргенде бізде тістің түбір аймағынан
қара дақ, яғни іріңді бөліністі анықтадық.
яғни бұл тіске біз периодонтит диагнозын қойдық.
жалпы емдеп, біз толыққанды ем шарасын жүргіздік.
және де емделіп болғаннан кейінгі көрінісіміз осындай.
яғни бүткіл анық іріңді бөліністі алып, тазалап, емдеп жібердік.
құрметті ата-аналар, балаларыңыздың тістерін жылына кем дегенде бір-екі рет тексертіп тұру керек.
және де біздің Гранит Дент стоматологиясында тегін консультацияға келсеңіздер болады."""
KEYS = {'15', 'жастағы', 'жағымсыз', 'иістің', 'қиындауынан', 'рентгенге', 'қара', 'дақ', 'іріңді',
        'периодонтит', 'толыққанды', 'тазалап', 'емдеп', 'жылына', 'бір-екі', 'рет', 'тексертіп',
        'гранит', 'дент', 'тегін', 'консультацияға'}

# ---------------------------------------------------------------- 1. тайминги слов
stt = json.load(open(STT))
wwords = [(w[0], w[1], w[2].strip()) for s in stt['segments'] for w in s['words']]


def norm(s):
    return re.sub(r'[^0-9a-zа-яёәғқңөұүһі]', '', s.lower())

# посимвольное выравнивание утверждённого текста с whisper
wchars, wtimes = [], []
for a, b, w in wwords:
    n = norm(w)
    for i, c in enumerate(n):
        wchars.append(c)
        wtimes.append(a + (b - a) * (i + 0.5) / max(1, len(n)))
lines = [l.strip() for l in TEXT.split('\n') if l.strip()]
toks = []  # (line_idx, word)
for li, l in enumerate(lines):
    for w in l.split():
        toks.append((li, w))
tchars, towner = [], []
for ti, (li, w) in enumerate(toks):
    for c in norm(w):
        tchars.append(c)
        towner.append(ti)
sm = difflib.SequenceMatcher(None, ''.join(tchars), ''.join(wchars), autojunk=False)
ctime = [None] * len(tchars)
for blk in sm.get_matching_blocks():
    for k in range(blk.size):
        ctime[blk.a + k] = wtimes[blk.b + k]
tok_t = []
for ti in range(len(toks)):
    ts = [ctime[i] for i in range(len(tchars)) if towner[i] == ti and ctime[i] is not None]
    tok_t.append((min(ts), max(ts)) if ts else None)
# интерполяция пропусков
for ti in range(len(toks)):
    if tok_t[ti] is None:
        p = next(tok_t[j][1] for j in range(ti - 1, -1, -1) if tok_t[j])
        n = next(tok_t[j][0] for j in range(ti + 1, len(toks)) if tok_t[j])
        tok_t[ti] = (p, n)

# ---------------------------------------------------------------- 2. паузы -> монтаж
def read_wav(path):
    w = wave.open(path)
    sr, ch = w.getframerate(), w.getnchannels()
    a = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768
    return a.reshape(-1, ch), sr

subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', SRC, '-vn', '-ac', '2', '-ar', str(SR), f'{OUT}/voice_src.wav'], check=True)
voice, _ = read_wav(f'{OUT}/voice_src.wav')
mono = voice.mean(1)
hop = SR // 100
nfr = len(mono) // hop
db = 20 * np.log10(np.sqrt((mono[:nfr * hop].reshape(nfr, hop) ** 2).mean(1)) + 1e-6)
th = np.percentile(db, 20) + 8
sil = db < th
silences = []
i = 0
while i < nfr:
    if sil[i]:
        j = i
        while j < nfr and sil[j]:
            j += 1
        silences.append((i / 100, j / 100))
        i = j
    else:
        i += 1

SPEECH_START, SPEECH_END = 2.06, 60.70     # речь
SRC_END = 61.62                           # дальше — заставка CapCut, её не берём
PAD = 0.10
cuts = [(a + PAD, b - PAD) for a, b in silences if b - a >= 0.30 and a > SPEECH_START and b < SPEECH_END]
segs = []
cur = SPEECH_START
for a, b in cuts:
    segs.append((cur, a))
    cur = b
segs.append((cur, SRC_END))
# сетка кадров 30 fps
segs = [(round(a * FPS) / FPS, round(b * FPS) / FPS) for a, b in segs]
segs = [(a, b) for a, b in segs if b - a >= 2 / FPS]
offs = []
acc = 0.0
for a, b in segs:
    offs.append(acc)
    acc += b - a
CUT_DUR = acc
HOLD = 1.4                                 # стоп-кадр под CTA
TOTAL = CUT_DUR + HOLD
NFRAMES = int(round(TOTAL * FPS))
print(f'segments: {len(segs)}  cut duration {CUT_DUR:.2f}s (src {SRC_END - SPEECH_START:.2f}s)  total {TOTAL:.2f}s')


def o(t):
    """source time -> output time"""
    for (a, b), off in zip(segs, offs):
        if t < a:
            return off
        if t <= b:
            return off + (t - a)
    return CUT_DUR


def s_of(to):
    for (a, b), off in zip(segs, offs):
        if to < off + (b - a):
            return a + (to - off)
    return segs[-1][1] - 1 / FPS

# слова в выходном времени (+ уточнение конца слова по паузе)
words = []
for ti, (li, w) in enumerate(toks):
    a, b = tok_t[ti]
    nxt = tok_t[ti + 1][0] if ti + 1 < len(toks) else b + 0.3
    for sa, sb in silences:
        if a < sa < b and sb >= nxt - 0.15:
            b = sa
    words.append(dict(li=li, w=w, a=o(a), b=o(min(b, nxt)), key=norm(w) in {norm(k) for k in KEYS}))

json.dump(dict(segs=segs, words=[(x['w'], round(x['a'], 2), round(x['b'], 2)) for x in words]),
          open(f'{OUT}/timeline.json', 'w'), ensure_ascii=False, indent=0)

def wt(word, n=1):
    """output start time of the n-th occurrence of word"""
    k = 0
    for x in words:
        if norm(x['w']).startswith(norm(word)):
            k += 1
            if k == n:
                return x['a']
    raise KeyError(word)

# ---------------------------------------------------------------- шрифты / графика
_fc = {}


def font(kind, size, wght=900):
    k = (kind, size, wght)
    if k not in _fc:
        if kind == 'mont':
            f = ImageFont.truetype(MONT, size)
            f.set_variation_by_axes([wght])
        else:
            f = ImageFont.truetype(INTER, size)
        _fc[k] = f
    return _fc[k]

_ec = {}


def emoji(name, size):
    k = (name, size)
    if k not in _ec:
        _ec[k] = Image.open(os.path.join(ASSETS, 'emoji', name + '.png')).convert('RGBA').resize((size, size), Image.LANCZOS)
    return _ec[k]


def text_img(txt, f, fill, shadow=True, stroke=0, stroke_fill=None):
    bb = f.getbbox(txt, stroke_width=stroke)
    w, h = bb[2] - bb[0], bb[3] - bb[1]
    pad = 24
    im = Image.new('RGBA', (w + pad * 2, h + pad * 2), (0, 0, 0, 0))
    if shadow:
        sh = Image.new('RGBA', im.size, (0, 0, 0, 0))
        ImageDraw.Draw(sh).text((pad - bb[0] + 3, pad - bb[1] + 6), txt, font=f, fill=(0, 0, 0, 150), stroke_width=stroke)
        im = Image.alpha_composite(im, sh.filter(ImageFilter.GaussianBlur(7)))
    ImageDraw.Draw(im).text((pad - bb[0], pad - bb[1]), txt, font=f, fill=fill, stroke_width=stroke, stroke_fill=stroke_fill)
    return im


def fit_font(txt, kind, size, maxw, wght=900):
    while size > 20:
        f = font(kind, size, wght)
        bb = f.getbbox(txt)
        if bb[2] - bb[0] <= maxw:
            return f
        size -= 2
    return font(kind, size, wght)


def shadowed(im, blur=14, off=(0, 10), alpha=110):
    pad = blur * 3
    out = Image.new('RGBA', (im.width + pad * 2, im.height + pad * 2), (0, 0, 0, 0))
    a = im.split()[3].point(lambda v: v * alpha // 255)
    sh = Image.new('RGBA', im.size, (0, 0, 0, 255))
    sh.putalpha(a)
    out.paste(sh, (pad + off[0], pad + off[1]), sh)
    out = out.filter(ImageFilter.GaussianBlur(blur))
    out.alpha_composite(im, (pad, pad))
    return out


def pill(txt, em, bg, fg, size=46, h=100, emsz=70):
    f = font('inter', size)
    bb = f.getbbox(txt)
    tw = bb[2] - bb[0]
    w = 34 + emsz + 18 + tw + 40
    im = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((0, 0, w - 1, h - 1), radius=h // 2, fill=bg)
    if em:
        e = emoji(em, emsz)
        im.alpha_composite(e, (30, (h - emsz) // 2))
    d.text((34 + emsz + 18 - bb[0], (h - (bb[3] - bb[1])) // 2 - bb[1]), txt, font=f, fill=fg)
    return shadowed(im, blur=12, off=(0, 8), alpha=90)

# ---------------------------------------------------------------- анимация
def clamp(x, a=0.0, b=1.0):
    return max(a, min(b, x))


def pop(p):
    """scale 0 -> 1.10 -> 1.00 (spring)"""
    if p <= 0:
        return 0.0
    if p >= 1:
        return 1.0
    if p < 0.6:
        q = p / 0.6
        return 1.10 * (1 - (1 - q) ** 3)
    q = (p - 0.6) / 0.4
    return 1.10 - 0.10 * (q * q * (3 - 2 * q))


def back(p, s=1.9):
    p = clamp(p)
    p -= 1
    return p * p * ((s + 1) * p + s) + 1


def damp(t, freq=3.2, decay=4.0):
    """bounce offset (0 at rest)"""
    if t < 0:
        return 0.0
    return math.exp(-decay * t) * math.sin(2 * math.pi * freq * t)


def paste(base, im, cx, cy, scale=1.0, rot=0.0, alpha=1.0):
    if scale <= 0.01 or alpha <= 0.01:
        return
    if scale != 1.0:
        im = im.resize((max(1, int(im.width * scale)), max(1, int(im.height * scale))), Image.BILINEAR)
    if rot:
        im = im.rotate(rot, resample=Image.BICUBIC, expand=True)
    if alpha < 1:
        a = im.split()[3].point(lambda v: int(v * alpha))
        im = im.copy()
        im.putalpha(a)
    base.alpha_composite(im, (int(cx - im.width / 2), int(cy - im.height / 2))) if False else \
        _composite(base, im, int(cx - im.width / 2), int(cy - im.height / 2))


def _composite(base, im, x, y):
    # клиппинг для alpha_composite
    x0, y0 = max(0, x), max(0, y)
    x1, y1 = min(base.width, x + im.width), min(base.height, y + im.height)
    if x1 <= x0 or y1 <= y0:
        return
    crop = im.crop((x0 - x, y0 - y, x1 - x, y1 - y))
    base.alpha_composite(crop, (x0, y0))


def vgrad(color, h, a0, a1=0):
    g = np.zeros((h, W, 4), np.uint8)
    g[..., :3] = color
    t = np.linspace(0, 1, h)[:, None]
    g[..., 3] = (a0 + (a1 - a0) * (t ** 1.3) * np.ones((1, W))).astype(np.uint8)
    return Image.fromarray(g, 'RGBA')

GRAD_PURPLE = vgrad(PURPLE, 900, 235)
GRAD_DARK = vgrad((10, 6, 24), 1000, 225)

SFX = []  # (time, kind)


def sfx(t, kind='pop'):
    SFX.append((t, kind))

# ---------------------------------------------------------------- 3. сценарий
T_HOOK_END = 2.75
hook_top, hook_bot = 'ІРІҢ', 'САУ ТІС'

# Этапы (N=4)
STEPS = [
    dict(t=wt('15') - 0.25, title='ШАҒЫМ', em='mask', mini='15 жас', mini_t=wt('15')),
    dict(t=wt('жалпы', 1) - 0.1, title='РЕНТГЕН', em='xray'),
    dict(t=wt('яғни', 2) - 0.05, title='ПЕРИОДОНТИТ', em='microbe', sub='ДИАГНОЗ'),
    dict(t=wt('жалпы', 2) - 0.05, title='ЕМДЕУ', em='stetho'),
]
STEP_START = STEPS[0]['t']
STEP_END = wt('яғни', 3) - 0.05
for s in STEPS[1:]:
    sfx(s['t'], 'whoosh')
sfx(STEP_START, 'whoosh')
sfx(STEPS[0]['mini_t'], 'pop')

PILLS = [
    dict(t=wt('жағымсыз'), e=wt('тамақ') - 0.05, txt='Жағымсыз иіс', em='nose', bg=LIME, fg=BLACK, rot=-5),
    dict(t=wt('тамақ'), e=wt('жалпы', 1) - 0.15, txt='Тамақ жеу қиын', em='plate', bg=WHITE, fg=BLACK, rot=4),
    dict(t=wt('қара'), e=wt('іріңді', 1) - 0.05, txt='Қара дақ', em='blackc', bg=WHITE, fg=BLACK, rot=-4),
    dict(t=wt('іріңді', 1), e=wt('яғни', 2) - 0.1, txt='Іріңді бөлініс', em='warn', bg=LIME, fg=BLACK, rot=5),
    dict(t=wt('толыққанды'), e=wt('және', 1) - 0.05, txt='Толыққанды ем', em='check', bg=LIME, fg=BLACK, rot=-5),
    dict(t=wt('көрінісіміз'), e=STEP_END - 0.1, txt='Емнен кейін', em='grin', bg=WHITE, fg=BLACK, rot=4),
]
for p in PILLS:
    p['img'] = pill(p['txt'], p['em'], p['bg'], p['fg'])
    sfx(p['t'], 'pop')

LIST_END = wt('құрметті') - 0.05
LIST = [
    dict(t=wt('іріңді', 2), txt='Іріңді алып', em='microbe', bg=LIME, fg=BLACK, rot=-4),
    dict(t=wt('тазалап'), txt='Тазалап', em='toothbrush', bg=WHITE, fg=BLACK, rot=3),
    dict(t=wt('емдеп', 2), txt='Емдеп', em='pill', bg=PURPLE, fg=WHITE, rot=-3),
]
for p in LIST:
    p['img'] = pill(p['txt'], p['em'], p['bg'], p['fg'], size=50, h=108, emsz=76)
    sfx(p['t'], 'pop')

KEY_T, KEY_END = wt('жылына') - 0.2, wt('және', 2) - 0.05
sfx(KEY_T, 'whoosh')
sfx(wt('бір-екі'), 'pop')

BRAND_T, BRAND_END = wt('біздің', 1) - 0.05, wt('тегін') + 0.05
sfx(BRAND_T, 'whoosh')
sfx(BRAND_END, 'whoosh')
CTA_T = BRAND_END + 0.05
sfx(CTA_T + 0.05, 'pop')
sfx(CTA_T + 0.30, 'pop')

for i in range(len(hook_top)):
    pass
sfx(0.05, 'whoosh')
sfx(0.55, 'pop')
sfx(1.05, 'pop')

# ---------- subtitles: чанки
chunks = []
for li in range(len(lines)):
    ws = [x for x in words if x['li'] == li]
    cur = []
    for x in ws:
        cur.append(x)
        txt = ' '.join(y['w'] for y in cur)
        if len(cur) >= 5 or len(txt) >= 30 or x['w'][-1] in ',.!':
            chunks.append(cur)
            cur = []
    if cur:
        chunks.append(cur)
# слить слишком короткие чанки (1 слово) с предыдущими в той же строке
merged = []
for c in chunks:
    if merged and len(c) == 1 and merged[-1][-1]['li'] == c[0]['li'] and len(' '.join(y['w'] for y in merged[-1] + c)) <= 40:
        merged[-1] += c
    else:
        merged.append(c)
chunks = merged
for i, c in enumerate(chunks):
    c_start = c[0]['a'] - 0.06
    c_end = chunks[i + 1][0]['a'] - 0.06 if i + 1 < len(chunks) else c[-1]['b'] + 1.5
    c_end = min(c_end, c[-1]['b'] + 0.8)
    chunks[i] = dict(words=c, a=c_start, b=c_end)

SUB_F = font('inter', 46)
SUB_CY = 1360
SUB_MAXW = 860


def layout_chunk(ch):
    f = SUB_F
    sp = f.getlength(' ')
    rows, row, roww = [], [], 0
    for x in ch['words']:
        disp = x['w']
        if x is ch['words'][0]['__first__'] if False else False:
            pass
        wl = f.getlength(disp)
        if row and roww + sp + wl > SUB_MAXW:
            rows.append((row, roww))
            row, roww = [], 0
        row.append((x, disp, wl))
        roww += (sp if len(row) > 1 else 0) + wl
    if row:
        rows.append((row, roww))
    lh = 62
    padx, pady = 34, 20
    bw = int(max(r[1] for r in rows) + padx * 2)
    bh = int(lh * len(rows) + pady * 2)
    items = []
    for ri, (row, rw) in enumerate(rows):
        x0 = (bw - rw) / 2
        for x, disp, wl in row:
            items.append((x, disp, x0, pady + ri * lh))
            x0 += wl + sp
    ch['box'] = (bw, bh)
    ch['items'] = items

# Первую букву строки — заглавной, имена собственные — уже в тексте
first_of_line = {}
for x in words:
    if x['li'] not in first_of_line:
        first_of_line[x['li']] = x
        x['w'] = x['w'][0].upper() + x['w'][1:]
for ch in chunks:
    layout_chunk(ch)


def draw_subs(base, t):
    ch = next((c for c in chunks if c['a'] <= t < c['b']), None)
    if ch is None:
        return
    bw, bh = ch['box']
    p = clamp((t - ch['a']) / 0.22)
    sc = 0.85 + 0.15 * pop(p) if p < 1 else 1.0
    im = Image.new('RGBA', (bw, bh), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((0, 0, bw - 1, bh - 1), radius=30, fill=(0, 0, 0, 115))
    for x, disp, xx, yy in ch['items']:
        if t >= x['b']:
            col = LIME + (255,) if x['key'] else (255, 255, 255, 235)
        elif t >= x['a']:
            col = LIME + (255,) if x['key'] else (255, 255, 255, 255)
        else:
            col = (198, 244, 50, 130) if x['key'] else (165, 165, 165, 255)
        d.text((xx, yy), disp, font=SUB_F, fill=col)
    paste(base, im, W / 2, SUB_CY, scale=sc)

# ---------- step card
CARD_X0, CARD_Y0, CARD_W, CARD_H = 60, 150, 960, 300


def draw_step(base, t):
    if not (STEP_START <= t < STEP_END + 0.4):
        return
    pin = back((t - STEP_START) / 0.35, 1.4)
    pout = clamp((t - STEP_END) / 0.3)
    dy = -(1 - pin) * 520 - (pout ** 2) * 520
    idx = max(i for i, s in enumerate(STEPS) if s['t'] <= t)
    st = STEPS[idx]
    card = Image.new('RGBA', (CARD_W, CARD_H), (0, 0, 0, 0))
    d = ImageDraw.Draw(card)
    d.rounded_rectangle((0, 0, CARD_W - 1, CARD_H - 1), radius=44, fill=PURPLE + (255,))
    # мелкий заголовок
    small = f'ҚАДАМ {idx + 1} / {len(STEPS)}' + (f'  ·  {st["sub"]}' if st.get('sub') else '')
    d.text((48, 40), small, font=font('inter', 36), fill=(255, 255, 255, 200))
    # смена шага: поп текста
    ps = pop(clamp((t - st['t']) / 0.25)) if idx > 0 or t - st['t'] < 0.25 else 1.0
    tf = fit_font(st['title'], 'mont', 104, 700)
    timg = text_img(st['title'], tf, WHITE, shadow=False)
    if ps > 0.01:
        ti = timg.resize((max(1, int(timg.width * ps)), max(1, int(timg.height * ps))), Image.BILINEAR)
        card.alpha_composite(ti, (int(24 + timg.width * (1 - ps) / 2), int(84 + timg.height * (1 - ps) / 2)))
    # эмодзи в углу
    eb = damp(t - st['t'], 2.5, 3.5)
    e = emoji(st['em'], 150)
    e = e.rotate(8 + 10 * eb, resample=Image.BICUBIC, expand=True)
    card.alpha_composite(e, (CARD_W - e.width - 26, 18 + int(-18 * eb)))
    # мини-таблетка с цифрами
    if st.get('mini') and t >= st['mini_t']:
        mp = pop(clamp((t - st['mini_t']) / 0.25))
        f = font('inter', 40)
        bb = f.getbbox(st['mini'])
        mw, mh = bb[2] - bb[0] + 48, 64
        mi = Image.new('RGBA', (mw, mh), (0, 0, 0, 0))
        md = ImageDraw.Draw(mi)
        md.rounded_rectangle((0, 0, mw - 1, mh - 1), radius=32, fill=LIME + (255,))
        md.text((24 - bb[0], (mh - (bb[3] - bb[1])) // 2 - bb[1]), st['mini'], font=f, fill=BLACK)
        mi = mi.resize((max(1, int(mw * mp)), max(1, int(mh * mp))), Image.BILINEAR).rotate(-4, expand=True, resample=Image.BICUBIC)
        tx = 24 + timg.width + 6
        card.alpha_composite(mi, (int(tx + (mw - mi.width) / 2), int(112 + (mh - mi.height) / 2)))
    # сегментный прогресс-бар
    n = len(STEPS)
    gap, bx0, bx1, by = 14, 48, CARD_W - 48, 238
    sw = (bx1 - bx0 - gap * (n - 1)) / n
    for i in range(n):
        x0 = bx0 + i * (sw + gap)
        d.rounded_rectangle((x0, by, x0 + sw, by + 22), radius=11, fill=(255, 255, 255, 70))
        if i < idx:
            fill = 1.0
        elif i == idx:
            fill = 1 - (1 - clamp((t - st['t']) / 0.45)) ** 3
        else:
            fill = 0
        if fill > 0:
            d.rounded_rectangle((x0, by, x0 + max(22, sw * fill), by + 22), radius=11, fill=LIME + (255,))
    card = shadowed(card, blur=16, off=(0, 12), alpha=110)
    paste(base, card, CARD_X0 + CARD_W / 2, CARD_Y0 + CARD_H / 2 + dy)

# ---------- pills
PILL_POS = (370, 690)


def draw_pills(base, t):
    for p in PILLS:
        if p['t'] <= t < p['e'] + 0.2:
            sc = pop(clamp((t - p['t']) / 0.26))
            if t > p['e']:
                sc *= 1 - clamp((t - p['e']) / 0.2)
            img = p['img']
            cx = 40 + img.width / 2
            paste(base, img, cx, PILL_POS[1], scale=sc, rot=p['rot'])


def draw_list(base, t):
    if not (LIST[0]['t'] <= t < LIST_END + 0.25):
        return
    out = clamp((t - LIST_END) / 0.25)
    for i, p in enumerate(LIST):
        if t < p['t']:
            continue
        sc = pop(clamp((t - p['t']) / 0.26)) * (1 - out)
        img = p['img']
        paste(base, img, 34 + img.width / 2, 200 + i * 128, scale=sc, rot=p['rot'])

# ---------- hook
def draw_hook(base, t):
    if t > T_HOOK_END + 0.3:
        return
    out = clamp((t - T_HOOK_END) / 0.3)
    ga = clamp(t / 0.2) * (1 - out)
    paste(base, GRAD_PURPLE, W / 2, 450, alpha=ga)
    f = font('mont', 170)
    # верхнее слово — побуквенно
    def letters(word, col, cy, t0):
        widths = [f.getlength(c) for c in word]
        tot = sum(widths)
        x = W / 2 - tot / 2
        for i, c in enumerate(word):
            lt = t0 + i * 0.07
            if t >= lt and c != ' ':
                sc = pop(clamp((t - lt) / 0.25)) * (1 - out)
                im = _letter(c, col)
                paste(base, im, x + widths[i] / 2, cy, scale=sc)
            x += widths[i]
    letters(hook_top, WHITE, 270, 0.10)
    # стрелка вниз
    if t >= 0.48:
        sc = pop(clamp((t - 0.48) / 0.22)) * (1 - out)
        bob = 10 * math.sin((t - 0.48) * 9)
        paste(base, ARROW_SMALL, W / 2, 420 + bob, scale=sc)
    letters(hook_bot, LIME, 565, 0.62)
    # 3D-эмодзи
    for name, cx, cy, t0, rot in (('mask', 150, 250, 0.35, -12), ('grin', 985, 455, 1.05, 10)):
        if t >= t0:
            sc = pop(clamp((t - t0) / 0.25)) * (1 - out)
            b = damp(t - t0, 2.2, 1.6)
            paste(base, emoji(name, 160), cx, cy - 40 * abs(b), scale=sc, rot=rot + 8 * b)

_lc = {}


def _letter(c, col):
    k = (c, col)
    if k not in _lc:
        _lc[k] = text_img(c, font('mont', 170), col)
    return _lc[k]


def chevron(color, w, h, th):
    im = Image.new('RGBA', (w + th * 2, h + th * 2), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    pts = [(th, th), (th + w / 2, th + h), (th + w, th)]
    d.line(pts, fill=color, width=th, joint='curve')
    for x, y in (pts[0], pts[2], pts[1]):
        d.ellipse((x - th / 2, y - th / 2, x + th / 2, y + th / 2), fill=color)
    return im

ARROW_SMALL = shadowed(chevron(WHITE + (255,), 70, 38, 14), blur=8, off=(0, 4), alpha=90)
ARROW_LIME = shadowed(chevron(LIME + (255,), 96, 50, 18), blur=8, off=(0, 5), alpha=110)

# ---------- ключевое слово
KEY_SMALL = text_img('балаңыздың тісін жылына', font('inter', 50), WHITE)
KEY_BIG = text_img('1–2 РЕТ', font('mont', 200), LIME)
KEY_SMALL2 = text_img('тексертіңіз', font('inter', 50), WHITE)


def draw_key(base, t):
    if not (KEY_T <= t < KEY_END + 0.3):
        return
    out = clamp((t - KEY_END) / 0.3)
    ga = clamp((t - KEY_T) / 0.2) * (1 - out)
    paste(base, GRAD_PURPLE, W / 2, 450, alpha=ga)
    sc = pop(clamp((t - KEY_T) / 0.25)) * (1 - out)
    paste(base, KEY_SMALL, W / 2, 210, scale=sc)
    tb = wt('бір-екі') - 0.1
    if t >= tb:
        sc2 = pop(clamp((t - tb) / 0.28)) * (1 - out)
        paste(base, KEY_BIG, W / 2 - 40, 380, scale=sc2)
        # мерцающая звёздочка
        tw = 0.75 + 0.25 * math.sin((t - tb) * 11)
        rot = 12 * math.sin((t - tb) * 4)
        paste(base, emoji('sparkles', 140), W / 2 + KEY_BIG.width / 2 - 30, 290, scale=sc2 * tw, rot=rot)
    tk = wt('тексертіп') - 0.1
    if t >= tk:
        paste(base, KEY_SMALL2, W / 2, 560, scale=pop(clamp((t - tk) / 0.25)) * (1 - out))

# ---------- бренд-экран
BR_TITLE1 = text_img('ГРАНИТ', font('mont', 150), BLACK, shadow=False)
BR_TITLE2 = text_img('ДЕНТ', font('mont', 150), BLACK, shadow=False)


def _brand_pill():
    f = font('inter', 44)
    txt = 'стоматология · тегін кеңес'
    bb = f.getbbox(txt)
    w, h = bb[2] - bb[0] + 60, 88
    im = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((0, 0, w - 1, h - 1), radius=44, fill=(0, 0, 0, 255))
    d.text((30 - bb[0], (h - (bb[3] - bb[1])) // 2 - bb[1]), txt, font=f, fill=WHITE)
    return im
BR_PILL = _brand_pill()
_card_mask = {}


def brand_frame(base_frame, t):
    """returns composited Image for brand screen, or None"""
    if not (BRAND_T <= t < BRAND_END + 0.3):
        return None
    pin = clamp((t - BRAND_T) / 0.35)
    pout = clamp((t - BRAND_END) / 0.3)
    k = back(pin, 1.3) * (1 - (pout * pout * (3 - 2 * pout)))  # 0..1 сила эффекта
    k = clamp(k, 0, 1.08)
    scale = 1 - 0.40 * k
    rot = 5 * k
    cx = W / 2 + (640 - W / 2) * k
    cy = H / 2 + (1300 - H / 2) * k
    bg = Image.new('RGBA', (W, H), LIME + (255,))
    bg.putalpha(int(255 * clamp(k)))
    out = base_frame.copy()
    out.alpha_composite(bg)
    vw, vh = int(W * scale), int(H * scale)
    v = base_frame.resize((vw, vh), Image.BILINEAR)
    key = (vw, vh)
    if key not in _card_mask:
        m = Image.new('L', (vw, vh), 0)
        ImageDraw.Draw(m).rounded_rectangle((0, 0, vw - 1, vh - 1), radius=int(48 * clamp(k * 1.2)), fill=255)
        _card_mask[key] = m
    v.putalpha(_card_mask[key])
    v = shadowed(v, blur=22, off=(0, 18), alpha=int(140 * clamp(k)))
    v = v.rotate(rot, resample=Image.BICUBIC, expand=True)
    _composite(out, v, int(cx - v.width / 2), int(cy - v.height / 2))
    # заголовок и таблетка
    tt = t - BRAND_T
    a = 1 - pout
    paste(out, BR_TITLE1, 60 + BR_TITLE1.width / 2, 150 + BR_TITLE1.height / 2, scale=pop(clamp((tt - 0.12) / 0.25)) * a)
    paste(out, BR_TITLE2, 60 + BR_TITLE2.width / 2, 300 + BR_TITLE2.height / 2, scale=pop(clamp((tt - 0.22) / 0.25)) * a)
    paste(out, BR_PILL, 74 + BR_PILL.width / 2, 520, scale=pop(clamp((tt - 0.35) / 0.25)) * a, rot=-3)
    if tt > 0.4:
        b = damp(tt - 0.4, 2.0, 1.2)
        paste(out, emoji('rocket', 200), 170, 900 - 60 * abs(b) - 30 * (tt - 0.4), scale=pop(clamp((tt - 0.4) / 0.25)) * a, rot=-10 * b)
    return out

# ---------- CTA
CTA_Q = text_img('Балаңыздың тісі ауыра ма?', font('inter', 52), WHITE)
CTA_L1 = text_img('ТЕГІН КЕҢЕСКЕ', fit_font('ТЕГІН КЕҢЕСКЕ', 'mont', 124, 960), LIME)
CTA_L2 = text_img('ЖАЗЫЛЫҢЫЗ', fit_font('ЖАЗЫЛЫҢЫЗ', 'mont', 124, 960), WHITE)


def draw_cta(base, t):
    if t < CTA_T:
        return
    tt = t - CTA_T
    paste(base, GRAD_DARK, W / 2, 500, alpha=clamp(tt / 0.25))
    paste(base, CTA_Q, W / 2, 170, scale=pop(clamp(tt / 0.25)))
    paste(base, CTA_L1, W / 2, 300, scale=pop(clamp((tt - 0.12) / 0.26)), rot=0)
    paste(base, CTA_L2, W / 2, 440, scale=pop(clamp((tt - 0.30) / 0.26)))
    for i in range(3):
        t0 = 0.5 + i * 0.1
        if tt >= t0:
            sc = pop(clamp((tt - t0) / 0.22))
            bob = 16 * abs(math.sin((tt - t0) * math.pi * 1.75 - i * 0.6))
            paste(base, ARROW_LIME, W / 2 - 60, 560 + i * 52 + bob, scale=sc)
    if tt >= 0.8:
        b = damp(tt - 0.8, 1.8, 0.8)
        paste(base, emoji('down', 150), W / 2 + 100, 640 + 22 * abs(math.sin((tt - 0.8) * math.pi * 1.75)),
              scale=pop(clamp((tt - 0.8) / 0.25)), rot=8 * b)

# ---------------------------------------------------------------- 4. рендер видео
def render():
    # исходник -> 1080x1920 @30, читаем последовательно
    dec = subprocess.Popen(['ffmpeg', '-v', 'error', '-i', SRC, '-t', f'{SRC_END + 0.2}', '-vf',
                            'fps=30,scale=1080:1920:flags=lanczos', '-pix_fmt', 'rgb24', '-f', 'rawvideo', '-'],
                           stdout=subprocess.PIPE, bufsize=10 ** 8)
    enc = subprocess.Popen(['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}',
                            '-r', str(FPS), '-i', '-', '-c:v', 'libx264', '-preset', 'medium', '-crf', '17',
                            '-pix_fmt', 'yuv420p', '-movflags', '+faststart', f'{OUT}/video_only.mp4'],
                           stdin=subprocess.PIPE)
    fsz = W * H * 3
    src_idx = -1
    cur = None
    for k in range(NFRAMES):
        to = k / FPS
        st = s_of(min(to, CUT_DUR - 1 / FPS))
        want = int(round(st * FPS))
        while src_idx < want:
            buf = dec.stdout.read(fsz)
            if len(buf) < fsz:
                break
            cur = buf
            src_idx += 1
        frame = Image.frombuffer('RGB', (W, H), cur, 'raw', 'RGB', 0, 1).convert('RGBA')
        t = to
        bf = brand_frame(frame, t)
        if bf is not None:
            frame = bf
        draw_hook(frame, t)
        draw_step(frame, t)
        draw_pills(frame, t)
        draw_list(frame, t)
        draw_key(frame, t)
        draw_cta(frame, t)
        if bf is None or t > BRAND_END + 0.25:
            draw_subs(frame, t)
        enc.stdin.write(frame.convert('RGB').tobytes())
        if k % 150 == 0:
            print(f'frame {k}/{NFRAMES}', flush=True)
    enc.stdin.close()
    enc.wait()
    dec.kill()

# ---------------------------------------------------------------- 5. звук
def synth_music(dur):
    bpm = 100
    beat = 60 / bpm
    n = int(dur * SR)
    out = np.zeros((n, 2), np.float32)
    rng = np.random.default_rng(7)
    tt = lambda d: np.arange(int(d * SR)) / SR

    def add(sig, t0, pan=0.0):
        i0 = int(t0 * SR)
        if i0 >= n:
            return
        sig = sig[:n - i0]
        out[i0:i0 + len(sig), 0] += sig * (1 - max(0, pan))
        out[i0:i0 + len(sig), 1] += sig * (1 + min(0, pan))

    x = tt(0.35)
    kick = np.sin(2 * np.pi * (45 * x + 90 * (1 - np.exp(-x * 30)) / 30)) * np.exp(-x * 9) * 0.9
    x = tt(0.22)
    clap = rng.standard_normal(len(x)) * np.exp(-x * 22) * 0.35
    clap = np.convolve(clap, np.ones(3) / 3, 'same')
    x = tt(0.05)
    hat = np.diff(rng.standard_normal(len(x) + 1)) * np.exp(-x * 90) * 0.12
    # аккорды Am - F - C - G (лёгкий pluck)
    chords = [[57, 60, 64], [53, 57, 60], [48, 52, 55], [55, 59, 62]]
    roots = [45, 41, 36, 43]
    mtof = lambda m: 440 * 2 ** ((m - 69) / 12)
    bar = beat * 4
    nb = int(dur / beat) + 1
    for b in range(nb):
        t0 = b * beat
        bi = (b // 4) % 4
        if b % 4 in (0, 2):
            add(kick, t0)
        if b % 4 == 2 and (b // 4) % 2 == 1:
            add(kick * 0.6, t0 + beat * 0.75)
        if b % 4 in (1, 3):
            add(clap, t0)
        for h in range(2):
            sw = 0.04 if h else 0
            add(hat * (1.0 if h == 0 else 0.6), t0 + h * beat / 2 + sw, pan=0.3)
        if b % 2 == 0:
            for m in chords[bi]:
                x = tt(beat * 1.6)
                f = mtof(m + 12)
                s = (np.sin(2 * np.pi * f * x) + 0.3 * np.sin(4 * np.pi * f * x)) * np.exp(-x * 3.2) * 0.07
                add(s, t0 + (beat / 2 if b % 4 == 2 else 0), pan=-0.2)
        # бас
        x = tt(beat * 0.9)
        f = mtof(roots[bi])
        bass = np.sin(2 * np.pi * f * x) * np.minimum(1, x * 80) * np.exp(-x * 2.5) * 0.35
        add(bass, t0)
    return out


def synth_sfx(kind):
    if kind == 'pop':
        x = np.arange(int(0.09 * SR)) / SR
        f = 300 + 900 * np.exp(-x * 60)
        s = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-x * 45) * 0.5
        s[:40] += np.linspace(0.3, 0, 40)
        return s
    x = np.arange(int(0.32 * SR)) / SR
    rng = np.random.default_rng(3)
    nz = rng.standard_normal(len(x))
    env = np.sin(np.pi * np.clip(x / 0.32, 0, 1)) ** 2
    # «подвижный» low-pass: смесь разной гладкости
    out = np.zeros_like(nz)
    k1 = np.convolve(nz, np.ones(24) / 24, 'same')
    k2 = np.convolve(nz, np.ones(6) / 6, 'same')
    m = x / 0.32
    out = k1 * (1 - m) + k2 * m
    return out * env * 0.55


def build_audio():
    # голос по монтажу
    parts = []
    fade = int(0.008 * SR)
    for a, b in segs:
        p = voice[int(round(a * SR)):int(round(b * SR))].copy()
        r = np.linspace(0, 1, fade)[:, None]
        p[:fade] *= r
        p[-fade:] *= r[::-1]
        parts.append(p)
    v = np.concatenate(parts)
    n = int(round(TOTAL * SR))
    v = np.pad(v, ((0, max(0, n - len(v))), (0, 0)))[:n]
    vrms = np.sqrt(np.mean(v[np.abs(v).mean(1) > 0.01] ** 2))
    # музыка: −20 dB под голосом, при речи — приглушение
    mus = synth_music(TOTAL)
    mrms = np.sqrt(np.mean(mus ** 2))
    mus *= (vrms * 10 ** (-20 / 20)) / mrms
    env = np.abs(v).mean(1)
    win = int(0.05 * SR)
    env = np.convolve(env, np.ones(win) / win, 'same')
    speaking = (env > vrms * 0.15).astype(np.float32)
    # attack 40 ms / release 350 ms
    g = np.empty_like(speaking)
    acc = 0.0
    a_c, r_c = 1 / (0.04 * SR), 1 / (0.35 * SR)
    for i in range(0, len(speaking), 64):
        target = speaking[i]
        acc += (target - acc) * min(1, (a_c if target > acc else r_c) * 64)
        g[i:i + 64] = acc
    gain = 10 ** ((-6 * g + 4 * (1 - g)) / 20)       # речь: −20 dB, паузы/финал: −14 dB
    mus *= gain[:, None]
    # плавный вход/выход музыки
    fi = int(0.4 * SR)
    mus[:fi] *= np.linspace(0, 1, fi)[:, None]
    fo = int(1.0 * SR)
    mus[-fo:] *= np.linspace(1, 0, fo)[:, None]
    # sfx
    fx = np.zeros_like(v)
    for t0, kind in SFX:
        s = synth_sfx(kind) * (vrms * 1.1)
        i0 = int(t0 * SR)
        if i0 < 0 or i0 >= n:
            continue
        s = s[:n - i0]
        fx[i0:i0 + len(s)] += s[:, None]
    mix = v + mus + fx
    peak = np.abs(mix).max()
    if peak > 0.97:
        mix *= 0.97 / peak
    pcm = (mix * 32767).astype(np.int16)
    with wave.open(f'{OUT}/mix.wav', 'wb') as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())


if __name__ == '__main__':
    only = os.environ.get('ONLY')
    if os.environ.get('PREVIEW'):
        ts = [float(x) for x in os.environ['PREVIEW'].split(',')]
        tiles = []
        for t in ts:
            st = s_of(min(t, CUT_DUR - 1 / FPS))
            raw = subprocess.run(['ffmpeg', '-v', 'error', '-ss', f'{st:.3f}', '-i', SRC, '-frames:v', '1', '-vf',
                                  'scale=1080:1920', '-pix_fmt', 'rgb24', '-f', 'rawvideo', '-'], capture_output=True).stdout
            frame = Image.frombuffer('RGB', (W, H), raw, 'raw', 'RGB', 0, 1).convert('RGBA')
            bf = brand_frame(frame, t)
            if bf is not None:
                frame = bf
            for fn in (draw_hook, draw_step, draw_pills, draw_list, draw_key, draw_cta):
                fn(frame, t)
            if bf is None or t > BRAND_END + 0.25:
                draw_subs(frame, t)
            ImageDraw.Draw(frame).text((20, 1860), f'{t:.2f}', font=font('inter', 40), fill=(255, 0, 0, 255))
            tiles.append(frame.convert('RGB').resize((360, 640)))
        sheet = Image.new('RGB', (360 * min(6, len(tiles)), 640 * ((len(tiles) + 5) // 6)))
        for i, im in enumerate(tiles):
            sheet.paste(im, ((i % 6) * 360, (i // 6) * 640))
        sheet.save(f'{OUT}/preview.jpg', quality=88)
        print('preview saved'); sys.exit()
    build_audio()
    print('audio ok; sfx', len(SFX))
    if only == 'audio':
        sys.exit()
    render()
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', f'{OUT}/video_only.mp4', '-i', f'{OUT}/mix.wav',
                    '-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k', '-shortest', '-movflags', '+faststart',
                    f'{OUT}/video1_edu_reels.mp4'], check=True)
    print('done', f'{OUT}/video1_edu_reels.mp4')
