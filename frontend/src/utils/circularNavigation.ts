import { CIRCULAR_RADIUS_M } from "./circularProjection";

export type CircularView = { x: number; y: number; zoom: number };
export type CircularFrame = { width: number; height: number; radius: number };
export const INITIAL_CIRCULAR_VIEW: CircularView = { x: 0, y: 0, zoom: 1 };

export function circularWorld(view: CircularView, frame: CircularFrame, sx: number, sy: number) {
  const scale=frame.radius/CIRCULAR_RADIUS_M*view.zoom;
  return { x:view.x+(sx-frame.width/2)/scale, y:view.y-(sy-frame.height/2)/scale };
}

export function panCircular(view: CircularView, frame: CircularFrame, dx: number, dy: number): CircularView {
  const scale=frame.radius/CIRCULAR_RADIUS_M*view.zoom;
  return { ...view, x:view.x-dx/scale, y:view.y+dy/scale };
}

export function zoomCircular(view: CircularView, frame: CircularFrame, sx: number, sy: number, factor: number): CircularView {
  const before=circularWorld(view,frame,sx,sy);
  const next={...view,zoom:Math.min(64,Math.max(.2,view.zoom*factor))};
  const after=circularWorld(next,frame,sx,sy);
  return { ...next,x:next.x+before.x-after.x,y:next.y+before.y-after.y };
}
