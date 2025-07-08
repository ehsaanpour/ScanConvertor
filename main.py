import customtkinter as ctk
import threading
import time
from PIL import Image, ImageTk
import mss
from CTkMessagebox import CTkMessagebox

# Mock device and format lists
MOCK_DEVICES = ["Decklink 1", "Decklink 2"]
MOCK_FORMATS = ["1920x1080 50i", "1280x720 50p", "1920x1080 25p"]

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

def get_decklink_devices():
    # This should use the DeckLink SDK via Python bindings.
    # For now, let's mock the result:
    # return ["DeckLink 4K Extreme", "DeckLink Mini Recorder"]
    # If no devices:
    # return []
    pass

class ScanConverterApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Scan Converter")
        self.geometry("1100x700")
        self.resizable(False, False)

        self.sct = mss.mss()
        self.monitor_list = self.sct.monitors[1:]  # mss.monitors[0] is all, [1:] are real
        self.monitor_names = [f"Monitor {i+1}" for i in range(len(self.monitor_list))]
        self.selected_monitor_index = 0
        self.pvw_imgtk = None
        self.pvw_running = True

        # Title label
        self.title_label = ctk.CTkLabel(self, text="Scan Converter", font=("Arial", 28, "bold"))
        self.title_label.pack(pady=16)

        # Main frame
        self.main_frame = ctk.CTkFrame(self)
        self.main_frame.pack(fill="both", expand=True, padx=20, pady=10)

        # PVW and PGM panels
        self.pvw_frame = ctk.CTkFrame(self.main_frame, width=480, height=270, corner_radius=12)
        self.pvw_frame.grid(row=0, column=0, padx=20, pady=10)
        self.pvw_label = ctk.CTkLabel(self.pvw_frame, text="PVW (Preview)", font=("Arial", 16, "bold"))
        self.pvw_label.place(relx=0.5, rely=0.05, anchor="n")
        self.pvw_canvas = ctk.CTkCanvas(self.pvw_frame, width=440, height=220, bg="#222")
        self.pvw_canvas.place(relx=0.5, rely=0.55, anchor="center")
        self.pvw_canvas_img = self.pvw_canvas.create_image(0, 0, anchor="nw")
        # Monitor selection dropdown
        self.monitor_option = ctk.CTkOptionMenu(self.pvw_frame, values=self.monitor_names, command=self.change_monitor)
        self.monitor_option.set(self.monitor_names[0])
        self.monitor_option.place(relx=0.5, rely=0.95, anchor="s")

        self.pgm_frame = ctk.CTkFrame(self.main_frame, width=480, height=270, corner_radius=12)
        self.pgm_frame.grid(row=0, column=1, padx=20, pady=10)
        self.pgm_label = ctk.CTkLabel(self.pgm_frame, text="PGM (Program)", font=("Arial", 16, "bold"))
        self.pgm_label.place(relx=0.5, rely=0.05, anchor="n")
        self.pgm_canvas = ctk.CTkCanvas(self.pgm_frame, width=440, height=220, bg="#222")
        self.pgm_canvas.place(relx=0.5, rely=0.55, anchor="center")

        # Controls frame
        self.controls_frame = ctk.CTkFrame(self.main_frame)
        self.controls_frame.grid(row=1, column=0, columnspan=2, pady=30)

        # Device selection
        self.device_label = ctk.CTkLabel(self.controls_frame, text="Decklink Device:")
        self.device_label.grid(row=0, column=0, padx=10, pady=5)

        # Use real detection (mocked for now)
        devices = get_decklink_devices()
        if not devices:
            devices = ["No DeckLink card detected."]
        self.device_option = ctk.CTkOptionMenu(self.controls_frame, values=devices, command=self.on_device_selected)
        self.device_option.grid(row=0, column=1, padx=10, pady=5)
        self.device_option.set(devices[0])

        # Format selection
        self.format_label = ctk.CTkLabel(self.controls_frame, text="Signal Format:")
        self.format_label.grid(row=0, column=2, padx=10, pady=5)
        self.format_option = ctk.CTkOptionMenu(self.controls_frame, values=MOCK_FORMATS)
        self.format_option.grid(row=0, column=3, padx=10, pady=5)

        # Send to PGM button
        self.send_button = ctk.CTkButton(self.controls_frame, text="Send to PGM", font=("Arial", 16, "bold"), command=self.send_to_pgm)
        self.send_button.grid(row=0, column=4, padx=30, pady=5)

        # Settings button (optional)
        self.settings_button = ctk.CTkButton(self.controls_frame, text="Settings", command=self.open_settings)
        self.settings_button.grid(row=0, column=5, padx=10, pady=5)

        self.start_pvw_update()

    def change_monitor(self, value):
        self.selected_monitor_index = self.monitor_names.index(value)

    def start_pvw_update(self):
        import mss
        self.sct_for_pvw = mss.mss()
        self.update_pvw_frame()

    def update_pvw_frame(self):
        try:
            monitor = self.sct_for_pvw.monitors[self.selected_monitor_index + 1]
            img = self.sct_for_pvw.grab(monitor)
            img_pil = Image.frombytes('RGB', img.size, img.rgb)
            img_pil = img_pil.resize((440, 220), Image.LANCZOS)
            self.pvw_imgtk = ImageTk.PhotoImage(img_pil)
            self.pvw_canvas.itemconfig(self.pvw_canvas_img, image=self.pvw_imgtk)
        except Exception as e:
            print("PVW error:", e)
        # Schedule next update (50ms = ~20fps)
        self.after(50, self.update_pvw_frame)

    def send_to_pgm(self):
        ctk.CTkMessagebox(title="Info", message="Send to PGM clicked! (Stub)")

    def open_settings(self):
        CTkMessagebox(title="Settings", message="Settings dialog (to be implemented)")

    def on_device_selected(self, value):
        if value == "No DeckLink card detected.":
            CTkMessagebox(title="No Device", message="No DeckLink card detected.")

    def on_closing(self):
        self.pvw_running = False
        if hasattr(self, 'sct_for_pvw'):
            self.sct_for_pvw.close()
        self.destroy()

    def roi_start_event(self, event):
        self.roi_start = (event.x, event.y)
        if self.roi_rect:
            self.pvw_canvas.delete(self.roi_rect)
            self.roi_rect = None
        self.roi_size_label.configure(text="")

    def roi_drag_event(self, event):
        if not self.roi_start:
            return
        x0, y0 = self.roi_start
        x1, y1 = event.x, event.y
        # Remove previous rectangle
        if self.roi_rect:
            self.pvw_canvas.delete(self.roi_rect)
        self.roi_rect = self.pvw_canvas.create_rectangle(x0, y0, x1, y1, outline="red", width=2)
        width = abs(x1 - x0)
        height = abs(y1 - y0)
        self.roi_size_label.configure(text=f"ROI: {width} x {height}")

    def roi_end_event(self, event):
        if not self.roi_start:
            return
        x0, y0 = self.roi_start
        x1, y1 = event.x, event.y
        width = abs(x1 - x0)
        height = abs(y1 - y0)
        self.roi_size_label.configure(text=f"ROI: {width} x {height}")
        # Save ROI coordinates if needed
        self.roi_coords = (min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))
        # Optionally: print or use self.roi_coords for cropping
        self.roi_start = None

if __name__ == "__main__":
    app = ScanConverterApp()
    app.protocol("WM_DELETE_WINDOW", app.on_closing)
    app.mainloop()
