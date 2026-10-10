"""PlantLock — social media lock that unlocks only by planting (via camera).

Flow:  Start Planting  ->  camera opens  ->  CLIP judges every second
       NOT planting  ->  number does not move
       planting      ->  number moves (10 planting-seconds = 1 tree)
       2 trees       ->  social media released (hosts file, admin)
"""
import sys
import threading
import tkinter as tk
from tkinter import messagebox

import customtkinter as ctk
from PIL import Image, ImageTk

import hostslock
from detector import PlantingDetector

MIN_TREES = 2          # the minimum
TICKS_PER_TREE = 10     # planting-seconds per tree
GOAL_TICKS = MIN_TREES * TICKS_PER_TREE

BG = "#0b1410"
PANEL = "#12211a"
GREEN = "#22c55e"
DIM = "#7fa893"
CORAL = "#ff8b75"

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("green")


class App(ctk.CTk):
    def __init__(self, auto_start: bool = False):
        super().__init__()
        self.title("PlantLock — plant to unlock")
        self.geometry("860x740")
        self.configure(fg_color=BG)

        self.ticks = 0
        self.session_done = False
        self.det = None
        self.img_ref = None
        self.last_verdict_t = 0.0
        self.elevated = hostslock.is_elevated()
        self.locked_on = hostslock.locked()

        # header
        head = ctk.CTkFrame(self, fg_color=PANEL, corner_radius=0, height=54)
        head.pack(fill="x")
        ctk.CTkLabel(head, text="🌱 PlantLock", font=("Consolas", 18, "bold"),
                     text_color=GREEN).pack(side="left", padx=16, pady=8)
        self.lock_lbl = ctk.CTkLabel(head,
            text="social media: LOCKED" if self.locked_on else "social media: not locked yet",
            text_color=CORAL if self.locked_on else DIM, font=("Consolas", 12))
        self.lock_lbl.pack(side="right", padx=16)

        # camera
        self.cam_lbl = ctk.CTkLabel(self, text="camera off — press Start Planting",
                                    width=640, height=400, fg_color="#06100c",
                                    corner_radius=16)
        self.cam_lbl.pack(padx=16, pady=(16, 8))

        # counter
        ctk.CTkLabel(self, text="TREES PLANTED", text_color=DIM,
                     font=("Consolas", 12)).pack()
        self.tree_lbl = ctk.CTkLabel(self, text=f"0 / {MIN_TREES} minimum",
                                     text_color="#e7f5ee",
                                     font=("Consolas", 44, "bold"))
        self.tree_lbl.pack()
        self.prog = ctk.CTkProgressBar(self, width=560)
        self.prog.set(0)
        self.prog.pack(pady=4)

        # verdict badge
        self.verdict_lbl = ctk.CTkLabel(self, text="● IDLE", text_color=DIM,
                                        font=("Consolas", 15, "bold"))
        self.verdict_lbl.pack(pady=(4, 2))
        self.engine_lbl = ctk.CTkLabel(self, text="", text_color=DIM,
                                       font=("Consolas", 11))
        self.engine_lbl.pack()
        self.status_lbl = ctk.CTkLabel(self, text="", text_color=DIM,
                                       font=("Consolas", 11))
        self.status_lbl.pack(pady=2)

        # buttons
        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(pady=10)
        self.start_btn = ctk.CTkButton(row, text="Start Planting", height=56,
                                       width=280, fg_color=GREEN,
                                       hover_color="#16a34a",
                                       font=("Consolas", 18, "bold"),
                                       command=self.start_planting)
        self.start_btn.pack(side="left", padx=10)
        self.stop_btn = ctk.CTkButton(row, text="Stop camera", height=56, width=160,
                                      fg_color="#334155",
                                      command=self.stop_camera, state="disabled")
        self.stop_btn.pack(side="left", padx=10)

        if auto_start:
            self.after(400, self.start_planting)

    # ---------------- actions
    def start_planting(self):
        if self.det is not None or self.session_done:
            return
        # admin gate for the hosts lock
        if not self.elevated and not self.locked_on:
            ok = messagebox.askyesno(
                "PlantLock",
                "Locking social media edits the hosts file and needs Administrator.\n\n"
                "A UAC prompt will appear. Accept it to lock.\n"
                "(Decline = camera still counts, but no lock.)")
            if ok:
                self.relaunch_elevated()
                return
            self.status_lbl.configure(
                text="counting only — social media NOT locked (no admin)")

        if self.elevated or self.locked_on:
            if hostslock.apply_lock():
                self.locked_on = True
                self.lock_lbl.configure(text="social media: LOCKED",
                                        text_color=CORAL)
                self.status_lbl.configure(text="instagram · facebook · x · "
                                               "tiktok · reddit · threads blocked")
            else:
                self.status_lbl.configure(text="hosts lock FAILED — run as admin")

        self.det = PlantingDetector(use_clip=True)
        self.engine_lbl.configure(text=f"engine: {self.det.engine.name}")
        if not self.det.start():
            self.status_lbl.configure(text="camera unavailable (webcam busy or missing)")
            self.det = None
            return
        self.start_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")
        self.verdict_lbl.configure(text="● WATCHING…", text_color=DIM)
        self._poll()

    def relaunch_elevated(self):
        import ctypes
        if getattr(sys, "frozen", False):
            params = "--auto-start"
            target = sys.executable
        else:
            params = f'"{__file__}" --auto-start'
            target = sys.executable
        rc = ctypes.windll.shell32.ShellExecuteW(
            None, "runas", target, params, None, 1)
        if rc <= 32:
            messagebox.showinfo("PlantLock",
                                "Elevation declined — camera will count without a lock.")
            self.status_lbl.configure(text="counting only — no admin")
            return
        self.destroy()

    def stop_camera(self):
        if self.det:
            self.det.stop()
            self.det = None
        self.start_btn.configure(state="normal" if not self.session_done else "disabled")
        self.stop_btn.configure(state="disabled")
        self.cam_lbl.configure(image=None, text="camera off")
        self.verdict_lbl.configure(text="● STOPPED", text_color=DIM)

    # ---------------- main loop (200ms)
    def _poll(self):
        if self.det is None:
            return
        frame, verdict = self.det.snapshot()
        if frame is not None:
            import cv2
            small = cv2.resize(frame, (640, 400))
            img = Image.fromarray(small)
            self.img_ref = ImageTk.PhotoImage(img)
            self.cam_lbl.configure(image=self.img_ref, text="")

        new_tick = verdict["t"] != self.last_verdict_t
        if new_tick:
            self.last_verdict_t = verdict["t"]
            if verdict["planting"]:
                self.ticks += 1                              # number moves
                self.verdict_lbl.configure(
                    text=f"● PLANTING ✓  {verdict['score']*100:.0f}%",
                    text_color=GREEN)
            else:
                self.verdict_lbl.configure(                  # number does NOT move
                    text=f"● NOT PLANTING  {verdict['score']*100:.0f}%",
                    text_color=CORAL)

        trees = self.ticks // TICKS_PER_TREE
        self.tree_lbl.configure(
            text=f"{trees} / {MIN_TREES} minimum" if trees < MIN_TREES
                 else f"{trees} 🌳  UNLOCKED")
        self.prog.set((self.ticks % TICKS_PER_TREE) / TICKS_PER_TREE)

        if trees >= MIN_TREES and not self.session_done:
            self.session_done = True
            if self.locked_on and hostslock.release_lock():
                self.lock_lbl.configure(text="social media: UNLOCKED",
                                        text_color=GREEN)
                self.status_lbl.configure(
                    text=f"{trees} trees planted — social media released. 🌳")
            elif self.locked_on:
                self.status_lbl.configure(text="UNLOCK FAILED — hosts needs admin!")
            else:
                self.status_lbl.configure(
                    text=f"{trees} trees planted. nothing to unlock (never locked).")
            self.verdict_lbl.configure(text="● GO TOUCH GRASS — DONE", text_color=GREEN)
            self.stop_camera()
            return

        self.after(200, self._poll)


if __name__ == "__main__":
    if "--auto-start" in sys.argv:
        App(auto_start=True).mainloop()
    else:
        App().mainloop()
