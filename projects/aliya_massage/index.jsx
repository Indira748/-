import {registerRoot, Composition} from 'remotion';
import {Reel} from './Reel';
import data from './data.json';
const Root = () => <Composition id="Reel" component={Reel} durationInFrames={Math.round(data.duration*30)} fps={30} width={1080} height={1920}/>;
registerRoot(Root);
