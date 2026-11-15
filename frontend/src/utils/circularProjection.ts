const R = 1737400;
const RAD = Math.PI/180;
export const CIRCULAR_RADIUS_M = 2*R*Math.tan(5*RAD);
export type MapCenter = { latitude: number; longitude: number };

function axes(center: MapCenter) {
  const p=center.latitude*RAD, l=center.longitude*RAD;
  return {
    up: [Math.cos(p)*Math.cos(l), Math.cos(p)*Math.sin(l), Math.sin(p)],
    east: [-Math.sin(l), Math.cos(l), 0],
    north: [-Math.sin(p)*Math.cos(l), -Math.sin(p)*Math.sin(l), Math.cos(p)],
  };
}

// A genuine local stereographic projection, not a circular crop of a world map.
export function circularProjection(center: MapCenter) {
  const { up, east, north }=axes(center);
  return {
    inverse(x: number, y: number): MapCenter {
      const q=(x*x+y*y)/(4*R*R), d=1+q;
      const v=up.map((u,i)=>((1-q)*u+x/R*east[i]+y/R*north[i])/d);
      return { latitude: Math.asin(Math.max(-1,Math.min(1,v[2])))/RAD, longitude: Math.atan2(v[1],v[0])/RAD };
    },
    forward(latitude: number, longitude: number) {
      const p=latitude*RAD,l=longitude*RAD;
      const v=[Math.cos(p)*Math.cos(l),Math.cos(p)*Math.sin(l),Math.sin(p)];
      const dot=(a:number[])=>a.reduce((sum,x,i)=>sum+x*v[i],0);
      const d=1+dot(up);
      return d<1e-12 ? { x: Infinity, y: Infinity } : { x:2*R*dot(east)/d, y:2*R*dot(north)/d };
    },
  };
}
