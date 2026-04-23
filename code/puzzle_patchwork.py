#!/usr/bin/env python3
"""
puzzle_patchwork.py  v16
────────────────────────
Cut lines derived from a tile-ownership map (zero gaps, single pixel):
  1. Build tmap: stamp shaped masks → zeros filled from rectangle ownership
  2. Boundary = adjacent pixels in tmap with different values
  3. Draw this boundary as a dark overlay after compositing

Two rendering passes:
  Pass 1 — full rectangles  (every pixel filled)
  Pass 2 — shaped pieces    (tabs/blanks via alpha mask)
  Pass 3 — tmap boundary    (single dark pixel at every piece edge)

Usage:
    python puzzle_patchwork.py -i FOLDER -o out.jpg --cols 5 --rows 8 --tile 450
"""

import argparse, random, sys
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageOps

EXTS = {".jpg",".jpeg",".png",".bmp",".tif",".tiff",".webp"}

# ── Geometry ──────────────────────────────────────────────────────────────────

def make_tab(tc,nw,nh,rx,ry,lean):
    x1=1.
    xNL=tc-nw; xNR=tc+nw; sw=nw*1.4; xSL=tc-sw; xSR=tc+sw
    hcx=tc+lean; hcy=nh+ry; k=0.5523
    HL=np.array([hcx-rx,hcy]); HR=np.array([hcx+rx,hcy]); HT=np.array([hcx,hcy+ry])
    SL=np.array([xSL,0.]); NLb=np.array([xNL,nh*.3])
    NRb=np.array([xNR,nh*.3]); SR=np.array([xSR,0.])
    return [
        (np.array([xSL*.4,0]),            np.array([xSL*.85,0]),            SL),
        (np.array([xSL+(xNL-xSL)*.5,0]), np.array([xNL,0]),                NLb),
        (NLb+np.array([0,(HL[1]-NLb[1])*.55]),HL+np.array([rx*.15,-ry*.5]),HL),
        (HL+np.array([0,ry*k]),           HT+np.array([-rx*k,0]),           HT),
        (HT+np.array([rx*k,0]),           HR+np.array([0,ry*k]),            HR),
        (HR+np.array([-rx*.15,-ry*.5]),   NRb+np.array([0,(HR[1]-NRb[1])*.55]),NRb),
        (np.array([xNR,0]),               np.array([xSR-(xSR-xNR)*.5,0]),   SR),
        (np.array([xSR+(x1-xSR)*.15,0]), np.array([xSR+(x1-xSR)*.6,0]),    np.array([x1,0])),
    ]

def cbez(p0,c1,c2,p3,n=20):
    pts=[]
    for i in range(n+1):
        t=i/n; u=1-t
        pts.append(u**3*p0+3*u**2*t*c1+3*u*t**2*c2+t**3*p3)
    return pts

def jigsaw_edge(p1,p2,flip,seed):
    p1=np.array(p1,float); p2=np.array(p2,float)
    v=p2-p1; L=np.linalg.norm(v); u=v/L
    nv=np.array([u[1],-u[0]])
    if flip==0: return [p1,p2]
    rng=np.random.default_rng(seed)
    tc=rng.uniform(.40,.60); nw=rng.uniform(.08,.12)
    nh=rng.uniform(.03,.06); rx=rng.uniform(.13,.18)
    ry=rng.uniform(.09,.13); lean=rng.uniform(-.03,.03)
    def w(lp): return p1+lp[0]*v+lp[1]*flip*L*nv
    pts=[w(np.array([0.,0.]))]
    prev=np.array([0.,0.])
    for c1,c2,end in make_tab(tc,nw,nh,rx,ry,lean):
        for lp in cbez(prev,c1,c2,end)[1:]: pts.append(w(lp))
        prev=end
    return pts

def piece_mask(PW,PH,tw,th,ext,tf,ts,rf,rs,bf,bs,lf,ls):
    e=ext
    TL=(e,e); TR=(e+tw,e); BR=(e+tw,e+th); BL=(e,e+th)
    pts  = jigsaw_edge(TL,TR,tf,ts)
    pts += jigsaw_edge(TR,BR,rf,rs)[1:]
    pts += jigsaw_edge(BR,BL,bf,bs)[1:]
    pts += jigsaw_edge(BL,TL,lf,ls)[1:]
    msk=Image.new("L",(PW,PH),0)
    ImageDraw.Draw(msk).polygon(
        [(int(round(p[0])),int(round(p[1]))) for p in pts],fill=255)
    return msk

# ── Helpers ───────────────────────────────────────────────────────────────────

def load_images(folder):
    p=sorted(x for x in Path(folder).rglob("*") if x.suffix.lower() in EXTS)
    if not p: sys.exit(f"[ERROR] No images in {folder}")
    return p

def crop_to(img,W,H):
    om=img.mode; img=img.convert("RGB")
    iw,ih=img.size; s=max(W/iw,H/ih)
    nw,nh=int(iw*s+.5),int(ih*s+.5)
    img=img.resize((nw,nh),Image.LANCZOS)
    l=(nw-W)//2; t=(nh-H)//2
    img=img.crop((l,t,l+W,t+H))
    if om in ("L","LA"): img=img.convert("L").convert("RGB")
    return img

# ── Assembly ──────────────────────────────────────────────────────────────────

def build(input_folder,output_path,
          cols=6,rows=5,tile_size=180,
          gray_ratio=0.0,seed=None,bg=(18,18,18)):

    rng=random.Random(seed)
    all_p=load_images(input_folder)
    n=cols*rows
    if len(all_p)<n:
        best=max(((c,r) for c in range(1,cols+1) for r in range(1,rows+1)
                  if c*r<=len(all_p)),key=lambda x:x[0]*x[1])
        print(f"[WARN] {len(all_p)}<{cols}x{rows}. Using {best[0]}x{best[1]}")
        cols,rows=best; n=cols*rows

    sel=rng.sample(all_p,n); rng.shuffle(sel)
    tw=th=tile_size
    ext=int(tw*0.38)+10
    PW,PH=tw+2*ext,th+2*ext
    CW,CH=cols*tw,rows*th

    ng=round(n*gray_ratio)
    gf=[True]*ng+[False]*(n-ng); rng.shuffle(gf)

    HF=[[rng.choice([1,-1]) for _ in range(cols)] for _ in range(rows-1)]
    HS=[[rng.randint(0,2**31) for _ in range(cols)] for _ in range(rows-1)]
    VF=[[rng.choice([1,-1]) for _ in range(cols-1)] for _ in range(rows)]
    VS=[[rng.randint(0,2**31) for _ in range(cols-1)] for _ in range(rows)]

    def ge(r,c,side):
        if side=='bottom': return (0,0) if r==rows-1 else ( HF[r][c],   HS[r][c])
        if side=='top':    return (0,0) if r==0      else (-HF[r-1][c], HS[r-1][c])
        if side=='right':  return (0,0) if c==cols-1 else ( VF[r][c],   VS[r][c])
        if side=='left':   return (0,0) if c==0      else (-VF[r][c-1], VS[r][c-1])

    # Preload images — tiles_rect is the centre crop of tiles_pad so both
    # use identical scale factors; pixels match exactly at the boundary.
    tiles_rect=[]; tiles_pad=[]
    for idx in range(n):
        img=ImageOps.exif_transpose(Image.open(sel[idx]))
        if gf[idx]: img=img.convert("L").convert("RGB")
        pad=crop_to(img,PW,PH)
        # Derive rect by cropping the centre of the padded image
        rect=pad.crop((ext,ext,ext+tw,ext+th))
        tiles_rect.append(rect)
        tiles_pad.append(pad)

    masks={}
    tmap=np.zeros((CH,CW),dtype=np.int32)

    # Build masks + tile-ownership map (no dilation — zeros filled from rect)
    for idx in range(n):
        r,c=divmod(idx,cols)
        tf,ts=ge(r,c,'top');   rf,rs=ge(r,c,'right')
        bf,bs=ge(r,c,'bottom');lf,ls=ge(r,c,'left')
        msk=piece_mask(PW,PH,tw,th,ext,tf,ts,rf,rs,bf,bs,lf,ls)
        masks[(r,c)]=msk
        arr=np.array(msk)>127
        cx=c*tw-ext; cy=r*th-ext
        sx=max(0,-cx); sy=max(0,-cy); ddx=max(0,cx); ddy=max(0,cy)
        cw2=min(PW-sx,CW-ddx); ch2=min(PH-sy,CH-ddy)
        if cw2>0 and ch2>0:
            reg=arr[sy:sy+ch2,sx:sx+cw2]
            tmap[ddy:ddy+ch2,ddx:ddx+cw2]=np.where(
                reg, idx+1, tmap[ddy:ddy+ch2,ddx:ddx+cw2])

    # Fill any remaining zeros from rectangle ownership
    for idx in range(n):
        r,c=divmod(idx,cols)
        roi=tmap[r*th:(r+1)*th, c*tw:(c+1)*tw]
        tmap[r*th:(r+1)*th, c*tw:(c+1)*tw]=np.where(roi==0, idx+1, roi)

    # Single-pixel boundary from tmap
    h=np.zeros((CH,CW),np.uint8)
    v=np.zeros((CH,CW),np.uint8)
    h[:-1,:]=np.where(tmap[:-1,:]!=tmap[1:,:],255,0).astype(np.uint8)
    v[:,:-1]=np.where(tmap[:,:-1]!=tmap[:,1:],255,0).astype(np.uint8)
    boundary=np.clip(h.astype(int)+v.astype(int),0,255).astype(np.uint8)

    canvas=Image.new("RGBA",(CW,CH),bg+(255,))

    # Pass 1: full rectangles
    for idx in range(n):
        r,c=divmod(idx,cols)
        canvas.alpha_composite(tiles_rect[idx].convert("RGBA"),dest=(c*tw,r*th))

    # Pass 2: shaped pieces
    for idx in range(n):
        r,c=divmod(idx,cols)
        msk=masks[(r,c)]
        pad=tiles_pad[idx].convert("RGBA"); pad.putalpha(msk)
        cx=c*tw-ext; cy=r*th-ext
        sx=max(0,-cx); sy=max(0,-cy); ddx=max(0,cx); ddy=max(0,cy)
        cw2=min(PW-sx,CW-ddx); ch2=min(PH-sy,CH-ddy)
        if cw2>0 and ch2>0:
            canvas.alpha_composite(pad.crop((sx,sy,sx+cw2,sy+ch2)),dest=(ddx,ddy))

    # Pass 3: single-pixel cut lines from tmap boundary
    line_rgba=Image.new("RGBA",(CW,CH),(0,0,0,0))
    line_rgba.putalpha(Image.fromarray(boundary))
    canvas.alpha_composite(line_rgba)

    out=Image.new("RGB",(CW,CH),bg)
    out.paste(canvas,mask=canvas.split()[3])
    Path(output_path).parent.mkdir(parents=True,exist_ok=True)
    out.save(output_path,quality=95)
    print(f"[OK] {cols}x{rows} → {Path(output_path).resolve()}")
    print(f"     {n} tiles | {ng} desaturated | {n-ng} colour")

# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--input","-i",required=True)
    ap.add_argument("--output","-o",default="patchwork.jpg")
    ap.add_argument("--cols",type=int,default=6)
    ap.add_argument("--rows",type=int,default=5)
    ap.add_argument("--tile",type=int,default=180)
    ap.add_argument("--gray-ratio",type=float,default=0.0)
    ap.add_argument("--seed",type=int,default=None)
    ap.add_argument("--bg",default="121212")
    a=ap.parse_args()
    bg=tuple(int(a.bg[i:i+2],16) for i in (0,2,4))
    build(a.input,a.output,a.cols,a.rows,a.tile,a.gray_ratio,a.seed,bg)

if __name__=="__main__":
    main()