import sys, json
from faster_whisper import WhisperModel
m = WhisperModel(sys.argv[3], device="cpu", compute_type="int8")
import numpy as np, wave
audio=np.frombuffer(wave.open(sys.argv[1]).readframes(10**9),dtype="<i2").astype(np.float32)/32768
segs, info = m.transcribe(audio, language="kk", word_timestamps=True, vad_filter=False, beam_size=5)
out=[]
for s in segs:
    out.append(dict(s=s.start,e=s.end,t=s.text,w=[(w.start,w.end,w.word,w.probability) for w in s.words]))
    print(f"{s.start:6.2f}-{s.end:6.2f} {s.text}", flush=True)
json.dump(out, open(sys.argv[2],"w"), ensure_ascii=False)
