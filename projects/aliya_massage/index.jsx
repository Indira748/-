import {registerRoot, Composition} from 'remotion';
import {Reel, AD_END, END_CARD} from './Reel';
const Root = () => <Composition id="Reel" component={Reel} durationInFrames={Math.round((AD_END+END_CARD)*30)} fps={30} width={1080} height={1920}
  defaultProps={{hook: 'Шаршадыңыз ба?', sub: '7 жыл тәжірибелі массажист', cta: 'МАССАЖҒА ЖАЗЫЛЫҢЫЗ'}}/>;
registerRoot(Root);
