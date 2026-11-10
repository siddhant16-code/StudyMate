
import tkinter as tk
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from tkinter import ttk, messagebox, filedialog
import webbrowser
from urllib.parse import quote_plus
root = tk.Tk()
root.title("StudyMate - Personal Learning Companion")
root.geometry("1000x650")
root.minsize(800, 550)
root.configure(bg="#F4F6FA")

# Colors
NAVY = "#172554"
BLUE = "#2563EB"
BG = "#F4F6FA"
WHITE = "#FFFFFF"
GREY = "#64748B"

# Sidebar
sidebar = tk.Frame(root, bg=NAVY, width=230)
sidebar.pack(side="left", fill="y")
sidebar.pack_propagate(False)

tk.Label(
    sidebar, text="StudyMate",
    font=("Arial", 24, "bold"),
    bg=NAVY, fg=WHITE
).pack(pady=(35, 5))

tk.Label(
    sidebar, text="YOUR LEARNING COMPANION",
    font=("Arial", 9), bg=NAVY, fg="#BFDBFE"
).pack(pady=(0, 35))

# Main content area
content = tk.Frame(root, bg=BG)
content.pack(side="left", fill="both", expand=True)

def show_page(page_name):

    # Clear previous page
    for widget in content.winfo_children():
        widget.destroy()

    # Page heading
    tk.Label(
        content,
        text=page_name,
        font=("Arial", 25, "bold"),
        bg=BG, fg=NAVY
    ).pack(anchor="w", padx=35, pady=(35, 10))

    # Dashboard
    if page_name == "Dashboard":

        tk.Label(
            content,
            text="Welcome to StudyMate!",
            font=("Arial", 14),
            bg=BG, fg=GREY
        ).pack(anchor="w", padx=35, pady=10)

        cards = tk.Frame(content, bg=BG)
        cards.pack(fill="x", padx=25, pady=25)

        for title, number in [
            ("Total Subjects", "0"),
            ("Study Tasks", "0"),
            ("Completed Tasks", "0")
        ]:
            card = tk.Frame(cards, bg=WHITE, padx=20, pady=20)
            card.pack(side="left", fill="both", expand=True, padx=7)

            tk.Label(
                card, text=title,
                font=("Arial", 11),
                bg=WHITE, fg=GREY
            ).pack(anchor="w")

            tk.Label(
                card, text=number,
                font=("Arial", 25, "bold"),
                bg=WHITE, fg=NAVY
            ).pack(anchor="w", pady=10)

        tk.Label(
            content,
            text="Organize your studies. Track your progress. Learn smarter.",
            font=("Arial", 12),
            bg=WHITE, fg=GREY,
            padx=25, pady=30
        ).pack(fill="x", padx=35, pady=20)

    else:
        tk.Label(
            content,
            text=f"Welcome to {page_name}!",
            font=("Arial", 16),
            bg=WHITE, fg=NAVY,
            padx=25, pady=30
        ).pack(fill="x", padx=35, pady=20)

        tk.Label(
            content,
            text="This section is under development.",
            font=("Arial", 11),
            bg=BG, fg=GREY
        ).pack(anchor="w", padx=35)

# Navigation
pages = [
    "Dashboard",
    "My Subjects",
    "Study Tasks",
    "Progress Report",
    "Doubt Assistance",
    "Learning Helper"
]

for name in pages:
    tk.Button(
        sidebar,
        text="   " + name,
        font=("Arial", 11),
        bg=NAVY, fg=WHITE,
        activebackground="#1E40AF",
        activeforeground=WHITE,
        relief="flat",
        anchor="w",
        padx=20, pady=12,
        command=lambda p=name: show_page(p)
    ).pack(fill="x", padx=8, pady=2)

# Initial page
show_page("Dashboard")

root.mainloop()
