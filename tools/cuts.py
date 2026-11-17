import numpy as np, wave, json
w=wave.open('audio16.wav');a=np.frombuffer(w.readframes(w.getnframes()),np.int16).astype(float)/32768
h=160;n=len(a)//h  # 10ms
db=np.array([20*np.log10(np.sqrt(np.mean(a[i*h:(i+1)*h]**2))+1e-9) for i in range(n)])
sil=db<-42
runs=[];i=0
while i<n:
    if sil[i]:
        j=i
        while j<n and sil[j]: j+=1
        if (j-i)>=30: runs.append((i/100,j/100))
        i=j
    else: i+=1
PAD=0.07; T=n/100
keep=[];cur=0.0
for s,e in runs:
    a_=s+PAD if s>0.01 else 0; b_=e-PAD if e<T-0.01 else T
    if a_>cur: keep.append([round(cur,3),round(a_,3)])
    cur=max(cur,b_)
if cur<T-0.05: keep.append([round(cur,3),round(T,3)])
keep=[k for k in keep if k[1]-k[0]>0.12]
print(len(keep),'segments, kept %.2fs of %.2fs'%(sum(b-a for a,b in keep),T))
for k in keep: print(k)
json.dump(keep,open('keep.json','w'))
