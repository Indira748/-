import math, subprocess, sys, wave
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

D = '/tmp/claude-0/-home-user--/4d24e793-9976-53cc-a9d4-de1c07ee49ef/scratchpad/'
A = D + 'assets/'
W, H, FPS = 720, 1280, 25
OFF = 2.70          # trim leading silence of the voiceover
VO_END = 67.40      # speech ends ~65.0, hold CTA to the end
DUR = VO_END - OFF
PREVIEW = len(sys.argv) > 1 and sys.argv[1] == 'preview'

BG = Image.open(A + 'bg2.png').convert('RGBA')

def font(size):
    f = ImageFont.truetype(A + 'Nunito.ttf', size)
    f.set_variation_by_axes([900])
    return f

COL = {
    'b': ((30, 139, 255), (255, 255, 255), 7),
    'g': ((60, 224, 74), (16, 61, 16), 5),
    'r': ((255, 51, 51), (255, 255, 255), 7),
}

def ease_out(p): return 1 - (1 - p) ** 3
def ease_back(p, s=1.9):
    p -= 1
    return p * p * ((s + 1) * p + s) + 1

def with_shadow(img, off=6, blur=8, alpha=0.30):
    pad = blur * 2 + off
    out = Image.new('RGBA', (img.width + pad * 2, img.height + pad * 2), (0, 0, 0, 0))
    sh = Image.new('RGBA', img.size, (20, 30, 60, 0))
    sh.putalpha(img.getchannel('A').point(lambda v: int(v * alpha)))
    out.alpha_composite(sh, (pad, pad + off))
    out = out.filter(ImageFilter.GaussianBlur(blur))
    out.alpha_composite(img, (pad, pad))
    return out

_text_cache = {}
def text_sprite(txt, c, size):
    key = (txt, c, size)
    if key in _text_cache: return _text_cache[key]
    fill, stroke, sw = COL[c]
    f = font(size)
    while f.getlength(txt) > 650 and size > 30:
        size -= 2; f = font(size)
    l, t, r, b = f.getbbox(txt, stroke_width=sw)
    im = Image.new('RGBA', (r - l + 4, b - t + 4), (0, 0, 0, 0))
    ImageDraw.Draw(im).text((2 - l, 2 - t), txt, font=f, fill=fill, stroke_width=sw, stroke_fill=stroke)
    if c == 'g':  # extra white outer ring for readability on paper
        big = Image.new('RGBA', (im.width + 8, im.height + 8), (0, 0, 0, 0))
        ring = im.getchannel('A').filter(ImageFilter.MaxFilter(7))
        ringimg = Image.new('RGBA', im.size, (255, 255, 255, 0)); ringimg.putalpha(ring)
        big.alpha_composite(ringimg, (4, 4)); big.alpha_composite(im, (4, 4)); im = big
    im = with_shadow(im, off=4, blur=5, alpha=0.25)
    _text_cache[key] = im
    return im

_emo_cache = {}
def emoji(name, size):
    key = (name, size)
    if key in _emo_cache: return _emo_cache[key]
    im = Image.open(A + 'em/' + name + '.png').convert('RGBA')
    im = im.resize((size, int(im.height * size / im.width)), Image.LANCZOS)
    im = with_shadow(im, off=10, blur=10, alpha=0.28)
    _emo_cache[key] = im
    return im

def img_sprite(path, width=None, border=0):
    im = Image.open(path).convert('RGBA')
    if width: im = im.resize((width, int(im.height * width / im.width)), Image.LANCZOS)
    if border:
        bg = Image.new('RGBA', (im.width + border * 2, im.height + border * 2), (255, 255, 255, 255))
        mask = Image.new('L', bg.size, 0); ImageDraw.Draw(mask).rounded_rectangle([0, 0, bg.width - 1, bg.height - 1], 24, fill=255)
        bg.putalpha(mask)
        inner = Image.new('L', im.size, 0); ImageDraw.Draw(inner).rounded_rectangle([0, 0, im.width - 1, im.height - 1], 16, fill=255)
        im.putalpha(inner)
        bg.alpha_composite(im, (border, border)); im = with_shadow(bg, off=10, blur=12, alpha=0.3)
    return im

AG = Image.open(A + 'user.png').convert('RGBA')
IG = img_sprite(A + 'profile_card.png', width=600, border=10)

# ---------------- element constructors ----------------
def T(t, txt, y, c='b', size=56, x=0, end=None):
    return dict(k='text', t=t, txt=txt, y=y, c=c, size=size, x=x, end=end)
def E(t, name, x, y, size, end=None, bob=True):
    return dict(k='emo', t=t, name=name, x=x, y=y, size=size, end=end, bob=bob)
def LINE(t, pts, dur=0.9, color=(60, 200, 80), w=12, head=True):
    return dict(k='line', t=t, pts=pts, dur=dur, color=color, w=w, head=head, end=None)
def CIRCLE(t, box, dur=0.45):
    return dict(k='circle', t=t, box=box, dur=dur, end=None)
def AGILA(t):
    return dict(k='agila', t=t, end=None)
def IGCARD(t, cx, cy):
    return dict(k='ig', t=t, x=cx, y=cy, end=None)

S = [
 (2.85, 6.0, [
    T(2.85, 'Неге барлығы', 200),
    T(3.70, 'ТАРГЕТ қояды,', 280, x=40),
    E(3.0, 'thinking_face', 330, 600, 300),
    E(4.90, 'money_with_wings', 560, 470, 170),
    T(4.64, 'бірақ ақша', 900, x=-40),
    T(5.30, 'ТАППАЙДЫ?', 990, c='r', size=84),
 ]),
 (6.0, 7.75, [
    T(6.08, 'Көп кәсіпкерлер', 220),
    T(6.90, 'маған келіп:', 300, x=40),
    E(6.25, 'office_worker', 260, 660, 300),
    E(6.95, 'speech_balloon', 520, 560, 200),
 ]),
 (7.75, 11.0, [
    E(7.80, 'speech_balloon', 610, 170, 120, bob=False),
    T(8.30, '«Таргет қосып едім,', 250, size=54),
    T(9.52, 'бірде-бір ЗАЯВКА', 330, x=30, size=58),
    T(10.02, 'БОЛМАДЫ»', 420, c='r', size=78),
    E(8.60, 'laptop', 360, 760, 340, end=9.95),
    E(10.0, 'crying_face', 360, 760, 320),
 ]),
 (11.0, 12.55, [
    T(11.12, 'НЕГЕ олай', 300, size=74),
    T(11.84, 'болады?', 390, x=50, size=74),
    E(11.30, 'red_question_mark', 360, 760, 330),
 ]),
 (12.55, 15.65, [
    T(12.62, 'Өйткені көбісі', 200),
    T(13.96, 'жай ғана', 280, x=50),
    E(13.0, 'laptop', 330, 640, 360),
    E(14.40, 'computer_mouse', 570, 790, 170),
    T(14.38, 'КНОПКА БАСАДЫ', 1010, c='r', size=72),
 ]),
 (15.65, 19.9, [
    T(15.72, 'немесе', 200),
    T(16.45, 'бизнесіңізге АНАЛИЗ', 280, x=20, size=54),
    T(17.76, 'жасамайтын', 360, x=60),
    E(17.30, 'magnifying_glass_tilted_left', 360, 680, 300),
    E(17.90, 'cross_mark', 530, 800, 160),
    T(18.38, 'ТАРГЕТОЛОГ', 1020, c='r', size=78),
 ]),
 (19.9, 22.95, [
    T(19.98, 'ЕСІҢІЗДЕ БОЛСЫН!', 200, size=66),
    T(21.22, 'таргетолог —', 285, x=-40),
    E(21.70, 'magic_wand', 360, 640, 330),
    E(20.10, 'sparkles', 590, 470, 140),
    T(21.78, 'сиқырлы таяқша', 930, size=60),
    T(22.60, 'ЕМЕС!', 1020, c='r', size=88),
    E(22.62, 'cross_mark', 560, 760, 150),
 ]),
 (22.95, 27.6, [
    T(23.00, 'Таргеттің жұмысы —', 200, size=54),
    T(24.75, 'АДАМДАРДЫ', 285, c='g', size=76),
    E(24.80, 'busts_in_silhouette', 180, 640, 230),
    LINE(25.30, [(300, 640), (360, 600), (420, 640)], dur=0.35, color=(255, 70, 70), w=10),
    E(25.70, 'mobile_phone', 530, 640, 260),
    T(25.74, 'парақшаңызға', 940),
    T(26.42, 'ӘКЕЛІП БЕРУ', 1025, size=72),
 ]),
 (27.6, 31.6, [
    T(27.76, 'Ал келген адамның', 200),
    T(29.40, 'сізден', 280, x=50),
    E(29.20, 'thinking_face', 580, 470, 150),
    E(29.90, 'shopping_cart', 340, 650, 330),
    T(29.94, 'САТЫП АЛУ-АЛМАУЫ', 1000, c='g', size=66),
 ]),
 (31.6, 33.7, [
    T(31.70, '2', 380, c='g', size=230),
    T(31.94, 'маңызды нәрсеге', 600, size=60),
    T(32.80, 'байланысты', 680, x=40),
    E(32.30, 'balance_scale', 360, 930, 260),
 ]),
 (33.7, 35.95, [
    T(33.82, '1. ЭКСПЕРТТІК', 220, c='g', size=74),
    T(34.96, 'УПАКОВКА', 310, size=82),
    E(34.90, 'package', 360, 690, 340),
    E(35.20, 'sparkles', 560, 540, 140),
 ]),
 (35.95, 39.15, [
    T(36.04, 'Парақшаңызға', 200),
    T(36.80, 'кірген бойда', 280, x=50),
    E(37.40, 'trophy', 360, 640, 300),
    T(37.72, 'МЫҚТЫ МАМАН', 960, c='g', size=76),
    T(38.42, 'екеніңіз', 1045, x=40),
 ]),
 (39.15, 42.7, [
    T(39.24, 'және не ұсынатыныңыз', 200, size=52),
    T(40.62, '1 СЕКУНДТА', 290, c='g', size=80),
    E(40.55, 'stopwatch', 360, 640, 300),
    T(41.38, 'түсінікті болу керек', 960, size=54),
    E(41.90, 'check_mark_button', 570, 780, 150),
 ]),
 (42.7, 44.5, [
    T(42.82, '2. САТУ', 240, c='g', size=84),
    T(43.62, 'ЖҮЙЕСІ', 335, size=84),
    E(43.00, 'gear', 290, 690, 280),
    E(43.70, 'chart_increasing', 510, 780, 220),
 ]),
 (44.5, 47.5, [
    T(44.60, 'Келген адамның', 200),
    T(45.45, '«ойланып көрейін»', 285, x=20),
    E(45.50, 'thinking_face', 360, 650, 300),
    T(46.40, 'деген сөзін', 950),
    T(46.90, 'ЖОЙЫП', 1035, c='r', size=82),
    E(46.95, 'cross_mark', 520, 560, 170),
 ]),
 (47.5, 50.3, [
    T(47.58, 'бірден', 200),
    T(47.92, 'ШЕШІМ', 285, c='g', size=76),
    T(48.42, 'қабылдауға', 370, x=50),
    E(48.00, 'handshake', 360, 680, 300),
    T(48.88, 'көмектесетін', 960),
    T(49.46, 'ҚАДАМДАР', 1045, size=80),
    E(49.50, 'check_mark_button', 580, 820, 140),
 ]),
 (50.3, 53.5, [
    T(50.46, 'Егер таргетіңіз', 200),
    T(52.02, 'СЛИВ болып', 290, c='r', size=78),
    T(52.48, 'шаршасаңыз', 375, x=50),
    E(51.90, 'money_with_wings', 360, 720, 300),
    E(52.50, 'weary_face', 570, 900, 170),
 ]),
 (53.5, 56.8, [
    T(53.54, 'ал бизнесіңізге', 200),
    T(54.46, 'НАҚТЫ НӘТИЖЕ', 290, c='g', size=74),
    T(55.32, 'мен ЖҮЙЕ', 380, c='g', size=74),
    E(54.50, 'bullseye', 250, 690, 260),
    E(55.44, 'gear', 500, 760, 200),
    T(55.76, 'керек болса', 1010, x=40),
 ]),
 (56.8, 58.4, [
    AGILA(56.82),
    T(56.88, 'ҚАЗІР', 985, c='g', size=88),
    T(57.14, 'ӘРЕКЕТ ЕТІҢІЗ!', 1080, size=72),
    E(57.20, 'high_voltage', 610, 220, 150),
 ]),
 (58.4, 63.1, [
    T(58.50, 'Бизнесіңізге', 200),
    T(59.22, 'кездейсоқ емес,', 280, x=50),
    T(60.42, 'ТҰРАҚТЫ түрде', 365, c='g', size=68),
    LINE(60.50, [(110, 820), (220, 740), (300, 780), (420, 640), (500, 680), (610, 520)], dur=1.1),
    E(61.15, 'money_bag', 600, 640, 150),
    T(61.12, 'клиент әкелетін', 960),
    T(61.90, 'ЖҮЙЕ құрғыңыз келсе', 1045, size=60),
 ]),
 (63.1, DUR + OFF + 0.01, [
    T(63.16, 'ДИРЕКТКЕ', 180, size=78),
    T(63.94, '«ТАРГЕТ»', 275, c='g', size=82),
    T(64.42, 'деп жазыңыз', 360, x=50, size=60),
    IGCARD(63.30, 360, 720),
    LINE(63.45, [(590, 200), (660, 290), (692, 470), (694, 700), (676, 845), (612, 912)], dur=0.9, color=(255, 50, 50), w=11),
    CIRCLE(64.30, (322, 890, 594, 958)),
 ]),
]

# --------------- drawing ---------------
def paste_center(frame, im, cx, cy, scale=1.0, alpha=1.0):
    if scale <= 0.01 or alpha <= 0.01: return
    if abs(scale - 1) > 0.005:
        im = im.resize((max(1, int(im.width * scale)), max(1, int(im.height * scale))), Image.BILINEAR)
    if alpha < 0.999:
        im = im.copy(); im.putalpha(im.getchannel('A').point(lambda v: int(v * alpha)))
    frame.alpha_composite(im, (int(cx - im.width / 2), int(cy - im.height / 2))) if (
        0 <= int(cx - im.width / 2) and 0 <= int(cy - im.height / 2)
        and int(cx - im.width / 2) + im.width <= W and int(cy - im.height / 2) + im.height <= H) else _safe(frame, im, int(cx - im.width / 2), int(cy - im.height / 2))

def _safe(frame, im, x, y):
    layer = Image.new('RGBA', frame.size, (0, 0, 0, 0)); layer.paste(im, (x, y)); frame.alpha_composite(layer)

def draw_el(frame, e, t):
    dt = t - e['t']
    if dt < 0 or (e['end'] and t >= e['end']): return
    k = e['k']
    if k == 'text':
        sp = text_sprite(e['txt'], e['c'], e['size'])
        p = min(1, dt / 0.30); q = ease_out(p)
        im = sp
        if p < 1:
            r = (1 - q) * 16
            im = sp.filter(ImageFilter.GaussianBlur((r * 2.2, r * 0.25))) if r > 0.3 else sp
        paste_center(frame, im, W / 2 + e['x'] - (1 - q) * 70, e['y'], alpha=min(1, q * 1.3))
    elif k == 'emo':
        sp = emoji(e['name'], e['size'])
        p = min(1, dt / 0.38)
        sc = ease_back(p) if p < 1 else 1 + 0.025 * math.sin(dt * 2.6)
        bob = 7 * math.sin(dt * 2.8 + e['x'] * 0.01) if e['bob'] else 0
        paste_center(frame, sp, e['x'], e['y'] + bob, scale=max(0.01, sc), alpha=min(1, p * 2.5))
    elif k == 'line':
        p = ease_out(min(1, dt / e['dur']))
        pts = e['pts']; segs = [math.dist(pts[i], pts[i + 1]) for i in range(len(pts) - 1)]
        total = sum(segs) * p; out = [pts[0]]
        for i, L in enumerate(segs):
            if total >= L: out.append(pts[i + 1]); total -= L
            else:
                f = total / L; out.append((pts[i][0] + (pts[i + 1][0] - pts[i][0]) * f, pts[i][1] + (pts[i + 1][1] - pts[i][1]) * f)); break
        layer = Image.new('RGBA', frame.size, (0, 0, 0, 0)); d = ImageDraw.Draw(layer)
        if len(out) > 1:
            d.line(out, fill=e['color'] + (255,), width=e['w'], joint='curve')
            for pt in out: d.ellipse([pt[0] - e['w'] / 2, pt[1] - e['w'] / 2, pt[0] + e['w'] / 2, pt[1] + e['w'] / 2], fill=e['color'] + (255,))
            if e['head']:
                (x1, y1), (x2, y2) = out[-2], out[-1]
                a = math.atan2(y2 - y1, x2 - x1); L = e['w'] * 2.6
                d.polygon([(x2 + math.cos(a) * L * 0.6, y2 + math.sin(a) * L * 0.6),
                           (x2 + math.cos(a + 2.4) * L, y2 + math.sin(a + 2.4) * L),
                           (x2 + math.cos(a - 2.4) * L, y2 + math.sin(a - 2.4) * L)], fill=e['color'] + (255,))
        frame.alpha_composite(with_shadow_layer(layer))
    elif k == 'circle':
        p = ease_out(min(1, dt / e['dur']))
        layer = Image.new('RGBA', frame.size, (0, 0, 0, 0))
        ImageDraw.Draw(layer).arc(e['box'], -200, -200 + 360 * p, fill=(255, 50, 50, 255), width=7)
        frame.alpha_composite(layer)
    elif k == 'agila':
        p = min(1, dt / 0.4); q = ease_out(p)
        sc = 0.92 + 0.08 * q
        paste_center(frame, AG, 360, 490 + (1 - q) * 30, scale=sc, alpha=q)
    elif k == 'ig':
        p = min(1, dt / 0.4)
        paste_center(frame, IG, e['x'], e['y'], scale=max(0.01, ease_back(p, 1.3)), alpha=min(1, p * 2))

def with_shadow_layer(layer):
    sh = Image.new('RGBA', layer.size, (20, 30, 60, 0))
    sh.putalpha(layer.getchannel('A').point(lambda v: int(v * 0.25)))
    sh = sh.filter(ImageFilter.GaussianBlur(4))
    out = Image.new('RGBA', layer.size, (0, 0, 0, 0)); out.alpha_composite(sh, (0, 4)); out.alpha_composite(layer)
    return out

def frame_at(tv):
    t = tv + OFF
    fr = BG.copy()
    for s0, s1, els in S:
        if s0 <= t < s1:
            for e in els: draw_el(fr, e, t)
    return fr

# --------------- audio: voiceover + synthesized pops/whooshes ---------------
def build_audio(path):
    sr = 44100
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-ss', str(OFF), '-t', str(DUR), '-i', D + 'vo/vo.bin',
                          '-ac', '2', '-ar', str(sr), '-f', 's16le', '-'], capture_output=True).stdout
    vo = np.frombuffer(raw, dtype=np.int16).reshape(-1, 2).astype(np.float32) / 32768
    n = int((DUR + 0.1) * sr); mix = np.zeros((n, 2), np.float32); mix[:len(vo)] += vo
    rng = np.random.default_rng(1)
    def pop():
        L = int(0.09 * sr); tt = np.arange(L) / sr
        f = 500 + 900 * tt / 0.09
        return (np.sin(2 * np.pi * np.cumsum(f) / sr) * np.exp(-tt * 45) * 0.10).astype(np.float32)
    def whoosh():
        L = int(0.28 * sr); tt = np.arange(L) / sr
        x = rng.standard_normal(L).astype(np.float32)
        k = np.ones(40) / 40; x = np.convolve(x, k, 'same')
        env = np.sin(np.pi * tt / 0.28) ** 2
        return (x * env * 0.12).astype(np.float32)
    def add(sig, t):
        i = int(t * sr)
        if i < 0 or i >= n: return
        j = min(n, i + len(sig)); mix[i:j] += sig[:j - i, None]
    P, Wh = pop(), whoosh()
    for s0, s1, els in S:
        add(Wh, s0 - OFF - 0.05)
        for e in els:
            if e['k'] in ('emo', 'ig', 'agila'): add(P, e['t'] - OFF)
    mix = np.clip(mix, -1, 1)
    with wave.open(path, 'wb') as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(sr)
        w.writeframes((mix * 32767).astype(np.int16).tobytes())

if __name__ == '__main__':
    if PREVIEW:
        ts = [float(x) for x in sys.argv[2:]]
        ims = [frame_at(tt - OFF).convert('RGB').resize((240, 427)) for tt in ts]
        cols = 6; rows = (len(ims) + cols - 1) // cols
        sheet = Image.new('RGB', (240 * cols, 427 * rows), 'black')
        for i, im in enumerate(ims): sheet.paste(im, ((i % cols) * 240, (i // cols) * 427))
        sheet.save(D + 'preview.jpg', quality=85); sys.exit()
    build_audio(D + 'mix.wav')
    nfr = int(DUR * FPS)
    ff = subprocess.Popen(['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}', '-r', str(FPS),
                           '-i', '-', '-i', D + 'mix.wav', '-c:v', 'libx264', '-preset', 'medium', '-crf', '18',
                           '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '192k', '-shortest', D + 'main.mp4'], stdin=subprocess.PIPE)
    for i in range(nfr):
        ff.stdin.write(frame_at(i / FPS).convert('RGB').tobytes())
        if i % 250 == 0: print(i, '/', nfr, flush=True)
    ff.stdin.close(); ff.wait()
    print('done')
