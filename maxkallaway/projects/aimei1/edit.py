# Ai Mei reel: монтаж жоспары + аудио қию + уақыт картасы
import json, subprocess, sys, os
D = os.path.dirname(os.path.abspath(__file__))

END = 67.62
# -36dB / 0.15s silencedetect нәтижесі
SIL = [(0,2.154),(2.168,2.788),(5.343,5.675),(8.417,8.570),(9.800,10.256),(15.228,15.513),(16.911,17.262),
 (19.484,19.683),(21.046,21.433),(26.923,27.472),(29.643,29.803),(31.663,32.149),(34.765,34.989),(38.651,38.873),
 (39.001,39.162),(41.740,41.975),(41.997,42.169),(44.920,45.561),(49.183,49.433),(49.756,49.940),(53.072,53.441),
 (55.759,56.260),(56.273,56.470),(59.279,59.469),(59.540,59.725),(63.020,63.211),(63.272,63.454),(64.596,64.746),
 (66.152,66.465),(67.165,67.350),(67.614,69.34)]
# сөз емес аралдар (ыңылдау / тыныс / шырт) — қиылады
JUNK = [(2.154,2.168),(41.975,41.997),(49.433,49.756),(56.260,56.273),(59.469,59.540),(63.211,63.272)]

def merged_silence():
    iv = sorted(SIL + JUNK)
    out = []
    for a,b in iv:
        if out and a <= out[-1][1] + 1e-3: out[-1][1] = max(out[-1][1], b)
        else: out.append([a,b])
    return out

KEEP_GAP = 0.13   # әр паузадан қалатын ұзындық
def keep_segments():
    sil = merged_silence()
    segs = []; cur = None
    speech = []
    t = 0.0
    for a,b in sil:
        if a > t: speech.append((t,a))
        t = b
    pad = KEEP_GAP/2
    return [(max(0,a-pad), min(END+0.05,b+pad)) for a,b in speech if a < END]

SEGS = keep_segments()
def tmap(x):
    """түпнұсқа уақыт -> қиылған уақыт"""
    acc = 0.0
    for a,b in SEGS:
        if x < a: return acc
        if x <= b: return acc + (x-a)
        acc += b-a
    return acc
TOTAL = sum(b-a for a,b in SEGS)

def cut_audio(src, dst):
    parts = []; fl = []
    for i,(a,b) in enumerate(SEGS):
        fl.append(f"[0:a]atrim={a:.3f}:{b:.3f},asetpts=PTS-STARTPTS,afade=t=in:d=0.012,afade=t=out:st={b-a-0.015:.3f}:d=0.015[s{i}]")
        parts.append(f"[s{i}]")
    fl.append("".join(parts) + f"concat=n={len(SEGS)}:v=0:a=1[c]")
    fl.append("[c]highpass=f=80,lowpass=f=14000,acompressor=threshold=-20dB:ratio=3:attack=8:release=120:makeup=2,"
              "loudnorm=I=-15:TP=-1.5:LRA=8[v]")
    subprocess.run(["ffmpeg","-v","error","-y","-i",src,"-filter_complex",";".join(fl),"-map","[v]","-ar","48000","-ac","1",dst],check=True)

if __name__ == "__main__":
    cut_audio(os.path.join(D,"dl/f1"), os.path.join(D,"vo_cut.wav"))
    print("segments", len(SEGS), "total", round(TOTAL,2))
    for x in (2.79,8.57,10.26,17.26,21.43,27.47,32.15,44.92,49.94,53.44,56.47,59.72,63.45,67.61):
        print(x, round(tmap(x),2))
