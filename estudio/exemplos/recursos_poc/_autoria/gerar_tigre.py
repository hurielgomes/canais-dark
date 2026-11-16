"""
FERRAMENTA DE AUTORIA (nao faz parte do motor): escreve tigre.json. Simula o que uma IA/ilustrador entregaria.
O motor so le o JSON gerado; nao existe nenhum codigo do tigre dentro do motor.
"""
import json, math, sys

PELO, PELO_ESC, PELO_CLARO = "#ee8f33", "#c9701f", "#f7a64a"
LISTRA, BARRIGA, ROSA, OLHO = "#2b1a14", "#f6ead2", "#d9808a", "#f2b630"
FAR = "#b5611b"; FAR_L = "#9c5316"

def poly(pts, fill, **kw): return dict(t="poly", pts=[[round(x,1),round(y,1)] for x,y in pts], fill=fill, **kw)
def ell(cx,cy,rx,ry,fill,**kw): return dict(t="ellipse", cx=cx, cy=cy, rx=rx, ry=ry, fill=fill, **kw)
def path(d, fill=None, **kw): return dict(t="path", d=d, fill=fill, **kw)

def seg(x0,y0,x1,y1,w0,w1,fill):
    dx,dy=x1-x0,y1-y0; L=math.hypot(dx,dy); nx,ny=-dy/L,dx/L
    q=[(x0+nx*w0/2,y0+ny*w0/2),(x1+nx*w1/2,y1+ny*w1/2),(x1-nx*w1/2,y1-ny*w1/2),(x0-nx*w0/2,y0-ny*w0/2)]
    return [poly(q,fill), ell(x0,y0,w0/2,w0/2,fill), ell(x1,y1,w1/2,w1/2,fill)]

def bez(p0,p1,p2,p3,n):
    out=[]
    for k in range(n+1):
        t=k/n;u=1-t
        out.append((u**3*p0[0]+3*u*u*t*p1[0]+3*u*t*t*p2[0]+t**3*p3[0], u**3*p0[1]+3*u*u*t*p1[1]+3*u*t*t*p2[1]+t**3*p3[1]))
    return out

partes=[]
def parte(id, pai, pivo, z, formas, variantes=None, var_padrao=None):
    p=dict(id=id, pivo=pivo, z=z, formas=formas)
    if pai: p["pai"]=pai
    if variantes: p["variantes"]=variantes
    if var_padrao: p["var_padrao"]=var_padrao
    partes.append(p)

# ------------------------------------------------------------------ corpo
CORPO="M 196 300 C 205 252 300 236 400 238 C 500 238 600 232 692 258 C 742 276 765 330 750 378 C 738 410 700 424 650 421 C 560 416 470 424 390 421 C 320 419 250 424 214 398 C 184 374 186 332 196 300 Z"
stripes=[]
import random; rnd=random.Random(5)
x=232
while x<700:
    w=rnd.uniform(13,19); yb=rnd.uniform(325,392); tilt=rnd.uniform(-10,14); top=232
    d=f"M {x:.0f} {top} L {x+w:.0f} {top} Q {x+w*0.9+tilt*0.5:.0f} {(top+yb)/2:.0f} {x+w*0.3+tilt:.0f} {yb:.0f} Q {x-2+tilt*0.2:.0f} {(top+yb)/2+10:.0f} {x:.0f} {top} Z"
    stripes.append(d); 
    if rnd.random()<0.55:      # listra curta intermediaria
        x2=x+w+9; yb2=rnd.uniform(290,340)
        stripes.append(f"M {x2:.0f} {top} L {x2+9:.0f} {top} Q {x2+8+tilt*0.3:.0f} {(top+yb2)/2:.0f} {x2+3+tilt*0.5:.0f} {yb2:.0f} Q {x2-1:.0f} {(top+yb2)/2:.0f} {x2:.0f} {top} Z")
    x+=rnd.uniform(36,46)
formas=[path(CORPO,{"g":[[0,PELO_CLARO],[0.55,PELO],[1,PELO_ESC]],"dir":"v"}),
        path("M 200 392 C 300 372 440 392 560 388 C 650 386 720 380 760 372 L 760 440 L 190 440 Z",BARRIGA,clip="base"),
        ell(276,350,92,84,"#d4731c",op=0.35,clip="base"), ell(652,352,74,90,"#d4731c",op=0.30,clip="base"),
        path(" ".join(stripes),LISTRA,clip="base"),
        path("M 200 330 C 215 300 240 290 262 300 C 240 318 222 336 214 358 Z",LISTRA,clip="base",op=0.0)]
parte("corpo",None,[480,330],0,formas)

# ------------------------------------------------------------------ pernas
def perna(prefix, longe, sx, sy, ex, ey, wx, wy, px, py, esp0, esp1, esp2, esp3, z, pai_c):
    cor, cor2 = (FAR,FAR_L) if longe else (PELO,PELO_ESC)
    f_sup=seg(sx,sy,ex,ey,esp0,esp1,cor)
    # listras curtas
    f_sup.append(path(f"M {sx-esp0/2:.0f} {sy+28:.0f} L {sx+esp0/2:.0f} {sy+22:.0f} L {sx+esp0/2:.0f} {sy+34:.0f} L {sx-esp0/2:.0f} {sy+40:.0f} Z", LISTRA, op=0.9 if not longe else 0.6))
    parte(prefix+"_sup", pai_c, [sx,sy], z, f_sup)
    f_inf=seg(ex,ey,wx,wy,esp1,esp2,cor)
    f_inf.append(path(f"M {ex-esp1/2:.0f} {ey+30:.0f} L {ex+esp1/2:.0f} {ey+24:.0f} L {ex+esp1/2:.0f} {ey+34:.0f} L {ex-esp1/2:.0f} {ey+40:.0f} Z", LISTRA, op=0.9 if not longe else 0.6))
    parte(prefix+"_inf", prefix+"_sup", [ex,ey], z+0.01, f_inf)
    pata=[ell(px,py,esp3*0.62,esp3*0.42,BARRIGA if not longe else "#cdb89a"), ell(px+esp3*0.1,py+4,esp3*0.5,esp3*0.28,"#e9d8b8" if not longe else "#b9a583")]
    for k in (-1,0,1): pata.append(dict(t="line",pts=[[px+esp3*0.22+k*esp3*0.17,py+esp3*0.12],[px+esp3*0.28+k*esp3*0.17,py+esp3*0.34]],stroke="#9a7a55",sw=2,cap=True))
    parte(prefix+"_pata", prefix+"_inf", [wx,wy], z+0.02, pata)

GROUND=612
# frente (ombro 660,345)
perna("pfl", True, 628,348, 626,456, 630,566, 640,590, 92,62,48,72, -3.0, "corpo")
perna("pfn", False,662,348, 664,456, 668,566, 678,590, 98,66,52,76, 3.0, "corpo")
# traseira (quadril 278,345)
perna("ptl", True, 305,352, 335,452, 300,548, 306,596, 100,64,46,72, -3.2, "corpo")
perna("ptn", False,272,348, 308,452, 268,548, 278,596, 108,68,48,76, 2.5, "corpo")

# ------------------------------------------------------------------ cauda (3 segmentos encadeados)
pts=bez((205,305),(118,330),(52,236),(104,140),24)
segs=[pts[0:9],pts[8:17],pts[16:25]]
larg=[36,31,27]
for i,sp in enumerate(segs):
    fs=[dict(t="line",pts=[[round(x,1),round(y,1)] for x,y in sp],stroke=PELO if i<2 else PELO,sw=larg[i],cap=True)]
    # bandas escuras
    for a in ((2,3),(5,6)) if i<2 else ((1,2),(4,5),(6,8)):
        sub=sp[a[0]:a[1]+1]
        if len(sub)>=2: fs.append(dict(t="line",pts=[[round(x,1),round(y,1)] for x,y in sub],stroke=LISTRA,sw=larg[i]+1,cap=False))
    parte(f"cauda{i+1}", "corpo" if i==0 else f"cauda{i}", [round(sp[0][0],1),round(sp[0][1],1)], -1.0+i*0.01, fs)

# ------------------------------------------------------------------ cabeca
HEAD="M 728 238 C 735 198 790 178 835 190 C 868 198 890 222 905 250 C 915 270 918 292 906 308 C 896 322 872 326 850 322 C 835 335 805 346 775 340 C 745 334 722 290 728 238 Z"
cab=[path(HEAD,{"g":[[0,PELO_CLARO],[1,PELO]],"dir":"v"}),
     ell(852,314,62,26,BARRIGA,clip="base"),
     ell(886,296,34,22,BARRIGA,clip="base"),
     path("M 770 196 L 782 196 Q 786 220 780 240 Q 772 222 770 196 Z M 800 190 L 812 192 Q 814 214 808 232 Q 800 214 800 190 Z M 830 194 L 840 198 Q 840 214 836 226 Q 828 212 830 194 Z",LISTRA,clip="base"),
     path("M 742 262 Q 770 268 790 284 L 790 292 Q 766 284 742 274 Z M 746 296 Q 772 296 796 306 L 796 313 Q 770 308 748 306 Z",LISTRA,clip="base"),
     path("M 890 232 Q 868 222 846 228 L 848 235 Q 868 230 886 240 Z",LISTRA,clip="base",op=0.85),
     poly([(900,267),(918,268),(918,278),(908,284),(900,278)],ROSA,stroke="#8a4a50",sw=2),
     dict(t="line",pts=[[908,284],[907,300],[896,312],[870,318],[846,318]],stroke="#3a1c18",sw=3),
     dict(t="line",pts=[[890,298],[944,286]],stroke="#ffffff",sw=1.6,op=0.8),
     dict(t="line",pts=[[890,303],[948,304]],stroke="#ffffff",sw=1.6,op=0.8),
     dict(t="line",pts=[[888,308],[942,324]],stroke="#ffffff",sw=1.6,op=0.8)]
parte("cabeca","corpo",[742,296],4.0,cab)
parte("boca_dentro","cabeca",[800,318],3.8,[path("M 800 318 C 835 322 880 316 906 306 C 900 340 850 352 810 342 Z","#6a1d24")])
parte("mandibula","cabeca",[800,318],4.1,[path("M 796 318 C 830 328 880 322 906 306 C 903 326 880 342 850 346 C 822 349 798 342 788 330 Z",{"g":[[0,BARRIGA],[1,"#e6d3b0"]],"dir":"v"}),
     poly([(872,318),(878,332),(884,316)],"#ffffff"), dict(t="line",pts=[[800,330],[850,338],[890,328]],stroke="#b99a70",sw=2,op=0.6)])
parte("orelha_f","cabeca",[758,214],3.5,[path("M 740 226 C 730 190 752 168 780 178 C 786 196 782 212 772 226 Z",PELO_ESC),path("M 748 220 C 744 198 758 184 772 190 C 774 202 770 212 764 220 Z","#8a5a4a")])
parte("orelha_n","cabeca",[800,218],4.4,[path("M 772 218 C 764 178 794 158 826 176 C 836 192 832 208 824 222 Z",{"g":[[0,PELO_CLARO],[1,PELO]],"dir":"v"},stroke=LISTRA,sw=2),
                                    path("M 782 210 C 780 190 798 178 814 188 C 820 198 816 208 810 214 Z","#f1c9b2"),
                                    path("M 776 216 C 770 190 790 168 812 174 C 790 178 782 196 786 216 Z",LISTRA,op=0.5)])
olho_aberto=[path("M 832 246 C 842 236 862 236 872 246 C 862 254 842 255 832 246 Z","#fff6d8",stroke=LISTRA,sw=2.2),
             ell(853,245,8.5,8.5,OLHO), ell(853,245,3.2,7.5,"#140a08"), ell(850,241,2.2,2.2,"#ffffff")]
olho_fechado=[dict(t="line",pts=[[832,247],[843,251],[855,252],[872,247]],stroke=LISTRA,sw=3.4)]
parte("olho","cabeca",[852,246],5.0,[],{"aberto":olho_aberto,"fechado":olho_fechado},"aberto")

# ------------------------------------------------------------------ animacoes
def loopkeys(fn, n=12):
    return [[round(i/n,4), round(fn(i/n),2)] for i in range(n+1)]

def stance_swing(phi, A):
    """-A (frente) -> +A (tras) na fase de apoio (0..0.6); +A -> -A no balanco"""
    phi%=1.0
    if phi<0.6: return -A+2*A*(phi/0.6)
    u=(phi-0.6)/0.4; u=u*u*(3-2*u)
    return A-2*A*u

def lift(phi, B):
    phi%=1.0
    if phi<0.6: return -2
    u=(phi-0.6)/0.4
    return B*math.sin(math.pi*u)**1.2

faixas={}
offs={"pfn":0.25,"pfl":0.75,"ptn":0.0,"ptl":0.5}
for nome,off in offs.items():
    front=nome.startswith("pf")
    A=24 if front else 22
    up=lambda t,off=off,A=A: stance_swing(t-off,A)
    lo=lambda t,off=off,front=front: (lift(t-off,48) if front else -lift(t-off,46)*0.0 + lift(t-off,52))
    pa=lambda t,off=off,front=front: -(stance_swing(t-off,A)*0.55) - (lift(t-off,48 if front else 52))*0.45
    faixas[nome+"_sup"]={"rot":loopkeys(up)}
    faixas[nome+"_inf"]={"rot":loopkeys(lo)}
    faixas[nome+"_pata"]={"rot":loopkeys(pa)}
faixas["corpo"]={"ty":loopkeys(lambda t:-6*math.sin(4*math.pi*t+0.6)),"rot":loopkeys(lambda t:1.4*math.sin(2*math.pi*t+0.3))}
faixas["cabeca"]={"rot":loopkeys(lambda t:-1.5*math.sin(2*math.pi*t+0.3)+1.2*math.sin(4*math.pi*t)),"ty":loopkeys(lambda t:2*math.sin(4*math.pi*t+0.3))}
for i in range(3):
    faixas[f"cauda{i+1}"]={"rot":loopkeys(lambda t,i=i:(7+4*i)*math.sin(2*math.pi*t-0.7*i+1.0))}
faixas["olho"]={"var":[[0,"aberto"],[0.84,"fechado"],[0.92,"aberto"],[1,"aberto"]]}
faixas["orelha_n"]={"rot":[[0,0],[0.3,0],[0.36,-7],[0.42,0],[1,0]]}
caminhar={"dur":1.0,"loop":True,"faixas":faixas}

parado={"dur":4.0,"loop":True,"faixas":{
  "corpo":{"sy":[[0,1],[2,1.012],[4,1]]},
  "cabeca":{"rot":[[0,0],[1.4,-2.5],[2.8,1.5],[4,0]]},
  "cauda1":{"rot":[[0,0],[2,6],[4,0]]},"cauda2":{"rot":[[0,0],[2,9],[4,0]]},"cauda3":{"rot":[[0,0],[2,13],[4,0]]},
  "olho":{"var":[[0,"aberto"],[2.6,"fechado"],[2.74,"aberto"],[4,"aberto"]]},
  "orelha_n":{"rot":[[0,0],[1.7,0],[1.78,-8],[1.86,0],[4,0]]}}}
rugir={"dur":1.4,"loop":False,"faixas":{
  "cabeca":{"rot":[[0,0],[0.25,-9],[1.0,-9],[1.4,0]],"ty":[[0,0],[0.25,-6],[1.0,-6],[1.4,0]]},
  "mandibula":{"rot":[[0,0],[0.25,24],[0.9,22],[1.4,0]]},
  "olho":{"var":[[0,"aberto"],[0.2,"fechado"],[1.1,"fechado"],[1.25,"aberto"]]},
  "corpo":{"sy":[[0,1],[0.25,1.03],[1.0,1.03],[1.4,1]]}}}

rec=dict(formato="m1-recurso/1", id="tigre", tipo="personagem", nome="Tigre-de-bengala", tags=["animal","felino","extincao"],
  caixa=[40,90,960,640], base=[480,GROUND], frente="direita", passo=330,
  sombra=dict(rx=330,ry=20,y=GROUND,x=480,a=0.55),
  ancoras={"focinho":[918,278],"olho":[853,245]},
  aliases={"correr":"caminhar","andar":"caminhar"},
  pose_base={"cabeca":{"sx":1.24,"sy":1.24}}, partes=partes, animacoes=dict(parado=parado, caminhar=caminhar, rugir=rugir))
json.dump(rec, open(sys.argv[1] if len(sys.argv)>1 else "tigre.json","w",encoding="utf-8"), ensure_ascii=False, separators=(",",":"))
print("ok", len(json.dumps(rec))//1024, "KB", len(partes), "partes")
