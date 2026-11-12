"""Locate UI-colored objects inside an explicitly recorded viewport and target ROI.

Returns evidence only; a pixel bound is never a measured clash boundary.
No guessed compass position or center-box fallback is allowed.
"""
from collections import deque

UI_TARGET_COLORS = ((255, 161, 56), (31, 214, 224))

def highlight_bounds(image, *, viewport, compass, target_roi, excluded=(), min_pixels=12, pad=28):
    import numpy as np
    a=np.asarray(image.convert('RGB'));h,w=a.shape[:2]
    def rect(value):
        if len(value)!=4: raise ValueError('Rectangle requires left, top, right, bottom')
        x0,y0,x1,y1=map(int,value)
        if not (0<=x0<x1<=w and 0<=y0<y1<=h): raise ValueError('Rectangle outside image')
        return x0,y0,x1,y1
    v=rect(viewport);roi=rect(target_roi);cuts=[rect(compass),*[rect(r) for r in excluded]]
    if not (v[0]<=roi[0]<roi[2]<=v[2] and v[1]<=roi[1]<roi[3]<=v[3]):
        raise ValueError('Target ROI must lie inside viewport')
    # Hue/chroma matching tolerates lighting and JPEG noise, but rejects gray UI.
    rgb=a.astype(float);mx=rgb.max(axis=2);mn=rgb.min(axis=2);delta=mx-mn
    hue=np.zeros((h,w));nonzero=delta>0
    for channel,offset in [(0,0),(1,2),(2,4)]:
        hit=nonzero&(rgb[:,:,channel]==mx)
        numerator=rgb[:,:,(channel+1)%3]-rgb[:,:,(channel+2)%3]
        hue[hit]=(numerator[hit]/delta[hit]+offset)*60
    hue%=360
    colored=(delta>45)&(mx>70)&(((hue>=15)&(hue<=48))|((hue>=170)&(hue<=200)))
    allowed=np.zeros((h,w),bool);allowed[roi[1]:roi[3],roi[0]:roi[2]]=True
    for x0,y0,x1,y1 in cuts: allowed[y0:y1,x0:x1]=False
    mask=colored&allowed;seen=np.zeros_like(mask);points=[];components=[]
    for y,x in zip(*np.nonzero(mask)):
        if seen[y,x]: continue
        queue=deque([(int(x),int(y))]);seen[y,x]=True;component=[]
        while queue:
            px,py=queue.popleft();component.append((px,py))
            for dx,dy in ((-1,0),(1,0),(0,-1),(0,1)):
                nx,ny=px+dx,py+dy
                if 0<=nx<w and 0<=ny<h and mask[ny,nx] and not seen[ny,nx]:
                    seen[ny,nx]=True;queue.append((nx,ny))
        if len(component)>=min_pixels: points.extend(component);components.append(len(component))
    audit=dict(viewport=list(v),compass=list(cuts[0]),target_roi=list(roi),excluded=[list(r) for r in cuts[1:]],palette=UI_TARGET_COLORS,component_pixels=components,basis='highlighted object pixels, not clash boundary')
    if not points: return dict(audit,status='NEEDS_REVIEW',box=None,reason='No reliable target highlights')
    xs,ys=zip(*points);raw=(min(xs),min(ys),max(xs)+1,max(ys)+1)
    # An object reaching a mask/ROI edge may be truncated: never silently accept it.
    borders=raw[0]<=roi[0] or raw[1]<=roi[1] or raw[2]>=roi[2] or raw[3]>=roi[3]
    for x0,y0,x1,y1 in cuts:
        borders|=any(x0-1<=x<=x1 and y0-1<=y<=y1 for x,y in points)
    if borders:return dict(audit,status='NEEDS_REVIEW',box=None,reason='Highlights touch ROI or excluded UI; recapture or adjust masks')
    box=[max(v[0],raw[0]-pad),max(v[1],raw[1]-pad),min(v[2],raw[2]+pad),min(v[3],raw[3]+pad)]
    if any(box[0]<r[2] and box[2]>r[0] and box[1]<r[3] and box[3]>r[1] for r in cuts):
        return dict(audit,status='NEEDS_REVIEW',box=None,reason='Expanded box intersects excluded UI; adjust view')
    return dict(audit,status='OK',box=box,reason=None)
