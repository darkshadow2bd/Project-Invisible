#!/usr/bin/env python3
"""
Project Invisible v3 — Windows Native GUI
Premium steganography desktop suite with fully dynamic theme switching.
Contributors:
  - DarkShadow (darkshadow2bd)  — Original CLI engine
  - Imran Hossain (ImranVibes)  — Windows Native GUI
"""

import os
import sys
import threading
import traceback
import subprocess
import tkinter as tk
from tkinter import filedialog, messagebox
import customtkinter as ctk

import en
import de

# ─────────────────────────────────────────────────────────
#  DEPENDENCY FLAGS
# ─────────────────────────────────────────────────────────
HAS_CRYPTO = en.HAS_CRYPTO

try:
    import brotli as _brotli
    HAS_BROTLI = True
except ImportError:
    HAS_BROTLI = False

# ─────────────────────────────────────────────────────────
#  GLOBAL CRASH REPORTER
# ─────────────────────────────────────────────────────────
def _global_exception_hook(exc_type, exc_value, exc_tb):
    if issubclass(exc_type, KeyboardInterrupt):
        return
    details = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
    try:
        messagebox.showerror(
            "Unexpected Error",
            f"An unexpected error occurred:\n\n{exc_value}\n\n"
            f"Details:\n{details[:800]}",
        )
    except Exception:
        pass

sys.excepthook = _global_exception_hook

# ─────────────────────────────────────────────────────────
#  DESIGN TOKENS
#  All colours are (light_value, dark_value) tuples.
#  CTk reads these natively and swaps on theme change —
#  this is the ONLY correct way to do live theme switching.
# ─────────────────────────────────────────────────────────

# Surfaces
C_BASE   = ("#F3F2FA", "#0D0D12")   # window background
C_S1     = ("#FAFAFF", "#13131A")   # sidebar / topmost surface
C_S2     = ("#FFFFFF", "#1A1A26")   # card background
C_S3     = ("#EAE9F5", "#22223A")   # interactive / inset surface
C_BORDER = ("#D8D6EE", "#2D2D4A")   # borders

# Text
C_TEXT   = ("#1A1840", "#F3F4F6")   # primary text (deep ink / near white)
C_SUB    = ("#524F78", "#9CA3AF")   # secondary / body text
C_MUTED  = ("#9693B8", "#6B7280")   # hints, labels, captions

# Accent — single hues that look great on both themes
VIOLET        = "#7C3AED"
VIOLET_HOVER  = "#6D28D9"
C_ACCENT_TEXT = ("#5B21B6", "#A78BFA")   # section labels (darker in light, lighter in dark)

EMERALD       = "#059669"
EMERALD_HOVER = "#047857"
C_SUCCESS_TXT = ("#047857", "#34D399")   # success status text

RUBY          = "#DC2626"
AMBER_LIGHT   = "#D97706"
C_WARN_TXT    = ("#92400E", "#FCD34D")   # warning / amber text

ctk.set_appearance_mode("light")
ctk.set_default_color_theme("blue")


# ─────────────────────────────────────────────────────────
#  REUSABLE WIDGET HELPERS
# ─────────────────────────────────────────────────────────
class Card(ctk.CTkFrame):
    def __init__(self, parent, **kwargs):
        super().__init__(
            parent,
            fg_color=C_S2,
            border_color=C_BORDER,
            border_width=1,
            corner_radius=12,
            **kwargs,
        )

class SectionLabel(ctk.CTkLabel):
    def __init__(self, parent, text, **kwargs):
        super().__init__(
            parent,
            text=text,
            font=ctk.CTkFont("Segoe UI", 11, "bold"),
            text_color=C_ACCENT_TEXT,
            **kwargs,
        )

class TitleLabel(ctk.CTkLabel):
    def __init__(self, parent, text, **kwargs):
        super().__init__(
            parent,
            text=text,
            font=ctk.CTkFont("Segoe UI", 13, "bold"),
            text_color=C_TEXT,
            **kwargs,
        )

class PrimaryButton(ctk.CTkButton):
    def __init__(self, parent, **kwargs):
        super().__init__(
            parent,
            fg_color=VIOLET,
            hover_color=VIOLET_HOVER,
            text_color="#FFFFFF",
            font=ctk.CTkFont("Segoe UI", 13, "bold"),
            corner_radius=8,
            height=42,
            **kwargs,
        )

class SecondaryButton(ctk.CTkButton):
    def __init__(self, parent, **kwargs):
        super().__init__(
            parent,
            fg_color=C_S3,
            hover_color=C_BORDER,
            text_color=C_TEXT,
            font=ctk.CTkFont("Segoe UI", 12),
            corner_radius=8,
            height=36,
            border_width=1,
            border_color=C_BORDER,
            **kwargs,
        )

class SuccessButton(ctk.CTkButton):
    def __init__(self, parent, **kwargs):
        super().__init__(
            parent,
            fg_color=EMERALD,
            hover_color=EMERALD_HOVER,
            text_color="#FFFFFF",
            font=ctk.CTkFont("Segoe UI", 13, "bold"),
            corner_radius=8,
            height=42,
            **kwargs,
        )


# ─────────────────────────────────────────────────────────
#  MAIN APPLICATION
# ─────────────────────────────────────────────────────────
class InvisibleGUI(ctk.CTk):

    def __init__(self):
        super().__init__()

        self.title("Project Invisible v3 — Steganography Suite")
        self.geometry("1180x740")
        self.minsize(1050, 660)
        self.configure(fg_color=C_BASE)

        self._current_tab = "encode"

        # State
        self.encode_payload_mode    = "text"
        self.encode_file_path       = ""
        self.encode_host_path       = ""
        self.encode_save_path       = "en_file.txt"
        self.decode_input_file      = ""
        self.decoded_payload_bytes  = None
        self.decoded_filename       = None

        self.grid_columnconfigure(0, weight=0, minsize=240)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self._build_sidebar()
        self._build_content()
        self.select_tab("encode")

    # ── Sidebar ──────────────────────────────────────────
    def _build_sidebar(self):
        self.sidebar = ctk.CTkFrame(self, fg_color=C_S1, corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_rowconfigure(8, weight=1)
        self.sidebar.grid_columnconfigure(0, weight=1)

        # Logo
        logo_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        logo_frame.grid(row=0, column=0, padx=24, pady=(32, 8), sticky="w")

        ctk.CTkLabel(
            logo_frame,
            text="◈  INVISIBLE",
            font=ctk.CTkFont("Segoe UI", 20, "bold"),
            text_color=C_ACCENT_TEXT,
        ).pack(anchor="w")

        ctk.CTkLabel(
            logo_frame,
            text="v3 · Steganography Suite",
            font=ctk.CTkFont("Segoe UI", 10),
            text_color=C_MUTED,
        ).pack(anchor="w")

        # Divider
        ctk.CTkFrame(self.sidebar, height=1, fg_color=C_BORDER).grid(
            row=1, column=0, sticky="ew", padx=20, pady=(12, 20)
        )

        # Nav section label
        ctk.CTkLabel(
            self.sidebar,
            text="NAVIGATION",
            font=ctk.CTkFont("Segoe UI", 9, "bold"),
            text_color=C_MUTED,
        ).grid(row=2, column=0, padx=24, pady=(0, 6), sticky="w")

        # Nav buttons — active uses VIOLET fg, inactive uses transparent
        self._nav_btns = {}
        nav_defs = [
            ("encode", "🔒  Hide Secret"),
            ("decode", "🔓  Reveal Secret"),
            ("about",  "📖  Guide"),
        ]
        for idx, (tab, label) in enumerate(nav_defs):
            btn = ctk.CTkButton(
                self.sidebar,
                text=label,
                font=ctk.CTkFont("Segoe UI", 13),
                fg_color="transparent",
                text_color=C_SUB,
                hover_color=C_S3,
                anchor="w",
                height=44,
                corner_radius=8,
                command=lambda t=tab: self.select_tab(t),
            )
            btn.grid(row=3 + idx, column=0, padx=12, pady=3, sticky="ew")
            self._nav_btns[tab] = btn

        # Divider
        ctk.CTkFrame(self.sidebar, height=1, fg_color=C_BORDER).grid(
            row=6, column=0, sticky="ew", padx=20, pady=(16, 16)
        )

        ctk.CTkLabel(
            self.sidebar,
            text="APPEARANCE",
            font=ctk.CTkFont("Segoe UI", 9, "bold"),
            text_color=C_MUTED,
        ).grid(row=7, column=0, padx=24, pady=(0, 6), sticky="w")

        self._theme_seg = ctk.CTkSegmentedButton(
            self.sidebar,
            values=["Dark", "Light", "System"],
            selected_color=VIOLET,
            selected_hover_color=VIOLET_HOVER,
            unselected_color=C_S3,
            unselected_hover_color=C_BORDER,
            text_color=C_TEXT,
            font=ctk.CTkFont("Segoe UI", 11),
            corner_radius=8,
            command=self._on_theme_change,
        )
        self._theme_seg.set("Light")
        self._theme_seg.grid(row=8, column=0, padx=12, sticky="ew")

        ctk.CTkLabel(
            self.sidebar,
            text="Project Invisible  v3",
            font=ctk.CTkFont("Segoe UI", 9),
            text_color=C_MUTED,
        ).grid(row=9, column=0, padx=24, pady=(16, 24), sticky="w")

    # ── Content shell ────────────────────────────────────
    def _build_content(self):
        self.content_host = ctk.CTkFrame(self, fg_color="transparent")
        self.content_host.grid(row=0, column=1, sticky="nsew", padx=24, pady=24)
        self.content_host.grid_columnconfigure(0, weight=1)
        self.content_host.grid_rowconfigure(1, weight=1)

        self._topbar_title = ctk.CTkLabel(
            self.content_host,
            text="Hide Secret",
            font=ctk.CTkFont("Segoe UI", 22, "bold"),
            text_color=C_TEXT,
            anchor="w",
        )
        self._topbar_title.grid(row=0, column=0, sticky="w", pady=(0, 18))

        self._build_encode_view()
        self._build_decode_view()
        self._build_about_view()

    # ─────────────────────────────────────────────────────
    #  ENCODE VIEW
    # ─────────────────────────────────────────────────────
    def _build_encode_view(self):
        self.encode_view = ctk.CTkFrame(self.content_host, fg_color="transparent")
        self.encode_view.grid_columnconfigure(0, weight=3, minsize=420)
        self.encode_view.grid_columnconfigure(1, weight=2, minsize=340)
        self.encode_view.grid_rowconfigure(0, weight=1)

        # ── Left column ──────────────────────
        left = ctk.CTkScrollableFrame(self.encode_view, fg_color="transparent")
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        left.grid_columnconfigure(0, weight=1)

        # Payload mode card
        mode_card = Card(left)
        mode_card.grid(row=0, column=0, sticky="ew", pady=(0, 14))
        mode_card.grid_columnconfigure(0, weight=1)

        SectionLabel(mode_card, "PAYLOAD TYPE").grid(
            row=0, column=0, padx=20, pady=(16, 10), sticky="w"
        )

        self.mode_seg = ctk.CTkSegmentedButton(
            mode_card,
            values=["✉  Text Message", "📁  File Payload"],
            selected_color=VIOLET,
            selected_hover_color=VIOLET_HOVER,
            unselected_color=C_S3,
            unselected_hover_color=C_BORDER,
            text_color=C_TEXT,
            font=ctk.CTkFont("Segoe UI", 12),
            corner_radius=8,
            command=self._on_mode_change,
        )
        self.mode_seg.set("✉  Text Message")
        self.mode_seg.grid(row=1, column=0, padx=20, pady=(0, 18), sticky="ew")

        # Text sub-panel
        self._text_sub = ctk.CTkFrame(mode_card, fg_color="transparent")
        self._text_sub.grid(row=2, column=0, sticky="ew", padx=20, pady=(0, 18))
        self._text_sub.grid_columnconfigure(0, weight=1)

        TitleLabel(self._text_sub, "Secret message to hide:").grid(
            row=0, column=0, sticky="w", pady=(0, 8)
        )

        self.txt_secret = ctk.CTkTextbox(
            self._text_sub,
            height=200,
            font=ctk.CTkFont("Consolas", 12),
            fg_color=C_S1,
            border_color=C_BORDER,
            border_width=1,
            corner_radius=8,
            wrap="word",
            text_color=C_TEXT,
        )
        self.txt_secret.grid(row=1, column=0, sticky="ew")

        # File sub-panel
        self._file_sub = ctk.CTkFrame(mode_card, fg_color="transparent")
        self._file_sub.grid_columnconfigure(0, weight=1)

        TitleLabel(self._file_sub, "Choose file to embed:").grid(
            row=0, column=0, sticky="w", pady=(0, 10)
        )
        SecondaryButton(
            self._file_sub, text="📂  Browse File…", command=self._select_encode_file
        ).grid(row=1, column=0, sticky="ew")

        self._lbl_file_sel = ctk.CTkLabel(
            self._file_sub,
            text="No file selected",
            font=ctk.CTkFont("Segoe UI", 11),
            text_color=C_MUTED,
            wraplength=360,
            anchor="w",
            justify="left",
        )
        self._lbl_file_sel.grid(row=2, column=0, sticky="w", pady=(8, 0))

        # ── Right column ─────────────────────
        right = ctk.CTkScrollableFrame(self.encode_view, fg_color="transparent")
        right.grid(row=0, column=1, sticky="nsew", padx=(12, 0))
        right.grid_columnconfigure(0, weight=1)

        # Carrier host card
        host_card = Card(right)
        host_card.grid(row=0, column=0, sticky="ew", pady=(0, 14))
        host_card.grid_columnconfigure(0, weight=1)

        SectionLabel(host_card, "CARRIER HOST (OPTIONAL)").grid(
            row=0, column=0, padx=20, pady=(16, 4), sticky="w"
        )
        ctk.CTkLabel(
            host_card,
            text="Embed invisibly inside an existing text file.",
            font=ctk.CTkFont("Segoe UI", 11),
            text_color=C_MUTED,
            anchor="w",
        ).grid(row=1, column=0, padx=20, pady=(0, 10), sticky="w")
        SecondaryButton(
            host_card, text="📄  Browse Host File…", command=self._select_encode_host
        ).grid(row=2, column=0, padx=20, pady=(0, 10), sticky="ew")
        self._lbl_host_sel = ctk.CTkLabel(
            host_card,
            text="None — pure invisible output",
            font=ctk.CTkFont("Segoe UI", 11),
            text_color=C_MUTED,
            wraplength=280,
            anchor="w",
            justify="left",
        )
        self._lbl_host_sel.grid(row=3, column=0, padx=20, pady=(0, 16), sticky="w")

        # Compression card
        comp_card = Card(right)
        comp_card.grid(row=1, column=0, sticky="ew", pady=(0, 14))
        comp_card.grid_columnconfigure(0, weight=1)

        SectionLabel(comp_card, "COMPRESSION").grid(
            row=0, column=0, padx=20, pady=(16, 10), sticky="w"
        )
        self._comp_opt = ctk.CTkOptionMenu(
            comp_card,
            values=["Auto — best ratio", "gzip", "lzma", "brotli", "None"],
            fg_color=C_S3,
            button_color=C_BORDER,
            button_hover_color=VIOLET,
            dropdown_fg_color=C_S2,
            dropdown_text_color=C_TEXT,
            dropdown_hover_color=C_S3,
            text_color=C_TEXT,
            font=ctk.CTkFont("Segoe UI", 12),
            corner_radius=8,
        )
        self._comp_opt.grid(row=1, column=0, padx=20, pady=(0, 18), sticky="ew")

        # Encryption card
        enc_card = Card(right)
        enc_card.grid(row=2, column=0, sticky="ew", pady=(0, 14))
        enc_card.grid_columnconfigure(0, weight=1)

        SectionLabel(enc_card, "ENCRYPTION").grid(
            row=0, column=0, padx=20, pady=(16, 10), sticky="w"
        )
        self._encrypt_var = tk.BooleanVar(value=False)
        ctk.CTkCheckBox(
            enc_card,
            text="AES-256-GCM encryption",
            variable=self._encrypt_var,
            font=ctk.CTkFont("Segoe UI", 12),
            text_color=C_TEXT,
            fg_color=VIOLET,
            hover_color=VIOLET_HOVER,
            checkmark_color="#FFFFFF",
            corner_radius=5,
            command=self._toggle_enc_pw,
        ).grid(row=1, column=0, padx=20, pady=(0, 10), sticky="w")

        self._enc_pw_frame = ctk.CTkFrame(enc_card, fg_color="transparent")
        self._enc_pw_frame.grid_columnconfigure(0, weight=1)

        TitleLabel(self._enc_pw_frame, "Password:").grid(
            row=0, column=0, sticky="w", padx=20, pady=(0, 6)
        )
        pw_row = ctk.CTkFrame(self._enc_pw_frame, fg_color="transparent")
        pw_row.grid(row=1, column=0, sticky="ew", padx=20, pady=(0, 14))
        pw_row.grid_columnconfigure(0, weight=1)

        self._entry_enc_pw = ctk.CTkEntry(
            pw_row,
            show="●",
            placeholder_text="Enter a strong password…",
            fg_color=C_S1,
            border_color=C_BORDER,
            border_width=1,
            corner_radius=8,
            height=38,
            font=ctk.CTkFont("Segoe UI", 12),
            text_color=C_TEXT,
        )
        self._entry_enc_pw.grid(row=0, column=0, sticky="ew")
        ctk.CTkButton(
            pw_row,
            text="👁",
            width=38,
            height=38,
            fg_color=C_S3,
            hover_color=C_BORDER,
            text_color=C_TEXT,
            corner_radius=8,
            font=ctk.CTkFont("Segoe UI", 14),
            command=lambda: self._toggle_pw_vis(self._entry_enc_pw),
        ).grid(row=0, column=1, padx=(8, 0))

        # Output card
        out_card = Card(right)
        out_card.grid(row=3, column=0, sticky="ew", pady=(0, 14))
        out_card.grid_columnconfigure(0, weight=1)

        SectionLabel(out_card, "OUTPUT DESTINATION").grid(
            row=0, column=0, padx=20, pady=(16, 10), sticky="w"
        )
        SecondaryButton(
            out_card, text="💾  Choose Save Location…", command=self._select_encode_save
        ).grid(row=1, column=0, padx=20, pady=(0, 8), sticky="ew")
        self._lbl_enc_save = ctk.CTkLabel(
            out_card,
            text=f"📄  {self.encode_save_path}",
            font=ctk.CTkFont("Consolas", 11),
            text_color=C_SUCCESS_TXT,
            anchor="w",
        )
        self._lbl_enc_save.grid(row=2, column=0, padx=20, pady=(0, 16), sticky="w")

        # Action card
        action_card = Card(right)
        action_card.grid(row=4, column=0, sticky="ew")
        action_card.grid_columnconfigure(0, weight=1)

        self._lbl_enc_status = ctk.CTkLabel(
            action_card,
            text="Ready to encode",
            font=ctk.CTkFont("Segoe UI", 11),
            text_color=C_MUTED,
        )
        self._lbl_enc_status.grid(row=0, column=0, padx=20, pady=(16, 8))

        self._enc_progress = ctk.CTkProgressBar(
            action_card,
            fg_color=C_S3,
            progress_color=VIOLET,
            corner_radius=4,
            height=4,
        )
        self._enc_progress.set(0)

        self._btn_encode = PrimaryButton(
            action_card,
            text="⚡  Hide & Create Payload",
            command=self._start_encode,
        )
        self._btn_encode.grid(row=2, column=0, padx=20, pady=(8, 20), sticky="ew")

    # ─────────────────────────────────────────────────────
    #  DECODE VIEW
    # ─────────────────────────────────────────────────────
    def _build_decode_view(self):
        self.decode_view = ctk.CTkFrame(self.content_host, fg_color="transparent")
        self.decode_view.grid_columnconfigure(0, weight=2, minsize=380)
        self.decode_view.grid_columnconfigure(1, weight=3, minsize=420)
        self.decode_view.grid_rowconfigure(0, weight=1)

        # ── Left: settings ────────────────────
        left = ctk.CTkScrollableFrame(self.decode_view, fg_color="transparent")
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        left.grid_columnconfigure(0, weight=1)

        src_card = Card(left)
        src_card.grid(row=0, column=0, sticky="ew", pady=(0, 14))
        src_card.grid_columnconfigure(0, weight=1)

        SectionLabel(src_card, "CARRIER FILE").grid(
            row=0, column=0, padx=20, pady=(16, 6), sticky="w"
        )
        ctk.CTkLabel(
            src_card,
            text="Select the text file with the hidden payload.",
            font=ctk.CTkFont("Segoe UI", 11),
            text_color=C_MUTED,
            anchor="w",
        ).grid(row=1, column=0, padx=20, pady=(0, 10), sticky="w")
        SecondaryButton(
            src_card, text="📂  Open Carrier File…", command=self._select_decode_src
        ).grid(row=2, column=0, padx=20, pady=(0, 10), sticky="ew")
        self._lbl_dec_src = ctk.CTkLabel(
            src_card,
            text="No file selected",
            font=ctk.CTkFont("Segoe UI", 11),
            text_color=C_MUTED,
            wraplength=280,
            anchor="w",
            justify="left",
        )
        self._lbl_dec_src.grid(row=3, column=0, padx=20, pady=(0, 16), sticky="w")

        opt_card = Card(left)
        opt_card.grid(row=1, column=0, sticky="ew", pady=(0, 14))
        opt_card.grid_columnconfigure(0, weight=1)

        SectionLabel(opt_card, "OPTIONS").grid(
            row=0, column=0, padx=20, pady=(16, 12), sticky="w"
        )
        self._dec_media_var = tk.BooleanVar(value=False)
        ctk.CTkCheckBox(
            opt_card,
            text="Payload is a media / binary file",
            variable=self._dec_media_var,
            font=ctk.CTkFont("Segoe UI", 12),
            text_color=C_TEXT,
            fg_color=EMERALD,
            hover_color=EMERALD_HOVER,
            checkmark_color="#FFFFFF",
            corner_radius=5,
        ).grid(row=1, column=0, padx=20, pady=(0, 16), sticky="w")

        dec_enc_card = Card(left)
        dec_enc_card.grid(row=2, column=0, sticky="ew", pady=(0, 14))
        dec_enc_card.grid_columnconfigure(0, weight=1)

        SectionLabel(dec_enc_card, "DECRYPTION").grid(
            row=0, column=0, padx=20, pady=(16, 6), sticky="w"
        )
        ctk.CTkLabel(
            dec_enc_card,
            text="Leave blank if the payload is not encrypted.",
            font=ctk.CTkFont("Segoe UI", 11),
            text_color=C_MUTED,
        ).grid(row=1, column=0, padx=20, pady=(0, 10), sticky="w")

        dec_pw_row = ctk.CTkFrame(dec_enc_card, fg_color="transparent")
        dec_pw_row.grid(row=2, column=0, sticky="ew", padx=20, pady=(0, 16))
        dec_pw_row.grid_columnconfigure(0, weight=1)

        self._entry_dec_pw = ctk.CTkEntry(
            dec_pw_row,
            show="●",
            placeholder_text="Decryption password…",
            fg_color=C_S1,
            border_color=C_BORDER,
            border_width=1,
            corner_radius=8,
            height=38,
            font=ctk.CTkFont("Segoe UI", 12),
            text_color=C_TEXT,
        )
        self._entry_dec_pw.grid(row=0, column=0, sticky="ew")
        ctk.CTkButton(
            dec_pw_row,
            text="👁",
            width=38,
            height=38,
            fg_color=C_S3,
            hover_color=C_BORDER,
            text_color=C_TEXT,
            corner_radius=8,
            font=ctk.CTkFont("Segoe UI", 14),
            command=lambda: self._toggle_pw_vis(self._entry_dec_pw),
        ).grid(row=0, column=1, padx=(8, 0))

        dec_action = Card(left)
        dec_action.grid(row=3, column=0, sticky="ew")
        dec_action.grid_columnconfigure(0, weight=1)

        self._lbl_dec_status = ctk.CTkLabel(
            dec_action,
            text="Ready to decode",
            font=ctk.CTkFont("Segoe UI", 11),
            text_color=C_MUTED,
        )
        self._lbl_dec_status.grid(row=0, column=0, padx=20, pady=(16, 8))

        self._dec_progress = ctk.CTkProgressBar(
            dec_action,
            fg_color=C_S3,
            progress_color=EMERALD,
            corner_radius=4,
            height=4,
        )
        self._dec_progress.set(0)

        self._btn_decode = SuccessButton(
            dec_action,
            text="🔍  Reveal & Extract Secret",
            command=self._start_decode,
        )
        self._btn_decode.grid(row=2, column=0, padx=20, pady=(8, 20), sticky="ew")

        # ── Right: output ──────────────────────
        right_wrap = ctk.CTkFrame(self.decode_view, fg_color="transparent")
        right_wrap.grid(row=0, column=1, sticky="nsew", padx=(12, 0))
        right_wrap.grid_columnconfigure(0, weight=1)
        right_wrap.grid_rowconfigure(1, weight=1)

        out_hdr = Card(right_wrap)
        out_hdr.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        out_hdr.grid_columnconfigure(0, weight=1)

        SectionLabel(out_hdr, "EXTRACTED OUTPUT").grid(
            row=0, column=0, padx=20, pady=(16, 4), sticky="w"
        )
        self._lbl_out_desc = ctk.CTkLabel(
            out_hdr,
            text="Decoded text or file will appear here after extraction.",
            font=ctk.CTkFont("Segoe UI", 11),
            text_color=C_MUTED,
            anchor="w",
        )
        self._lbl_out_desc.grid(row=1, column=0, padx=20, pady=(0, 14), sticky="w")

        self._txt_dec_output = ctk.CTkTextbox(
            right_wrap,
            font=ctk.CTkFont("Consolas", 12),
            fg_color=C_S2,
            border_color=C_BORDER,
            border_width=1,
            corner_radius=10,
            wrap="word",
            text_color=C_TEXT,
        )
        self._txt_dec_output.grid(row=1, column=0, sticky="nsew")

        self._dl_panel = Card(right_wrap)
        self._dl_panel.grid_columnconfigure(0, weight=1)

        self._lbl_dl_info = ctk.CTkLabel(
            self._dl_panel,
            text="📦  Binary File Payload Detected",
            font=ctk.CTkFont("Segoe UI", 13, "bold"),
            text_color=C_SUCCESS_TXT,
        )
        self._lbl_dl_info.grid(row=0, column=0, padx=20, pady=(16, 4), sticky="w")

        self._lbl_dl_name = ctk.CTkLabel(
            self._dl_panel,
            text="",
            font=ctk.CTkFont("Consolas", 11),
            text_color=C_SUB,
        )
        self._lbl_dl_name.grid(row=1, column=0, padx=20, pady=(0, 12), sticky="w")

        SuccessButton(
            self._dl_panel,
            text="💾  Save Extracted File…",
            command=self._save_decoded_file,
        ).grid(row=2, column=0, padx=20, pady=(0, 20), sticky="ew")

    # ─────────────────────────────────────────────────────
    #  ABOUT VIEW
    # ─────────────────────────────────────────────────────
    def _build_about_view(self):
        self.about_view = ctk.CTkScrollableFrame(
            self.content_host, fg_color="transparent"
        )
        self.about_view.grid_columnconfigure(0, weight=1)

        sections = [
            ("What is Project Invisible?",
             "Project Invisible converts any file or message into invisible zero-width Unicode characters "
             "(U+200B, U+200C, U+200D, U+2060). The output looks completely empty to the human eye — yet "
             "carries your payload byte-perfect. Combined with AES-256-GCM encryption, decryption is "
             "computationally infeasible without the correct password."),
            ("How to Hide a Secret",
             "1. Open the 'Hide Secret' tab.\n"
             "2. Select 'Text Message' or 'File Payload'.\n"
             "3. Optionally pick a Carrier Host file.\n"
             "4. Choose a Compression mode (Auto picks the best).\n"
             "5. Enable AES-256-GCM and set a password for encryption.\n"
             "6. Click 'Hide & Create Payload' — the output folder opens automatically."),
            ("How to Reveal a Secret",
             "1. Open the 'Reveal Secret' tab.\n"
             "2. Browse for the encoded carrier text file.\n"
             "3. Enter the decryption password if the payload was encrypted.\n"
             "4. Click 'Reveal & Extract Secret'.\n"
             "5. Text is shown inline; binary files can be saved to disk."),
            ("Encryption (AES-256-GCM)",
             "• Algorithm: AES-256 in Galois/Counter Mode\n"
             "• Key derivation: PBKDF2-HMAC-SHA256 · 1 000 000 iterations\n"
             "• Salt: random 16 bytes (unique per payload)\n"
             "• Nonce: random 12 bytes\n"
             "• GCM authentication detects any tampering"),
            ("Compression Engine",
             "Auto mode tries Gzip, LZMA, and Brotli then keeps the smallest:\n"
             "• Brotli  — 75–95 % savings on text/HTML\n"
             "• LZMA    — 80–90 % savings, best for structured data\n"
             "• Gzip    — 70–85 % savings, always available"),
            ("Contributors",
             "Original CLI steganography engine:\n"
             "  DarkShadow (@darkshadow2bd)  ·  X: @darkshadow2bd  ·  Telegram: t.me/ShellSec\n\n"
             "Windows Native GUI:\n"
             "  Imran Hossain (@ImranVibes)"),
        ]

        for i, (title, body) in enumerate(sections):
            card = Card(self.about_view)
            card.grid(row=i, column=0, sticky="ew", pady=(0, 14))
            card.grid_columnconfigure(0, weight=1)

            ctk.CTkLabel(
                card,
                text=title,
                font=ctk.CTkFont("Segoe UI", 14, "bold"),
                text_color=C_ACCENT_TEXT,
                anchor="w",
            ).grid(row=0, column=0, padx=20, pady=(18, 8), sticky="w")

            ctk.CTkLabel(
                card,
                text=body,
                font=ctk.CTkFont("Segoe UI", 12),
                text_color=C_SUB,
                wraplength=780,
                anchor="w",
                justify="left",
            ).grid(row=1, column=0, padx=20, pady=(0, 18), sticky="w")

    # ─────────────────────────────────────────────────────
    #  TAB SWITCHING
    # ─────────────────────────────────────────────────────
    def select_tab(self, tab):
        self._current_tab = tab
        titles = {"encode": "Hide Secret", "decode": "Reveal Secret", "about": "Guide"}
        self._topbar_title.configure(text=titles.get(tab, ""))

        for key, btn in self._nav_btns.items():
            if key == tab:
                btn.configure(fg_color=VIOLET, text_color="#FFFFFF")
            else:
                btn.configure(fg_color="transparent", text_color=C_SUB)

        for view in (self.encode_view, self.decode_view, self.about_view):
            view.grid_forget()

        if tab == "encode":
            self.encode_view.grid(row=1, column=0, sticky="nsew")
        elif tab == "decode":
            self.decode_view.grid(row=1, column=0, sticky="nsew")
        elif tab == "about":
            self.about_view.grid(row=1, column=0, sticky="nsew")

    # ─────────────────────────────────────────────────────
    #  THEME SWITCHING
    #  CTk handles ALL widget recoloring automatically when
    #  colors are defined as (light, dark) tuples.
    #  We only need to update the window background.
    # ─────────────────────────────────────────────────────
    def _on_theme_change(self, mode):
        ctk.set_appearance_mode(mode)
        self.configure(fg_color=C_BASE)   # window bg uses tuple too

    # ─────────────────────────────────────────────────────
    #  UI HELPERS
    # ─────────────────────────────────────────────────────
    def _toggle_pw_vis(self, entry):
        entry.configure(show="" if entry.cget("show") == "●" else "●")

    def _toggle_enc_pw(self):
        if self._encrypt_var.get():
            self._enc_pw_frame.grid(row=2, column=0, sticky="ew")
        else:
            self._enc_pw_frame.grid_forget()

    def _on_mode_change(self, mode):
        if "Text" in mode:
            self.encode_payload_mode = "text"
            self._file_sub.grid_forget()
            self._text_sub.grid(row=2, column=0, sticky="ew", padx=20, pady=(0, 18))
        else:
            self.encode_payload_mode = "file"
            self._text_sub.grid_forget()
            self._file_sub.grid(row=2, column=0, sticky="ew", padx=20, pady=(0, 18))

    def _fmt_bytes(self, n):
        if n < 1024:      return f"{n} B"
        if n < 1024**2:   return f"{n/1024:.1f} KB"
        return f"{n/(1024**2):.2f} MB"

    # ── File dialogs ─────────────────────────────────────
    def _select_encode_file(self):
        p = filedialog.askopenfilename(title="Select File to Hide")
        if not p: return
        if not os.path.isfile(p):
            messagebox.showerror("File Not Found", f"Cannot access:\n{p}"); return
        if not os.access(p, os.R_OK):
            messagebox.showerror("Permission Denied", f"No read access:\n{p}"); return
        try:
            size = os.path.getsize(p)
        except OSError as e:
            messagebox.showerror("File Error", f"Could not read file info:\n{e}"); return
        self.encode_file_path = p
        self._lbl_file_sel.configure(
            text=f"📄  {os.path.basename(p)}  ({self._fmt_bytes(size)})",
            text_color=C_ACCENT_TEXT,
        )

    def _select_encode_host(self):
        p = filedialog.askopenfilename(
            title="Select Carrier Host File",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
        )
        if p:
            if not os.access(p, os.R_OK):
                messagebox.showerror("Permission Denied", f"Cannot read:\n{p}"); return
            self.encode_host_path = p
            self._lbl_host_sel.configure(
                text=f"📄  {os.path.basename(p)}", text_color=C_ACCENT_TEXT
            )
        else:
            self.encode_host_path = ""
            self._lbl_host_sel.configure(
                text="None — pure invisible output", text_color=C_MUTED
            )

    def _select_encode_save(self):
        p = filedialog.asksaveasfilename(
            title="Save Encoded Output As",
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
        )
        if p:
            directory = os.path.dirname(p) or "."
            if not os.access(directory, os.W_OK):
                messagebox.showerror("Permission Denied", f"Cannot write to:\n{directory}"); return
            self.encode_save_path = p
            self._lbl_enc_save.configure(text=f"📄  {os.path.basename(p)}")

    def _select_decode_src(self):
        p = filedialog.askopenfilename(
            title="Open Carrier File",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
        )
        if not p: return
        if not os.path.isfile(p):
            messagebox.showerror("File Not Found", f"Cannot find:\n{p}"); return
        if not os.access(p, os.R_OK):
            messagebox.showerror("Permission Denied", f"Cannot read:\n{p}"); return
        self.decode_input_file = p
        self._lbl_dec_src.configure(
            text=f"📄  {os.path.basename(p)}", text_color=C_SUCCESS_TXT
        )

    def _save_decoded_file(self):
        if not self.decoded_payload_bytes:
            messagebox.showwarning("Nothing to Save", "Run 'Reveal & Extract' first."); return
        p = filedialog.asksaveasfilename(
            title="Save Extracted File",
            initialfile=self.decoded_filename or "extracted_payload",
            filetypes=[("All files", "*.*")],
        )
        if not p: return
        directory = os.path.dirname(p) or "."
        if not os.access(directory, os.W_OK):
            messagebox.showerror("Permission Denied", f"Cannot write to:\n{directory}"); return
        try:
            with open(p, "wb") as f:
                f.write(self.decoded_payload_bytes)
            messagebox.showinfo("Saved", f"File saved to:\n{p}")
        except OSError as e:
            messagebox.showerror("Save Failed", f"Could not write file:\n{e}")

    # ─────────────────────────────────────────────────────
    #  ENCODE PIPELINE
    # ─────────────────────────────────────────────────────
    def _start_encode(self):
        if self.encode_payload_mode == "text":
            if not self.txt_secret.get("1.0", "end-1c").strip():
                messagebox.showerror("Empty Payload",
                    "The message box is empty.\nPlease type the text you want to hide."); return
        else:
            if not self.encode_file_path:
                messagebox.showerror("No File", "Please select a file to embed."); return
            if not os.path.isfile(self.encode_file_path):
                messagebox.showerror("File Not Found",
                    f"The file no longer exists:\n{self.encode_file_path}\n\nPlease re-select it.")
                self.encode_file_path = ""; return
            if not os.access(self.encode_file_path, os.R_OK):
                messagebox.showerror("Permission Denied",
                    f"Cannot read:\n{self.encode_file_path}"); return

        if self._encrypt_var.get():
            if not HAS_CRYPTO:
                messagebox.showerror("Missing Dependency",
                    "AES-256-GCM requires the 'cryptography' package.\n\n"
                    "Install with:  pip install cryptography"); return
            pw = self._entry_enc_pw.get()
            if not pw:
                messagebox.showerror("No Password",
                    "Please enter a password or uncheck encryption."); return
            if len(pw) < 6:
                if not messagebox.askyesno("Weak Password",
                    "Password is very short (< 6 chars).\n"
                    "This weakens encryption significantly.\n\nContinue anyway?"): return

        if self._comp_opt.get() == "brotli" and not HAS_BROTLI:
            messagebox.showerror("Missing Dependency",
                "Brotli requires the 'brotli' package.\n\n"
                "Install with:  pip install brotli\n\nOr choose a different algorithm."); return

        out_dir = os.path.dirname(self.encode_save_path) or "."
        if not os.path.isdir(out_dir):
            messagebox.showerror("Invalid Path", f"Output folder doesn't exist:\n{out_dir}"); return
        if not os.access(out_dir, os.W_OK):
            messagebox.showerror("Permission Denied", f"Cannot write to:\n{out_dir}"); return

        self._btn_encode.configure(state="disabled", text="Encoding…")
        self._enc_progress.grid(row=1, column=0, padx=20, pady=(0, 4), sticky="ew")
        self._enc_progress.set(0)
        self._lbl_enc_status.configure(text="Starting…", text_color=C_MUTED)
        threading.Thread(target=self._encode_thread, daemon=True).start()

    def _encode_thread(self):
        try:
            try:
                if self.encode_payload_mode == "text":
                    raw = self.txt_secret.get("1.0", "end-1c").encode("utf-8")
                    is_media, preset_name = False, ""
                else:
                    raw = en.read_file_binary(self.encode_file_path)
                    is_media = en.is_compressed_extension(self.encode_file_path)
                    preset_name = os.path.basename(self.encode_file_path)
            except (IOError, OSError) as e:
                raise RuntimeError(f"Cannot read payload file:\n{e}")
            except MemoryError:
                raise RuntimeError("File too large to load into memory.")

            self.after(0, lambda: (self._enc_progress.set(0.15),
                self._lbl_enc_status.configure(text="Compressing…")))

            try:
                sel = self._comp_opt.get()
                if sel.startswith("Auto"):
                    comp, algo, _ = en.try_best_compression(raw, verbose=False)
                elif sel == "None":
                    comp, algo = raw, en.ALGO_NONE
                else:
                    import gzip as _gz, lzma as _lz
                    comp_map = {
                        "gzip":   (en.ALGO_GZIP,   lambda d: _gz.compress(d)),
                        "lzma":   (en.ALGO_LZMA,   lambda d: _lz.compress(d)),
                        "brotli": (en.ALGO_BROTLI, lambda d: _brotli.compress(d)),
                    }
                    algo, fn = comp_map.get(sel, (en.ALGO_NONE, lambda d: d))
                    comp = fn(raw)
            except Exception as e:
                raise RuntimeError(f"Compression failed:\n{e}")

            self.after(0, lambda: (self._enc_progress.set(0.40),
                self._lbl_enc_status.configure(
                    text="Encrypting…" if self._encrypt_var.get() else "Building payload…")))

            if self._encrypt_var.get():
                try:
                    comp = en.encrypt(comp, self._entry_enc_pw.get())
                except Exception as e:
                    raise RuntimeError(f"Encryption failed:\n{e}")

            self.after(0, lambda: self._enc_progress.set(0.65))
            self.after(0, lambda: self._lbl_enc_status.configure(
                text="Encoding to zero-width characters…"))

            try:
                flags = en.FLAG_MEDIA if is_media else 0
                invisible = en.bytes_to_invisible(comp, preset_name, algo, flags, prog=None)
            except Exception as e:
                raise RuntimeError(f"Zero-width encoding failed:\n{e}")

            self.after(0, lambda: self._enc_progress.set(0.85))

            try:
                if self.encode_host_path and os.path.isfile(self.encode_host_path):
                    host = en.read_file_text(self.encode_host_path)
                    final = host + invisible
                else:
                    final = invisible
                en.write_file_text(self.encode_save_path, final)
            except (IOError, OSError) as e:
                raise RuntimeError(
                    f"Could not write output file:\n{e}\n\n"
                    "Check the destination folder exists and you have write permission.")

            self.after(0, lambda n=len(invisible): self._encode_done(n))

        except Exception as ex:
            traceback.print_exc()
            self.after(0, lambda e=ex: self._encode_fail(e))

    def _encode_done(self, char_count):
        self._btn_encode.configure(state="normal", text="⚡  Hide & Create Payload")
        self._enc_progress.set(1.0)
        self._lbl_enc_status.configure(
            text=f"✓  Done — {char_count:,} invisible characters written",
            text_color=C_SUCCESS_TXT,
        )
        messagebox.showinfo(
            "Encoding Complete",
            f"Payload successfully hidden!\n\nSaved to: {self.encode_save_path}\n"
            f"Invisible characters: {char_count:,}\n\n"
            "The output folder will now open with the file selected.",
        )
        try:
            subprocess.Popen(["explorer", "/select,", os.path.abspath(self.encode_save_path)])
        except Exception:
            pass

    def _encode_fail(self, err):
        self._btn_encode.configure(state="normal", text="⚡  Hide & Create Payload")
        self._enc_progress.grid_forget()
        self._lbl_enc_status.configure(text="✕  Encoding failed", text_color=RUBY)
        messagebox.showerror("Encoding Failed",
            f"{err}\n\nIf this persists, report it to the contributors.")

    # ─────────────────────────────────────────────────────
    #  DECODE PIPELINE
    # ─────────────────────────────────────────────────────
    def _start_decode(self):
        if not self.decode_input_file:
            messagebox.showerror("No File", "Please select a carrier file first."); return
        if not os.path.isfile(self.decode_input_file):
            messagebox.showerror("File Not Found",
                f"File no longer exists:\n{self.decode_input_file}\n\nPlease re-select it.")
            self.decode_input_file = ""
            self._lbl_dec_src.configure(text="No file selected", text_color=C_MUTED); return
        if not os.access(self.decode_input_file, os.R_OK):
            messagebox.showerror("Permission Denied",
                f"Cannot read:\n{self.decode_input_file}"); return

        self._dl_panel.grid_forget()
        self._txt_dec_output.delete("1.0", "end")
        self._btn_decode.configure(state="disabled", text="Decoding…")
        self._dec_progress.grid(row=1, column=0, padx=20, pady=(0, 4), sticky="ew")
        self._dec_progress.set(0)
        self._lbl_dec_status.configure(text="Loading file…", text_color=C_MUTED)
        threading.Thread(target=self._decode_thread, daemon=True).start()

    def _decode_thread(self):
        try:
            try:
                with open(self.decode_input_file, "r", encoding="utf-8") as f:
                    encoded_text = f.read()
            except UnicodeDecodeError:
                raise ValueError(
                    "This file is not valid UTF-8 text.\n\n"
                    "Project Invisible outputs are always UTF-8 text files.\n"
                    "You may have selected a binary file by mistake.")
            except (IOError, OSError) as e:
                raise RuntimeError(f"Cannot read carrier file:\n{e}")

            if not encoded_text.strip():
                raise ValueError("The file is empty — no hidden payload to extract.")

            self.after(0, lambda: (self._dec_progress.set(0.20),
                self._lbl_dec_status.configure(text="Scanning for invisible characters…")))

            try:
                raw, output_name = de.invisible_to_bytes(encoded_text, prog=None)
            except Exception as e:
                raise RuntimeError(f"Failed to parse invisible characters:\n{e}")

            if not raw:
                raise ValueError(
                    "No hidden payload found in this file.\n\n"
                    "Possible causes:\n"
                    "  • File was not encoded with Project Invisible\n"
                    "  • Invisible characters were stripped by another app\n"
                    "  • File was corrupted or altered after encoding")

            self.after(0, lambda: self._dec_progress.set(0.45))

            if len(raw) >= 3 and raw[:3] == de.V3_MAGIC:
                if len(raw) < 6:
                    raise ValueError("Payload header is truncated or corrupted.")
                algo, flags, name_len = raw[3], raw[4], raw[5]
                if 6 + name_len > len(raw):
                    raise ValueError("Header filename length is invalid — file may be corrupted.")
                if name_len > 0:
                    output_name = raw[6:6+name_len].decode("utf-8", errors="replace")
                payload = raw[6+name_len:]
                if not payload:
                    raise ValueError("Payload is empty after the header — file may be truncated.")

                pw = self._entry_dec_pw.get()
                if pw:
                    if not HAS_CRYPTO:
                        raise RuntimeError(
                            "Decryption requires 'cryptography'.\n\nInstall with: pip install cryptography")
                    self.after(0, lambda: self._lbl_dec_status.configure(text="Decrypting…"))
                    try:
                        payload = de.decrypt(payload, pw)
                    except Exception:
                        raise ValueError(
                            "Decryption failed — wrong password or corrupted data.\n\n"
                            "Passwords are case-sensitive.")

                self.after(0, lambda: (self._dec_progress.set(0.70),
                    self._lbl_dec_status.configure(text="Decompressing…")))

                try:
                    raw = de.decompress_v3(payload, algo)
                except ImportError as e:
                    raise RuntimeError(f"Missing library: {e}\n\nInstall with: pip install brotli")
                except Exception as e:
                    hint = ("\n\nHint: Wrong password can cause decompression failure."
                            if self._entry_dec_pw.get() else
                            "\n\nHint: If payload was encrypted, enter the password and try again.")
                    raise ValueError(f"Decompression failed — data may be corrupted.{hint}\n\nDetail: {e}")
            else:
                pw = self._entry_dec_pw.get()
                if pw:
                    if not HAS_CRYPTO:
                        raise RuntimeError(
                            "Decryption requires 'cryptography'.\n\nInstall with: pip install cryptography")
                    try:
                        raw = de.decrypt(raw, pw)
                    except Exception:
                        raise ValueError(
                            "Decryption failed — wrong password or corrupted data.")

            self.after(0, lambda: self._dec_progress.set(0.90))
            self.after(0, lambda rb=raw, fn=output_name: self._decode_done(rb, fn))

        except Exception as ex:
            traceback.print_exc()
            self.after(0, lambda e=ex: self._decode_fail(e))

    def _decode_done(self, payload_bytes, output_name):
        self._btn_decode.configure(state="normal", text="🔍  Reveal & Extract Secret")
        self._dec_progress.set(1.0)
        self.decoded_payload_bytes = payload_bytes
        self.decoded_filename      = output_name

        try:
            text = payload_bytes.decode("utf-8")
            if "\x00" in text:
                raise UnicodeDecodeError("", b"", 0, 1, "null byte")
            self._txt_dec_output.delete("1.0", "end")
            self._txt_dec_output.insert("1.0", text)
            self._lbl_out_desc.configure(
                text=f"Text payload — {len(payload_bytes):,} chars",
                text_color=C_SUCCESS_TXT,
            )
            self._lbl_dec_status.configure(
                text="✓  Text extracted successfully", text_color=C_SUCCESS_TXT
            )
            messagebox.showinfo("Extracted",
                "The hidden message has been extracted and is shown in the output area.")
        except (UnicodeDecodeError, ValueError):
            name = output_name or "payload.bin"
            self._txt_dec_output.delete("1.0", "end")
            self._txt_dec_output.insert("1.0",
                f"[Binary file — cannot display as text]\n\n"
                f"File name : {name}\n"
                f"Size      : {self._fmt_bytes(len(payload_bytes))}\n\n"
                "Use 'Save Extracted File' below to write it to disk.")
            self._lbl_dl_name.configure(text=f"{name}  ·  {self._fmt_bytes(len(payload_bytes))}")
            self._dl_panel.grid(row=2, column=0, sticky="ew", pady=(10, 0))
            self._lbl_out_desc.configure(
                text="Binary file payload — save to disk below",
                text_color=C_WARN_TXT,
            )
            self._lbl_dec_status.configure(
                text="✓  Binary file extracted", text_color=C_SUCCESS_TXT
            )
            messagebox.showinfo("Extracted",
                f"Hidden binary file found!\n\nFile: {name}\nSize: {self._fmt_bytes(len(payload_bytes))}\n\n"
                "Use 'Save Extracted File' to save it.")

    def _decode_fail(self, err):
        self._btn_decode.configure(state="normal", text="🔍  Reveal & Extract Secret")
        self._dec_progress.grid_forget()
        self._lbl_dec_status.configure(text="✕  Extraction failed", text_color=RUBY)
        messagebox.showerror("Extraction Failed",
            f"{err}\n\nIf this persists, report it to the contributors.")


# ─────────────────────────────────────────────────────────
#  ENTRY POINT
# ─────────────────────────────────────────────────────────
if __name__ == "__main__":
    app = InvisibleGUI()
    app.mainloop()
