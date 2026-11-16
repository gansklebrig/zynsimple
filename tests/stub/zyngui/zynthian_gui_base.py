
class _F:
    def rowconfigure(s,*a,**k): pass
    def columnconfigure(s,*a,**k): pass
class zynthian_gui_base:
    def __init__(self):
        self.width=800; self.height=440; self.main_frame=_F(); import builtins; self.zyngui=getattr(builtins,'_ZG',None)

    def show(self): self.shown = True
    def hide(self): pass
    def set_title(self, *a, **k): pass
