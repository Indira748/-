import numpy as np, wave, sys, json
SR=48000
def save(name,x):
    x=np.clip(x,-1,1); y=(x*32767).astype(np.int16)
    if y.ndim==1: y=np.stack([y,y],1)
    w=wave.open(name,'w');w.setnchannels(2);w.setsampwidth(2);w.setframerate(SR);w.writeframes(y.tobytes());w.close()
rng=np.random.default_rng(7)
def reverb(x,sec=2.2,mix=0.3):
    n=int(sec*SR);t=np.arange(n)/SR
    irL=rng.standard_normal(n)*np.exp(-t*3.2); irR=rng.standard_normal(n)*np.exp(-t*3.2)
    from numpy.fft import rfft,irfft
    L=len(x)+n; N=1<<(L-1).bit_length()
    X=rfft(x,N); wl=irfft(X*rfft(irL,N),N)[:len(x)]; wr=irfft(X*rfft(irR,N),N)[:len(x)]
    wl/=np.abs(wl).max()+1e-9; wr/=np.abs(wr).max()+1e-9
    d=x/ (np.abs(x).max()+1e-9)
    return np.stack([d*(1-mix)+wl*mix, d*(1-mix)+wr*mix],1)
hz=lambda m:440*2**((m-69)/12)
# ---------------- MUSIC ----------------
dur=float(sys.argv[1]); bpm=72; beat=60/bpm; bar=4*beat
chords=[[53,57,60,64],[57,60,64,67],[50,57,60,65],[48,55,59,64]]  # Fmaj7 Am7 Dm(add) Cmaj7
bass=[41,45,38,36]
N=int((dur+3)*SR); t=np.arange(N)/SR; mus=np.zeros(N)
nb=int(np.ceil((dur+3)/bar))
for b in range(nb):
    ch=chords[b%4]; s0=int(b*bar*SR); L=int(bar*SR*1.15); tt=np.arange(min(L,N-s0))/SR
    env=np.minimum(tt/1.2,1)*np.exp(-np.maximum(tt-bar,0)*6)
    for m in ch:
        f=hz(m); v=np.sin(2*np.pi*f*tt)+0.25*np.sin(2*np.pi*2*f*tt+0.3)+0.6*np.sin(2*np.pi*f*1.003*tt)
        mus[s0:s0+len(tt)]+=0.05*v*env
    f=hz(bass[b%4]); mus[s0:s0+len(tt)]+=0.12*np.sin(2*np.pi*f*tt)*np.minimum(tt/0.05,1)*np.exp(-tt*0.6)
    # soft e-piano arpeggio (8ths)
    arp=[ch[0]+12,ch[2]+12,ch[1]+12,ch[3]+12,ch[2]+12,ch[1]+12,ch[3]+12,ch[2]+12]
    for k,m in enumerate(arp):
        s=s0+int(k*beat/2*SR); tt2=np.arange(int(1.6*SR))/SR; tt2=tt2[:max(0,N-s)]
        f=hz(m); v=(np.sin(2*np.pi*f*tt2)+0.3*np.sin(2*np.pi*2*f*tt2))*np.exp(-tt2*3.5)*np.minimum(tt2/0.004,1)
        mus[s:s+len(tt2)]+=0.045*v*(0.8 if k%2 else 1)
    # soft shaker on offbeats
    for k in range(8):
        s=s0+int((k+0.5)*beat/2*SR); n=int(0.07*SR)
        if s+n<N:
            nz=np.diff(rng.standard_normal(n+1))*np.exp(-np.arange(n)/SR*60)
            mus[s:s+n]+=0.012*nz
st=reverb(mus,2.5,0.35)[:int(dur*SR)]
fade=np.ones(len(st)); fi=int(1.0*SR); fo=int(2.5*SR)
fade[:fi]=np.linspace(0,1,fi); fade[-fo:]=np.linspace(1,0,fo)
st*=fade[:,None]; st/=np.abs(st).max(); save('music.wav',st*0.9)
# ---------------- SFX ----------------
def pop(f0=900,f1=250,d=0.12,amp=0.8):
    tt=np.arange(int(d*SR))/SR; f=f0*(f1/f0)**(tt/d); ph=2*np.pi*np.cumsum(f)/SR
    return amp*np.sin(ph)*np.exp(-tt*28)*np.minimum(tt/0.002,1)
def whoosh(d=0.55,amp=0.6):
    n=int(d*SR); x=rng.standard_normal(n); tt=np.arange(n)/SR
    out=np.zeros(n); y=0; c=np.linspace(0.02,0.35,n)**1.5
    for i in range(n): y+=c[i]*(x[i]-y); out[i]=y
    env=np.sin(np.pi*np.minimum(tt/d,1))**2
    return amp*out/np.abs(out).max()*env
def ding(f=1318.5,d=1.6,amp=0.5):
    tt=np.arange(int(d*SR))/SR
    return amp*(np.sin(2*np.pi*f*tt)+0.4*np.sin(2*np.pi*2.76*f*tt)*np.exp(-tt*6)+0.2*np.sin(2*np.pi*5.4*f*tt)*np.exp(-tt*10))*np.exp(-tt*2.2)*np.minimum(tt/0.002,1)
S={'pop':pop(),'pop2':pop(1200,180,0.18,0.9)+0.4*np.concatenate([np.zeros(int(0.05*SR)),pop(1500,600,0.13,0.6)])[:int(0.18*SR)],'whoosh':whoosh(),'ding':ding()}
ev=json.loads(sys.argv[2]); sfx=np.zeros(int(dur*SR)+SR*2)
for name,at,g in ev:
    x=S[name]; s=max(0,int(at*SR)); sfx[s:s+len(x)]+=x*g
sfx=sfx[:int(dur*SR)]; save('sfx.wav',reverb(sfx,0.8,0.15)*0.9)
print('ok')
