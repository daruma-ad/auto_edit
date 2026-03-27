import { Composition } from "remotion";
import { z } from "zod"; // remotionからではなくzodから直接インポート
import { MainVideo } from "./MainVideo";

const CompositionSchema = z.object({
  fontSizeOffset: z.number().default(0),
  bottomOffset: z.number().default(0),
});

export const RemotionRoot: React.FC = () => {
  return (
    <Composition 
      id="MainVideo" 
      component={MainVideo} 
      durationInFrames={10654} 
      fps={30} 
      width={640} 
      height={360} 
      schema={CompositionSchema}
      defaultProps={{
        fontSizeOffset: 0,
        bottomOffset: 0,
      }}
    />
  );
};
