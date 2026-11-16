"""FERRAMENTA DE AUTORIA (nao faz parte do motor): escreve homem.json (personagem humano de perfil) e sofa.json.
A animacao 'levantar' e baked por cinematica inversa (pes plantados) so aqui; o motor apenas le keyframes."""
import json, math, sys
PELE,CAB,CAMISA,CALCA,SAPATO,SOLA="#e3b08a","#3a2a22","#3f78b8","#2f3b52","#f1f1f1","#25252b"
def shade(h,k):
    h=h.lstrip('#'); r,g,b=[int(h[i:i+2],16) for i in (0,2,4)]
    return "#%02x%02x%02x"%(int(r*k),int(g*k),int(b*k))
def poly(p,f,**k): return dict(t="poly",pts=[[round(x,1),round(y,1)] for x,y in p],fill=f,**k)
def ell(cx,cy,rx,ry,f,**k): return dict(t="ellipse",cx=cx,cy=cy,rx=rx,ry=ry,fill=f,**k)
def path(d,f=None,**k): return dict(t="path",d=d,fill=f,**k)
def seg(x0,y0,x1,y1,w0,w1,f):
    dx,dy=x1-x0,y1-y0;L=math.hypot(dx,dy);nx,ny=-dy/L,dx/L
    return [poly([(x0+nx*w0/2,y0+ny*w0/2),(x1+nx*w1/2,y1+ny*w1/2),(x1-nx*w1/2,y1-ny*w1/2),(x0-nx*w0/2,y0-ny*w0/2)],f),ell(x0,y0,w0/2,w0/2,f),ell(x1,y1,w1/2,w1/2,f)]
partes=[]
def parte(id,pai,pivo,z,formas,var=None,vp=None):
    p=dict(id=id,pivo=pivo,z=z,formas=formas)
    if pai:p["pai"]=pai
    if var:p["variantes"]=var
    if vp:p["var_padrao"]=vp
    partes.append(p)
HIP=(230,425);KNEE=(232,545);ANK=(230,655);SH=(232,290);EL=(236,375);WR=(240,452);L1=120;L2=110
parte("pelve",None,list(HIP),0,[path("M 198 410 C 200 395 262 395 264 412 L 266 462 C 250 474 214 474 196 462 Z",CALCA)])
parte("torso","pelve",list(HIP),1,[path("M 204 432 C 196 380 198 322 210 290 C 214 272 226 262 240 262 C 262 266 270 296 268 340 C 266 384 262 410 258 434 Z",{"g":[[0,shade(CAMISA,1.12)],[1,CAMISA]],"dir":"v"}),
   path("M 222 262 C 232 276 248 276 258 262 C 250 256 232 256 222 262 Z",shade(CAMISA,0.8)),
   dict(t="line",pts=[[232,300],[235,420]],stroke=shade(CAMISA,0.8),sw=2,op=0.5)])
parte("cabeca","torso",[236,262],3,[
   dict(t="rect",x=226,y=248,w=24,h=28,r=8,fill=shade(PELE,0.92)),
   ell(242,222,40,44,PELE), ell(226,230,10,14,shade(PELE,0.92)),
   path("M 202 218 C 198 180 226 168 252 172 C 276 176 286 196 280 214 C 268 196 244 192 226 206 C 214 212 208 224 206 238 C 202 232 202 224 202 218 Z",CAB),
   path("M 276 226 C 286 230 288 240 280 244 Z",shade(PELE,0.95)),
   dict(t="line",pts=[[262,262],[274,264]],stroke="#8a4a40",sw=2.4),
   dict(t="line",pts=[[258,210],[276,208]],stroke=CAB,sw=3.4)],
   {"aberto":[ell(266,222,3.6,4.4,"#1a1a22")],"fechado":[dict(t="line",pts=[[261,223],[271,223]],stroke="#1a1a22",sw=2.6)]},"aberto")
def braco(pref,longe,z):
    k=0.72 if longe else 1.0
    cam,pe=shade(CAMISA,k),shade(PELE,k)
    parte(pref+"_sup","torso",list(SH),z,seg(SH[0],SH[1],EL[0],EL[1],38,32,cam))
    parte(pref+"_inf",pref+"_sup",list(EL),z+0.01,seg(EL[0],EL[1],WR[0],WR[1],30,24,pe))
    var={"controle":[path("M 238 456 L 276 446 L 280 458 L 242 470 Z","#222831",stroke="#000",sw=1),ell(262,455,3.2,3.2,"#ff4a4a")]} if not longe else None
    parte(pref+"_mao",pref+"_inf",list(WR),z+0.02,[ell(WR[0]+2,WR[1]+12,15,17,pe)],var)
braco("bf",True,-2); braco("bn",False,4)
def perna(pref,longe,dx,z):
    k=0.72 if longe else 1.0
    cal,sap=shade(CALCA,k),shade(SAPATO,k)
    parte("c"+pref,"pelve",[HIP[0]+dx,HIP[1]],z,seg(HIP[0]+dx,HIP[1],KNEE[0]+dx,KNEE[1],64,52,cal))
    parte("s"+pref,"c"+pref,[KNEE[0]+dx,KNEE[1]],z+0.01,seg(KNEE[0]+dx,KNEE[1],ANK[0]+dx,ANK[1],50,38,cal))
    parte("p"+pref,"s"+pref,[ANK[0]+dx,ANK[1]],z+0.02,[path(f"M {ANK[0]+dx-22} {ANK[1]-8} L {ANK[0]+dx+18} {ANK[1]-12} C {ANK[0]+dx+50} {ANK[1]-6} {ANK[0]+dx+66} {ANK[1]+16} {ANK[0]+dx+66} {ANK[1]+36} L {ANK[0]+dx-26} {ANK[1]+36} C {ANK[0]+dx-30} {ANK[1]+10} {ANK[0]+dx-28} {ANK[1]} {ANK[0]+dx-22} {ANK[1]-8} Z",sap),
        poly([(ANK[0]+dx-26,ANK[1]+32),(ANK[0]+dx+66,ANK[1]+32),(ANK[0]+dx+66,ANK[1]+45),(ANK[0]+dx-26,ANK[1]+45)],SOLA)])
perna("f",True,14,-3); perna("n",False,0,2)
# ---------- cinematica
def ik(H,A,front=True):
    dx,dy=A[0]-H[0],A[1]-H[1];D=min(math.hypot(dx,dy),L1+L2-1e-6)
    th=math.atan2(-dx,dy)
    c=max(-1,min(1,(L1*L1+D*D-L2*L2)/(2*L1*D)))
    a1=th-math.acos(c)
    K=(H[0]-L1*math.sin(a1),H[1]+L1*math.cos(a1))
    ab=math.atan2(-(A[0]-K[0]),A[1]-K[1])
    return math.degrees(a1),math.degrees(ab-a1)
def sm(u): u=max(0,min(1,u)); return u*u*(3-2*u)
def pose_sentado():
    H=(150,535)
    f={"pelve":{"tx":H[0]-HIP[0],"ty":H[1]-HIP[1]},"torso":{"rot":-6},"cabeca":{"rot":5}}
    for pref,dx in (("n",0),("f",14)):
        a1,a2=ik((HIP[0]+H[0]-HIP[0]+dx*0,H[1]),(ANK[0]+dx-0,ANK[1])) if False else ik((H[0]+dx*0,H[1]),(ANK[0]+dx,ANK[1]))
        f["c"+pref]={"rot":a1};f["s"+pref]={"rot":a2};f["p"+pref]={"rot":-(a1+a2)}
    f["bn_sup"]={"rot":-12};f["bn_inf"]={"rot":-62};f["bf_sup"]={"rot":-12};f["bf_inf"]={"rot":-66}
    return f
SENT=pose_sentado()
def pose_t(t,dur=2.0):
    H0,H1=(150,535),(230,425)
    sx=sm((t-0.30)/1.25); sy=sm((t-0.50)/1.20)
    H=(H0[0]+(H1[0]-H0[0])*sx**0.9,H0[1]+(H1[1]-H0[1])*sy)
    torso= -6+38*sm(t/0.55)-38*sm((t-0.55)/0.55)+ (0)*0 - 6*0 
    torso=-6+(38*sm(t/0.5))*(1-sm((t-0.65)/0.9))+6*sm((t-0.65)/0.9)*0
    torso=(-6+44*sm(t/0.5))*(1-sm((t-0.6)/1.0))
    f={"pelve":{"tx":H[0]-HIP[0],"ty":H[1]-HIP[1]},"torso":{"rot":round(torso,2)},"cabeca":{"rot":round(5*(1-sm(t/1.0))-torso*0.45,2)}}
    for pref,dx in (("n",0),("f",14)):
        a1,a2=ik(H,(ANK[0]+dx,ANK[1]))
        f["c"+pref]={"rot":round(a1,2)};f["s"+pref]={"rot":round(a2,2)};f["p"+pref]={"rot":round(-(a1+a2),2)}
    sw=math.sin(math.pi*sm((t-0.15)/1.5))
    f["bn_sup"]={"rot":round(-12-50*sw+12*sm((t-1.5)/0.5),2)};f["bn_inf"]={"rot":round(-62+28*sw+62*sm((t-1.4)/0.6),2)}
    f["bf_sup"]={"rot":round(-12-44*sw+12*sm((t-1.5)/0.5),2)};f["bf_inf"]={"rot":round(-66+30*sw+66*sm((t-1.4)/0.6),2)}
    return f
def keys_de(poses,ts,dur):
    faixas={}
    for t,p in zip(ts,poses):
        for pid,props in p.items():
            for pr,v in props.items():
                faixas.setdefault(pid,{}).setdefault(pr,[]).append([round(t,3),v])
    return faixas
N=26;ts=[2.0*i/N for i in range(N+1)]
levantar={"dur":2.0,"loop":False,"faixas":keys_de([pose_t(t) for t in ts],ts,2.0)}
levantar["faixas"]["cabeca"]=levantar["faixas"].get("cabeca",{})
sentado={"dur":4.0,"loop":True,"faixas":{**{pid:{pr:[[0,v],[4,v]] for pr,v in props.items()} for pid,props in SENT.items()},
   "torso":{"rot":[[0,-6],[2,-5.2],[4,-6]]},"cabeca":{"rot":[[0,5],[1.5,2],[3,6],[4,5]],"var":[[0,"aberto"],[3.0,"fechado"],[3.12,"aberto"],[4,"aberto"]]}}}
parado={"dur":4.0,"loop":True,"faixas":{"torso":{"rot":[[0,0],[2,0.8],[4,0]]},"cabeca":{"rot":[[0,0],[2,-1.5],[4,0]],"var":[[0,"aberto"],[2.2,"fechado"],[2.32,"aberto"],[4,"aberto"]]},
   "bn_sup":{"rot":[[0,0],[2,1.5],[4,0]]},"bf_sup":{"rot":[[0,0],[2,-1.5],[4,0]]}}}
apontar={"dur":1.8,"loop":False,"faixas":{"bn_sup":{"rot":[[0,0],[0.5,-78],[1.4,-78],[1.8,-5]]},"bn_inf":{"rot":[[0,0],[0.5,-10],[0.62,-18],[0.74,-10],[1.4,-8],[1.8,0]]},
   "bn_mao":{"rot":[[0,0],[0.5,-6],[1.4,-6],[1.8,0]],"var":[[0,"controle"],[1.8,"controle"]]},"torso":{"rot":[[0,0],[0.5,3],[1.4,3],[1.8,0]]},"cabeca":{"rot":[[0,0],[0.5,-4],[1.4,-4],[1.8,0]]}}}
rec=dict(formato="m1-recurso/1",id="homem",tipo="personagem",nome="Homem (perfil)",tags=["humano","adulto"],caixa=[120,150,380,704],base=[230,700],frente="direita",passo=0,
 sombra=dict(rx=70,ry=11,y=700,x=235,a=0.5),ancoras={"chao":[230,700]},aliases={"sentar":"sentado","em_pe":"parado","ligar_tv":"apontar"},
 partes=partes,animacoes=dict(levantar=levantar,sentado=sentado,parado=parado,apontar=apontar))
json.dump(rec,open("../homem.json","w",encoding="utf-8"),ensure_ascii=False,separators=(",",":"))
# ---------------- sofa (coordenadas proprias; ancora 'chao' = onde ficam os pes de quem senta)
SOF,SOF2="#8a4b3a","#6d3a2d"
sp=[]
def sparte(id,z,formas): sp.append(dict(id=id,pivo=[0,0],z=z,formas=formas))
sparte("braco_longe",-2,[dict(t="rect",x=40,y=470,w=190,h=150,r=26,fill=shade(SOF,0.62))])
sparte("encosto",-1,[dict(t="rect",x=36,y=360,w=96,h=270,r=34,fill={"g":[[0,SOF],[1,SOF2]],"dir":"h"}),dict(t="rect",x=50,y=380,w=14,h=220,r=7,fill="#ffffff",op=0.08)])
sparte("assento",1,[dict(t="rect",x=36,y=560,w=190,h=62,r=22,fill={"g":[[0,"#a35c48"],[1,SOF]],"dir":"v"}),dict(t="rect",x=36,y=606,w=190,h=60,r=10,fill=SOF2),
   dict(t="line",pts=[[44,563],[216,563]],stroke="#ffffff",sw=2,op=0.18)])
sparte("pes",0,[dict(t="rect",x=52,y=664,w=16,h=36,r=4,fill="#2a1a14"),dict(t="rect",x=192,y=664,w=16,h=36,r=4,fill="#2a1a14")])
sparte("almofada",2,[dict(t="rect",x=70,y=476,w=64,h=64,r=18,fill="#e8b04a"),dict(t="line",pts=[[84,490],[122,526]],stroke="#c98a2a",sw=3)])
sofa=dict(formato="m1-recurso/1",id="sofa",tipo="objeto",nome="Sofa de 2 lugares (perfil)",tags=["movel","sala"],caixa=[20,340,260,704],base=[130,700],
 sombra=dict(rx=140,ry=16,y=700,x=130,a=0.5),ancoras={"chao":[240,700],"assento":[150,563]},partes=sp,animacoes={})
json.dump(sofa,open("../sofa.json","w",encoding="utf-8"),ensure_ascii=False,separators=(",",":"))
print("ok")
