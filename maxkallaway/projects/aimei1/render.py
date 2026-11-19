# Ai Mei reel рендері: кадрлар (зум), субтитр, карточкалар, аудио микс
import json, os, sys, math, subprocess
import numpy as np, cv2
from PIL import Image, ImageDraw, ImageFont, ImageFilter
D = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, D)
from edit import tmap, merged_silence, TOTAL

W, H, FPS = 1080, 1920, 30
PREVIEW = '--preview' in sys.argv
ONLY = None
for a in sys.argv:
    if a.startswith('--t='): ONLY = [float(x) for x in a[4:].split(',')]
DUR = TOTAL + 1.0

GREEN = (22, 163, 74); GREEN_D = (20, 83, 45); WHITE = (255, 255, 255)
FB = '/usr/share/fonts/opentype/inter/Inter-Bold.otf'
FS = '/usr/share/fonts/opentype/inter/Inter-SemiBold.otf'
FM = '/usr/share/fonts/opentype/inter/Inter-Medium.otf'
_fc = {}
def font(p, s):
    k = (p, s)
    if k not in _fc: _fc[k] = ImageFont.truetype(p, s)
    return _fc[k]

def ease(x): x = min(1, max(0, x)); return x*x*(3-2*x)
def ease_out(x): x = min(1, max(0, x)); return 1-(1-x)**3

# ---------------- сөздер ----------------
SIL = merged_silence()
def fix_start(t):
    for a, b in SIL:
        if a <= t < b: return b
    return t
def fix_end(t):
    for a, b in SIL:
        if a < t <= b: return a
    return t

segs = json.load(open(os.path.join(D, 'stt_turbo.json')))[:-1]
raw = [[w[0], w[1], w[2].strip()] for s in segs for w in s['w']]
FIX = {'бірде': 'бірдей', 'конгтың': 'Конгтың', 'мыя': 'ми', 'ағзанызды': 'ағзаңызды', 'оламаңыз': 'уламаңыз',
       'тәжірбелі': 'тәжірибелі', 'аймей': 'Ai Mei', 'бізді': 'біздің', '6а': '6А', 'ауданы': 'ауданы,',
       'көмектеседі': 'көмектеседі?'}
words = []; qand = 0
for a, b, t in raw:
    if t in ('жаймыз',):
        words[-1][1] = b; words[-1][2] = 'мекенжайымыз'; continue
    if t in ('дұроп', '3') and words and words[-1][2].startswith('11'):
        words[-1][1] = b; words[-1][2] = '11/3'; continue
    if t == 'қанд':
        t = 'қант' if qand == 0 else 'қан'; qand += 1
    t = FIX.get(t, t)
    words.append([a, b, t])
for w in words:
    a, b = fix_start(w[0]), fix_end(w[1])
    if b <= a: b = a + 0.15
    w[0], w[1] = tmap(a), tmap(b)

PHR = """Қытай медицинасының|ең басты ерекшелігі|аурудың белгісін|уақытша басу емес|оны түбірінен емдеу|Оның ішінде|доктор Конгтың|табиғи шөп дәрілері|ағзаны қалпына келтіруде|керемет нәтиже береді|Ең маңыздысы|бұл табиғи шөптер|барлығына бірдей емес|әр адамның ағзасына|диагнозына және жағдайына|қатаң түрде|жеке дайындалады|Доктор Конгтың|шөптік терапиясы|қандай мәселелерге көмектеседі?|#қант диабеті мен|#қан қысымының көтерілуіне|#жүрек қан тамырлары|#және бас ми жүйесінің бұзылысына|#асқазан және ішек жолдарының ауруларына|#өттегі тас және бауыр жұмысының бұзылуына|#түрлі созылмалы тері ауруларына|#қарсы аса тиімді|Синтетикалық препараттармен|ағзаңызды уламаңыз|Табиғи әрі түбірлі|емді таңдаңыз|Денсаулығыңызды|тәжірибелі маманға|сеніп тапсырыңыз|Ai Mei орталығына келіп|доктор Конгтың|қабылдауына жазылыңыз|#біздің мекенжайымыз|#6А шағын ауданы, 11/3"""
phrases = []; i = 0
for p in PHR.split('|'):
    hidden = p.startswith('#'); p = p.lstrip('#')
    toks = p.replace('Ai Mei', 'Ai~Mei').split()
    toks = [t.replace('~', ' ') for t in toks]
    ws = []
    for t in toks:
        assert words[i][2].lower() == t.lower(), (i, words[i][2], t)
        ws.append([words[i][0], words[i][1], t]); i += 1
    phrases.append(dict(w=ws, hidden=hidden))
assert i == len(words), (i, len(words))
for k, p in enumerate(phrases):
    p['s'] = p['w'][0][0] - 0.04
    nxt = phrases[k+1]['w'][0][0] - 0.04 if k+1 < len(phrases) else DUR
    p['e'] = min(nxt, p['w'][-1][1] + 0.6)
WT = {}  # сөз -> уақыт (карточкалар үшін)
for p in phrases:
    for a, b, t in p['w']: WT.setdefault(t.lower(), []).append(a)

# ---------------- кадрлар ----------------
T = lambda x: tmap(x)
LIST_S, LIST_E = T(32.149) - 0.05, T(49.94) - 0.25   # тізім бөлімі
END_S = T(63.454) - 0.05
SHOTS = [  # (басы, соңы, клип, src_in, жылдамдық, z0, z1, фокус(x,y) 0..1)
 (0.0,        T(8.57),  5, 0.0, 0.80, 1.00, 1.10, (0.5, 0.40)),
 (T(8.57),    T(10.256),9, 0.0, 1.00, 1.02, 1.20, (0.5, 0.42)),
 (T(10.256),  T(17.262),4, 0.2, 1.00, 1.14, 1.00, (0.5, 0.45)),
 (T(17.262),  T(21.433),2, 0.0, 1.00, 1.00, 1.08, (0.6, 0.40)),
 (T(21.433),  T(27.472),2, 3.9, 0.85, 1.06, 1.20, (0.55, 0.62)),
 (T(27.472),  LIST_S,   7, 0.0, 0.70, 1.16, 1.02, (0.5, 0.5)),
 (LIST_S,     LIST_S+6.0, 8, 0.0, 0.60, 1.00, 1.08, (0.5, 0.5)),
 (LIST_S+6.0, LIST_S+8.6, 9, 1.5, 0.60, 1.05, 1.12, (0.5, 0.45)),
 (LIST_S+8.6, LIST_S+13.8,5, 0.2, 0.75, 1.10, 1.02, (0.5, 0.45)),
 (LIST_S+13.8,LIST_E,   4, 4.9, 1.00, 1.04, 1.10, (0.5, 0.5)),
 (LIST_E,     T(56.47), 8, 0.0, 0.68, 1.20, 1.00, (0.5, 0.5)),
 (T(56.47),   T(59.725),9, 0.1, 1.00, 1.00, 1.10, (0.5, 0.38)),
 (T(59.725),  END_S,    3, 0.3, 1.10, 1.00, 1.08, (0.5, 0.42)),
 (END_S,      DUR,      6, 0.0, 1.05, 1.14, 1.00, (0.5, 0.45)),
]

class Src:
    def __init__(self, n):
        self.cap = cv2.VideoCapture(os.path.join(D, f'pre/c{n}.mp4'))
        self.n = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT)); self.pos = -1; self.fr = None
    def get(self, idx):
        idx = min(max(0, idx), self.n-1)
        if idx < self.pos or idx > self.pos + 90:
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, idx); self.pos = idx-1
        while self.pos < idx:
            ok, f = self.cap.read()
            if not ok: break
            self.fr = f; self.pos += 1
        return self.fr

_src = {}
def shot_frame(t):
    for k, (s, e, c, si, sp, z0, z1, (fx, fy)) in enumerate(SHOTS):
        if s <= t < e or k == len(SHOTS)-1: break
    if c not in _src: _src[c] = Src(c)
    src = _src[c]; loc = t - s
    f = src.get(int(round((si + loc*sp)*60)))
    sh, sw = f.shape[:2]
    u = ease((loc)/(e-s))
    if k == 1:  # түбірінен — жылдам панч-зум
        u = ease_out(loc/0.5)
    z = z0 + (z1-z0)*u
    sc = (W/sw)*z
    hw, hh = W/2/sc, H/2/sc
    cx = min(max(fx*sw, hw), sw-hw); cy = min(max(fy*sh, hh), sh-hh)
    M = np.float32([[sc, 0, W/2 - sc*cx], [0, sc, H/2 - sc*cy]])
    return cv2.warpAffine(f, M, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)

def grade(img):
    # жеңіл түстік түзету: контраст + аздап жылылық
    x = img.astype(np.float32)
    x = (x - 128)*1.04 + 128 + 2
    return np.clip(x, 0, 255)

# ---------------- графика ----------------
def text_w(d, s, f): return d.textlength(s, font=f)

def shadowed(layer_size, draw_fn, blur=10, op=150):
    sh = Image.new('L', layer_size, 0); draw_fn(ImageDraw.Draw(sh), True)
    sh = sh.filter(ImageFilter.GaussianBlur(blur)).point(lambda v: v*op//255)
    return sh

def draw_sub(ov, t):
    p = None
    for q in phrases:
        if q['s'] <= t < q['e'] and not q['hidden']: p = q
    if not p: return
    age = t - p['s']; a = ease_out(age/0.18); dy = int((1-a)*18)
    size = 64
    f = font(FB, size); d0 = ImageDraw.Draw(ov)
    toks = [w[2] for w in p['w']]
    sp = size*0.28
    while sum(text_w(d0, x, f) for x in toks) + sp*(len(toks)-1) > 940:
        size -= 2; f = font(FB, size); sp = size*0.28
    widths = [text_w(d0, x, f) for x in toks]
    total = sum(widths) + sp*(len(toks)-1)
    x0 = (W-total)/2; y = 1330 + dy
    act = -1
    for j, (ws, we, _) in enumerate(p['w']):
        if t >= ws - 0.03: act = j
    L = Image.new('RGBA', (W, 220), (0, 0, 0, 0)); ld = ImageDraw.Draw(L)
    yy = 70
    def shapes(dd, mask):
        x = x0
        for j, tok in enumerate(toks):
            dd.text((x, yy), tok, font=f, fill=255 if mask else WHITE)
            x += widths[j] + sp
    shm = shadowed((W, 220), shapes, blur=9, op=170)
    L.paste((0, 0, 0, 255), (0, 0), shm)
    x = x0
    for j, tok in enumerate(toks):
        if j == act:
            pa = ease_out((t - p['w'][j][0] + 0.03)/0.12)
            pad = 14; bx0, bx1 = x - pad, x + widths[j] + pad
            asc = f.getbbox('ҚӘ')[1]; desc = f.getbbox('ДЩуғ')[3]
            r = (bx0, yy + asc - 12, bx1, yy + desc + 10)
            ld.rounded_rectangle(r, radius=16, fill=GREEN + (int(255*pa),))
        ld.text((x, yy), tok, font=f, fill=WHITE)
        x += widths[j] + sp
    if a < 1: L.putalpha(L.getchannel('A').point(lambda v: int(v*a)))
    ov.alpha_composite(L, (0, y - 70 - 40))

def pill(d, xy, text, f, fill, tc, padx=26, pady=14):
    x, y = xy; tw = d.textlength(text, font=f); bb = f.getbbox('ҚЫТАЙ')
    h = bb[3] - bb[1]
    d.rounded_rectangle((x, y, x + tw + 2*padx, y + h + 2*pady), radius=(h + 2*pady)//2, fill=fill)
    d.text((x + padx, y + pady - bb[1]), text, font=f, fill=tc)
    return tw + 2*padx, h + 2*pady

def fade_layer(L, a):
    if a >= 1: return L
    L = L.copy(); L.putalpha(L.getchannel('A').point(lambda v: int(v*a))); return L

def draw_title(ov, t):
    s, e = 0.15, T(8.4)
    if not (s <= t < e + 0.3): return
    a_in = ease_out((t-s)/0.5); a_out = 1 - ease((t-e)/0.3)
    a = min(a_in, a_out)
    L = Image.new('RGBA', (W, 400), (0, 0, 0, 0)); d = ImageDraw.Draw(L)
    f1 = font(FB, 34); f2 = font(FB, 74)
    tw = d.textlength('ҚЫТАЙ МЕДИЦИНАСЫ', font=f1) + 52
    pill(d, ((W - tw)/2, 40), 'ҚЫТАЙ МЕДИЦИНАСЫ', f1, GREEN, WHITE)
    lines = ['Ауруды түбірінен', 'емдеу жолы']
    def sh(dd, m):
        for k, ln in enumerate(lines):
            dd.text(((W - dd.textlength(ln, font=f2))/2, 130 + k*92), ln, font=f2, fill=255 if m else WHITE)
    shm = shadowed((W, 400), sh, 12, 160); L.paste((0, 0, 0, 255), (0, 0), shm) if False else None
    base = Image.new('RGBA', (W, 400), (0, 0, 0, 0)); base.paste((0, 0, 0, 255), (0, 0), shm)
    base.alpha_composite(L); d = ImageDraw.Draw(base)
    for k, ln in enumerate(lines):
        d.text(((W - d.textlength(ln, font=f2))/2, 130 + k*92), ln, font=f2, fill=WHITE)
    ov.alpha_composite(fade_layer(base, a), (0, 220 + int((1-a_in)*30)))

CARDS = [('қант', 'Қант диабеті'), ('қан', 'Қан қысымының көтерілуі'), ('жүрек', 'Жүрек-қан тамырлары'),
         ('бас', 'Бас ми жүйесінің бұзылысы'), ('асқазан', 'Асқазан-ішек аурулары'),
         ('өттегі', 'Өттегі тас, бауыр жұмысы'), ('түрлі', 'Созылмалы тері аурулары')]
CARD_T = [WT[k][0] for k, _ in CARDS]
TIIMDI = WT['аса'][0]

def check_icon(d, cx, cy, r, bg, fg):
    d.ellipse((cx-r, cy-r, cx+r, cy+r), fill=bg)
    d.line([(cx - r*0.45, cy + r*0.02), (cx - r*0.1, cy + r*0.38), (cx + r*0.5, cy - r*0.35)], fill=fg, width=max(3, int(r*0.22)), joint='curve')

def draw_list(ov, t):
    if not (LIST_S - 0.1 <= t < LIST_E + 0.35): return
    a_out = 1 - ease((t - LIST_E)/0.35)
    L = Image.new('RGBA', (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(L)
    ha = min(ease_out((t - LIST_S)/0.4), a_out)
    f0 = font(FS, 40); f1 = font(FB, 58)
    hd1 = 'Доктор Конгтың шөптік терапиясы'; hd2 = 'көмектеседі:'
    d.text(((W - d.textlength(hd1, font=f0))/2, 300), hd1, font=f0, fill=(255, 255, 255, int(220*ha)))
    d.text(((W - d.textlength(hd2, font=f1))/2, 352), hd2, font=f1, fill=(255, 255, 255, int(255*ha)))
    d.rounded_rectangle((W/2 - 40, 438, W/2 + 40, 444), radius=3, fill=GREEN + (int(255*ha),))
    fc = font(FS, 42); y0 = 490; ch = 96; gap = 18; cw = 860; x0 = (W - cw)//2
    for k, ((_, label), ct) in enumerate(zip(CARDS, CARD_T)):
        a = ease_out((t - ct + 0.08)/0.35)
        if a <= 0: continue
        a = min(a, a_out)
        y = y0 + k*(ch + gap); dx = int((1 - ease_out((t - ct + 0.08)/0.35))*60)
        C = Image.new('RGBA', (cw, ch), (0, 0, 0, 0)); cd = ImageDraw.Draw(C)
        cd.rounded_rectangle((0, 0, cw-1, ch-1), radius=24, fill=(255, 255, 255, 240))
        check_icon(cd, 52, ch//2, 26, GREEN, WHITE)
        bb = fc.getbbox('Қы')
        cd.text((98, (ch - (bb[3]-bb[1]))/2 - bb[1]), label, font=fc, fill=GREEN_D)
        L.alpha_composite(fade_layer(C, a), (x0 + dx, y))
    # "аса тиімді" белгісі
    a = min(ease_out((t - TIIMDI + 0.05)/0.3), a_out)
    if a > 0:
        f2 = font(FB, 46); txt = 'АСА ТИІМДІ'
        tw = d.textlength(txt, font=f2) + 52 + 50
        P = Image.new('RGBA', (int(tw) + 4, 90), (0, 0, 0, 0)); pd = ImageDraw.Draw(P)
        bb = f2.getbbox('АТ'); hh = bb[3] - bb[1] + 36
        pd.rounded_rectangle((0, 0, tw, hh), radius=hh//2, fill=GREEN)
        check_icon(pd, 40, hh//2, 18, WHITE, GREEN)
        pd.text((70, 18 - bb[1]), txt, font=f2, fill=WHITE)
        s = 0.85 + 0.15*ease_out((t - TIIMDI + 0.05)/0.25)
        P = P.resize((int(P.width*s), int(P.height*s)), Image.LANCZOS)
        L.alpha_composite(fade_layer(P, a), (int((W - P.width)/2), y0 + 7*(ch+gap) + 30))
    ov.alpha_composite(L)

def pin_icon(d, cx, cy, r, col):
    d.ellipse((cx-r, cy-r*1.6, cx+r, cy+r*0.4), fill=col)
    d.polygon([(cx - r*0.82, cy - r*0.2), (cx + r*0.82, cy - r*0.2), (cx, cy + r*1.4)], fill=col)
    d.ellipse((cx - r*0.4, cy - r*1.0, cx + r*0.4, cy - r*0.2), fill=WHITE)

def draw_end(ov, t):
    if t < END_S: return
    a = ease_out((t - END_S)/0.45)
    cw, chh = 900, 470
    C = Image.new('RGBA', (cw, chh), (0, 0, 0, 0)); d = ImageDraw.Draw(C)
    d.rounded_rectangle((0, 0, cw-1, chh-1), radius=36, fill=(255, 255, 255, 245))
    d.rounded_rectangle((0, 0, cw-1, 14), radius=7, fill=GREEN)
    fA = font(FB, 84); fB = font(FM, 36); fC = font(FB, 46); fD = font(FS, 36)
    def ctext(y, s, f, col):
        d.text(((cw - d.textlength(s, font=f))/2, y), s, font=f, fill=col)
    ctext(48, 'Ai Mei', fA, GREEN)
    ctext(150, 'Қытай медицинасы орталығы', fB, (70, 85, 75))
    d.line((cw/2 - 300, 222, cw/2 + 300, 222), fill=(220, 230, 222), width=2)
    addr = '6А шағын ауданы, 11/3'
    tw = d.textlength(addr, font=fC); x = (cw - tw - 54)/2
    pin_icon(d, x + 18, 286, 17, GREEN)
    d.text((x + 54, 258), addr, font=fC, fill=GREEN_D)
    b2 = 'Доктор Конгтың қабылдауына'; b3 = 'жазылыңыз'
    ctext(342, b2, fD, (60, 70, 64)); ctext(390, b3, fD, (60, 70, 64))
    sh = Image.new('L', (cw + 80, chh + 80), 0); ImageDraw.Draw(sh).rounded_rectangle((40, 50, cw + 40, chh + 50), radius=36, fill=120)
    sh = sh.filter(ImageFilter.GaussianBlur(20))
    s = 0.92 + 0.08*a
    yb = 1080 + int((1-a)*40)
    S = Image.new('RGBA', sh.size, (0, 0, 0, 0)); S.putalpha(sh)
    C2 = C.resize((int(cw*s), int(chh*s)), Image.LANCZOS); S2 = S.resize((int(S.width*s), int(S.height*s)), Image.LANCZOS)
    ov.alpha_composite(fade_layer(S2, a), (int((W - S2.width)/2), yb - int(40*s)))
    ov.alpha_composite(fade_layer(C2, a), (int((W - C2.width)/2), yb))

def list_bg(img, t):
    k = min(ease((t - LIST_S + 0.1)/0.4), 1 - ease((t - LIST_E)/0.35))
    if k <= 0: return img
    small = cv2.resize(img, (W//4, H//4), interpolation=cv2.INTER_AREA)
    bl = cv2.resize(cv2.GaussianBlur(small, (0, 0), 6), (W, H), interpolation=cv2.INTER_LINEAR).astype(np.float32)
    tint = np.array([28, 50, 14], np.float32)  # BGR қою жасыл
    dark = bl*0.42 + tint*0.58*0.6
    return img*(1-k) + dark*k

def vignette():
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    r = np.sqrt(((xx - W/2)/(W*0.75))**2 + ((yy - H/2)/(H*0.7))**2)
    v = 1 - 0.28*np.clip(r - 0.35, 0, 1)**1.5
    g = np.ones((H, W), np.float32)
    # субтитр аймағы үшін төменгі жарты жұмсақ қараю
    g -= 0.22*np.clip((yy - 1100)/500, 0, 1)*np.clip((1750 - yy)/300, 0, 1)
    g -= 0.25*np.clip((700 - yy)/500, 0, 1)
    return (v*g)[..., None]
VIG = vignette()

def frame(t):
    img = grade(shot_frame(t))
    img = list_bg(img, t)
    img = img*VIG
    ov = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    draw_title(ov, t); draw_list(ov, t)
    if not (LIST_S + 0.2 <= t < LIST_E) and t < END_S: draw_sub(ov, t)
    draw_end(ov, t)
    o = np.asarray(ov).astype(np.float32); al = o[..., 3:4]/255
    rgb = img[..., ::-1]*(1-al) + o[..., :3]*al
    # бастау / соңы fade
    k = min(1, t/0.25, (DUR - t)/0.6)
    return np.clip(rgb*k, 0, 255).astype(np.uint8)

if __name__ == '__main__':
    if ONLY:
        for tt in ONLY:
            Image.fromarray(frame(tt)).resize((540, 960), Image.LANCZOS).save(os.path.join(D, f'test/f_{tt:05.2f}.jpg'), quality=88)
        sys.exit()
    out = os.path.join(D, 'out_video.mp4')
    p = subprocess.Popen(['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}', '-r', str(FPS), '-i', '-',
                          '-c:v', 'libx264', '-preset', 'medium', '-crf', '17', '-pix_fmt', 'yuv420p', out], stdin=subprocess.PIPE)
    n = int(DUR*FPS)
    for i in range(n):
        p.stdin.write(frame(i/FPS).tobytes())
        if i % 150 == 0: print(i, '/', n, flush=True)
    p.stdin.close(); p.wait()
