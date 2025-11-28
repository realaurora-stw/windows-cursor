import tkinter as tk
import ctypes
import platform
import atexit
import sys

# --- WINDOWS API CONSTANTS ---
GWL_EXSTYLE = -20
WS_EX_LAYERED = 0x80000
WS_EX_TRANSPARENT = 0x20     
WS_EX_TOPMOST = 0x8          
WS_EX_TOOLWINDOW = 0x80      
WS_EX_NOACTIVATE = 0x08000000

HWND_TOPMOST = -1
SWP_NOMOVE = 0x0002
SWP_NOSIZE = 0x0001
SWP_NOACTIVATE = 0x0010
SWP_SHOWWINDOW = 0x0040

# --- SCREEN METRICS CONSTANTS ---
SM_XVIRTUALSCREEN = 76
SM_YVIRTUALSCREEN = 77
SM_CXVIRTUALSCREEN = 78
SM_CYVIRTUALSCREEN = 79

# --- CURSOR CONSTANTS ---
OCR_NORMAL = 32512
OCR_IBEAM = 32513
OCR_WAIT = 32514
OCR_CROSS = 32515
OCR_UP = 32516
OCR_SIZENWSE = 32642
OCR_SIZENESW = 32643
OCR_SIZEWE = 32644
OCR_SIZENS = 32645
OCR_SIZEALL = 32646
OCR_NO = 32648
OCR_HAND = 32649
OCR_APPSTARTING = 32650 

SPI_SETCURSORS = 0x0057

class POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    pass

# --- CURSOR HIDING LOGIC ---
class CursorController:
    def __init__(self):
        self.cursor_visible = True
        self.cursor_ids = [
            OCR_NORMAL, OCR_IBEAM, OCR_WAIT, OCR_CROSS, OCR_UP,
            OCR_SIZENWSE, OCR_SIZENESW, OCR_SIZEWE, OCR_SIZENS,
            OCR_SIZEALL, OCR_NO, OCR_HAND, OCR_APPSTARTING
        ]

    def hide(self):
        if not self.cursor_visible: return
        and_mask = bytes([0xFF] * 128) 
        xor_mask = bytes([0x00] * 128)
        
        for cid in self.cursor_ids:
            h_cursor = ctypes.windll.user32.CreateCursor(None, 0, 0, 32, 32, and_mask, xor_mask)
            ctypes.windll.user32.SetSystemCursor(h_cursor, cid)
        self.cursor_visible = False

    def show(self):
        if self.cursor_visible: return
        ctypes.windll.user32.SystemParametersInfoW(SPI_SETCURSORS, 0, None, 0)
        self.cursor_visible = True

cursor_controller = CursorController()

class SolidTrailCursor:
    def __init__(self, root):
        self.root = root
        
        # --- CONFIGURATION ---
        self.trail_length = 35       
        self.start_width = 16        
        self.friction = 0.60         
        self.color = "black"
        self.transparent_color = "#ff00ff"

        # --- SETUP FULL VIRTUAL SCREEN AREA ---
        user32 = ctypes.windll.user32
        self.offset_x = user32.GetSystemMetrics(SM_XVIRTUALSCREEN)
        self.offset_y = user32.GetSystemMetrics(SM_YVIRTUALSCREEN)
        width = user32.GetSystemMetrics(SM_CXVIRTUALSCREEN)
        height = user32.GetSystemMetrics(SM_CYVIRTUALSCREEN)
        
        # --- WINDOW CONFIG ---
        self.root.overrideredirect(True)
        self.root.geometry(f"{width}x{height}+{self.offset_x}+{self.offset_y}")
        self.root.config(bg=self.transparent_color)
        self.root.wm_attributes("-transparentcolor", self.transparent_color)
        
        self.canvas = tk.Canvas(root, width=width, height=height, 
                                bg=self.transparent_color, highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        
        # Pre-allocate physics nodes
        self.nodes = [[-100.0, -100.0] for _ in range(self.trail_length)]
        self.lines = []
        
        for i in range(self.trail_length - 1):
            line = self.canvas.create_line(0, 0, 0, 0, fill=self.color, 
                                         capstyle=tk.ROUND, joinstyle=tk.ROUND, width=1)
            self.lines.append(line)
            
        self.head_dot = self.canvas.create_oval(0, 0, 0, 0, fill=self.color, outline="")

        # REMOVED: Escape key binding
        # self.root.bind("<Escape>", self.quit_app)
        
        self.root.update()
        self.set_click_through()
        
        cursor_controller.hide()
        
        self.animate()
        self.root.after(500, self.maintenance_loop)

    def quit_app(self, event=None):
        cursor_controller.show()
        self.root.destroy()
        
    def get_mouse_pos(self):
        pt = POINT()
        ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))
        return pt.x, pt.y

    def set_click_through(self):
        try:
            hwnd = ctypes.windll.user32.GetParent(self.root.winfo_id())
            if hwnd == 0: hwnd = self.root.winfo_id()
            styles = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            new_styles = styles | WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE
            ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, new_styles)
            
            ctypes.windll.user32.SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0, 
                                            SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE | SWP_SHOWWINDOW)
        except Exception:
            pass

    def maintenance_loop(self):
        try:
            self.root.deiconify()
            self.root.lift()
            self.root.wm_attributes("-topmost", True)
            self.set_click_through()
        except Exception:
            pass
        self.root.after(500, self.maintenance_loop)

    def animate(self):
        try:
            abs_x, abs_y = self.get_mouse_pos()
            
            target_x = abs_x - self.offset_x
            target_y = abs_y - self.offset_y
            
            self.nodes[0] = [target_x, target_y]
            
            for i in range(1, self.trail_length):
                lx, ly = self.nodes[i-1]
                cx, cy = self.nodes[i]
                dx = (lx - cx) * self.friction
                dy = (ly - cy) * self.friction
                self.nodes[i][0] += dx
                self.nodes[i][1] += dy

            for i in range(len(self.lines)):
                x1, y1 = self.nodes[i]
                x2, y2 = self.nodes[i+1]
                pct = 1 - (i / len(self.lines))
                width = self.start_width * pct
                if width < 0.5: width = 0.5
                self.canvas.itemconfig(self.lines[i], width=width)
                self.canvas.coords(self.lines[i], x1, y1, x2, y2)

            r = self.start_width / 2
            self.canvas.coords(self.head_dot, target_x - r, target_y - r, target_x + r, target_y + r)

        except Exception:
            pass
        
        self.root.after(2, self.animate)

def exit_handler():
    cursor_controller.show()

atexit.register(exit_handler)

if __name__ == "__main__":
    root = tk.Tk()
    app = SolidTrailCursor(root)
    print("Full Screen Overlay Active.")
    print("Press Ctrl+C in this terminal window to quit.")
    
    try:
        root.mainloop()
    except KeyboardInterrupt:
        print("\nExiting safely via Ctrl+C...")
        cursor_controller.show()
        try:
            root.destroy()
        except:
            pass
        sys.exit(0)
