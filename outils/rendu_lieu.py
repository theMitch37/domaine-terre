"""Rendu en perspective (façon Minecraft) d'un lieu unique, pour juger sa forme AVANT de tester en jeu.

Contient une copie Python de la géométrie du Grand Canyon (GrandCanyon.java) : à garder synchronisée.
Approximation : le bruit n'est pas exactement celui du jeu, pas de végétation, de grottes ni d'éclairage.
Vue depuis le sud, en hauteur.

Usage : python3 outils/rendu_lieu.py <x0> <x1> <z0> <z1> <sortie.png> [pixels_par_bloc]
        (coordonnées de blocs en 1:250 ; ex. Grand Canyon Village : -49950 -49600 -16330 -16030)
"""
import sys, os
import numpy as np
from PIL import Image
from scipy import ndimage
os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import gzip, struct
raw=gzip.open('lieux/src/main/resources/domaine_terre_lieux/grand_canyon.bin').read()
lon0,lat0,pl,pa,W,H=struct.unpack('<4d2i',raw[:40]); n=W*H
G=[np.frombuffer(raw[40+2*n*i:40+2*n*(i+1)],'<i2').reshape(H,W).astype(float) for i in range(4)]
E,P,R,D=G
BPD=445.28; FOND=56; PIED=62.5
EP=[90,70,100,100,70,70,70,70,150,120,100,60]; FA=[1,0,1,0,1,0,1,0,1,1,0,1]; SOM=sum(EP)
def blocs(a):
    if a<=500: return 64+a/500*16
    if a<=2000: return 80+(a-500)/1500*60
    return 140+min((a-2000)/6800,1)*160
def ep(i,span):
    vis=min(max(span-SOM,0),300)
    return vis if i==12 else EP[i]*max(1,(span-vis)/SOM)
def sculpte(dm,span,net):
    if not net: return dm
    out=a=0
    for i in range(13):
        e=ep(i,span)
        if e<=0: continue
        u=min(max((dm-a)/e,0),1); f= i==12 or FA[i]
        out+=e*(min(max((u-.5)*8+.5,0),1) if f else u); a+=e
    return out
def v(g,x,y): return g[min(max(y,0),H-1),min(max(x,0),W-1)]
def ech(g,lon,lat):
    fx=(lon-lon0)/pl-.5; fy=(lat0-lat)/pa-.5; ix=int(np.floor(fx)); iy=int(np.floor(fy)); tx=fx-ix; ty=fy-iy
    a=v(g,ix,iy)+(v(g,ix+1,iy)-v(g,ix,iy))*tx; b=v(g,ix,iy+1)+(v(g,ix+1,iy+1)-v(g,ix,iy+1))*tx
    return a+(b-a)*ty
def lisse(t): t=min(max(t,0),1); return t*t*(3-2*t)
def calc(x,z,net):
    lon=x/BPD; lat=-z/BPD
    e=ech(E,lon,lat);p=ech(P,lon,lat);r=ech(R,lon,lat);dist=ech(D,lon,lat)*100
    can=lisse((p-e-15)/60)*lisse((lon+114.10)/0.12)*(1-lisse((lon+111.62)/0.08))*(1-lisse((dist-32000)/10000))
    span=max(p-r,1); base=blocs(e); reb=blocs(p)
    paroi=reb-min(sculpte(p-e,span,net)/span,1)*(reb-PIED)
    y=base+(paroi-base)*can
    lit=max(1-lisse((dist-350)/250),1-lisse((e-r-6)/20))
    y=y+(FOND-y)*lit
    return y,can,e,p,r



rng=np.random.default_rng(3)
def bruit(X,Z,ech,graine):
    r=np.random.default_rng(graine); g=r.standard_normal((64,64))
    g=ndimage.gaussian_filter(g,1.0,mode='wrap'); g/=g.std()
    return ndimage.map_coordinates(g,[(Z/ech)%64,(X/ech)%64],order=3,mode='grid-wrap')*0.5
# profil : (t, fraction de profondeur sous le rebord) du rebord (t=1) au fleuve (t=0)
TH=[90,70,100,100,70,70,70,70,150,120,100,60,300]; TOT=sum(TH); cum=np.cumsum([0]+TH)/TOT
PROF=[(1.00,cum[0]),(0.97,cum[1]),(0.90,cum[2]),(0.87,cum[3]),(0.76,cum[4]),(0.74,cum[5]),(0.66,cum[6]),(0.64,cum[7]),
      (0.56,cum[8]),(0.52,cum[9]),(0.50,cum[10]),(0.22,cum[11]),(0.20,cum[12]),(0.05,1.0),(0.0,1.0)]
PT=np.array([p[0] for p in PROF][::-1]); PG=np.array([p[1] for p in PROF][::-1])
def profil(t): return np.interp(t,PT,PG)
W0=75.0
E3=ndimage.gaussian_filter(E,6)
def modele_proc(X,Z):
    lon=X/BPD; lat=-Z/BPD
    fx=(lon-lon0)/pl-.5; fy=(lat0-lat)/pa-.5
    s=lambda g: ndimage.map_coordinates(g,[fy,fx],order=1,mode='nearest')
    e=s(E);p=s(P);r=s(R);dist=s(D)*100
    db=dist*BPD/111320.0
    lis=lambda t: (lambda u: u*u*(3-2*u))(np.clip(t,0,1))
    inten=lis((lon+114.10)/0.25)*(1-lis((lon+111.62+0.25)/0.25))
    w=W0*np.maximum(inten,0.06)
    pl_=np.minimum(6.0,w*0.3)
    d=db+bruit(X,Z,W0*0.9,1)*w*0.35+bruit(X,Z,23,2)*w*0.07
    d=np.where(db<pl_,db,np.maximum(d,pl_))
    t=d/w
    g=profil(np.clip(t,0,1))
    b=bruit(X,Z,W0*0.45,7)
    temple=(t>0.28)&(t<0.92)&(b>0.25)
    sb=np.clip((b-0.25)/0.15,0,1)
    gt=cum[3]+(1-sb)*(g-cum[3])
    gt=cum[np.clip(np.searchsorted(cum,gt),0,13)]
    g=np.where(temple,np.minimum(g,gt),g)
    reb=np.vectorize(blocs)(p); base=np.vectorize(blocs)(e)
    # le terrain du mod (h) est approché par le relief réel ; le canyon ne fait que creuser dedans
    # (le mod lit une carte à 3' : relief réel lissé ~6 points de 15")
    h=np.vectorize(blocs)(s(E3))+bruit(X,Z,48,11)*3
    y=np.where(t<=1,np.minimum(h,reb-g*(reb-PIED)),h)
    lit=np.maximum(1-lis((db-2.5)/1.5),1-lis((e-r-6)/20))
    y=y+(FOND-y)*lit
    canyon=(t<1.1)
    return y,canyon,reb,g
def rendu(Y, COL, out, K=3, VY=1.0, ZY=0.55, base=40):
    H,W=Y.shape; top=Y.max()
    hpx=int((H*ZY+(top-base)*VY)*K)+K*4
    img=np.full((hpx,W*K,3),(165,200,235),np.uint8)
    for j in range(H):
        for i in range(W):
            y=Y[j,i]
            s0=int((j*ZY+(top-y)*VY)*K); s1=int((j*ZY+(top-base)*VY)*K)
            c=np.array(COL[j,i],float)
            img[s0+K:s1, i*K:(i+1)*K]=(c*0.68).astype(np.uint8)   # face avant (ombre)
            img[s0:s0+K, i*K:(i+1)*K]=c.astype(np.uint8)          # dessus
    Image.fromarray(img).save(out)

COULEURS = [(209,178,161),(152,94,67),(216,203,155),(143,61,46),(161,83,37),(143,61,46),(161,83,37),(143,61,46),
            (152,94,67),(135,107,98),(135,107,98),(77,51,35),(80,80,85)]   # mêmes couches que StratesFeature

if __name__ == "__main__":
    x0, x1, z0, z1 = map(int, sys.argv[1:5]); out = sys.argv[5]; K = int(sys.argv[6]) if len(sys.argv) > 6 else 2
    X, Z = np.meshgrid(np.arange(x0, x1), np.arange(z0, z1))
    y, can, reb, g = modele_proc(X.astype(float), Z.astype(float)); Y = np.floor(y)
    gg = np.clip((reb - Y) / (reb - 62.5), 0, 1); k = np.clip(np.searchsorted(cum, gg, side="right") - 1, 0, 12)
    C = np.array(COULEURS)[k].astype(float)
    C = np.where((can & ((reb - Y) > 2))[..., None], C, np.array([100, 140, 60.]))
    C[Y < 62] = (60, 110, 160)
    rendu(Y, C, out, K=K)
    print("écrit", out)
