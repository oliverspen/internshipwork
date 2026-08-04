"""Interactive dialog system for pipeline mapping wizard.

Provides a set of reusable Tkinter dialogs for collecting user input in a
wizard-style interface. Dialogs support Back/Cancel navigation and maintain
consistent positioning across all prompts.
"""

import tkinter as tk
from tkinter import font as tkfont
from tkinter import messagebox

from .models import BackRequested, UserCancelled


# Global Tk root window and dialog positioning state
ROOT: tk.Tk | None = None
DIALOG_ORIGIN: tuple[int, int] | None = None


def init_dialog_root() -> None:
    """Initialize the hidden Tkinter root window and configure fonts."""
    global ROOT
    if ROOT is None:
        ROOT = tk.Tk()

        # Configure standard Tkinter fonts for consistent appearance
        default_font = tkfont.nametofont("TkDefaultFont")
        default_font.configure(family="Segoe UI", size=12)

        text_font = tkfont.nametofont("TkTextFont")
        text_font.configure(family="Segoe UI", size=12)

        fixed_font = tkfont.nametofont("TkFixedFont")
        fixed_font.configure(family="Consolas", size=11)

        heading_font = tkfont.nametofont("TkHeadingFont")
        heading_font.configure(family="Segoe UI", size=13)

        menu_font = tkfont.nametofont("TkMenuFont")
        menu_font.configure(family="Segoe UI", size=11)

        caption_font = tkfont.nametofont("TkCaptionFont")
        caption_font.configure(family="Segoe UI", size=11)

        ROOT.withdraw()


def prepare_dialog(dialog: tk.Toplevel, width: int, height: int) -> None:
    """Place dialogs in a consistent location and with a consistent size.
    
    All dialogs appear centered on screen at the same position to create
    a consistent step-by-step wizard feel.
    
    Args:
        dialog: The Toplevel window to position
        width: Dialog width in pixels
        height: Dialog height in pixels
    """
    init_dialog_root()
    global DIALOG_ORIGIN

    if DIALOG_ORIGIN is None:
        # Calculate center position once and reuse for all dialogs
        screen_w = ROOT.winfo_screenwidth() if ROOT is not None else 1920
        screen_h = ROOT.winfo_screenheight() if ROOT is not None else 1080
        x = max(20, (screen_w - width) // 2)
        y = max(20, (screen_h - height) // 2)
        DIALOG_ORIGIN = (x, y)

    x, y = DIALOG_ORIGIN
    dialog.geometry(f"{width}x{height}+{x}+{y}")


def show_modal_dialog(dialog: tk.Toplevel, focus_widget: tk.Widget | None = None) -> None:
    """Show a dialog as a modal window with consistent activation behavior.
    
    Ensures dialogs are shown on top and prevents interaction with other windows,
    enforcing strict step-by-step wizard progression.
    
    Args:
        dialog: The Toplevel window to show modally
        focus_widget: Optional widget to focus after dialog becomes active
    """
    # Modal setup prevents user from interacting with older dialogs out of order
    dialog.update_idletasks()
    dialog.lift()
    dialog.attributes("-topmost", True)
    dialog.after(100, lambda: dialog.attributes("-topmost", False))
    dialog.wait_visibility()
    dialog.grab_set()
    if focus_widget is not None:
        focus_widget.focus_set()
    dialog.focus_force()
    ROOT.wait_window(dialog)


def ask_yes_no_with_back(prompt: str) -> bool:
    """Ask a yes/no question with Back and Cancel options."""
    init_dialog_root()

    # state is stored outside nested callbacks so button handlers can update it.
    result: dict[str, str] = {"state": "open"}

    dialog = tk.Toplevel(ROOT)
    dialog.title("Pipe Mapping")
    dialog.resizable(False, False)
    prepare_dialog(dialog, width=700, height=210)

    tk.Label(dialog, text=prompt, wraplength=660, justify="left").pack(padx=16, pady=(18, 14), anchor="w")

    def on_yes() -> None:
        result["state"] = "yes"
        dialog.destroy()

    def on_no() -> None:
        result["state"] = "no"
        dialog.destroy()

    def on_back() -> None:
        result["state"] = "back"
        dialog.destroy()

    def on_cancel() -> None:
        result["state"] = "cancel"
        dialog.destroy()

    button_frame = tk.Frame(dialog)
    button_frame.pack(padx=12, pady=(0, 16))
    tk.Button(button_frame, text="Back", width=10, command=on_back).pack(side="left", padx=6)
    tk.Button(button_frame, text="Yes", width=10, command=on_yes).pack(side="left", padx=6)
    tk.Button(button_frame, text="No", width=10, command=on_no).pack(side="left", padx=6)
    tk.Button(button_frame, text="Cancel", width=10, command=on_cancel).pack(side="left", padx=6)

    dialog.bind("<Escape>", lambda _event: on_cancel())
    dialog.protocol("WM_DELETE_WINDOW", on_cancel)

    show_modal_dialog(dialog)

    state = result["state"]
    if state == "yes":
        return True
    if state == "no":
        return False
    if state == "back":
        raise BackRequested("User requested previous step from yes/no input.")
    raise UserCancelled("User cancelled yes/no input.")


def ask_non_empty_with_back(prompt: str, default: str | None = None) -> str:
    """Ask for text with Back/Cancel options for wizard-like navigation."""
    init_dialog_root()

    while True:
        # Each loop iteration creates a fresh dialog so invalid input simply
        # retries the same step without leaking previous widget state.
        result: dict[str, object] = {"state": "open", "value": ""}

        dialog = tk.Toplevel(ROOT)
        dialog.title("Pipe Mapping")
        dialog.resizable(False, False)
        prepare_dialog(dialog, width=760, height=240)

        tk.Label(dialog, text=prompt, wraplength=720, justify="left").pack(padx=16, pady=(18, 8), anchor="w")

        entry_var = tk.StringVar(value=default if default else "")
        entry = tk.Entry(dialog, textvariable=entry_var, width=60)
        entry.pack(padx=16, pady=(0, 14), fill="x")
        entry.selection_range(0, tk.END)

        def on_ok() -> None:
            value = entry_var.get().strip()
            if value:
                result["state"] = "ok"
                result["value"] = value
                dialog.destroy()
                return

            if default is not None:
                result["state"] = "ok"
                result["value"] = default
                dialog.destroy()
                return

            messagebox.showerror("Pipe Mapping", "Value cannot be empty.", parent=dialog)

        def on_back() -> None:
            result["state"] = "back"
            dialog.destroy()

        def on_cancel() -> None:
            result["state"] = "cancel"
            dialog.destroy()

        button_frame = tk.Frame(dialog)
        button_frame.pack(padx=12, pady=(0, 16))
        tk.Button(button_frame, text="Back", width=10, command=on_back).pack(side="left", padx=6)
        tk.Button(button_frame, text="OK", width=10, command=on_ok).pack(side="left", padx=6)
        tk.Button(button_frame, text="Cancel", width=10, command=on_cancel).pack(side="left", padx=6)

        dialog.bind("<Return>", lambda _event: on_ok())
        dialog.bind("<Escape>", lambda _event: on_cancel())
        dialog.protocol("WM_DELETE_WINDOW", on_cancel)

        show_modal_dialog(dialog, focus_widget=entry)

        state = result["state"]
        if state == "ok":
            return result["value"]  # type: ignore[return-value]
        if state == "back":
            raise BackRequested("User requested previous step from text input.")
        raise UserCancelled("User cancelled text input.")


def ask_select_nodes(
    prompt: str,
    allowed_nodes: set[str],
    min_sources: int = 1,
    allow_back: bool = False,
) -> list[str]:
    """Ask user to select one or more nodes from a pop-up checkbox dialog."""
    init_dialog_root()
    # Selections are sorted so the user sees a stable order from one dialog to the next.
    options = sorted(allowed_nodes)

    if not options:
        raise ValueError("No nodes available for selection.")

    if min_sources > len(options):
        raise ValueError(
            f"Need at least {min_sources} available node(s), but only {len(options)} exist."
        )

    if len(options) == 1 and min_sources <= 1:
        return [options[0]]

    while True:
        # The dialog returns the chosen node names in the same sorted order so
        # downstream graph updates remain predictable.
        result: dict[str, object] = {"ok": False, "selection": []}

        dialog = tk.Toplevel(ROOT)
        dialog.title("Pipe Mapping")
        dialog.resizable(False, False)
        prepare_dialog(dialog, width=760, height=560)

        tk.Label(dialog, text=prompt, wraplength=720, justify="left").pack(padx=16, pady=(18, 6), anchor="w")
        tk.Label(dialog, text=f"Select at least {min_sources} stream(s).", fg="dim gray").pack(
            padx=16,
            pady=(0, 10),
            anchor="w",
        )

        list_frame = tk.Frame(dialog)
        list_frame.pack(padx=16, pady=6, fill="both", expand=True)

        variables: dict[str, tk.BooleanVar] = {}
        for node_name in options:
            var = tk.BooleanVar(value=False)
            variables[node_name] = var
            tk.Checkbutton(list_frame, text=node_name, variable=var, anchor="w").pack(
                fill="x",
                anchor="w",
            )

        def select_all() -> None:
            for var in variables.values():
                var.set(True)

        def clear_all() -> None:
            for var in variables.values():
                var.set(False)

        quick_actions = tk.Frame(dialog)
        quick_actions.pack(padx=16, pady=(0, 10), anchor="w")
        tk.Button(quick_actions, text="Select all", command=select_all).pack(side="left", padx=(0, 6))
        tk.Button(quick_actions, text="Clear", command=clear_all).pack(side="left")

        def on_ok() -> None:
            selected = [name for name, var in variables.items() if var.get()]
            if len(selected) < min_sources:
                messagebox.showerror(
                    "Pipe Mapping",
                    f"Please select at least {min_sources} stream(s).",
                    parent=dialog,
                )
                return

            result["ok"] = True
            result["selection"] = selected
            dialog.destroy()

        def on_cancel() -> None:
            dialog.destroy()

        def on_back() -> None:
            result["ok"] = False
            result["selection"] = None
            dialog.destroy()

        button_frame = tk.Frame(dialog)
        button_frame.pack(padx=12, pady=(4, 16))
        if allow_back:
            tk.Button(button_frame, text="Back", width=10, command=on_back).pack(side="left", padx=6)
        tk.Button(button_frame, text="OK", width=10, command=on_ok).pack(side="left", padx=6)
        tk.Button(button_frame, text="Cancel", width=10, command=on_cancel).pack(side="left", padx=6)

        dialog.bind("<Return>", lambda _event: on_ok())
        dialog.bind("<Escape>", lambda _event: on_cancel())
        dialog.protocol("WM_DELETE_WINDOW", on_cancel)

        show_modal_dialog(dialog)

        if result["ok"]:
            return result["selection"]  # type: ignore[return-value]

        if allow_back and result["selection"] is None:
            raise BackRequested("User requested previous step from node selection.")

        raise UserCancelled("User cancelled node selection.")
