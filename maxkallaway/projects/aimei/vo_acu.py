# Иглотерапия рилсіне ер адам дауысы (Piper TTS, ISSAI KazakhTTS — Iseke, speaker 1).
# Әр сөйлем бөлек синтезделеді (src/vo_acu/*.wav, кэш), сосын көріністер уақыты дауысқа қарай есептеледі.
import os, wave
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
MODEL = os.path.join(HERE, 'assets', 'tts', 'kk_KZ-issai-high.onnx')
CACHE = os.path.join(HERE, 'src', 'vo_acu')
SPEAKER = 1          # ISSAI_KazakhTTS_M1_Iseke — ер дауысы
LENGTH = 0.9         # табиғи қарқын

# (көрініс, id, мәтін) — экрандағы мәтінмен мағынасы бірдей
SCRIPT = [
    ('intro', 'i1', 'Иглотерапия қандай жағдайда көмектеседі?'),
    ('what', 'w1', 'Иглотерапия — денедегі белсенді нүктелерге өте жіңішке, стерильді инелер қою әдісі.'),
    ('what', 'w2', 'Ол ағзаның өзін-өзі қалпына келтіруіне көмектеседі.'),
    ('list', 'l0', 'Иглотерапия мына жағдайларда көмектеседі.'),
    ('list', 'l1', 'Бел мен мойын ауыруы.'),
    ('list', 'l2', 'Буын ауыруы.'),
    ('list', 'l3', 'Бас ауыруы мен мигрень.'),
    ('list', 'l4', 'Ұйқысыздық пен стресс.'),
    ('list', 'l5', 'Невралгия және бет нервісінің қабынуы.'),
    ('list', 'l6', 'Ас қорыту бұзылыстары.'),
    ('list', 'l7', 'Ем дәрігердің тексеруінен кейін жеке тағайындалады.'),
    ('why', 'y0', 'Неге Ай Мэй?'),
    ('why', 'y1', 'Тәжірибелі қытай дәрігері.'),
    ('why', 'y2', 'Тамыр арқылы диагностика.'),
    ('why', 'y3', 'Иглотерапия және шөп емі.'),
    ('cta', 'c1', 'Ай Мэй орталығына келіп, емделіңіз.'),
    ('cta', 'c2', 'Телефон: плюс жеті, жеті жүз жетпіс сегіз, алты жүз алпыс бес, сексен сегіз, сексен сегіз.'),
    ('cta', 'c3', 'Алдын ала қабылдауға жазылыңыз.'),
]
LEAD = {'intro': 0.6, 'what': 0.5, 'list': 0.6, 'why': 0.5, 'cta': 0.7}   # көрініс басынан дауысқа дейін
GAP = {'list': 0.22, 'why': 0.3}           # сөйлемдер арасы (әдепкі 0.35)
TAIL = {'intro': 0.6, 'cta': 2.2}          # көрініс соңындағы үнсіздік (әдепкі 0.5)
MIN_DUR = {'intro': 3.6}


def synth():
    os.makedirs(CACHE, exist_ok=True)
    todo = [(i, t) for _, i, t in SCRIPT if not os.path.exists(os.path.join(CACHE, f'{i}.wav'))]
    if todo:
        from piper import PiperVoice, SynthesisConfig
        v = PiperVoice.load(MODEL)
        cfg = SynthesisConfig(speaker_id=SPEAKER, length_scale=LENGTH, noise_scale=0.6, noise_w_scale=0.7)
        for i, t in todo:
            with wave.open(os.path.join(CACHE, f'{i}.wav'), 'wb') as w:
                v.synthesize_wav(t, w, syn_config=cfg)


def load(i):
    with wave.open(os.path.join(CACHE, f'{i}.wav')) as w:
        sr = w.getframerate()
        x = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768
    nz = np.where(np.abs(x) > 0.01)[0]                      # басы/соңындағы тыныштықты кесу
    x = x[max(0, nz[0] - int(0.03 * sr)):nz[-1] + int(0.08 * sr)] if len(nz) else x
    return x, sr


def timeline():
    """SCENES [(name, start, end)], TL {name: {id: local_start}}, CLIPS [(abs_start, id)]"""
    synth()
    scenes, tl, clips, t = [], {}, [], 0.0
    order = []
    for name, i, _ in SCRIPT:
        if name not in order: order.append(name)
    for name in order:
        cur = LEAD.get(name, 0.5)
        tl[name] = {}
        for nm, i, _ in SCRIPT:
            if nm != name: continue
            x, sr = load(i)
            tl[name][i] = cur
            clips.append((t + cur, i))
            cur += len(x) / sr + GAP.get(name, 0.35)
        dur = max(MIN_DUR.get(name, 0), cur - GAP.get(name, 0.35) + TAIL.get(name, 0.5))
        scenes.append((name, round(t, 3), round(t + dur, 3)))
        t += dur
    return scenes, tl, clips


def voice_track(clips, dur, sr_out=44100):
    out = np.zeros(int(dur * sr_out) + sr_out, np.float32)
    for t0, i in clips:
        x, sr = load(i)
        xs = np.interp(np.arange(0, len(x) * sr_out / sr) * sr / sr_out, np.arange(len(x)), x).astype(np.float32)
        a = int(t0 * sr_out); out[a:a + len(xs)] += xs[:len(out) - a]
    return out[:int(dur * sr_out)]


if __name__ == '__main__':
    s, tl, c = timeline()
    for x in s: print(x)
    for k, v in tl.items(): print(k, {i: round(t, 2) for i, t in v.items()})
