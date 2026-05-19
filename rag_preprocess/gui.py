from __future__ import annotations

from pathlib import Path


def ask_directory() -> Path | None:
    try:
        from tkinter import Tk, filedialog
    except Exception:
        return None

    root = Tk()
    root.withdraw()
    selected = filedialog.askdirectory(title="PDF dosyalarının bulunduğu klasörü seçin")
    root.destroy()
    return Path(selected) if selected else None


def show_info(title: str, message: str) -> None:
    try:
        from tkinter import Tk, messagebox

        root = Tk()
        root.withdraw()
        messagebox.showinfo(title, message)
        root.destroy()
    except Exception:
        print(f"{title}\n{message}")


def show_error(title: str, message: str) -> None:
    try:
        from tkinter import Tk, messagebox

        root = Tk()
        root.withdraw()
        messagebox.showerror(title, message)
        root.destroy()
    except Exception:
        print(f"{title}\n{message}")
