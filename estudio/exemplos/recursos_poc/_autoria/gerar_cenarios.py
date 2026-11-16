"""FERRAMENTA DE AUTORIA (nao faz parte do motor): escreve savana.json e sala_noite.json (cenarios por camadas)."""
import json, math, random
def rect(x,y,w,h,fill,**k): return dict(t="rect",x=x,y=y,w=w,h=h,fill=fill,**k)
def ell(cx,cy,rx,ry,fill,**k): return dict(t="ellipse",cx=cx,cy=cy,rx=rx,ry=ry,fill=fill,**k)
def path(d,fill,**k): return dict(t="path",d=d,fill=fill,**k)
def glow(cx,cy,r,cor,a,exp=2.0,ry=None): return dict(t="glow",cx=cx,cy=cy,r=r,rx=r,ry=ry or r,cor=cor,a=a,exp=exp)
def silhueta(rnd,x0,x1,ybase,alt,passo,topo_var):
    pts=[]; x=x0
    d=f"M {x0} {ybase+400} L {x0} {ybase}"
    while x<x1:
        x+=passo*rnd.uniform(0.7,1.3); y=ybase-alt*rnd.uniform(0.35,1.0)*topo_var
        d+=f" Q {x-passo*0.5:.0f} {y-alt*0.15:.0f} {x:.0f} {ybase-alt*rnd.uniform(0.1,0.5):.0f}"
    d+=f" L {x1} {ybase+400} Z"; return d
# ====================================================================== SAVANA
rnd=random.Random(11); HZ=700
camadas=[
 dict(id="ceu",k=0.02,formas=[rect(-3000,-2600,9000,2600+HZ+30,{"g":[[0,"#1b1740"],[0.55,"#3a2a68"],[0.80,"#b0506c"],[0.93,"#f08a4b"],[1,"#ffd08a"]],"dir":"v"})]),
 dict(id="sol",k=0.03,formas=[glow(1500,640,900,"#ffa850",0.65,1.5,520),glow(1500,650,260,"#ffe0a0",0.8,1.6),ell(1500,652,92,92,"#fff3cf")]),
 dict(id="nuvens",k=0.05,formas=[ell(rnd.uniform(200,3000),rnd.uniform(250,560),rnd.uniform(220,420),rnd.uniform(14,26),"#ff9a82",op=rnd.uniform(0.28,0.5)) for _ in range(9)]),
 dict(id="montanhas",k=0.08,formas=[path(silhueta(rnd,-600,4200,HZ+20,170,170,1.0),"#4a2f66",op=1.0)]),
 dict(id="colinas",k=0.16,formas=[path(silhueta(rnd,-600,4200,HZ+30,70,260,1.0),"#5c2c48")]),
]
arv=[]
for i in range(8):
    x=rnd.uniform(-200,3400); h=rnd.uniform(110,190); s=rnd.uniform(0.8,1.2)
    arv+= [rect(x-4*s,HZ-h*0.7,8*s,h*0.75,"#241628"), ell(x,HZ-h*0.78,h*0.75,h*0.17,"#241628"), ell(x-h*0.35,HZ-h*0.62,h*0.4,h*0.1,"#241628")]
camadas.append(dict(id="acacias",k=0.30,formas=arv))
chao=[rect(-3000,HZ,9000,1800,{"g":[[0,"#c28b3c"],[0.15,"#a56e2e"],[1,"#5e3519"]],"dir":"v"}),
      rect(-3000,HZ,9000,26,"#ffd08a",op=0.18)]
for i in range(260):
    x=rnd.uniform(-600,3800); yy=HZ+20+(rnd.random()**1.7)*520; sc=0.5+(yy-HZ)/520*1.5
    h=rnd.uniform(22,46)*sc; n=rnd.randint(3,5)
    d=f"M {x-10*sc:.0f} {yy:.0f}"
    for j in range(n):
        bx=x-10*sc+j*(20*sc/(n-1)); d+=f" L {bx+rnd.uniform(-6,6)*sc:.0f} {yy-h*rnd.uniform(0.6,1.0):.0f} L {bx+4*sc:.0f} {yy:.0f}"
    d+=" Z"
    chao.append(path(d,rnd.choice(["#7d4b1f","#8d5a26","#6d3f1a","#b07a35"]),op=0.9))
for i in range(14):
    x=rnd.uniform(-500,3700); yy=HZ+40+(rnd.random()**1.3)*480; sc=0.6+(yy-HZ)/480*1.4
    chao.append(ell(x,yy,26*sc,11*sc,"#5a3a2a")); chao.append(ell(x-4*sc,yy-4*sc,20*sc,7*sc,"#8a6a4c",op=0.6))
camadas.append(dict(id="chao",k=1.0,formas=chao))
fg=[]
for i in range(26):
    x=rnd.uniform(-500,3600); yy=1300+rnd.uniform(0,60); h=rnd.uniform(160,300)
    for j in range(5):
        bx=x+j*22; fg.append(path(f"M {bx:.0f} {yy+120:.0f} Q {bx+rnd.uniform(-30,30):.0f} {yy-h*0.5:.0f} {bx+rnd.uniform(-50,50):.0f} {yy-h*rnd.uniform(0.7,1.0):.0f} Q {bx+10:.0f} {yy-h*0.4:.0f} {bx+16:.0f} {yy+120:.0f} Z","#1b0f12"))
camadas.append(dict(id="frente",k=1.55,desfoque=7,formas=fg))
json.dump(dict(formato="m1-recurso/1",id="savana",tipo="cenario",nome="Savana ao entardecer",tags=["natureza","savana","por-do-sol"],caixa=[0,0,3200,1400],camadas=camadas),open("../savana.json","w",encoding="utf-8"),ensure_ascii=False,separators=(",",":"))
# ====================================================================== SALA
rnd=random.Random(4); FL=640
c=[]
c.append(dict(id="parede",k=0.08,formas=[rect(-2000,-1600,6400,1600+FL,{"g":[[0,"#1a2040"],[0.7,"#2a3358"],[1,"#242c4e"]],"dir":"v"})]+
   [rect(x,-1000,6,1000+FL,"#ffffff",op=0.025) for x in range(-1000,3600,90)]))
c.append(dict(id="janela",k=0.10,formas=[rect(1700,120,330,360,"#0b1230"),rect(1700,120,330,360,{"g":[[0,"#0d1538"],[1,"#2a3a78"]],"dir":"v"}),glow(1900,200,180,"#aac4ff",0.45,1.8),ell(1930,205,24,24,"#e8efff"),
   path("M 1700 480 L 1700 400 L 1730 400 L 1730 360 L 1770 360 L 1770 410 L 1810 410 L 1810 340 L 1850 340 L 1850 400 L 1900 400 L 1900 380 L 1940 380 L 1940 420 L 2030 420 L 2030 480 Z","#0a0e22")]+
   [rect(1700+i*5,y,3,3,"#ffd070",op=0.9) for i,y in ((2,372),(6,392),(10,364),(14,354),(18,372),(22,392),(26,372),(28,400),(31,396)) ]+
   [dict(t="rect",x=1692,y=112,w=346,h=14,fill="#141a38"),dict(t="rect",x=1692,y=482,w=346,h=14,fill="#141a38"),dict(t="rect",x=1692,y=112,w=14,h=384,fill="#141a38"),dict(t="rect",x=2024,y=112,w=14,h=384,fill="#141a38"),dict(t="rect",x=1860,y=120,w=10,h=360,fill="#141a38"),dict(t="rect",x=1700,y=290,w=330,h=10,fill="#141a38")]))
c.append(dict(id="quadro",k=0.12,formas=[rect(780,170,230,160,"#0d1230",r=4),rect(792,182,206,136,{"g":[[0,"#5a4a8a"],[1,"#d67a5a"]],"dir":"v"}),ell(895,270,40,40,"#ffd9a0",op=0.9),path("M 792 318 C 840 270 880 300 930 280 C 960 270 980 290 998 286 L 998 318 Z","#2a2450")]))
c.append(dict(id="rodape",k=0.2,formas=[rect(-2000,FL-26,6400,26,"#10142c"),rect(-2000,FL-28,6400,3,"#ffffff",op=0.08)]))
piso=[rect(-2000,FL,6400,1200,{"g":[[0,"#4a3322"],[0.2,"#3a281b"],[1,"#1f140e"]],"dir":"v"})]
for i in range(-10,30): piso.append(rect(-2000+i*180,FL,3,1200,"#000000",op=0.22))
for j in range(1,9): piso.append(rect(-2000,FL+(j**1.9)*14,6400,2,"#ffffff",op=0.05))
c.append(dict(id="piso",k=0.55,formas=piso))
c.append(dict(id="tapete",k=0.6,formas=[ell(1300,FL+190,620,86,"#5a2a3a"),ell(1300,FL+190,560,70,"#7a3a4c"),ell(1300,FL+190,420,48,"#5a2a3a",op=0.8)]))
lampada=[rect(250,FL-460,10,450,"#15182c"),ell(255,FL-8,52,10,"#15182c"),path(f"M 190 {FL-455} L 320 {FL-455} L 295 {FL-540} L 215 {FL-540} Z","#e8b86a"),glow(255,FL-500,360,"#ffc070",0.5,1.7),glow(255,FL-200,300,"#ffb060",0.22,1.6,420)]
c.append(dict(id="luminaria",k=0.85,formas=lampada))
plant=[]
for i in range(9):
    a=rnd.uniform(-70,-10); L=rnd.uniform(250,520); x=-60; y=1500
    ex=x+L*math.cos(math.radians(a)); ey=y+L*math.sin(math.radians(a))
    plant.append(path(f"M {x} {y} Q {(x+ex)/2+rnd.uniform(-40,40):.0f} {(y+ey)/2-60:.0f} {ex:.0f} {ey:.0f} Q {(x+ex)/2+30:.0f} {(y+ey)/2+30:.0f} {x+40} {y} Z","#0a0f1c"))
c.append(dict(id="planta",k=1.5,desfoque=5,formas=plant))
json.dump(dict(formato="m1-recurso/1",id="sala_noite",tipo="cenario",nome="Sala de estar a noite",tags=["interior","sala","noite"],caixa=[0,0,2600,1100],camadas=c),open("../sala_noite.json","w",encoding="utf-8"),ensure_ascii=False,separators=(",",":"))
print("ok")
