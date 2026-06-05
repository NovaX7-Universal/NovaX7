
import tkinter as tk
from tkinter import filedialog, messagebox
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet

days = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"]

root = tk.Tk()
root.title("Wochen-Essensplan")
root.geometry("600x500")

entries = {}

title = tk.Label(root, text="Essensplan für die Woche", font=("Arial", 16, "bold"))
title.pack(pady=10)

frame = tk.Frame(root)
frame.pack(fill="both", expand=True, padx=10)

for day in days:
    row = tk.Frame(frame)
    row.pack(fill="x", pady=3)

    tk.Label(row, text=day, width=12, anchor="w").pack(side="left")

    entry = tk.Entry(row)
    entry.pack(side="left", fill="x", expand=True)

    entries[day] = entry

def export_pdf():
    path = filedialog.asksaveasfilename(
        defaultextension=".pdf",
        filetypes=[("PDF-Dateien", "*.pdf")]
    )

    if not path:
        return

    doc = SimpleDocTemplate(path)
    styles = getSampleStyleSheet()

    content = [Paragraph("Wochen-Essensplan", styles["Title"]), Spacer(1, 12)]

    for day in days:
        meal = entries[day].get().strip()
        if not meal:
            meal = "-"
        content.append(Paragraph(f"<b>{day}:</b> {meal}", styles["BodyText"]))

    doc.build(content)

    messagebox.showinfo("Fertig", "PDF erfolgreich exportiert.")

btn = tk.Button(root, text="Als PDF exportieren", command=export_pdf)
btn.pack(pady=15)

root.mainloop()
