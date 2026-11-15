import { useEffect, useMemo, useRef, useState } from "react";
import { CIRCULAR_RADIUS_M, circularProjection } from "../../utils/circularProjection";
import type { GlobeSite } from "./Globe3D";
import type { MapCenter } from "../../utils/circularProjection";
import { INITIAL_CIRCULAR_VIEW, circularWorld, panCircular, zoomCircular } from "../../utils/circularNavigation";
import type { CircularView, CircularFrame } from "../../utils/circularNavigation";
import "./CircularSiteMap.css";

type Raster = { width: number; height: number; data: Uint8ClampedArray };
const tileCache = new Map<string, Raster | null>();
let basePromise: Promise<Raster> | null = null;
async function raster(url: string, signal?: AbortSignal): Promise<Raster> {
  const response=await fetch(url,{signal});
  if (!response.ok) throw new Error("Lunar imagery unavailable.");
  const bitmap=await createImageBitmap(await response.blob());
  const canvas=document.createElement("canvas");canvas.width=bitmap.width;canvas.height=bitmap.height;
  const ctx=canvas.getContext("2d")!;ctx.drawImage(bitmap,0,0);bitmap.close();
  return { width:canvas.width,height:canvas.height,data:ctx.getImageData(0,0,canvas.width,canvas.height).data };
}

type Props = {
  center: MapCenter; sites: GlobeSite[]; selectedId: string | null;
  addMode: boolean; onPick: (id: string)=>void; onPlace:(lat:number,lon:number)=>void;
};

export default function CircularSiteMap({center,sites,selectedId,addMode,onPick,onPlace}:Props) {
  const canvasRef=useRef<HTMLCanvasElement>(null);
  const [view,setView]=useState<CircularView>(INITIAL_CIRCULAR_VIEW);
  const viewRef=useRef(view);
  const drag=useRef<{sx:number;sy:number;view:CircularView;moved:boolean}|null>(null);
  const gesture=useRef<{image:HTMLCanvasElement;view:CircularView}|null>(null);
  const wheelTimer=useRef<number|null>(null);
  const [status,setStatus]=useState("Loading circular lunar map...");
  const projection=useMemo(()=>circularProjection(center),[center.latitude,center.longitude]);
  const geometry=useRef<CircularFrame>({width:1,height:1,radius:1});
  function captureGesture() {
    const canvas=canvasRef.current!,image=document.createElement("canvas");
    image.width=canvas.width;image.height=canvas.height;image.getContext("2d")!.drawImage(canvas,0,0);
    gesture.current={image,view:{...viewRef.current}};
  }
  function preview(next:CircularView) {
    const canvas=canvasRef.current!,snapshot=gesture.current;if(!snapshot)return;
    const frame=geometry.current,ratio=next.zoom/snapshot.view.zoom,scale=frame.radius/CIRCULAR_RADIUS_M*next.zoom;
    const dx=frame.width/2*(1-ratio)+(snapshot.view.x-next.x)*scale;
    const dy=frame.height/2*(1-ratio)-(snapshot.view.y-next.y)*scale;
    const ctx=canvas.getContext("2d")!;
    ctx.setTransform(1,0,0,1,0,0);ctx.fillStyle="#08090b";ctx.fillRect(0,0,canvas.width,canvas.height);
    ctx.setTransform(ratio,0,0,ratio,dx*devicePixelRatio,dy*devicePixelRatio);ctx.drawImage(snapshot.image,0,0);ctx.setTransform(1,0,0,1,0,0);
  }
  function commit(next:CircularView) {
    if(wheelTimer.current!==null)window.clearTimeout(wheelTimer.current);
    wheelTimer.current=null;gesture.current=null;viewRef.current=next;setView({...next});
  }
  useEffect(()=>{
    const canvas=canvasRef.current!;
    const wheel=(event:WheelEvent)=>{
      event.preventDefault();if(drag.current)return;
      if(!gesture.current)captureGesture();
      const box=canvas.getBoundingClientRect();
      const next=zoomCircular(viewRef.current,geometry.current,event.clientX-box.left,event.clientY-box.top,Math.exp(-event.deltaY*.0015));
      viewRef.current=next;preview(next);
      if(wheelTimer.current!==null)window.clearTimeout(wheelTimer.current);
      wheelTimer.current=window.setTimeout(()=>commit(viewRef.current),120);
    };
    canvas.addEventListener("wheel",wheel,{passive:false});
    return()=>{canvas.removeEventListener("wheel",wheel);if(wheelTimer.current!==null)window.clearTimeout(wheelTimer.current);};
  },[]);
  useEffect(()=>{
    const canvas=canvasRef.current!;
    const controller=new AbortController();let stopped=false,raf=0;
    let draw:()=>void=()=>{};
    const queue=()=>{cancelAnimationFrame(raf);raf=requestAnimationFrame(()=>draw());};
    const observer=new ResizeObserver(queue);observer.observe(canvas);
    if (!basePromise) basePromise=raster("/globe/lroc_wac_global.jpg").catch(error=>{basePromise=null;throw error;});
    void basePromise.then(async base=>{
      if(stopped)return;
      let grid: {lat:Float32Array;lon:Float32Array;n:number;m:number;w:number;h:number;level:number}|null=null;
      const requested=new Set<string>();
      const loadTiles=async(keys:string[])=>{
        let cursor=0;
        await Promise.all(Array.from({length:4},async()=>{
          while(cursor<keys.length && !stopped){
            const key=keys[cursor++];
            try{
              const tile=await raster(`https://trek.nasa.gov/tiles/Moon/EQ/LRO_WAC_Mosaic_Global_303ppd_v02/1.0.0/default/default028mm/${key}.jpg`,controller.signal);
              if(stopped)return;tileCache.set(key,tile);
              if(tileCache.size>256)tileCache.delete(tileCache.keys().next().value!);
              queue();
            }catch{if(!stopped)tileCache.set(key,null);}
          }
        }));
      };
      draw=()=>{
        if(stopped||gesture.current)return;
        const w=canvas.clientWidth,h=canvas.clientHeight,baseRadius=Math.max(1,Math.min(w,h)/2-24);
        const scale=baseRadius/CIRCULAR_RADIUS_M*view.zoom,r=baseRadius*view.zoom;
        const cx=w/2-view.x*scale,cy=h/2+view.y*scale;
        const n=Math.min(1024,Math.ceil(w*devicePixelRatio)),m=Math.min(1024,Math.ceil(h*devicePixelRatio));
        geometry.current={width:w,height:h,radius:baseRadius};canvas.width=Math.ceil(w*devicePixelRatio);canvas.height=Math.ceil(h*devicePixelRatio);
        const ctx=canvas.getContext("2d")!;ctx.scale(devicePixelRatio,devicePixelRatio);ctx.fillStyle="#08090b";ctx.fillRect(0,0,w,h);
        if(!grid||grid.n!==n||grid.w!==w||grid.h!==h){
          const lat=new Float32Array(n*m),lon=new Float32Array(n*m);lat.fill(NaN);
          const keys=new Map<string,number>();
          const level=Math.max(2,Math.min(8,Math.ceil(Math.log2(2*Math.PI*1737400/(w/n/scale)/512))));
          for(let row=0;row<m;row++)for(let col=0;col<n;col++){
            const {x,y}=circularWorld(view,geometry.current,(col+.5)/n*w,(row+.5)/m*h);if(x*x+y*y>CIRCULAR_RADIUS_M**2)continue;
            const p=projection.inverse(x,y),i=row*n+col;lat[i]=p.latitude;lon[i]=p.longitude;
            if(row%8===0&&col%8===0){const tx=Math.floor(((p.longitude+180)/360)*(2**(level+1)))%(2**(level+1)),ty=Math.min(2**level-1,Math.floor((90-p.latitude)/180*2**level));const key=`${level}/${ty}/${tx}`;keys.set(key,Math.min(keys.get(key)??Infinity,x*x+y*y));}
          }
          grid={lat,lon,n,m,w,h,level};
          const pending=[...keys].sort((a,b)=>a[1]-b[1]).map(([key])=>key).filter(key=>!tileCache.has(key)&&!requested.has(key)).slice(0,128);
          pending.forEach(key=>requested.add(key));void loadTiles(pending);
        }
        const image=ctx.createImageData(n,m),{lat,lon,level}=grid;
        for(let i=0;i<lat.length;i++){
          if(!Number.isFinite(lat[i]))continue;
          const u=((lon[i]+180)/360+1)%1,v=Math.max(0,Math.min(1-1e-10,(90-lat[i])/180));
          const tx=u*2**(level+1),ty=v*2**level;
          const tile=tileCache.get(`${level}/${Math.floor(ty)}/${Math.floor(tx)}`);
          const source=tile||base;
          const px=Math.floor((tile?tx%1:u)*source.width),py=Math.floor((tile?ty%1:v)*source.height),j=(py*source.width+px)*4;
          image.data.set(source.data.subarray(j,j+4),i*4);
        }
        const layer=document.createElement("canvas");layer.width=n;layer.height=m;layer.getContext("2d")!.putImageData(image,0,0);
        ctx.drawImage(layer,0,0,w,h);
        ctx.save();ctx.beginPath();ctx.arc(cx,cy,r,0,2*Math.PI);ctx.clip();
        for(const site of sites){
          const p=projection.forward(site.latitude,site.longitude);if(Math.hypot(p.x,p.y)>CIRCULAR_RADIUS_M)continue;
          const x=cx+p.x*scale,y=cy-p.y*scale;
          ctx.beginPath();ctx.arc(x,y,site.id===selectedId?6:4,0,2*Math.PI);ctx.fillStyle=site.color;ctx.fill();
          ctx.strokeStyle="#000";ctx.lineWidth=2;ctx.stroke();ctx.fillStyle="#fff";ctx.font="12px system-ui";ctx.fillText(site.label,x+9,y-6);
        }
        ctx.strokeStyle="#71d4e7";ctx.lineWidth=1;ctx.beginPath();ctx.moveTo(cx-10,cy);ctx.lineTo(cx+10,cy);ctx.moveTo(cx,cy-10);ctx.lineTo(cx,cy+10);ctx.stroke();ctx.restore();
        ctx.beginPath();ctx.arc(cx,cy,r,0,2*Math.PI);ctx.strokeStyle="#7c8996";ctx.lineWidth=1;ctx.stroke();
      };
      queue();setStatus("LROC WAC imagery · NASA/GSFC/ASU · circular stereographic map");
    }).catch(()=>{if(!stopped)setStatus("Lunar imagery unavailable. Check your connection and try again.");});
    return()=>{stopped=true;controller.abort();observer.disconnect();cancelAnimationFrame(raf);};
  },[projection,view,sites,selectedId]);
  function selectAt(event:React.PointerEvent<HTMLCanvasElement>) {
    const box=event.currentTarget.getBoundingClientRect();
    const {x,y}=circularWorld(viewRef.current,geometry.current,event.clientX-box.left,event.clientY-box.top);
    if(Math.hypot(x,y)>CIRCULAR_RADIUS_M)return;
    const scale=geometry.current.radius/CIRCULAR_RADIUS_M*viewRef.current.zoom;
    const nearest=sites.find(site=>{const p=projection.forward(site.latitude,site.longitude);return Math.hypot(p.x-x,p.y-y)*scale<9;});
    if(nearest)onPick(nearest.id);else if(addMode){const p=projection.inverse(x,y);onPlace(p.latitude,p.longitude);}
  }
  return <div className="circular-site-map">
    <canvas ref={canvasRef} aria-label="Circular 2D map centered on chosen coordinates" style={{cursor:addMode?"crosshair":undefined}}
      onPointerDown={event=>{
        if(event.button!==0)return;
        commit(viewRef.current);captureGesture();drag.current={sx:event.clientX,sy:event.clientY,view:{...viewRef.current},moved:false};
        event.currentTarget.setPointerCapture(event.pointerId);event.currentTarget.classList.add("dragging");
      }}
      onPointerMove={event=>{
        if(!drag.current)return;
        const dx=event.clientX-drag.current.sx,dy=event.clientY-drag.current.sy;
        if(Math.hypot(dx,dy)>3)drag.current.moved=true;
        const next=panCircular(drag.current.view,geometry.current,dx,dy);viewRef.current=next;preview(next);
      }}
      onPointerUp={event=>{
        const moved=drag.current?.moved;drag.current=null;event.currentTarget.classList.remove("dragging");
        if(event.currentTarget.hasPointerCapture(event.pointerId))event.currentTarget.releasePointerCapture(event.pointerId);
        commit(viewRef.current);if(moved===false)selectAt(event);
      }}
      onPointerCancel={event=>{drag.current=null;event.currentTarget.classList.remove("dragging");commit(viewRef.current);}}
      onDoubleClick={()=>commit(INITIAL_CIRCULAR_VIEW)} />
    <div className="circular-map-controls"><button type="button" aria-label="Zoom in circular map" onClick={()=>commit(zoomCircular(viewRef.current,geometry.current,geometry.current.width/2,geometry.current.height/2,1.5))}>+</button><button type="button" aria-label="Zoom out circular map" onClick={()=>commit(zoomCircular(viewRef.current,geometry.current,geometry.current.width/2,geometry.current.height/2,1/1.5))}>−</button><button type="button" onClick={()=>commit(INITIAL_CIRCULAR_VIEW)}>Reset view</button><span>{Math.round(2*CIRCULAR_RADIUS_M/view.zoom/1000)} km view</span></div>
    <div className="circular-map-caption" role="status">Center: {center.latitude.toFixed(3)}°, {center.longitude.toFixed(3)}°<br/>{status}</div>
  </div>;
}
