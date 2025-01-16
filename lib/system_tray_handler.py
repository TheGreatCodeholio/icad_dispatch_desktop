import sys

from pystray import MenuItem as item, Icon as icon
from lib.main_config_handler import read_main_config
import tkinter as tk
from tkinter import ttk
import os
import webbrowser
from PIL import Image

global tray_icon


def show_notification(text, title):
    global tray_icon
    tray_icon.notify(text, title)


def exit_program():
    os._exit(0)


def open_pwa():
    icad_config = read_main_config()
    if icad_config["web_gui"]["ip"] == "0.0.0.0":
        if sys.platform == "linux":
            webbrowser.open(
                "http://" + str(icad_config["web_gui"]["ip"]) + ":" + str(icad_config["web_gui"]["port"]),
                new=0, autoraise=True)
        else:
            webbrowser.open(
                "http://127.0.0.1:" + str(icad_config["web_gui"]["port"]),
                new=0, autoraise=True)
    else:
        webbrowser.open(
            "http://" + str(icad_config["web_gui"]["ip"]) + ":" + str(icad_config["web_gui"]["port"]),
            new=0, autoraise=True)


def popup_static(title_text, body_text, button_text):
    popup = tk.Tk()
    popup.wm_title(title_text)
    label = ttk.Label(popup, text=body_text, font=("Verdana", 10))
    label.pack(side="top", fill="x", pady=10)
    b1 = ttk.Button(popup, text=button_text, command=popup.destroy)
    b1.pack()
    popup.mainloop()


def popup_countdown(title_text, body_text, button_text):
    popup = tk.Tk()
    popup.wm_title(title_text)
    label = ttk.Label(popup, text=body_text, font=("Verdana", 10))
    label.pack(side="top", fill="x", pady=10)
    b1 = ttk.Button(popup, text=button_text, command=popup.destroy)
    b1.pack()
    popup.mainloop()


def start_tray_icon():
    global tray_icon

    image = Image.open('bin/160x160_icad.png')
    menu = (item(text='Configure', action=open_pwa, default=True), item(text='Exit', action=exit_program))
    # In order for the icon to be displayed, you must provide an icon
    tray_icon = icon("iCAD", image, "Dispatch", menu)
    try:
        tray_icon.run()
    except Exception:
        os._exit(0)
