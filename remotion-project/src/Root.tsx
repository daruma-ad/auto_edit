import "./index.css";
import { Composition } from "remotion";
import { MainVideo } from "./MainVideo";

export const RemotionRoot: React.FC = () => {
  return (<Composition id="MainVideo" component={MainVideo} durationInFrames={2911} fps={30} width={1920} height={1080} />);
};
