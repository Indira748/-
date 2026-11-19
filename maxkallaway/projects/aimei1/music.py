import numpy as np, wave, sys
SR=44100; DUR=float(sys.argv[2]); N=int(SR*DUR)
rng=np.random.default_rng(7)
t=np.arange(N)/SR
out=np.zeros((N,2))
def note(f): return 440*2**((f-69)/12)
# D major pentatonic: D E F# A B
scale=[62,64,66,69,71,74,76,78,81]
# chord pads (soft), 4 bars of 4s each loop: D, Bm, G(add9)->use pentatonic-friendly, A
chords=[[50,57,62,66],[47,54,59,62],[43,50,57,62],[45,52,57,64]]
bar=4.0
for i in range(int(DUR/bar)+1):
    c=chords[i%4]; s=int(i*bar*SR); e=min(N,int((i+1)*bar*SR+SR*1.5))
    if s>=N: break
    tt=np.arange(e-s)/SR; L=len(tt)
    env=np.minimum(1,tt/1.2)*np.minimum(1,(L/SR-tt)/1.5)
    for m in c:
        f=note(m)
        for det,pan in ((0.997,0.3),(1.003,0.7)):
            w=np.sin(2*np.pi*f*det*tt)+0.25*np.sin(2*np.pi*2*f*det*tt)
            out[s:e,0]+=0.022*env*w*(1-pan); out[s:e,1]+=0.022*env*w*pan
# soft plucks (guzheng-ish) on 8th-note grid with sparse probability
step=0.5
for k in range(int(DUR/step)):
    if rng.random()<0.45:
        m=scale[rng.integers(0,len(scale))]
        s=int(k*step*SR); L=int(2.2*SR); e=min(N,s+L)
        tt=np.arange(e-s)/SR; f=note(m)
        env=np.exp(-tt*2.8)*np.minimum(1,tt/0.004)
        w=(np.sin(2*np.pi*f*tt)+0.4*np.sin(2*np.pi*2*f*tt)*np.exp(-tt*4)+0.15*np.sin(2*np.pi*3*f*tt)*np.exp(-tt*6))
        pan=rng.uniform(0.3,0.7); a=0.06
        out[s:e,0]+=a*env*w*(1-pan); out[s:e,1]+=a*env*w*pan
# simple stereo reverb (feedback delays)
for d,g in ((0.113,0.35),(0.171,0.3),(0.239,0.25),(0.307,0.2)):
    n=int(d*SR); y=out.copy()
    for ch,off in ((0,0),(1,int(0.011*SR))):
        out[n+off:,ch]+=g*y[:N-n-off,1-ch]
fade=np.minimum(1,np.minimum(t/1.5,(DUR-t)/2.5))
out*=fade[:,None]; out/=np.abs(out).max()*1.12
w=wave.open(sys.argv[1],'wb'); w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
w.writeframes((out*32767).astype('<i2').tobytes()); w.close()
