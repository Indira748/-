import '@fontsource/montserrat/800.css';
import '@fontsource/montserrat/900.css';
import {AbsoluteFill, OffthreadVideo, Img, staticFile, useCurrentFrame, useVideoConfig,
  interpolate, spring, Easing, Sequence} from 'remotion';
import data from './data.json';

const FPS = 30;
const C = {cream: '#FFF8EF', teal: '#1E6B60', tealDark: '#123F39', gold: '#F2B544', ink: '#1B1B1B'};
const FONT = 'Montserrat, sans-serif';
const emoji = (code, size) => <Img src={staticFile(`emoji/${code}.svg`)} style={{width: size, height: size}} />;
const f = (sec) => Math.round(sec * FPS);

// ---------- ZOOM (кесінді сайын масштаб; бет нүктесіне бағытталған) ----------
// [start, end, scaleFrom, scaleTo, punchAt?, punchScale?]
const SEG = [
  [0, 2.32, 1.0, 1.05],
  [2.32, 4.97, 1.16, 1.2, 4.03, 1.34],
  [4.97, 6.92, 1.0, 1.04],
  [6.92, 9.09, 1.14, 1.18, 8.94, 1.3],
  [9.09, 10.02, 1.3, 1.32],
  [10.02, 17.09, 1.0, 1.12],
  [17.09, 20.11, 1.18, 1.22, 19.38, 1.34],
  [20.11, 24.05, 1.0, 1.04],
  [24.05, 27.09, 1.12, 1.16],
  [27.09, 27.89, 1.24, 1.26],
  [27.89, 29.14, 1.0, 1.03],
  [29.14, 30.66, 1.16, 1.2],
  [30.66, 31.25, 1.0, 1.02],
  [31.25, 34.39, 1.1, 1.15],
  [34.39, 36.37, 1.0, 1.04],
  [36.37, 99, 1.18, 1.28],
];
const zoomAt = (t) => {
  const s = SEG.find(([a, b]) => t >= a && t < b) || SEG[SEG.length - 1];
  const [a, b, z0, z1, pAt, pZ] = s;
  const end = Math.min(b, data.duration);
  let z = interpolate(t, [a, end], [z0, z1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
    easing: Easing.inOut(Easing.quad)});
  if (pAt) {
    const k = interpolate(t, [pAt - 0.05, pAt + 0.35], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
      easing: Easing.out(Easing.cubic)});
    z = z + (pZ - z0) * k;
  }
  return z;
};

// ---------- СУБТИТР ----------
const pages = (() => {
  const out = []; let cur = [];
  data.words.forEach((w, i) => {
    cur.push(w);
    const len = cur.map((x) => x.w).join(' ').length;
    const next = data.words[i + 1];
    const gap = next ? next.s - w.e : 9;
    if (/[.!?,»]$/.test(w.w) || cur.length >= 3 || len > 16 || gap > 0.35) { out.push(cur); cur = []; }
  });
  if (cur.length) out.push(cur);
  return out.map((p, i) => ({words: p, s: p[0].s, e: out[i + 1] ? out[i + 1][0].s : data.duration}));
})();

const Captions = () => {
  const frame = useCurrentFrame(); const t = frame / FPS;
  const p = pages.find((x) => t >= x.s - 0.05 && t < x.e);
  if (!p) return null;
  const inK = spring({frame: frame - f(p.s - 0.05), fps: FPS, config: {damping: 14, stiffness: 220}});
  return (
    <AbsoluteFill style={{justifyContent: 'flex-start', alignItems: 'center', top: 1235}}>
      <div style={{display: 'flex', flexWrap: 'wrap', justifyContent: 'center', gap: '6px 18px', maxWidth: 860,
        transform: `scale(${0.85 + 0.15 * inK}) translateY(${(1 - inK) * 20}px)`, opacity: inK}}>
        {p.words.map((w, i) => {
          const active = t >= w.s - 0.03 && t < (p.words[i + 1]?.s ?? p.e);
          const said = t >= w.s - 0.03;
          return (
            <span key={i} style={{fontFamily: FONT, fontWeight: 900, fontSize: 76, textTransform: 'uppercase',
              letterSpacing: -1, padding: '2px 14px', borderRadius: 18,
              color: active ? C.ink : said ? '#fff' : 'rgba(255,255,255,0.92)',
              background: active ? C.gold : 'transparent',
              transform: `scale(${active ? 1.07 : 1})`,
              WebkitTextStroke: active ? '0px' : '3px rgba(0,0,0,0.9)', paintOrder: 'stroke fill',
              textShadow: active ? 'none' : '0 6px 18px rgba(0,0,0,0.55)',
              boxShadow: active ? '0 8px 24px rgba(0,0,0,0.35)' : 'none'}}>
              {w.w.replace(/[«»]/g, '')}
            </span>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};

// ---------- КАРТОЧКАЛАР ----------
const useInOut = (dur) => {
  const frame = useCurrentFrame();
  const inK = spring({frame, fps: FPS, config: {damping: 13, stiffness: 180}});
  const outK = interpolate(frame, [dur - 7, dur], [1, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  return {inK, outK, frame};
};
const Card = ({children, dur, top = 230, style = {}}) => {
  const {inK, outK} = useInOut(dur);
  return (
    <AbsoluteFill style={{alignItems: 'center', top}}>
      <div style={{background: C.cream, borderRadius: 40, padding: '30px 46px', fontFamily: FONT, color: C.tealDark,
        boxShadow: '0 24px 60px rgba(0,0,0,0.35)', border: `5px solid ${C.teal}`,
        transform: `scale(${(0.6 + 0.4 * inK) * (0.9 + 0.1 * outK)}) rotate(${(1 - inK) * -6}deg)`,
        opacity: Math.min(inK * 1.5, 1) * outK, ...style}}>
        {children}
      </div>
    </AbsoluteFill>
  );
};

const NameCard = ({dur}) => (
  <Card dur={dur} top={210}>
    <div style={{display: 'flex', alignItems: 'center', gap: 26}}>
      {emoji('1f486-200d-2640-fe0f', 110)}
      <div>
        <div style={{fontWeight: 900, fontSize: 92, lineHeight: 1, color: C.teal}}>АЛИЯ</div>
        <div style={{fontWeight: 800, fontSize: 44, marginTop: 8}}>массажист-маман</div>
      </div>
    </div>
  </Card>
);

const YearsCard = ({dur}) => {
  const frame = useCurrentFrame();
  const n = Math.round(interpolate(frame, [0, 10], [3, 7], {extrapolateRight: 'clamp'}));
  return (
    <Card dur={dur} top={200}>
      <div style={{textAlign: 'center'}}>
        <div style={{fontWeight: 900, fontSize: 170, lineHeight: 0.95, color: C.teal}}>{n} <span style={{fontSize: 110}}>ЖЫЛ</span></div>
        <div style={{fontWeight: 800, fontSize: 48, marginTop: 6}}>{emoji('2b50', 46)} тәжірибе {emoji('2b50', 46)}</div>
      </div>
    </Card>
  );
};

const ArtCard = ({dur, strikeAt}) => {
  const frame = useCurrentFrame();
  const strike = interpolate(frame, [strikeAt, strikeAt + 8], [0, 100], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  const artK = spring({frame: frame - strikeAt - 6, fps: FPS, config: {damping: 10, stiffness: 200}});
  return (
    <Card dur={dur} top={210}>
      <div style={{display: 'flex', alignItems: 'center', gap: 30}}>
        <div style={{position: 'relative', fontWeight: 800, fontSize: 64, color: '#7a7a7a'}}>
          кәсіп
          <div style={{position: 'absolute', left: -6, top: '52%', height: 9, width: `${strike + 6}%`, background: '#E04848', borderRadius: 6}} />
        </div>
        <div style={{fontSize: 64, fontWeight: 900, color: C.gold}}>→</div>
        <div style={{display: 'flex', alignItems: 'center', gap: 14, transform: `scale(${artK})`}}>
          <span style={{fontWeight: 900, fontSize: 92, color: C.teal}}>ӨНЕР</span>{emoji('1f3a8', 84)}
        </div>
      </div>
    </Card>
  );
};

const Bubble = ({dur}) => {
  const {inK, outK, frame} = useInOut(dur);
  const wob = Math.sin(frame / 6) * 2;
  return (
    <AbsoluteFill style={{alignItems: 'center', top: 240}}>
      <div style={{position: 'relative', background: '#fff', borderRadius: 50, padding: '30px 50px', fontFamily: FONT,
        fontWeight: 900, fontSize: 64, color: C.ink, boxShadow: '0 24px 60px rgba(0,0,0,0.35)',
        transform: `scale(${inK * (0.9 + 0.1 * outK)}) rotate(${wob}deg)`, opacity: outK, display: 'flex', gap: 20, alignItems: 'center'}}>
        {emoji('1f914', 86)} Қалай шаршамайсыз?
        <div style={{position: 'absolute', bottom: -34, left: '50%', width: 0, height: 0, borderLeft: '30px solid transparent',
          borderRight: '30px solid transparent', borderTop: '40px solid #fff'}} />
      </div>
    </AbsoluteFill>
  );
};

const EnergyCard = ({dur}) => {
  const {inK, outK, frame} = useInOut(dur);
  const glow = 20 + Math.sin(frame / 3) * 12;
  return (
    <AbsoluteFill style={{alignItems: 'center', top: 250}}>
      <div style={{display: 'flex', alignItems: 'center', gap: 16, fontFamily: FONT, fontWeight: 900, fontSize: 110,
        color: C.gold, WebkitTextStroke: '4px #3a2a00', paintOrder: 'stroke fill',
        filter: `drop-shadow(0 0 ${glow}px rgba(242,181,68,0.9))`,
        transform: `scale(${(0.3 + 0.7 * inK)})`, opacity: outK}}>
        {emoji('26a1', 120)}ЭНЕРГИЯ{emoji('26a1', 120)}
      </div>
    </AbsoluteFill>
  );
};

const LIST = [['Классикалық', 0], ['Нүктелі', 21.51 - 19.92], ['Спорттық', 22.75 - 19.92],
  ['Балаларға', 24.76 - 19.92], ['Жүкті аналарға', 25.52 - 19.92]];
const ServicesCard = ({dur}) => {
  const {inK, outK, frame} = useInOut(dur);
  const badgeAt = f(27.54 - 19.92);
  const badgeK = spring({frame: frame - badgeAt, fps: FPS, config: {damping: 11, stiffness: 200}});
  return (
    <AbsoluteFill style={{alignItems: 'center', top: 120}}>
      <div style={{background: C.cream, borderRadius: 40, padding: '28px 44px 34px', fontFamily: FONT, color: C.tealDark,
        boxShadow: '0 24px 60px rgba(0,0,0,0.35)', border: `5px solid ${C.teal}`, minWidth: 640,
        transform: `translateY(${(1 - inK) * -80}px)`, opacity: Math.min(inK * 1.5, 1) * outK}}>
        <div style={{fontWeight: 900, fontSize: 46, color: '#fff', background: C.teal, borderRadius: 20,
          padding: '8px 22px', marginBottom: 14, textAlign: 'center'}}>МАССАЖ ТҮРЛЕРІ</div>
        {LIST.map(([name, at], i) => {
          const k = spring({frame: frame - f(at), fps: FPS, config: {damping: 14, stiffness: 220}});
          return (
            <div key={i} style={{display: 'flex', alignItems: 'center', gap: 18, fontWeight: 800, fontSize: 54,
              margin: '6px 0', opacity: k, transform: `translateX(${(1 - k) * -60}px)`}}>
              {emoji('2705', 52)}{name}
            </div>
          );
        })}
      </div>
      <div style={{marginTop: 14, background: C.gold, borderRadius: 30, padding: '12px 30px', fontFamily: FONT,
        fontWeight: 900, fontSize: 46, color: C.ink, display: 'flex', alignItems: 'center', gap: 12,
        boxShadow: '0 12px 30px rgba(0,0,0,0.35)', transform: `scale(${badgeK}) rotate(-3deg)`, opacity: outK}}>
        {emoji('2b50', 48)} ЖОҒАРЫ ДЕҢГЕЙДЕ
      </div>
    </AbsoluteFill>
  );
};

const WelcomeCard = ({dur}) => (
  <Card dur={dur} top={230}>
    <div style={{display: 'flex', alignItems: 'center', gap: 22, fontWeight: 900, fontSize: 70}}>
      {emoji('1f44b', 90)} Қош келдіңіз!
    </div>
  </Card>
);

const Chips = ({dur}) => {
  const {outK, frame} = useInOut(dur);
  const chip = (txt, code, delay, rot) => {
    const k = spring({frame: frame - delay, fps: FPS, config: {damping: 11, stiffness: 200}});
    return (
      <div style={{background: C.cream, border: `5px solid ${C.teal}`, borderRadius: 60, padding: '18px 38px',
        display: 'flex', alignItems: 'center', gap: 16, fontFamily: FONT, fontWeight: 900, fontSize: 66, color: C.tealDark,
        boxShadow: '0 18px 40px rgba(0,0,0,0.35)', transform: `scale(${k}) rotate(${rot}deg)`, opacity: outK}}>
        {emoji(code, 72)}{txt}
      </div>
    );
  };
  return (
    <AbsoluteFill style={{alignItems: 'center', top: 210, gap: 26}}>
      {chip('Денсаулық', '1f49a', 0, -3)}
      {chip('Сұлулық', '2728', f(32.14 - 30.85), 3)}
    </AbsoluteFill>
  );
};

const CTA = ({dur}) => {
  const {inK, frame} = useInOut(dur + 100);
  const pulse = 1 + Math.sin(frame / 5) * 0.04;
  const bounce = Math.abs(Math.sin(frame / 7)) * 22;
  return (
    <AbsoluteFill style={{alignItems: 'center', top: 200}}>
      <div style={{background: C.teal, borderRadius: 44, padding: '30px 50px', fontFamily: FONT, color: '#fff',
        textAlign: 'center', boxShadow: '0 24px 60px rgba(0,0,0,0.4)', transform: `scale(${inK * pulse})`}}>
        <div style={{display: 'flex', alignItems: 'center', gap: 18, fontWeight: 900, fontSize: 68}}>
          {emoji('1f4ac', 80)} ПІКІР ЖАЗЫҢЫЗ
        </div>
        <div style={{fontWeight: 800, fontSize: 42, marginTop: 8, color: C.gold}}>массаж туралы ойыңызбен бөлісіңіз</div>
      </div>
      <div style={{marginTop: 18, transform: `translateY(${bounce}px) scale(${inK})`}}>{emoji('1f447', 96)}</div>
    </AbsoluteFill>
  );
};

// card list: [component, start, end, props]
export const CARDS = [
  [NameCard, 0.9, 4.0, {}, 'pop'],
  [YearsCard, 4.03, 6.6, {}, 'pop2'],
  [ArtCard, 7.9, 10.02, {strikeAt: f(8.555 - 7.9)}, 'pop'],
  [Bubble, 10.9, 12.9, {}, 'pop'],
  [EnergyCard, 18.56, 19.85, {}, 'pop2'],
  [ServicesCard, 19.92, 29.0, {}, 'whoosh'],
  [WelcomeCard, 29.14, 30.5, {}, 'pop'],
  [Chips, 30.85, 34.3, {}, 'pop'],
  [CTA, 34.39, 99, {}, 'ding'],
];

export const Reel = () => {
  const frame = useCurrentFrame();
  const {durationInFrames} = useVideoConfig();
  const t = frame / FPS;
  const z = zoomAt(t);
  // кесінді ауысқанда жеңіл «flash»
  const lastCut = [0, ...data.cuts].filter((c) => c <= t).pop();
  const flash = interpolate(t - lastCut, [0, 0.12], [0.18, 0], {extrapolateRight: 'clamp'});
  return (
    <AbsoluteFill style={{background: '#000'}}>
      <AbsoluteFill style={{transform: `scale(${z})`, transformOrigin: '55.5% 47%'}}>
        <OffthreadVideo src={staticFile('cut.mp4')} muted />
      </AbsoluteFill>
      {/* төменгі жағын сәл қараңғылау — субтитр оқылуы үшін */}
      <AbsoluteFill style={{background: 'linear-gradient(180deg, rgba(0,0,0,0) 55%, rgba(0,0,0,0.35) 80%, rgba(0,0,0,0.15) 100%)'}} />
      <AbsoluteFill style={{background: '#fff', opacity: lastCut > 0 ? flash : 0}} />
      {CARDS.map(([Comp, s, e, props], i) => {
        const end = Math.min(f(e), durationInFrames);
        return (
          <Sequence key={i} from={f(s)} durationInFrames={end - f(s)}>
            <Comp dur={end - f(s)} {...props} />
          </Sequence>
        );
      })}
      <Captions />
    </AbsoluteFill>
  );
};
