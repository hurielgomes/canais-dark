"""FERRAMENTA DE AUTORIA (nao faz parte do motor): escreve homem.json e sofa.json (IK so para gerar keyframes)."""
import json, math, sys
PELE,PELE_E="#f0c09a","#d9a581"; CAMISA,CAMISA_E="#3f78c4","#2f5a98"; CALCA,CALCA_E="#34395a","#262a45"; CABELO="#3a2a22"; TENIS="#f4f4f6"
def poly(pts,fill,**k): return dict(t="poly",pts=[[round(x,1),round(y,1)] for x,y in pts],fill=fill,**k)
def ell(cx,cy,rx,ry,fill,**k): return dict(t="ellipse",cx=cx,cy=cy,rx=rx,ry=ry,fill=fill,**k)
def path(d,fill=None,**k): return dict(t="path",d=d,fill=fill,**k)
def seg(x0,y0,x1,y1,w0,w1,fill):
    dx,dy=x1-x0,y1-y0;L=math.hypot(dx,dy);nx,ny=-dy/L,dx/L
    return [poly([(x0+nx*w0/2,y0+ny*w0/2),(x1+nx*w1/2,y1+ny*w1/2),(x1-nx*w1/2,y1-ny*w1/2),(x0-nx*w0/2,y0-ny*w0/2)],fill),ell(x0,y0,w0/2,w0/2,fill),ell(x1,y1,w1/2,w1/2,fill)]
H=(230,400); A0=(230,650); L1=L2=125; Sh=(232,268); E=(236,346); W=(240,418)
partes=[]
def parte(id,pai,pivo,z,formas,variantes=None,vp=None,op=None):
    p=dict(id=id,pivo=pivo,z=z,formas=formas)
    if pai:p["pai"]=pai
    if variantes:p["variantes"]=variantes
    if vp:p["var_padrao"]=vp
    partes.append(p)
def braco(sfx,longe,dx,z):
    pele,cam=(PELE_E,CAMISA_E) if longe else (PELE,CAMISA)
    parte(f"braco_sup_{sfx}","torso",[Sh[0]+dx,Sh[1]],z,seg(Sh[0]+dx,Sh[1],E[0]+dx,E[1],38,32,cam))
    parte(f"braco_inf_{sfx}",f"braco_sup_{sfx}",[E[0]+dx,E[1]],z+0.01,seg(E[0]+dx,E[1],W[0]+dx,W[1],30,25,pele))
    mao=[ell(W[0]+dx+2,W[1]+10,15,14,pele)]
    parte(f"mao_{sfx}",f"braco_inf_{sfx}",[W[0]+dx,W[1]],z+0.02,mao)
def perna(sfx,longe,dx,z):
    cal,pe=(CALCA_E) if longe else CALCA,None
    K=(H[0]+dx+4,H[1]+L1)
    parte(f"coxa_{sfx}","pelve",[H[0]+dx,H[1]],z,seg(H[0]+dx,H[1],K[0],K[1],58,46,cal))
    parte(f"canela_{sfx}",f"coxa_{sfx}",[K[0],K[1]],z+0.01,seg(K[0],K[1],A0[0]+dx,A0[1],44,36,cal))
    tn="#c9c9d2" if longe else TENIS
    sap=[path(f"M {A0[0]+dx-18} {A0[1]-8} L {A0[0]+dx+8} {A0[1]-14} C {A0[0]+dx+30} {A0[1]-12} {A0[0]+dx+56} {A0[1]+4} {A0[0]+dx+64} {A0[1]+22} C {A0[0]+dx+66} {A0[1]+32} {A0[0]+dx+62} {A0[1]+34} {A0[0]+dx+54} {A0[1]+34} L {A0[0]+dx-18} {A0[1]+34} Z",tn,stroke="#6b6e80",sw=2),
         dict(t="rect",x=A0[0]+dx-18,y=A0[1]+26,w=82,h=8,fill="#4a4d5c",r=3)]
    parte(f"pe_{sfx}",f"canela_{sfx}",[A0[0]+dx,A0[1]],z+0.02,sap)
# ---- pelve/torso/cabeca
parte("pelve",None,list(H),0,[path("M 198 396 C 196 372 214 366 236 366 C 262 366 270 380 266 404 C 264 428 250 436 232 436 C 210 436 198 424 198 396 Z",CALCA)])
parte("torso","pelve",list(H),1,[path("M 198 408 C 188 360 192 300 214 264 C 230 246 256 246 270 264 C 286 300 288 360 268 408 Z",{"g":[[0,"#4a86d4"],[1,CAMISA]],"dir":"v"}),
    path("M 214 264 C 230 252 256 252 270 264 C 262 274 224 274 214 264 Z","#2f5a98",op=0.6)])
parte("cabeca","torso",[236,240],2,[rect:=dict(t="rect",x=224,y=224,w=26,h=34,fill=PELE_E,r=8),
    ell(250,198,38,43,PELE),
    path("M 210 196 C 204 156 240 142 272 160 C 286 170 292 188 288 204 C 276 186 256 180 238 190 C 226 197 216 212 210 196 Z",CABELO),
    ell(238,204,7,11,PELE_E), dict(t="line",pts=[[262,182],[278,184]],stroke=CABELO,sw=3.4), ell(290,204,6,5,PELE)])
parte("olho","cabeca",[270,196],2.1,[],{"aberto":[ell(270,196,3.6,4.6,"#1a1210"),ell(271,194,1.2,1.2,"#ffffff")],"fechado":[dict(t="line",pts=[[265,197],[275,197]],stroke="#1a1210",sw=2.4)]},"aberto")
parte("boca","cabeca",[276,224],2.1,[],{"neutra":[dict(t="line",pts=[[268,223],[281,222]],stroke="#8a4a40",sw=2.6)],
    "sorriso":[path("M 267 221 Q 275 231 284 220",None,stroke="#8a4a40",sw=2.8)],"surpresa":[ell(275,225,5,6.5,"#7a2f30")]},"neutra")
braco("f",True,14,-2); perna("f",True,14,-3)
perna("n",False,0,0.5); braco("n",False,0,3)
parte("controle","mao_n",[242,430],3.5,[dict(t="rect",x=238,y=420,w=14,h=44,fill="#1d1f2a",r=4),ell(245,430,3,3,"#ff5555"),ell(245,442,3,3,"#9ab")])
# ------------------------------------------------------------------ IK (so para gerar keyframes)
def ik(hip,ankle):
    dx,dy=ankle[0]-hip[0],ankle[1]-hip[1]; d=min(math.hypot(dx,dy),L1+L2-0.5)
    alpha=math.atan2(-dx,dy); g=math.acos(max(-1,min(1,(L1*L1+d*d-L2*L2)/(2*L1*d))))
    th1=alpha-g
    K=(hip[0]-L1*math.sin(th1),hip[1]+L1*math.cos(th1))
    ths=math.atan2(-(ankle[0]-K[0]),ankle[1]-K[1])
    return math.degrees(th1),math.degrees(ths-th1)
def ss(a,b,u): 
    t=max(0,min(1,(u-a)/(b-a))); return t*t*(3-2*t)
def pose_u(u):
    hx=-100*(1-ss(0.18,0.85,u)); hy=125*(1-ss(0.30,1.0,u))
    torso=-5+ (37)*ss(0.0,0.35,u) - 32*ss(0.45,1.0,u)
    return hx,hy,torso
def keys_sit_stand(n=18,dur=1.9):
    ks=[]
    for i in range(n+1):
        u=i/n; hx,hy,tor=pose_u(u); t=round(u*dur,3)
        hip=(H[0]+hx,H[1]+hy)
        a_n=ik(hip,A0); a_f=ik(hip,(A0[0]+14,A0[1]))
        arm_sup=-38*math.sin(math.pi*ss(0.1,0.9,u))
        arm_inf=-88*(1-ss(0.15,0.95,u))+(-20)*math.sin(math.pi*ss(0.1,0.9,u))
        ks.append((t,hx,hy,tor,a_n,a_f,arm_sup,arm_inf))
    return ks
ks=keys_sit_stand()
def fx(idx,fn): return [[k[0],round(fn(k),2)] for k in ks]
lev={"pelve":{"tx":fx(0,lambda k:k[1]),"ty":fx(0,lambda k:k[2])},"torso":{"rot":fx(0,lambda k:k[3])},
  "cabeca":{"rot":fx(0,lambda k:-0.55*k[3])},
  "coxa_n":{"rot":fx(0,lambda k:k[4][0])},"canela_n":{"rot":fx(0,lambda k:k[4][1])},"pe_n":{"rot":fx(0,lambda k:-(k[4][0]+k[4][1]))},
  "coxa_f":{"rot":fx(0,lambda k:k[5][0])},"canela_f":{"rot":fx(0,lambda k:k[5][1])},"pe_f":{"rot":fx(0,lambda k:-(k[5][0]+k[5][1]))},
  "braco_sup_n":{"rot":fx(0,lambda k:k[6])},"braco_inf_n":{"rot":fx(0,lambda k:k[7])},"braco_sup_f":{"rot":fx(0,lambda k:k[6]*0.8)},"braco_inf_f":{"rot":fx(0,lambda k:k[7]*0.9)},
  "boca":{"var":[[0,"neutra"],[0.9,"surpresa"],[1.3,"neutra"]]},"olho":{"var":[[0,"aberto"],[1.0,"aberto"]]}}
levantar={"dur":1.9,"loop":False,"faixas":lev}
hx,hy,tor=pose_u(0); hip=(H[0]+hx,H[1]+hy); an=ik(hip,A0); af=ik(hip,(A0[0]+14,A0[1]))
sent_f={"pelve":{"tx":[[0,hx],[4,hx]],"ty":[[0,hy],[2,hy+2],[4,hy]]},"torso":{"rot":[[0,tor],[2,tor+1.2],[4,tor]]},"cabeca":{"rot":[[0,1],[2,-1.5],[4,1]]},
 "coxa_n":{"rot":[[0,an[0]],[4,an[0]]]},"canela_n":{"rot":[[0,an[1]],[4,an[1]]]},"pe_n":{"rot":[[0,-(an[0]+an[1])],[4,-(an[0]+an[1])]]},
 "coxa_f":{"rot":[[0,af[0]],[4,af[0]]]},"canela_f":{"rot":[[0,af[1]],[4,af[1]]]},"pe_f":{"rot":[[0,-(af[0]+af[1])],[4,-(af[0]+af[1])]]},
 "braco_sup_n":{"rot":[[0,0],[4,0]]},"braco_inf_n":{"rot":[[0,-88],[4,-88]]},"braco_sup_f":{"rot":[[0,0],[4,0]]},"braco_inf_f":{"rot":[[0,-84],[4,-84]]},
 "olho":{"var":[[0,"aberto"],[2.2,"fechado"],[2.33,"aberto"],[4,"aberto"]]},"boca":{"var":[[0,"neutra"]]}}
sentado={"dur":4.0,"loop":True,"faixas":sent_f}
parado={"dur":4.0,"loop":True,"faixas":{"pelve":{"ty":[[0,0],[2,1.5],[4,0]]},"torso":{"sy":[[0,1],[2,1.012],[4,1]],"rot":[[0,0],[2,0.8],[4,0]]},"cabeca":{"rot":[[0,0],[2,-1],[4,0]]},
  "olho":{"var":[[0,"aberto"],[2.4,"fechado"],[2.52,"aberto"],[4,"aberto"]]},"braco_sup_n":{"rot":[[0,0],[2,1.5],[4,0]]},"braco_inf_n":{"rot":[[0,0],[2,2],[4,0]]}}}
apontar={"dur":2.0,"loop":False,"faixas":{"braco_sup_n":{"rot":[[0,0],[0.5,-78],[1.6,-78],[2.0,-70]]},"braco_inf_n":{"rot":[[0,0],[0.5,-16],[1.6,-16],[2.0,-10]]},
  "mao_n":{"rot":[[0,0],[0.5,-8],[0.95,-8],[1.05,2],[1.15,-8],[2.0,-4]]},"controle":{"op":[[0,0],[0.15,1],[2,1]]},
  "braco_sup_f":{"rot":[[0,0],[0.5,6],[2,6]]},"cabeca":{"rot":[[0,0],[0.6,-4],[2,-3]]},"boca":{"var":[[0,"neutra"],[1.2,"sorriso"]]}}}
acenar={"dur":1.2,"loop":True,"faixas":{"braco_sup_n":{"rot":[[0,-150]]},"braco_inf_n":{"rot":[[0,-20],[0.3,20],[0.6,-20],[0.9,20],[1.2,-20]]},"boca":{"var":[[0,"sorriso"]]}}}
homem=dict(formato="m1-recurso/1",id="homem",tipo="personagem",nome="Homem de camisa azul",tags=["humano","adulto"],caixa=[110,130,420,700],base=[230,684],frente="direita",passo=0,
  sombra=dict(rx=110,ry=14,y=684,x=250,a=0.5),ancoras={"pelve":[H[0],H[1],"pelve"],"mao":[W[0],W[1],"mao_n"]},
  aliases={"sentar":"sentado","em_pe":"parado","stand":"levantar"},
  pose_base={"controle":{"op":0}},partes=partes,animacoes=dict(parado=parado,sentado=sentado,levantar=levantar,apontar_controle=apontar,acenar=acenar))
json.dump(homem,open("../homem.json","w",encoding="utf-8"),ensure_ascii=False,separators=(",",":"))
# ------------------------------------------------------------------ sofa (vista lateral, sem braco proximo)
CS,CS2="#8a4f5e","#6f3d4a"
sofa_partes=[dict(id="base",pivo=[260,560],z=0,formas=[
  dict(t="rect",x=270,y=604,w=24,h=80,fill="#2a1d1a",r=4),dict(t="rect",x=150,y=640,w=250,h=26,fill="#3a2a24",r=4),
  dict(t="rect",x=140,y=590,w=268,h=58,fill=CS2,r=14),
  dict(t="rect",x=148,y=380,w=104,h=240,fill={"g":[[0,"#9d5c6c"],[1,CS]],"dir":"v"},r=34),
  dict(t="rect",x=150,y=540,w=230,h=60,fill={"g":[[0,"#a8697a"],[1,CS]],"dir":"v"},r=24),
  dict(t="rect",x=160,y=555,w=210,h=8,fill="#ffffff",op=0.10,r=4),
  dict(t="rect",x=148,y=380,w=104,h=14,fill="#ffffff",op=0.12,r=7),
  dict(t="rect",x=160,y=596,w=222,h=6,fill="#000000",op=0.25,r=3),
  dict(t="rect",x=148,y=506,w=104,h=10,fill="#000000",op=0.14,r=5),
  dict(t="rect",x=134,y=430,w=40,h=190,fill=CS2,r=18),
  dict(t="rect",x=100,y=548,w=26,h=120,fill="#3a2a24",r=4)]),
  dict(id="almofada",pivo=[210,470],z=1,formas=[dict(t="rect",x=198,y=430,w=64,h=86,fill="#e7b04a",r=22),dict(t="rect",x=205,y=438,w=50,h=70,fill="#f2c568",op=0.55,r=18)])]
sofa=dict(formato="m1-recurso/1",id="sofa",tipo="objeto",nome="Sofa lateral",tags=["movel","sala"],caixa=[90,360,420,700],base=[395,684],frente="direita",
  sombra=dict(rx=190,ry=16,y=684,x=260,a=0.5),ancoras={"chao":[395,684],"assento":[260,545]},partes=sofa_partes,animacoes={})
json.dump(sofa,open("../sofa.json","w",encoding="utf-8"),ensure_ascii=False,separators=(",",":"))
print("ok",len(partes),"partes homem")
