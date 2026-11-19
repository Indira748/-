# Ai Mei — «Иглотерапия қандай жағдайда көмектеседі?» ақпараттық рилс.
# Сабырлы, эстетикалы стиль: жасыл/ақ, жұмсақ анимациялар, дикторсыз (экрандағы мәтін + тыныш музыка).
# Іске қосу: python3 render_acu.py  ->  out/aimei_acupuncture.mp4   |   python3 render_acu.py still 2 7 ...
import math, os, subprocess, sys, wave
from functools import lru_cache
from multiprocessing import Pool
import numpy as np
from PIL import Image, ImageDraw, ImageFilter
from render import W, H, FPS, font, emoji, place, shadowed, card_mask, clamp, ease_out, photo, F_INTER, F_CJK

HERE = os.path.dirname(os.path.abspath(__file__))
A = lambda *p: os.path.join(HERE, 'assets', *p)
OUT = os.path.join(HERE, 'out')
VID = os.path.join(HERE, 'src', 'acuframes')

GREEN = (30, 91, 58)        # терең жасыл
LEAF = (127, 183, 126)      # жұмсақ жасыл
MINT = (226, 239, 225)      # ашық жасыл фон
CREAM = (250, 249, 244)     # ақ/кілегей
WHITE = (255, 255, 255)
INK = (34, 44, 38)          # негізгі мәтін
MUTED = (110, 124, 114)
F_SB = A('Montserrat-SemiBold.ttf')
F_B = A('Montserrat-Bold.ttf')
F_XB = A('Montserrat-ExtraBold.ttf')

ADDRESS = '6а-11/3'
PHONE = '+7 (778) 665-88-88'
import vo_acu
SCENES, TL, CLIPS = vo_acu.timeline()   # көріністер уақыты ер адам дауысына (TTS) қарай
DUR = SCENES[-1][2]
XF = 0.5
ITEMS = ['Бел мен мойын ауыруы', 'Буын ауыруы', 'Бас ауыруы, мигрень',
         'Ұйқысыздық пен стресс', 'Невралгия, бет нервісі', 'Ас қорыту бұзылыстары']
WHY = ['Тәжірибелі қытай дәрігері', 'Тамыр арқылы диагностика', 'Иглотерапия + шөп емі']


# ---------------------------------------------------------------- көмекшілер
def smooth(x): x = clamp(x); return x * x * (3 - 2 * x)


def rise(lt, t0, d=0.6):
    """(alpha, dy) — жұмсақ пайда болу: төменнен жоғары сырғу + fade"""
    k = ease_out((lt - t0) / d)
    return k, 36 * (1 - k)


def kb(name, lt, dur, z0, z1, fy, fx=0.5):
    """Ken Burns (баяу zoom) фото фоны"""
    src = photo(name)
    sw, sh = src.size
    z = z0 + (z1 - z0) * smooth(lt / dur)
    cw, ch = sw / 1.2 / z, sh / 1.2 / z
    cx = clamp(fx * sw, cw / 2, sw - cw / 2)
    cy = clamp(fy * sh, ch / 2, sh - ch / 2)
    return src.resize((W, H), Image.BILINEAR, box=(cx - cw / 2, cy - ch / 2, cx + cw / 2, cy + ch / 2)).convert('RGBA')


@lru_cache(None)
def vid_files(): return sorted(os.listdir(VID))


def vid(lt):
    f = vid_files()
    return Image.open(os.path.join(VID, f[min(len(f) - 1, int(lt * FPS))])).convert('RGBA')


def wrap(text, f, maxw):
    lines, cur = [], ''
    for w in text.split():
        t = (cur + ' ' + w).strip()
        if f.getlength(t) > maxw and cur: lines.append(cur); cur = w
        else: cur = t
    return lines + [cur]


@lru_cache(None)
def txt(text, path, size, color, maxw=None, lh=1.25, align='c'):
    f = font(path, size)
    lines = wrap(text, f, maxw) if maxw else [text]
    asc, desc = f.getmetrics()
    lhp = int(size * lh)
    w = int(max(f.getlength(l) for l in lines)) + 6
    im = Image.new('RGBA', (w, lhp * (len(lines) - 1) + asc + desc + 6), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    for i, l in enumerate(lines):
        x = (w - f.getlength(l)) / 2 if align == 'c' else 0
        d.text((x, i * lhp), l, font=f, fill=color)
    return im


def put(c, im, x, y, alpha=1.0, anchor='c'):
    """y — жоғарғы шет; anchor: 'c' ортасы бойынша x, 'l' сол жақ"""
    if alpha <= 0.01: return
    if alpha < 1: im = im.copy(); im.putalpha(im.split()[3].point(lambda v: int(v * alpha)))
    c.alpha_composite(im, (int(x - im.width / 2 if anchor == 'c' else x), int(y)))


@lru_cache(None)
def vgrad(color, y0, y1, a1):
    g = np.zeros((H, W, 4), np.uint8); g[..., :3] = color
    ramp = np.clip((np.arange(H) - y0) / max(1, y1 - y0), 0, 1)
    g[..., 3] = (smooth_np(ramp) * a1 * 255)[:, None]
    return Image.fromarray(g, 'RGBA')


def smooth_np(x): return x * x * (3 - 2 * x)


@lru_cache(None)
def rrect(w, h, r, color, a=255, shadow=True):
    im = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(im).rounded_rectangle((0, 0, w - 1, h - 1), radius=r, fill=color + (a,))
    return shadowed(im, off=10, blur=24, alpha=0.12) if shadow else im


@lru_cache(None)
def leaf_icon(size, color=GREEN):
    """жапырақ белгісі (жеке сызылған, минимал)"""
    s = size * 4
    im = Image.new('RGBA', (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.ellipse((s * 0.12, s * 0.30, s * 0.88, s * 0.70), fill=color)
    leaf = im.rotate(40, Image.BICUBIC)
    d = ImageDraw.Draw(leaf)
    d.line((s * 0.28, s * 0.74, s * 0.72, s * 0.28), fill=WHITE + (230,), width=max(2, s // 28))
    return leaf.resize((size, size), Image.LANCZOS)


@lru_cache(None)
def num_badge(n, size=72):
    s = size * 3
    im = Image.new('RGBA', (s, s), (0, 0, 0, 0))
    ImageDraw.Draw(im).ellipse((0, 0, s - 1, s - 1), fill=GREEN)
    f = font(F_B, int(s * 0.46))
    t = str(n); l, tp, r, b = f.getbbox(t)
    ImageDraw.Draw(im).text(((s - (r - l)) / 2 - l, (s - (b - tp)) / 2 - tp), t, font=f, fill=WHITE)
    return im.resize((size, size), Image.LANCZOS)


@lru_cache(None)
def needles_deco(w=300, h=300, color=LEAF):
    """нәзік декор: үш ине (логотиптегі сияқты), жіңішке сызықтар"""
    s = 3
    im = Image.new('RGBA', (w * s, h * s), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    for i, ang in enumerate((-28, -8, 12)):
        a = math.radians(ang)
        x0, y0 = w * s * (0.30 + i * 0.18), h * s * 0.92
        L = h * s * (0.78 - i * 0.06)
        x1, y1 = x0 + math.sin(a) * L, y0 - math.cos(a) * L
        d.line((x0, y0, x1, y1), fill=color + (255,), width=4 * s // 2)
        d.ellipse((x1 - 9 * s, y1 - 9 * s, x1 + 9 * s, y1 + 9 * s), fill=color + (255,))
    return im.resize((w, h), Image.LANCZOS)


@lru_cache(None)
def logo_circle(size=300):
    src = Image.open(A('photos', 'p3_sign.jpg')).convert('RGB')
    cx, cy, r = 489, 322, 235          # логотиптің вывескадағы орны
    crop = src.crop((cx - r, cy - r, cx + r, cy + r)).resize((size, size), Image.LANCZOS).convert('RGBA')
    m = Image.new('L', (size * 3, size * 3), 0)
    ImageDraw.Draw(m).ellipse((0, 0, size * 3 - 1, size * 3 - 1), fill=255)
    crop.putalpha(m.resize((size, size), Image.LANCZOS))
    ring = Image.new('RGBA', (size + 24, size + 24), (0, 0, 0, 0))
    ImageDraw.Draw(ring).ellipse((0, 0, size + 23, size + 23), fill=WHITE)
    ring.alpha_composite(crop, (12, 12))
    return shadowed(ring, off=10, blur=20, alpha=0.25)


@lru_cache(None)
def pill(text, size=46, bg=WHITE, fg=GREEN, ekey=None):
    f = font(F_INTER, size)
    eh = int(size * 1.3) if ekey else 0
    w = int(f.getlength(text)) + 80 + (eh + 14 if ekey else 0)
    h = int(size * 2.1)
    im = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((0, 0, w - 1, h - 1), radius=h // 2, fill=bg)
    x = 40
    if ekey: im.alpha_composite(emoji(ekey, eh), (x - 6, (h - eh) // 2)); x += eh + 8
    l, t, r, b = f.getbbox(text)
    d.text((x, (h - (b - t)) / 2 - t), text, font=f, fill=fg)
    return im


# ---------------------------------------------------------------- көріністер
def sc_intro(lt, dur):
    c = kb('p3_sign', lt, dur, 1.18, 1.30, 0.13, 0.42)        # логотип (инелер) жоғарыда
    c.alpha_composite(vgrad(CREAM, 820, 1330, 1.0))
    a, dy = rise(lt, 0.3)
    put(c, pill('AI MEI  ·  ҚЫТАЙ МЕДИЦИНАСЫ', 32, GREEN, WHITE), W / 2, 1230 + dy, a)
    a, dy = rise(lt, 0.6)
    put(c, txt('Иглотерапия', F_XB, 132, GREEN), W / 2, 1360 + dy, a)
    a, dy = rise(lt, 1.0)
    put(c, txt('қандай жағдайда көмектеседі?', F_SB, 54, INK), W / 2, 1535 + dy, a)
    k = ease_out((lt - 1.4) / 0.8)
    if k > 0:
        ImageDraw.Draw(c).rounded_rectangle((W / 2 - 80 * k, 1650, W / 2 + 80 * k, 1656), radius=3, fill=LEAF)
    return c


NEEDLE = os.path.join(HERE, 'src', 'needleframes')


@lru_cache(None)
def needle_files(): return sorted(os.listdir(NEEDLE))


def sc_what(lt, dur):
    f = needle_files()                                        # видео: дәрігер тізеге ине қояды
    vlen = len(f) / FPS / 0.85                                # 0.85x — сәл баяу
    c = Image.open(os.path.join(NEEDLE, f[min(len(f) - 1, int(lt * 0.85 * FPS))])).convert('RGBA')
    if lt > vlen - 0.6:                                       # сосын дәрігер фотосы (тамыр ұстау)
        k = smooth((lt - (vlen - 0.6)) / 0.6)
        c = Image.blend(c, kb('d1_pulse', lt - vlen + 0.6, dur - vlen, 1.0, 1.05, 0.0), k)
    a, dy = rise(lt, 0.35, 0.7)
    put(c, rrect(960, 370, 48, CREAM, 240), W / 2, 1452 - 58 + 58 + dy - 58, a)
    a2, dy2 = rise(lt, 0.6)
    put(c, leaf_icon(50), 120, 1488 + dy2, a2, 'l')
    put(c, txt('Иглотерапия деген не?', F_B, 52, GREEN), 186, 1482 + dy2, a2, 'l')
    a3, dy3 = rise(lt, TL['what']['w1'] + 0.3)
    body = 'Белсенді нүктелерге өте жіңішке стерильді инелер қойылады — бұл ағзаның өзін-өзі қалпына келтіруіне көмектеседі.'
    put(c, txt(body, F_INTER, 39, INK, 820, 1.4, 'l'), 120, 1572 + dy3, a3, 'l')
    return c


def sc_list(lt, dur):
    c = Image.new('RGBA', (W, H), CREAM + (255,))
    put(c, needles_deco(360, 360), W - 330, 40, 0.45 * ease_out(lt / 1.0), 'l')
    a, dy = rise(lt, 0.15)
    put(c, txt('КӨРСЕТКІШТЕР', F_B, 34, LEAF), 90, 190 + dy, a, 'l')
    a, dy = rise(lt, TL['list']['l0'] - 0.25)
    put(c, txt('Қандай жағдайда көмектеседі?', F_XB, 74, GREEN, 820, 1.15, 'l'), 90, 245 + dy, a, 'l')
    y0, step = 520, 142
    for i, item in enumerate(ITEMS):
        a, dy = rise(lt, TL['list'][f'l{i + 1}'] - 0.12, 0.55)
        row = rrect(900, 116, 58, WHITE, 255)
        put(c, row, W / 2, y0 + i * step + dy - 58, a)
        put(c, num_badge(i + 1, 68), 112, y0 + i * step + 24 + dy, a, 'l')
        put(c, txt(item, F_INTER, 44, INK), 205, y0 + i * step + 36 + dy, a, 'l')
    a, dy = rise(lt, TL['list']['l7'] - 0.6, 0.8)
    strip = kb('d2_pulse', lt, dur, 1.0, 1.0, 0.62).crop((60, 980, 1020, 1440))   # тек қолдар — тамыр ұстау
    strip.putalpha(card_mask(960, 460, 44))
    put(c, shadowed(strip, 10, 20, 0.18), W / 2, 1322 + dy, a)
    a, _ = rise(lt, TL['list']['l7'])
    put(c, txt('* Ем дәрігердің тексеруінен кейін жеке тағайындалады', F_INTER, 30, MUTED), W / 2, 1862, a)
    return c


def sc_why(lt, dur):
    c = vid(lt * min(1.0, len(vid_files()) / FPS / dur))     # видео сахна ұзақтығына сай баяулайды                                               # дәрігер шөп іріктейді (беті жоғарыда)
    c.alpha_composite(vgrad(CREAM, 1050, 1300, 0.0))
    a, dy = rise(lt, 0.35, 0.7)
    put(c, rrect(960, 450, 48, CREAM, 245), W / 2, 1245 + dy, a)
    a, dy = rise(lt, TL['why']['y0'] - 0.1)
    put(c, txt('Неге Ai Mei?', F_B, 58, GREEN), 120, 1362 + dy, a, 'l')
    for i, w in enumerate(WHY):
        a, dy = rise(lt, TL['why'][f'y{i + 1}'] - 0.12)
        y = 1470 + i * 92
        put(c, leaf_icon(46), 122, y + 4 + dy, a, 'l')
        put(c, txt(w, F_INTER, 44, INK), 190, y + dy, a, 'l')
    return c


def sc_cta(lt, dur):
    c = Image.new('RGBA', (W, H), GREEN + (255,))
    put(c, needles_deco(420, 420, (52, 118, 80)), -40, 1460, ease_out(lt / 1.2), 'l')
    put(c, needles_deco(300, 300, (52, 118, 80)), W - 280, 60, ease_out(lt / 1.2), 'l')
    a, dy = rise(lt, 0.2, 0.8)
    put(c, logo_circle(300), W / 2, 330 + dy, a)
    a, dy = rise(lt, TL['cta']['c1'] - 0.1)
    put(c, txt('Ai Mei орталығына келіп емделіңіз', F_XB, 84, WHITE, 900, 1.18), W / 2, 760 + dy, a)
    k = ease_out((lt - 1.2) / 0.8)
    if k > 0:
        ImageDraw.Draw(c).rounded_rectangle((W / 2 - 70 * k, 1110, W / 2 + 70 * k, 1116), radius=3, fill=LEAF)
    a, dy = rise(lt, TL['cta']['c2'] - 0.9)
    put(c, pill(f'Мекенжай: {ADDRESS}', 48, WHITE, GREEN, 'pin'), W / 2, 1180 + dy, a)
    a, dy = rise(lt, TL['cta']['c2'] - 0.1)
    put(c, pill(PHONE, 48, WHITE, GREEN, 'phone'), W / 2, 1310 + dy, a)
    a, dy = rise(lt, TL['cta']['c3'] - 0.1)
    put(c, txt('Алдын ала қабылдауға жазылыңыз', F_INTER, 42, MINT), W / 2, 1480 + dy, a)
    a, dy = rise(lt, TL['cta']['c3'] + 0.6)
    put(c, txt('AI MEI', F_XB, 56, LEAF), W / 2 - 70, 1720 + dy, a)
    put(c, txt('爱美', F_CJK, 56, LEAF), W / 2 + 110, 1720 + dy, a)
    return c


FN = dict(intro=sc_intro, what=sc_what, list=sc_list, why=sc_why, cta=sc_cta)


def frame(n):
    t = n / FPS
    for i, (name, a, b) in enumerate(SCENES):
        if a <= t < b or i == len(SCENES) - 1: break
    c = FN[name](t - a, b - a)
    if i + 1 < len(SCENES) and t > b - XF:               # жұмсақ crossfade келесі көрініске
        nx, na, nb = SCENES[i + 1]
        k = smooth((t - (b - XF)) / XF)
        c = Image.blend(c, FN[nx](t - na + 0.0 if t >= na else 0.0, nb - na), k)
    if t < 0.4: c = Image.blend(Image.new('RGBA', (W, H), CREAM + (255,)), c, smooth(t / 0.4))
    return c.convert('RGB').tobytes()


# ---------------------------------------------------------------- тыныш музыка
SR = 44100


def make_audio(path, music_only=False):
    N = int(DUR * SR); mus = np.zeros(N); rng = np.random.default_rng(11)
    def add(sig, t):
        i = int(t * SR); j = min(N, i + len(sig))
        if i < N: mus[i:j] += sig[:j - i]
    hz = lambda m: 440 * 2 ** ((m - 69) / 12)
    bar = 60 / 72 * 4
    chords = [[50, 57, 62, 66], [47, 54, 59, 62], [43, 50, 55, 59], [45, 52, 57, 61]]  # D Bm G A — жұмсақ
    for k in range(int(DUR / bar) + 1):
        ch = chords[k % 4]; L = int(bar * 1.15 * SR); x = np.arange(L) / SR
        pad = sum(np.sin(2 * np.pi * hz(m) * x + 0.3 * np.sin(2 * np.pi * 0.4 * x)) for m in ch)
        e = np.minimum(1, x / 0.8) * np.minimum(1, (L / SR - x) / 0.8)
        add(pad * e * 0.05, k * bar)
    penta = [74, 76, 78, 81, 83, 86]
    beat = 60 / 72
    for k in range(int(DUR / beat)):
        if rng.random() < 0.55:
            m = penta[rng.integers(len(penta))]; L = int(1.6 * SR); x = np.arange(L) / SR
            tone = (np.sin(2 * np.pi * hz(m) * x) + 0.25 * np.sin(4 * np.pi * hz(m) * x)) * np.exp(-x * 2.6)
            add(tone * 0.06, k * beat + (beat / 2 if rng.random() < 0.3 else 0))
    for name, a, b in SCENES[1:]:   # көрініс ауысқанда нәзік «қоңырау»
        L = int(2.0 * SR); x = np.arange(L) / SR
        add((np.sin(2 * np.pi * hz(88) * x) + 0.5 * np.sin(2 * np.pi * hz(95) * x)) * np.exp(-x * 3) * 0.035, a - XF / 2)
    # жеңіл reverb (кешіктірілген көшірмелер)
    for d, g in ((0.11, 0.35), (0.23, 0.22), (0.41, 0.14)):
        s = int(d * SR); mus[s:] += mus[:-s] * g
    mus /= np.abs(mus).max(); mus *= 10 ** (-9 / 20)
    f = int(2.0 * SR); mus[-f:] *= np.linspace(1, 0, f); mus[:int(0.6 * SR)] *= np.linspace(0, 1, int(0.6 * SR))
    if music_only:                       # тек музыка (render_acu2 өз дауысын қосады)
        st = (np.stack([mus, mus], 1) * 32767).astype(np.int16)
        with wave.open(path, 'wb') as w:
            w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes(st.tobytes())
        return
    voice = vo_acu.voice_track(CLIPS, DUR, SR).astype(np.float64)
    voice *= 10 ** (-2 / 20) / max(1e-6, np.abs(voice).max())
    win = int(0.05 * SR)
    env = np.sqrt(np.convolve(voice ** 2, np.ones(win) / win, 'same'))
    sp = (env > 0.02).astype(np.float64)
    sm = int(0.35 * SR); sp = np.minimum(1, np.convolve(sp, np.ones(sm) / sm * 3, 'same'))
    vr = np.sqrt(np.mean(voice[np.abs(voice) > 0.02] ** 2))
    mus = mus / max(1e-6, np.sqrt(np.mean(mus ** 2))) * vr * 10 ** ((-20 * sp - 11 * (1 - sp)) / 20)
    L = mus + voice
    Rr = np.roll(mus, int(0.012 * SR)) + voice
    st = (np.clip(np.stack([L, Rr], 1), -1, 1) * 32767).astype(np.int16)
    with wave.open(path, 'wb') as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes(st.tobytes())


if __name__ == '__main__':
    os.makedirs(OUT, exist_ok=True)
    if len(sys.argv) > 1 and sys.argv[1] == 'still':
        for s in sys.argv[2:]:
            Image.frombytes('RGB', (W, H), frame(int(float(s) * FPS))).save(os.path.join(OUT, f'a_still_{s}.jpg'), quality=85)
        sys.exit()
    wav = os.path.join(OUT, 'acu_music.wav'); make_audio(wav)
    dst = os.path.join(OUT, 'aimei_acupuncture.mp4')
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
