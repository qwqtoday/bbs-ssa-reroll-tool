from __future__ import annotations

import time
import tkinter as tk
from tkinter import messagebox, IntVar
import threading

from ahk import AHK
from paddleocr import PaddleOCR

import cv2
import mss
import numpy


# Init AutoHotkey
ahk = AHK(version='v2')
ahk.set_send_mode("Event")

# Init OCR
ocr = PaddleOCR(use_angle_cls=True, lang='en')

# Load template
template_files = {
    "prompt": "prompt_template.png",
    "keep_button": "keep_button_template.png",
    "replace_button": "replace_button_template.png",
    "no_button": "no_button_template.png",
    "yes_button": "yes_button_template.png",
}

templates: dict[str, cv2.Mat] = {}

for name, file in template_files.items():
    templates[name] = cv2.imread(file, cv2.IMREAD_UNCHANGED)
    if name != "prompt":
        templates[name] = cv2.cvtColor(templates[name], cv2.COLOR_BGRA2BGR)

alpha_channel = templates["prompt"][:, :, 3]
mask = numpy.where(alpha_channel > 0, 255, 0).astype('uint8')
templates["prompt"] = templates["prompt"][:, :, :3]

passive_names = [
    "Pop Star",
    "Guiding Star",
    "Star Shower",
    "Gummy Star",
    "Scorching Star",
    "Star Saw",
]

buff_names = [
    "Instant Conversion",
    "Blue Pollen",
    "Critical Chance",
    "Red Pollen",
    "Bee Ability Rate",
    "White Pollen",
    "Bee Gather Pollen",
    "Pollen",
    "Convert Rate"
]

class SuperStarAmulet:
    passives: list[str]
    buffs: dict[str, float]

    def __init__(self) -> None:
        self.passives = []
        self.buffs = {}
        self.convert_rate: float = 0.0

    @staticmethod
    def from_list(buffs: list[str]) -> SuperStarAmulet:
        amulet = SuperStarAmulet()
        for buff_name in buff_names:
            amulet.buffs[buff_name] = 0

        for buff in buffs:
            print(buff)
            if buff.startswith("+Passive:"):
                for passive in passive_names:
                    if passive in buff:
                        amulet.passives.append(passive)
                        break
                continue
            if buff.startswith("+"):
                value, name = buff.split(" ", 1)
                amulet.buffs[name] = float(value.replace("%", ""))
                continue

            if buff.startswith("x"):
                value, name = buff[1:].split(" ", 1)
                if name == "Convert Rate":
                    amulet.buffs["Convert Rate"] = float(value)
        return amulet


def roblox_position():
    position = ahk.win_get_position("Roblox")

    return (
        position.x + 8,  # Left
        position.y + 32,  # Top
        position.x + position.width - 8,  # Right
        position.y + position.height - 8  # Bottom
    )

def capture_roblox() -> cv2.Mat:    
    area = roblox_position()

    with mss.mss() as sct:
        img = sct.grab(area)
        ss = numpy.asarray(img)
        ss = cv2.cvtColor(ss, cv2.COLOR_BGRA2BGR)
    return ss

rerolling = False

def start_rerolling(buffs: dict[str, tuple[float, float]], double_passive: bool, selected_passives: list[str]):
    global rerolling
    if rerolling:
        return

    rerolling = True
    # Activate the Roblox window
    ahk.win_activate("Roblox")
    time.sleep(0.2)

    while rerolling:
        ahk.send("e")
        time.sleep(0.5)

        area = roblox_position()
        ss = capture_roblox()
        result = cv2.matchTemplate(ss, templates["no_button"], cv2.TM_CCOEFF_NORMED)
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)

        if max_val >= 0.8:
            x, y = max_loc
            x += templates["no_button"].shape[1] / 2
            y += templates["no_button"].shape[0] / 2

            # Click "Yes" if double passive is enabled, otherwise click "No"
            if double_passive:
                ahk.click(x - 150, y)  # Offset to the Yes button
            else:
                ahk.click(x, y)
            
            ahk.mouse_move(0, 0)
            time.sleep(0.6)

        

        try:
                # Capture the screen area
            ss = capture_roblox()

            # Get match result
            result = cv2.matchTemplate(ss, templates["prompt"], cv2.TM_CCOEFF_NORMED, mask=mask)

            yloc, xloc = numpy.where(result >= 0.99)

            # Crop and save/display each matched area
            for (x, y) in zip(xloc, yloc):
                # Crop the matched region
                prompt_img = ss[y:y + templates["prompt"].shape[0], x:x + templates["prompt"].shape[1]]
                break
            else:
                raise Exception("prompt not found")

            cv2.imwrite("prompt_img.png", prompt_img)

            new_buff = prompt_img[209: 345, 183: 357]
            cv2.imwrite('new_buff.png', new_buff)

            # Perform OCR on the new buff image
            result = ocr.ocr('new_buff.png', cls=True)

            buffs_detected: list[str] = list(map(lambda x: x[1][0], result[0]))

            amulet = SuperStarAmulet.from_list(buffs_detected)

            # Check if the generated amulet stats fall within user-defined ranges
            if (
                all(buffs[buff][0] <= amulet.buffs.get(buff, 0) <= buffs[buff][1] for buff in buffs) and all((selected_passive in amulet.passives for selected_passive in selected_passives))
            ):
                app.status_label.config(text="Rerolling stopped.")
                rerolling = False
                break
        except:
            pass

def stop_rerolling():
    global rerolling
    rerolling = False

ahk.add_hotkey("F2", stop_rerolling)

class AmuletRerollGUI:
    def __init__(self, master):
        self.master = master
        master.title("Amulet Reroller Config")

        # Create main frame for inputs
        self.main_frame = tk.Frame(master)
        self.main_frame.pack(side=tk.LEFT, padx=10)

        # Buffs
        self.buff_entries = {}
        self.buff_vars = {}
        self.buff_names = [
            "Instant Conversion",
            "Blue Pollen",
            "Critical Chance",
            "Red Pollen",
            "Bee Ability Rate",
            "White Pollen",
            "Bee Gather Pollen",
            "Pollen",
            "Convert Rate"
        ]

        # Set default values in compliance with limits
        default_values = {
            "Instant Conversion": (5, 12),  # Default 5% (limits 3% to 12%)
            "Pollen": (10, 20),              # Default 10% (limits 5% to 20%)
            "White Pollen": (20, 70),        # Default 20% (limits 15% to 70%)
            "Red Pollen": (30, 70),          # Default 30% (limits 15% to 70%)
            "Blue Pollen": (30, 70),         # Default 30% (limits 15% to 70%)
            "Bee Gather Pollen": (30, 70),   # Default 30% (limits 15% to 70%)
            "Bee Ability Rate": (5, 7),      # Default 5% (limits 1% to 7%)
            "Critical Chance": (5, 7),       # Default 5% (limits 1% to 7%)
            "Convert Rate": (1.10, 1.25)     # Default x1.10 (limits x1.05 to x1.25)
        }

        for buff in self.buff_names:
            frame = tk.Frame(self.main_frame)
            frame.pack(pady=2)

            label = tk.Label(frame, text=buff)
            label.pack(side=tk.LEFT)

            # Get default values
            default_min, default_max = default_values[buff]

            min_entry = tk.Entry(frame, width=5)
            min_entry.insert(0, str(default_min))  # Set default min value
            min_entry.pack(side=tk.LEFT)

            max_entry = tk.Entry(frame, width=5)
            max_entry.insert(0, str(default_max))  # Set default max value
            max_entry.pack(side=tk.LEFT)

            var = IntVar()
            checkbox = tk.Checkbutton(frame, variable=var)  # Checkbox for passive
            checkbox.pack(side=tk.LEFT)

            self.buff_entries[buff] = (min_entry, max_entry)
            self.buff_vars[buff] = var

        # Passive Selection Frame
        self.passive_frame = tk.Frame(master)
        self.passive_frame.pack(side=tk.RIGHT, padx=10)

        # Add Passive Checkboxes
        self.passive_vars = {name: IntVar() for name in passive_names}
        self.passive_checkboxes = []
        for name in passive_names:
            var = self.passive_vars[name]
            checkbox = tk.Checkbutton(self.passive_frame, text=name, variable=var, command=self.check_passive_selection)
            checkbox.pack(anchor=tk.W)
            self.passive_checkboxes.append(checkbox)

        # Double Passive Checkbox
        self.double_passive_var = tk.BooleanVar()
        self.double_passive_checkbox = tk.Checkbutton(master, text="Enable Double Passive", variable=self.double_passive_var)
        self.double_passive_checkbox.pack()

        # Start button
        self.start_button = tk.Button(master, text="Start Rerolling", command=self.start_rerolling)
        self.start_button.pack(pady=(10, 0))

        # Stop button
        self.stop_button = tk.Button(master, text="Stop Rerolling", command=self.stop_rerolling)
        self.stop_button.pack()

        # Status label
        self.status_label = tk.Label(master, text="")
        self.status_label.pack()

    def get_configuration(self):
        try:
            buffs = {}
            for name, (min_entry, max_entry) in self.buff_entries.items():
                if self.buff_vars[name].get() == 1:  # Only include checked buffs
                    min_val = float(min_entry.get())
                    max_val = float(max_entry.get())

                    # Set limits based on specified ranges
                    limits = {
                        "Instant Conversion": (3, 12),
                        "Pollen": (5, 20),
                        "White Pollen": (15, 70),
                        "Red Pollen": (15, 70),
                        "Blue Pollen": (15, 70),
                        "Bee Gather Pollen": (15, 70),
                        "Bee Ability Rate": (1, 7),
                        "Critical Chance": (1, 7),
                        "Convert Rate": (1.05, 1.25)
                    }

                    # Check if values are within limits
                    min_limit, max_limit = limits[name]
                    if min_val < min_limit or max_val > max_limit or min_val > max_val:
                        raise ValueError(f"{name} must be between {min_limit} and {max_limit}.")

                    buffs[name] = (min_val, max_val)

            return buffs
        except ValueError as e:
            messagebox.showerror("Input Error", str(e))
            return None

    def check_passive_selection(self):
        selected = sum(var.get() for var in self.passive_vars.values())
        if selected > 2:
            messagebox.showerror("Selection Error", "You can only select up to 2 passives.")
            # Reset the last checked passive
            for name, var in self.passive_vars.items():
                if var.get() == 1:
                    var.set(0)  # Uncheck last if limit exceeded
            return

    def start_rerolling(self):
        buffs = self.get_configuration()
        if buffs is None:
            return

        selected_passives = [name for name, var in self.passive_vars.items() if var.get() == 1]
        if len(selected_passives) > 2:
            messagebox.showerror("Selection Error", "You can only select up to 2 passives.")
            return

        # Start the rerolling in a new thread
        self.status_label.config(text="Rerolling started...")
        thread = threading.Thread(target=start_rerolling, args=(buffs, self.double_passive_var.get(), selected_passives))
        thread.start()

    def stop_rerolling(self):
        stop_rerolling()
        self.status_label.config(text="Rerolling stopped.")

if __name__ == "__main__":
    root = tk.Tk()
    app = AmuletRerollGUI(root)
    root.mainloop()