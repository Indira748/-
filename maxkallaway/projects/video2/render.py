# Overlay рендері: қызыл хук + 2–3 сөздік субтитр + B-roll карточкалар + фото. RGBA кадрлар ffmpeg-ке pipe арқылы.
import sys, math, subprocess
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from config import *
W,H,FPS = 1080,1920,30
aud = sys.argv[1]; out = sys.argv[2]
FB = '/usr/share/fonts/opentype/inter/Inter-Black.otf'
FX = '/usr/share/fonts/opentype/inter/Inter-ExtraBold.otf'
EMO = ImageFont.truetype('/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf', 109)
f = lambda p,s: ImageFont.truetype(p, s)

# --- уақыт картасы (бастапқы -> қиылған)
keep=[];t=0.0
for a,b in SIL: keep.append((t,a+PAD)); t=b-PAD
keep.append((t,END))
def m(ts):
    o=0
    for a,b in keep:
        if ts<a: return o
        if ts<=b: return o+ts-a
        o+=b-a
    return o
words=[]
for it in WORDS.split('|'):
    w,s,e=it.split(); words.append((w,m(float(s)),m(float(e))))
DUR = m(END)
def wt(key):  # кілт сөздің бірінші кездесуі
    return next(s for w,s,e in words if w==key)

# --- субтитр топтары (2–3 сөз, сөйлем соңында үзіледі)
groups=[];cur=[]
for i,x in enumerate(words):
    cur.append(x)
    gap = words[i+1][1]-x[2] if i+1<len(words) else 9
    if len(cur)==3 or (len(cur)>=2 and len(''.join(c[0] for c in cur))>14) or x[0][-1] in '.!?,»' or gap>0.25:
        groups.append(cur);cur=[]
if cur: groups.append(cur)

def ease(x): x=max(0,min(1,x)); return 1-(1-x)**3
def pop(x):  # overshoot
    x=max(0,min(1,x)); c=1.70158; return 1+(c+1)*(x-1)**3+c*(x-1)**2

def text_img(txt, font, fill, stroke=0, sc=None, shadow=True):
    bb=font.getbbox(txt, stroke_width=stroke); w,h=bb[2]-bb[0]+40, bb[3]-bb[1]+40
    im=Image.new('RGBA',(w,h)); d=ImageDraw.Draw(im)
    d.text((20-bb[0],20-bb[1]),txt,font=font,fill=fill,stroke_width=stroke,stroke_fill=sc)
    if shadow:
        sh=Image.new('RGBA',(w,h)); ImageDraw.Draw(sh).text((20-bb[0],24-bb[1]),txt,font=font,fill=(0,0,0,150),stroke_width=stroke,stroke_fill=(0,0,0,150))
        sh=sh.filter(ImageFilter.GaussianBlur(6)); sh.alpha_composite(im); im=sh
    return im

def emoji_img(e, size):
    im=Image.new('RGBA',(160,160)); ImageDraw.Draw(im).text((10,10),e,font=EMO,embedded_color=True)
    im=im.crop(im.getbbox()); r=size/max(im.size)
    return im.resize((max(1,int(im.width*r)),max(1,int(im.height*r))),Image.LANCZOS)

def pill(content_w, h, col, r=None):
    im=Image.new('RGBA',(content_w,h)); ImageDraw.Draw(im).rounded_rectangle((0,0,content_w-1,h-1),r or h//2,fill=col); return im

def paste_c(base, im, cx, cy, s=1.0, a=1.0):
    if s<=0.01 or a<=0.01: return
    if s!=1: im=im.resize((max(1,int(im.width*s)),max(1,int(im.height*s))),Image.BILINEAR)
    if a<1:
        al=im.getchannel('A').point(lambda v:int(v*a)); im=im.copy(); im.putalpha(al)
    base.alpha_composite(im,(int(cx-im.width/2),int(cy-im.height/2)))

# --- кэштер
SUBF=f(FB,76)
sub_cache={}
def sub_img(txt, hi):
    k=(txt,hi)
    if k not in sub_cache:
        sub_cache[k]=text_img(txt, SUBF, (255,214,0) if hi else (255,255,255), 7, (0,0,0))
    return sub_cache[k]

def hook_img(txt):
    font=f(FB,76); lines=[];cur=''
    for w in txt.split():
        if font.getlength((cur+' '+w).strip())>860: lines.append(cur); cur=w
        else: cur=(cur+' '+w).strip()
    lines.append(cur)
    ims=[text_img(l,font,(255,255,255),0,shadow=False) for l in lines]
    bw=max(i.width for i in ims)+50; bh=sum(i.height-18 for i in ims)+40
    box=pill(bw,bh,(226,30,40,255),28); y=20
    for i in ims: box.alpha_composite(i,((bw-i.width)//2,y-10)); y+=i.height-18
    return box
HOOK=hook_img(HOOKS[aud])

def card_emo(e,txt):
    font=f(FX,58); ti=text_img(txt,font,(25,25,25),0,shadow=False); ei=emoji_img(e,110)
    w=max(ti.width+60, 300); h=ei.height+ti.height+40
    c=pill(w,h,(255,255,255,240),40); c.alpha_composite(ei,((w-ei.width)//2,22)); c.alpha_composite(ti,((w-ti.width)//2,ei.height+18))
    return c
def card_num(n,txt):
    big=text_img(n,f(FB,260),(255,214,0),10,(0,0,0)); sm=pill(1,1,(0,0,0,0))
    lab=text_img(txt,f(FB,62),(255,255,255),0,shadow=False); p=pill(lab.width+40,lab.height,(226,30,40,255),24); p.alpha_composite(lab,(20,0))
    w=max(big.width,p.width); c=Image.new('RGBA',(w,big.height+p.height-30)); c.alpha_composite(big,((w-big.width)//2,0)); c.alpha_composite(p,((w-p.width)//2,big.height-30)); return c
def card_photo(path):
    im=Image.open(path).convert('RGBA'); r=780/im.width; im=im.resize((780,int(im.height*r)),Image.LANCZOS)
    mask=Image.new('L',im.size); ImageDraw.Draw(mask).rounded_rectangle((0,0,im.width-1,im.height-1),36,fill=255); im.putalpha(mask)
    c=Image.new('RGBA',(im.width+60,im.height+60)); sh=Image.new('RGBA',c.size); ImageDraw.Draw(sh).rounded_rectangle((30,40,im.width+30,im.height+40),36,fill=(0,0,0,170))
    c.alpha_composite(sh.filter(ImageFilter.GaussianBlur(14))); c.alpha_composite(im,(30,30)); return c
def chip(txt):
    t=text_img('✓ '+txt if False else txt,f(FX,56),(255,255,255),0,shadow=False); p=pill(t.width+50,t.height+10,(20,120,110,235),36); p.alpha_composite(t,(25,5)); return p

cards=[]
for key,dur,kind,data in CARDS:
    t0=wt(key)
    if kind=='list':
        items=[(wt(k),chip(lbl)) for k,lbl in data]; cards.append(dict(t0=t0,t1=wt('массажды')+0.4,kind='list',items=items))
    else:
        im={'emo':lambda:card_emo(*data),'num':lambda:card_num(*data),'photo':lambda:card_photo(data)}[kind]()
        cards.append(dict(t0=t0,t1=t0+dur,kind=kind,im=im))
# фото: екіншісі біріншінің үстіне сәл төмен түседі; бірінші екіншісі шыққанша тұрады
ph=[c for c in cards if c['kind']=='photo']; ph[0]['t1']=ph[1]['t1']

SUB_Y=1400; CARD_Y=500
def frame(t):
    fr=Image.new('RGBA',(W,H))
    # карточкалар
    for c in cards:
        if not (c['t0']<=t<c['t1']+0.25): continue
        k=(t-c['t0'])/0.28; out_k=1-max(0,(t-c['t1'])/0.25)
        if c['kind']=='list':
            for j,(ti,im) in enumerate(c['items']):
                if t<ti: continue
                kk=pop((t-ti)/0.3); paste_c(fr,im,W/2+(1-ease((t-ti)/0.3))*300,250+j*105,1,min(1,kk)*out_k)
        elif c['kind']=='photo':
            idx=ph.index(c); y=330+idx*230; rot=(-4 if idx==0 else 3)
            im=c['im'].rotate(rot*ease(k),resample=Image.BICUBIC,expand=True)
            paste_c(fr,im,W/2,y+(1-ease(k))*900,1,out_k)
        else:
            paste_c(fr,c['im'],W/2,CARD_Y,pop(k)*(0.85+0.15*out_k),out_k)
    # хук
    if t<HOOK_END+0.3:
        s=pop(t/0.35); a=1-max(0,(t-HOOK_END)/0.3); paste_c(fr,HOOK,W/2,380,s,a)
    # субтитр
    for g in groups:
        if g[0][1]-0.05<=t<(g[-1][2]+0.15):
            parts=[sub_img(w.upper().strip('«»,.!?') if False else w.upper(), g[j][1]<=t<g[j][2]+0.05) for j,(w,_,__) in enumerate(g)]
            tw=sum(p.width-40 for p in parts)+22*(len(parts)-1); fit=min(1,990/tw); tw*=fit; x=(W-tw)/2; s=fit*(0.9+0.1*ease((t-g[0][1]+0.05)/0.12))
            for p in parts: paste_c(fr,p,x+(p.width-40)*fit/2,SUB_Y,s); x+=(p.width-40+22)*fit
            break
    return fr

cmd=['ffmpeg','-v','error','-y','-i','out/cut.mp4','-f','rawvideo','-pix_fmt','rgba','-s',f'{W}x{H}','-r',str(FPS),'-i','-',
     '-filter_complex','[0:v][1:v]overlay=0:0:shortest=1[v]','-map','[v]','-map','0:a','-c:v','libx264','-crf','18','-preset','medium','-threads','4',
     '-pix_fmt','yuv420p','-c:a','copy','-movflags','+faststart',out]
if len(sys.argv)>3:  # кадр алдын ала көру: render.py aud out.png t
    frame(float(sys.argv[3])).save(out); sys.exit()
p=subprocess.Popen(cmd,stdin=subprocess.PIPE)
for i in range(int(DUR*FPS)+1):
    p.stdin.write(frame(i/FPS).tobytes())
p.stdin.close(); p.wait(); print('ok',out)
