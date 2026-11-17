import sys, json
from faster_whisper import WhisperModel
wav, out, model = sys.argv[1], sys.argv[2], sys.argv[3]
m = WhisperModel(model, device='cpu', compute_type='int8', cpu_threads=4)
import numpy as np, wave
w_=wave.open(wav); audio=np.frombuffer(w_.readframes(w_.getnframes()),np.int16).astype(np.float32)/32768
segs, info = m.transcribe(audio, language='kk', word_timestamps=True, beam_size=5, vad_filter=False,
    initial_prompt='Сәлеметсіз бе! Мен массажист, маманмын. Массаж, омыртқа, бел, мойын ауруы.')
res=[]
for s in segs:
    res.append(dict(start=s.start,end=s.end,text=s.text,words=[dict(w=w.word,s=w.start,e=w.end,p=w.probability) for w in s.words]))
    print(f"[{s.start:6.2f}-{s.end:6.2f}] {s.text}", flush=True)
json.dump(res, open(out,'w'), ensure_ascii=False, indent=1)
