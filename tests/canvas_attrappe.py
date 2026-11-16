import html  # noqa: F401
import math  # noqa: F401


class C:
    def __init__(s,W,H): s.W,s.H=W,H; s.items={}; s.n=0; s.order=[]
    def _add(s,svg): s.n+=1; s.items[s.n]=svg; s.order.append(s.n); return s.n
    def winfo_width(s): return s.W
    def winfo_height(s): return s.H
    def delete(s,*a):
        if a and a[0]=="all": s.items={}; s.order=[]
        else:
            for i in a: s.items.pop(i,None)
    def find_all(s): return tuple(i for i in s.order if i in s.items)
    def addtag_withtag(s,t,i): pass
    def tag_raise(s,i):
        if i in s.order: s.order.remove(i); s.order.append(i)
    def _f(s,kw): return kw.get("fill") or "none"
    def create_rectangle(s,x0,y0,x1,y1,**kw):
        if kw.get("state")=="hidden": return s._add("")
        op=' fill-opacity="0.55"' if kw.get("stipple") else ''
        da=' stroke-dasharray="5,3"' if kw.get("dash") else ''
        return s._add(f'<rect x="{x0}" y="{y0}" width="{x1-x0}" height="{y1-y0}" fill="{s._f(kw)}"{op} stroke="{kw.get("outline") or "none"}" stroke-width="{kw.get("width",1)}"{da}/>')
    def create_polygon(s,pts,**kw):
        if kw.get("state")=="hidden": return s._add("")
        xs=pts[0::2]; ys=pts[1::2]; x0,x1,y0,y1=min(xs),max(xs),min(ys),max(ys)
        return s._add(f'<rect x="{x0}" y="{y0}" width="{x1-x0}" height="{y1-y0}" rx="8" fill="{s._f(kw)}" stroke="{kw.get("outline") or "none"}" stroke-width="{kw.get("width",1)}"/>')
    def create_oval(s,x0,y0,x1,y1,**kw): return s._add(f'<ellipse cx="{(x0+x1)/2}" cy="{(y0+y1)/2}" rx="{abs(x1-x0)/2}" ry="{abs(y1-y0)/2}" fill="{s._f(kw)}" stroke="{kw.get("outline") or "none"}"/>')
    def create_arc(s,x0,y0,x1,y1,start=0,extent=90,style=None,outline="#fff",width=1,**kw):
        import math
        cx,cy,r=(x0+x1)/2,(y0+y1)/2,(x1-x0)/2
        a0=math.radians(start); a1=math.radians(start+extent)
        p0=(cx+r*math.cos(a0),cy-r*math.sin(a0)); p1=(cx+r*math.cos(a1),cy-r*math.sin(a1))
        large=1 if abs(extent)>180 else 0; sweep=1 if extent<0 else 0
        return s._add(f'<path d="M{p0[0]},{p0[1]} A{r},{r} 0 {large} {sweep} {p1[0]},{p1[1]}" fill="none" stroke="{outline}" stroke-width="{width}"/>')
    def create_line(s,*a,**kw):
        p=a if len(a)>2 else a[0]
        return s._add(f'<line x1="{p[0]}" y1="{p[1]}" x2="{p[2]}" y2="{p[3]}" stroke="{kw.get("fill","#fff")}" stroke-width="{kw.get("width",1)}"/>')
    def _text(s,x,y,text,font,fill,anchor,width):
        fs=font[1] if font else 10
        ta={"w":"start","e":"end","nw":"start","n":"middle"}.get(anchor,"middle")
        lines=[]
        for para in str(text).split("\n"):
            if width:
                cur=""
                for w in para.split():
                    if len(cur+" "+w)*fs*0.56>width and cur: lines.append(cur); cur=w
                    else: cur=(cur+" "+w).strip()
                lines.append(cur)
            else: lines.append(para)
        dy = fs*0.9 if anchor in ("nw","n") else fs*0.35-(len(lines)-1)*fs*0.62
        return "".join(f'<text x="{x}" y="{y+dy+i*fs*1.25}" font-size="{fs}" font-family="DejaVu Sans" fill="{fill}" text-anchor="{ta}">{html.escape(l)}</text>' for i,l in enumerate(lines)), len(lines)*fs*1.25
    def create_text(s,x,y,text="",font=None,fill="#fff",anchor="center",width=None,justify=None,state=None,**kw):
        i=s._add(""); s.items[i]=("T",x,y,text,font,fill,anchor,width,state); return i
    def bbox(s,i):
        t=s.items.get(i)
        if isinstance(t,tuple):
            _,x,y,text,font,fill,anchor,width,state=t; svg,h=s._text(x,y,text,font,fill,anchor,width); return (x,y,x+(width or 100),y+h)
        return (0,0,0,12)
    def coords(s,i,*p):
        t=s.items.get(i)
        if isinstance(t,tuple) and len(p)>=2: s.items[i]=("T",p[0],p[1])+t[3:]
    def itemconfig(s,i,**kw):
        t=s.items.get(i)
        if isinstance(t,tuple):
            l=list(t)
            if "text" in kw: l[3]=kw["text"]
            if "fill" in kw: l[5]=kw["fill"]
            if "state" in kw: l[8]=kw["state"]
            s.items[i]=tuple(l)
    def after(s,*a): return 1
    def after_cancel(s,*a): pass
    def svg(s):
        out=[]
        for i in s.order:
            t=s.items.get(i)
            if isinstance(t,tuple):
                if t[8]=="hidden": continue
                out.append(s._text(t[1],t[2],t[3],t[4],t[5],t[6],t[7])[0])
            elif t: out.append(t)
        return f'<svg xmlns="http://www.w3.org/2000/svg" width="{s.W}" height="{s.H}"><rect width="100%" height="100%" fill="#000"/>'+"".join(out)+"</svg>"
