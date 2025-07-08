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

class ROISelector(ctk.CTkToplevel):
    def __init__(self, monitor):
        super().__init__()
        self.monitor = monitor
        # Use monitor geometry to position the selector window
        self.geometry(f"{self.monitor['width']}x{self.monitor['height']}+{self.monitor['left']}+{self.monitor['top']}")
        self.attributes("-alpha", 0.5)  # Semi-transparent
        self.attributes("-topmost", True)  # Stay on top
        self.overrideredirect(True)  # No window decorations (borderless)

        self.canvas = ctk.CTkCanvas(self, cursor="cross", bg="white", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)

        self.start_x = None
        self.start_y = None
        self.rect = None
        self.roi_coords = None
        
        self.resolution_label = ctk.CTkLabel(self.canvas, text="", font=("Arial", 14, "bold"), fg_color="black", text_color="white")

        self.canvas.bind("<ButtonPress-1>", self.on_button_press)
        self.canvas.bind("<B1-Motion>", self.on_mouse_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_button_release)
        self.bind("<Escape>", self.cancel) # Allow canceling with Escape key

    def on_button_press(self, event):
        self.start_x = event.x
        self.start_y = event.y
        if self.rect:
            self.canvas.delete(self.rect)
        self.resolution_label.place_forget()

    def on_mouse_drag(self, event):
        if self.start_x is None or self.start_y is None:
            return
        if self.rect:
            self.canvas.delete(self.rect)
        
        cur_x, cur_y = event.x, event.y
        self.rect = self.canvas.create_rectangle(self.start_x, self.start_y, cur_x, cur_y, outline='red', width=2)
        
        width = abs(cur_x - self.start_x)
        height = abs(cur_y - self.start_y)
        resolution_text = f"{width}x{height}"
        self.resolution_label.configure(text=resolution_text)
        
        # Position label near the cursor
        self.resolution_label.place(x=event.x + 15, y=event.y)

    def on_button_release(self, event):
        if self.start_x is not None and self.start_y is not None:
            x1, y1 = (min(self.start_x, event.x), min(self.start_y, event.y))
            x2, y2 = (max(self.start_x, event.x), max(self.start_y, event.y))
            self.roi_coords = (x1, y1, x2, y2)
        self.resolution_label.place_forget()
        self.destroy()

    def cancel(self, event=None):
        self.roi_coords = None
        self.resolution_label.place_forget()
        self.destroy()

    def get_roi(self):
        self.wait_window()
        return self.roi_coords


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
        self.roi_coords = None

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

        # Controls for PVW
        self.pvw_controls_frame = ctk.CTkFrame(self.pvw_frame)
        self.pvw_controls_frame.place(relx=0.5, rely=0.92, anchor="s")

        self.monitor_option = ctk.CTkOptionMenu(self.pvw_controls_frame, values=self.monitor_names, command=self.change_monitor)
        self.monitor_option.set(self.monitor_names[0] if self.monitor_names else "")
        self.monitor_option.grid(row=0, column=0, padx=5, pady=5)

        self.select_roi_button = ctk.CTkButton(self.pvw_controls_frame, text="Select ROI", command=self.select_roi_on_desktop)
        self.select_roi_button.grid(row=0, column=1, padx=5, pady=5)

        self.clear_roi_button = ctk.CTkButton(self.pvw_controls_frame, text="Clear ROI", command=self.clear_roi)
        self.clear_roi_button.grid(row=0, column=2, padx=5, pady=5)

        # Add a label for ROI resolution
        self.roi_resolution_label = ctk.CTkLabel(self.pvw_frame, text="", font=("Arial", 12))
        self.roi_resolution_label.place(relx=0.5, rely=0.82, anchor="center")

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
        if not self.pvw_running or not self.winfo_exists():
            return
        try:
            monitor = self.sct_for_pvw.monitors[self.selected_monitor_index + 1]
            
            capture_region = monitor
            if self.roi_coords:
                x1, y1, x2, y2 = self.roi_coords
                width, height = x2 - x1, y2 - y1
                if width > 5 and height > 5: # Set a minimum ROI size
                    capture_region = {
                        "top": monitor["top"] + y1,
                        "left": monitor["left"] + x1,
                        "width": width,
                        "height": height,
                    }
                else: # Invalid ROI, reset it
                    self.roi_coords = None
            
            img = self.sct_for_pvw.grab(capture_region)
            img_pil = Image.frombytes('RGB', img.size, img.rgb)
            
            # Maintain aspect ratio for preview
            img_pil.thumbnail((440, 220), Image.LANCZOS)
            
            self.pvw_imgtk = ImageTk.PhotoImage(img_pil)
            
            # Redraw image in the center of the canvas
            self.pvw_canvas.delete("all")
            self.pvw_canvas_img = self.pvw_canvas.create_image(
                220, 110, anchor="center", image=self.pvw_imgtk
            )

        except Exception as e:
            print("PVW error:", e)
        
        # Schedule next update
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
        # Give the update loop a moment to stop before destroying
        self.after(100, self.destroy)

    def select_roi_on_desktop(self):
        if self.selected_monitor_index < 0 or self.selected_monitor_index >= len(self.monitor_list):
            CTkMessagebox(title="Error", message="Please select a valid monitor first.")
            return
        
        self.withdraw() # Hide main window
        self.after(200, self._perform_roi_selection) # Give time for window to hide

    def _perform_roi_selection(self):
        try:
            monitor = self.monitor_list[self.selected_monitor_index]
            roi_selector = ROISelector(monitor)
            roi = roi_selector.get_roi()
            if roi and (roi[2] - roi[0]) > 5 and (roi[3] - roi[1]) > 5:
                self.roi_coords = roi
                # Update resolution label
                width = roi[2] - roi[0]
                height = roi[3] - roi[1]
                self.roi_resolution_label.configure(text=f"ROI Resolution: {width}x{height}")
            else:
                self.roi_coords = None
                self.roi_resolution_label.configure(text="") # Clear if invalid
        finally:
            self.deiconify() # Show main window again

    def clear_roi(self):
        self.roi_coords = None
        self.roi_resolution_label.configure(text="")

if __name__ == "__main__":
    app = ScanConverterApp()
    app.protocol("WM_DELETE_WINDOW", app.on_closing)
    app.mainloop()
