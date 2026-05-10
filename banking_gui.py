#!/usr/bin/env python3
"""
banking_gui.py — Tkinter GUI for the Concurrent Banking Transaction System
CS-2006 Operating Systems | Spring 2026

Compile:  gcc -o banking banking.c -lpthread -lm
Run:      python3 banking_gui.py
"""

import tkinter as tk
from tkinter import ttk, messagebox
import subprocess, threading, queue, os, sys, time, copy

# ── Colors & Fonts ───────────────────────────────────────────────────────────
BG         = "#0a0f1e"
PANEL      = "#111827"
CARD       = "#0d1526"
BORDER     = "#1e3a5f"
ACCENT     = "#00d4ff"
ACCENT2    = "#0055aa"
VIP_CLR    = "#ffd700"
FREEZE_CLR = "#ff4444"
OK_CLR     = "#00e676"
WARN_CLR   = "#ffab40"
TEXT       = "#e2e8f0"
MUTED      = "#64748b"

F_TITLE  = ("Courier New", 20, "bold")
F_HEAD   = ("Courier New", 11, "bold")
F_MONO   = ("Courier New", 10)
F_SMALL  = ("Courier New", 9)
F_BTN    = ("Courier New", 10, "bold")

# ── Initial accounts (exact mirror of banking.c main()) ──────────────────────
INITIAL_ACCOUNTS = [
    {"id": 1, "owner": "Kamran Mirza",   "pin": "1111", "balance": 10000.0, "vip": True,  "frozen": False},
    {"id": 2, "owner": "Tariq Butt",     "pin": "2222", "balance":  8000.0, "vip": True,  "frozen": False},
    {"id": 3, "owner": "Sana Baig",      "pin": "3333", "balance":  5000.0, "vip": False, "frozen": False},
    {"id": 4, "owner": "Bilal Chaudhry", "pin": "4444", "balance":  7500.0, "vip": False, "frozen": False},
    {"id": 5, "owner": "Rabia Naqvi",    "pin": "5555", "balance":  6000.0, "vip": False, "frozen": False},
    {"id": 6, "owner": "Imran Siddiqui", "pin": "6666", "balance":  4500.0, "vip": False, "frozen": False},
    {"id": 7, "owner": "Faisal Sheikh",  "pin": "7777", "balance":  9000.0, "vip": False, "frozen": False},
    {"id": 8, "owner": "Huma Rashid",    "pin": "8888", "balance":  3000.0, "vip": False, "frozen": False},
]
ADMIN_PW    = "fast"
FRAUD_LIMIT = 8000.0
BINARY      = "./banking"


# ═══════════════════════════════════════════════════════════════════════════════
#  Helper dialogs
# ═══════════════════════════════════════════════════════════════════════════════

def mk_btn(parent, text, cmd, bg=ACCENT2, width=20):
    return tk.Button(parent, text=text, command=cmd, bg=bg, fg="white",
                     activebackground=ACCENT, activeforeground=BG,
                     font=F_BTN, relief="flat", cursor="hand2",
                     width=width, bd=0, padx=6, pady=5)


def center_win(win, parent, w, h):
    win.geometry(f"{w}x{h}")
    win.update_idletasks()
    x = parent.winfo_x() + (parent.winfo_width()  - w) // 2
    y = parent.winfo_y() + (parent.winfo_height() - h) // 2
    win.geometry(f"+{x}+{y}")


class PinDialog(tk.Toplevel):
    def __init__(self, parent, account_name, attempts_left=3):
        super().__init__(parent)
        self.result = None
        self.title("PIN Required")
        self.configure(bg=PANEL)
        self.resizable(False, False)
        self.grab_set()
        center_win(self, parent, 360, 200)

        tk.Label(self, text=f"Account: {account_name}", bg=PANEL,
                 fg=VIP_CLR, font=F_HEAD).pack(pady=(18, 4))
        tk.Label(self, text=f"Enter PIN  ({attempts_left} attempt(s) left)",
                 bg=PANEL, fg=TEXT, font=F_MONO).pack()

        self.var = tk.StringVar()
        e = tk.Entry(self, textvariable=self.var, show="●", font=F_MONO,
                     bg=CARD, fg=ACCENT, insertbackground=ACCENT,
                     relief="flat", highlightthickness=1,
                     highlightcolor=ACCENT, width=20, justify="center")
        e.pack(pady=10)
        e.focus()
        e.bind("<Return>", self._ok)

        bf = tk.Frame(self, bg=PANEL)
        bf.pack()
        mk_btn(bf, "OK",     self._ok,     ACCENT2,   10).pack(side="left", padx=5)
        mk_btn(bf, "Cancel", self._cancel, "#553333", 10).pack(side="left", padx=5)

    def _ok(self, *_):
        self.result = self.var.get()
        self.destroy()

    def _cancel(self, *_):
        self.destroy()


class AdminDialog(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.result = None
        self.title("Admin Access")
        self.configure(bg=PANEL)
        self.resizable(False, False)
        self.grab_set()
        center_win(self, parent, 340, 180)

        tk.Label(self, text="Admin Password", bg=PANEL,
                 fg=FREEZE_CLR, font=F_HEAD).pack(pady=(18, 8))
        self.var = tk.StringVar()
        e = tk.Entry(self, textvariable=self.var, show="●", font=F_MONO,
                     bg=CARD, fg=ACCENT, insertbackground=ACCENT,
                     relief="flat", highlightthickness=1,
                     highlightcolor=ACCENT, width=20, justify="center")
        e.pack(pady=6)
        e.focus()
        e.bind("<Return>", self._ok)

        bf = tk.Frame(self, bg=PANEL)
        bf.pack(pady=10)
        mk_btn(bf, "OK",     self._ok,     ACCENT2,   10).pack(side="left", padx=5)
        mk_btn(bf, "Cancel", self._cancel, "#553333", 10).pack(side="left", padx=5)

    def _ok(self, *_):
        self.result = self.var.get()
        self.destroy()

    def _cancel(self, *_):
        self.destroy()


class AmountDialog(tk.Toplevel):
    def __init__(self, parent, title="Enter Amount"):
        super().__init__(parent)
        self.result = None
        self.title(title)
        self.configure(bg=PANEL)
        self.resizable(False, False)
        self.grab_set()
        center_win(self, parent, 320, 160)

        tk.Label(self, text="Amount (Rs.):", bg=PANEL, fg=TEXT,
                 font=F_HEAD).pack(pady=(20, 6))
        self.var = tk.StringVar()
        e = tk.Entry(self, textvariable=self.var, font=F_MONO,
                     bg=CARD, fg=ACCENT, insertbackground=ACCENT,
                     relief="flat", highlightthickness=1,
                     highlightcolor=ACCENT, width=20, justify="center")
        e.pack(pady=4)
        e.focus()
        e.bind("<Return>", self._ok)

        bf = tk.Frame(self, bg=PANEL)
        bf.pack(pady=10)
        mk_btn(bf, "OK",     self._ok,     ACCENT2,   10).pack(side="left", padx=5)
        mk_btn(bf, "Cancel", self._cancel, "#553333", 10).pack(side="left", padx=5)

    def _ok(self, *_):
        try:
            self.result = float(self.var.get())
        except ValueError:
            self.result = None
        self.destroy()

    def _cancel(self, *_):
        self.destroy()


class AccPickDialog(tk.Toplevel):
    def __init__(self, parent, accounts, title="Select Account", exclude_id=None):
        super().__init__(parent)
        self.result = None
        self.title(title)
        self.configure(bg=PANEL)
        self.resizable(False, False)
        self.grab_set()
        center_win(self, parent, 440, 300)

        tk.Label(self, text=title, bg=PANEL, fg=ACCENT,
                 font=F_HEAD).pack(pady=(14, 6))

        frame = tk.Frame(self, bg=PANEL)
        frame.pack(fill="both", expand=True, padx=14)
        lb = tk.Listbox(frame, bg=CARD, fg=TEXT, font=F_MONO,
                        selectbackground=BORDER, activestyle="none",
                        relief="flat", bd=0, height=8, width=50)
        lb.pack(side="left", fill="both", expand=True)
        sb = ttk.Scrollbar(frame, orient="vertical", command=lb.yview)
        sb.pack(side="right", fill="y")
        lb.configure(yscrollcommand=sb.set)

        self._mapping = []
        for a in accounts:
            if a["id"] == exclude_id:
                continue
            status = "VIP" if a["vip"] else ("FROZEN" if a["frozen"] else "STD")
            lb.insert("end",
                      f"  {a['id']}.  {a['owner']:<20}  Rs.{a['balance']:>10,.2f}  [{status}]")
            color = VIP_CLR if a["vip"] else (FREEZE_CLR if a["frozen"] else TEXT)
            lb.itemconfig("end", fg=color)
            self._mapping.append(a["id"])

        self._lb = lb
        lb.bind("<Double-1>", self._pick)
        mk_btn(self, "Select", self._pick, ACCENT2, 16).pack(pady=8)

    def _pick(self, *_):
        sel = self._lb.curselection()
        if not sel:
            messagebox.showwarning("Select", "Please select an account.", parent=self)
            return
        self.result = self._mapping[sel[0]]
        self.destroy()


# ═══════════════════════════════════════════════════════════════════════════════
#  Main Application
# ═══════════════════════════════════════════════════════════════════════════════

class BankApp(tk.Tk):

    def __init__(self):
        super().__init__()
        self.accounts     = copy.deepcopy(INITIAL_ACCOUNTS)
        self.txn_id       = 0
        self._q           = queue.Queue()
        self._sim_running = False

        self._build_ui()
        self._refresh_accounts()

        if not os.path.exists(BINARY):
            messagebox.showwarning("Binary Not Found",
                f"'{BINARY}' not found.\n\n"
                "Compile with:\n  gcc -o banking banking.c -lpthread -lm\n\n"
                "Deposit / Withdraw / Transfer work without it.\n"
                "Simulation requires it.")
            self._status("Warning: binary not found — simulation unavailable.")
        else:
            self._status("Ready.  Select an action from the sidebar.")

    # ─────────────────────────────────────────────────────────────────────
    #  UI
    # ─────────────────────────────────────────────────────────────────────
    def _build_ui(self):
        self.title("Concurrent Banking System  —  CS-2006 OS")
        self.configure(bg=BG)
        self.geometry("1200x700")
        self.minsize(1000, 600)

        # Header
        hdr = tk.Frame(self, bg=BG)
        hdr.pack(fill="x", padx=20, pady=(14, 0))
        tk.Label(hdr, text="◈  CONCURRENT BANKING SYSTEM",
                 bg=BG, fg=ACCENT, font=F_TITLE).pack(side="left")
        tk.Label(hdr,
                 text="CS-2006 Operating Systems  •  Spring 2026  •  Dr. Ghufran Ahmed",
                 bg=BG, fg=MUTED, font=F_SMALL).pack(side="right", anchor="s", pady=4)
        tk.Frame(self, bg=BORDER, height=1).pack(fill="x", padx=20, pady=6)

        # Body
        body = tk.Frame(self, bg=BG)
        body.pack(fill="both", expand=True, padx=12, pady=2)
        body.columnconfigure(0, weight=0)
        body.columnconfigure(1, weight=1)
        body.rowconfigure(0, weight=1)

        self._build_sidebar(body)
        self._build_main(body)

        # Status bar
        self._status_var = tk.StringVar(value="Starting…")
        tk.Label(self, textvariable=self._status_var, bg=PANEL, fg=MUTED,
                 font=F_SMALL, anchor="w", padx=10, pady=3).pack(
                 fill="x", side="bottom")

    def _build_sidebar(self, parent):
        sb = tk.Frame(parent, bg=BG, width=215)
        sb.grid(row=0, column=0, sticky="ns", padx=(4, 10))
        sb.pack_propagate(False)

        tk.Label(sb, text="ACTIONS", bg=BG, fg=ACCENT,
                 font=F_HEAD).pack(anchor="w", pady=(4, 8))

        actions = [
            ("  Deposit",           self.do_deposit,     "#0a4a2a"),
            ("  Withdraw",          self.do_withdraw,    "#0a2a4a"),
            ("  Transfer",          self.do_transfer,    "#3a2a0a"),
            None,
            ("  Freeze/Unfreeze",   self.do_freeze,      "#4a0a0a"),
            ("  Consistency Check", self.do_consistency, "#1a1a4a"),
            ("  Run Simulation",    self.do_simulation,  "#2a0a4a"),
            None,
            ("  OS Concepts",       self.do_concepts,    "#0a3a3a"),
        ]
        for item in actions:
            if item is None:
                tk.Frame(sb, bg=BORDER, height=1).pack(fill="x", pady=5)
            else:
                txt, cmd, col = item
                mk_btn(sb, txt, cmd, col, 22).pack(fill="x", pady=2)

        tk.Frame(sb, bg=BORDER, height=1).pack(fill="x", pady=(16, 6))
        for line in ["Zain Khan    24K-0838",
                     "Atta Hussain 24K-0797",
                     "M. Zamin     24K-0982"]:
            tk.Label(sb, text=line, bg=BG, fg=MUTED,
                     font=F_SMALL, anchor="w").pack(fill="x")

    def _build_main(self, parent):
        mp = tk.Frame(parent, bg=BG)
        mp.grid(row=0, column=1, sticky="nsew")
        mp.rowconfigure(0, weight=1)
        mp.rowconfigure(2, weight=1)
        mp.columnconfigure(0, weight=1)

        self._build_acc_panel(mp)
        tk.Frame(mp, bg=BORDER, height=1).grid(row=1, column=0,
                                               sticky="ew", pady=6)
        bot = tk.Frame(mp, bg=BG)
        bot.grid(row=2, column=0, sticky="nsew")
        bot.rowconfigure(0, weight=1)
        bot.columnconfigure(0, weight=3)
        bot.columnconfigure(1, weight=2)
        self._build_log_panel(bot)
        self._build_terminal(bot)

    def _build_acc_panel(self, parent):
        pf = tk.Frame(parent, bg=BG)
        pf.grid(row=0, column=0, sticky="nsew")
        pf.columnconfigure(0, weight=1)
        pf.rowconfigure(1, weight=1)

        tk.Label(pf, text="ACCOUNTS", bg=BG, fg=ACCENT,
                 font=F_HEAD).grid(row=0, column=0, sticky="w", pady=(2, 4))

        container = tk.Frame(pf, bg=CARD, highlightthickness=1,
                             highlightbackground=BORDER)
        container.grid(row=1, column=0, sticky="nsew")
        container.columnconfigure(0, weight=1)
        container.rowconfigure(0, weight=1)

        cols = ("id", "owner", "balance", "status")
        self.acc_tree = ttk.Treeview(container, columns=cols,
                                     show="headings", selectmode="browse",
                                     height=8)
        self._style_tree()

        self.acc_tree.heading("id",      text="#")
        self.acc_tree.heading("owner",   text="Account Owner")
        self.acc_tree.heading("balance", text="Balance (Rs.)")
        self.acc_tree.heading("status",  text="Status")

        self.acc_tree.column("id",      width=40,  anchor="center")
        self.acc_tree.column("owner",   width=220, anchor="w")
        self.acc_tree.column("balance", width=180, anchor="e")
        self.acc_tree.column("status",  width=90,  anchor="center")

        self.acc_tree.grid(row=0, column=0, sticky="nsew")
        vsb = ttk.Scrollbar(container, orient="vertical",
                            command=self.acc_tree.yview)
        vsb.grid(row=0, column=1, sticky="ns")
        self.acc_tree.configure(yscrollcommand=vsb.set)

        self.acc_tree.tag_configure("vip",    foreground=VIP_CLR)
        self.acc_tree.tag_configure("frozen", foreground=FREEZE_CLR)
        self.acc_tree.tag_configure("std",    foreground=TEXT)

    def _build_log_panel(self, parent):
        pf = tk.Frame(parent, bg=BG)
        pf.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        pf.columnconfigure(0, weight=1)
        pf.rowconfigure(1, weight=1)

        tk.Label(pf, text="TRANSACTION LOG", bg=BG, fg=ACCENT,
                 font=F_HEAD).grid(row=0, column=0, sticky="w", pady=(0, 4))

        container = tk.Frame(pf, bg=CARD, highlightthickness=1,
                             highlightbackground=BORDER)
        container.grid(row=1, column=0, sticky="nsew")
        container.columnconfigure(0, weight=1)
        container.rowconfigure(0, weight=1)

        cols = ("#", "Type", "From", "To", "Amount", "Result")
        self.log_tree = ttk.Treeview(container, columns=cols,
                                     show="headings", selectmode="none")
        widths = [38, 80, 140, 140, 110, 110]
        for c, w in zip(cols, widths):
            self.log_tree.heading(c, text=c)
            self.log_tree.column(c, width=w,
                                 anchor="w" if c in ("From", "To") else "center")

        self.log_tree.grid(row=0, column=0, sticky="nsew")
        vsb = ttk.Scrollbar(container, orient="vertical",
                            command=self.log_tree.yview)
        vsb.grid(row=0, column=1, sticky="ns")
        self.log_tree.configure(yscrollcommand=vsb.set)

        self.log_tree.tag_configure("ok",     foreground=OK_CLR)
        self.log_tree.tag_configure("fail",   foreground=WARN_CLR)
        self.log_tree.tag_configure("frozen", foreground=FREEZE_CLR)
        self.log_tree.tag_configure("fraud",  foreground=FREEZE_CLR)

    def _build_terminal(self, parent):
        pf = tk.Frame(parent, bg=BG)
        pf.grid(row=0, column=1, sticky="nsew")
        pf.columnconfigure(0, weight=1)
        pf.rowconfigure(1, weight=1)

        tk.Label(pf, text="LIVE OUTPUT", bg=BG, fg=ACCENT,
                 font=F_HEAD).grid(row=0, column=0, sticky="w", pady=(0, 4))

        container = tk.Frame(pf, bg="#060c18", highlightthickness=1,
                             highlightbackground=BORDER)
        container.grid(row=1, column=0, sticky="nsew")
        container.columnconfigure(0, weight=1)
        container.rowconfigure(0, weight=1)

        self.terminal = tk.Text(container, bg="#060c18", fg="#00ff88",
                                font=F_SMALL, state="disabled",
                                relief="flat", wrap="none",
                                insertbackground=ACCENT)
        self.terminal.grid(row=0, column=0, sticky="nsew")
        vsb = ttk.Scrollbar(container, orient="vertical",
                            command=self.terminal.yview)
        vsb.grid(row=0, column=1, sticky="ns")
        self.terminal.configure(yscrollcommand=vsb.set)

        self.terminal.tag_config("vip",   foreground=VIP_CLR)
        self.terminal.tag_config("fraud", foreground=FREEZE_CLR)
        self.terminal.tag_config("ok",    foreground=OK_CLR)
        self.terminal.tag_config("warn",  foreground=WARN_CLR)
        self.terminal.tag_config("head",  foreground=ACCENT)

    def _style_tree(self):
        s = ttk.Style(self)
        s.theme_use("default")
        s.configure("Treeview",
                    background=CARD, foreground=TEXT,
                    fieldbackground=CARD, rowheight=26,
                    font=F_MONO, borderwidth=0)
        s.configure("Treeview.Heading",
                    background=PANEL, foreground=ACCENT,
                    font=("Courier New", 9, "bold"), relief="flat")
        s.map("Treeview", background=[("selected", BORDER)])
        s.configure("Vertical.TScrollbar",
                    background=PANEL, troughcolor=BG, arrowcolor=MUTED)

    # ─────────────────────────────────────────────────────────────────────
    #  Account table refresh  (reads from self.accounts)
    # ─────────────────────────────────────────────────────────────────────
    def _refresh_accounts(self):
        for row in self.acc_tree.get_children():
            self.acc_tree.delete(row)
        for a in self.accounts:
            if a["frozen"]:
                status, tag = "FROZEN", "frozen"
            elif a["vip"]:
                status, tag = "VIP",    "vip"
            else:
                status, tag = "STD",    "std"
            self.acc_tree.insert("", "end",
                values=(a["id"],
                        a["owner"],
                        f"Rs. {a['balance']:>12,.2f}",
                        status),
                tags=(tag,))

    def _get_acc(self, acc_id):
        for a in self.accounts:
            if a["id"] == acc_id:
                return a
        return None

    # ─────────────────────────────────────────────────────────────────────
    #  Transaction log
    # ─────────────────────────────────────────────────────────────────────
    def _add_log(self, txn_type, src_id, dst_id, amount, result):
        self.txn_id += 1
        src = self._get_acc(src_id)
        dst = self._get_acc(dst_id) if dst_id else None
        tag = ("ok"     if result == "SUCCESS"  else
               "fraud"  if "FRAUD"  in result   else
               "frozen" if "FROZEN" in result   else "fail")
        self.log_tree.insert("", "end", values=(
            self.txn_id,
            txn_type,
            src["owner"] if src else f"acc-{src_id}",
            dst["owner"] if dst else "—",
            f"Rs. {amount:,.2f}",
            result
        ), tags=(tag,))
        children = self.log_tree.get_children()
        if children:
            self.log_tree.see(children[-1])

    # ─────────────────────────────────────────────────────────────────────
    #  Security helpers
    # ─────────────────────────────────────────────────────────────────────
    def _verify_pin(self, acc_id):
        a = self._get_acc(acc_id)
        for attempt in range(3):
            d = PinDialog(self, a["owner"], 3 - attempt)
            self.wait_window(d)
            if d.result is None:
                return False
            if d.result == a["pin"]:
                return True
            if attempt < 2:
                messagebox.showwarning("Wrong PIN",
                    f"Incorrect PIN. {2 - attempt} attempt(s) left.")
        a["frozen"] = True
        self._refresh_accounts()
        messagebox.showerror("Account Frozen",
            f"Too many wrong attempts.\n'{a['owner']}' is now FROZEN.")
        return False

    def _verify_admin(self):
        for attempt in range(3):
            d = AdminDialog(self)
            self.wait_window(d)
            if d.result is None:
                return False
            if d.result == ADMIN_PW:
                return True
            if attempt < 2:
                messagebox.showwarning("Wrong Password",
                    f"Incorrect. {2 - attempt} attempt(s) left.")
        messagebox.showerror("Access Denied", "Too many wrong attempts.")
        return False

    def _fraud_check(self, acc_id, amount):
        """Returns None (ok), 'FROZEN', or 'FRAUD'."""
        a = self._get_acc(acc_id)
        if a["frozen"]:
            return "FROZEN"
        if amount > FRAUD_LIMIT:
            a["frozen"] = True
            self._refresh_accounts()
            return "FRAUD"
        return None

    # ─────────────────────────────────────────────────────────────────────
    #  DEPOSIT
    # ─────────────────────────────────────────────────────────────────────
    def do_deposit(self):
        d = AccPickDialog(self, self.accounts, "Deposit — Select Account")
        self.wait_window(d)
        if d.result is None:
            return
        if not self._verify_pin(d.result):
            return

        amt_d = AmountDialog(self, "Deposit Amount")
        self.wait_window(amt_d)
        if amt_d.result is None or amt_d.result <= 0:
            messagebox.showwarning("Invalid", "Please enter a valid amount.")
            return

        acc_id, amount = d.result, amt_d.result
        a = self._get_acc(acc_id)

        fraud = self._fraud_check(acc_id, amount)
        if fraud == "FROZEN":
            self._add_log("DEPOSIT", acc_id, None, amount, "FROZEN")
            self._term(f"  DEPOSIT acc-{acc_id} → BLOCKED (account frozen)\n", "warn")
            messagebox.showerror("Blocked", "This account is frozen.")
            return
        if fraud == "FRAUD":
            self._add_log("DEPOSIT", acc_id, None, amount, "FRAUD-BLOCK")
            self._term(f"  [FRAUD] acc-{acc_id}  Rs.{amount:.2f} exceeds Rs.{FRAUD_LIMIT:.0f} → FROZEN\n", "fraud")
            messagebox.showerror("Fraud Detected",
                f"Amount Rs.{amount:,.2f} exceeds fraud limit Rs.{FRAUD_LIMIT:,.0f}.\n"
                f"Account has been frozen.")
            return

        a["balance"] += amount
        self._refresh_accounts()
        self._add_log("DEPOSIT", acc_id, None, amount, "SUCCESS")
        self._term(f"  DEPOSIT  acc-{acc_id} ({a['owner']})  +Rs.{amount:.2f}"
                   f"  bal=Rs.{a['balance']:.2f}\n", "ok")
        messagebox.showinfo("Deposit Successful",
            f"Deposited Rs.{amount:,.2f} into {a['owner']}.\n"
            f"New balance: Rs.{a['balance']:,.2f}")
        self._status(f"✓  Deposited Rs.{amount:,.2f} → {a['owner']}")

    # ─────────────────────────────────────────────────────────────────────
    #  WITHDRAW
    # ─────────────────────────────────────────────────────────────────────
    def do_withdraw(self):
        d = AccPickDialog(self, self.accounts, "Withdraw — Select Account")
        self.wait_window(d)
        if d.result is None:
            return
        if not self._verify_pin(d.result):
            return

        amt_d = AmountDialog(self, "Withdrawal Amount")
        self.wait_window(amt_d)
        if amt_d.result is None or amt_d.result <= 0:
            messagebox.showwarning("Invalid", "Please enter a valid amount.")
            return

        acc_id, amount = d.result, amt_d.result
        a = self._get_acc(acc_id)

        fraud = self._fraud_check(acc_id, amount)
        if fraud == "FROZEN":
            self._add_log("WITHDRAW", acc_id, None, amount, "FROZEN")
            self._term(f"  WITHDRAW acc-{acc_id} → BLOCKED (frozen)\n", "warn")
            messagebox.showerror("Blocked", "This account is frozen.")
            return
        if fraud == "FRAUD":
            self._add_log("WITHDRAW", acc_id, None, amount, "FRAUD-BLOCK")
            self._term(f"  [FRAUD] acc-{acc_id}  Rs.{amount:.2f} exceeds limit → FROZEN\n", "fraud")
            messagebox.showerror("Fraud Detected",
                f"Amount Rs.{amount:,.2f} exceeds fraud limit.\nAccount frozen.")
            return

        if a["balance"] < amount:
            self._add_log("WITHDRAW", acc_id, None, amount, "INSUFFICIENT")
            self._term(f"  WITHDRAW acc-{acc_id}  Rs.{amount:.2f} → INSUFFICIENT"
                       f"  (bal=Rs.{a['balance']:.2f})\n", "warn")
            messagebox.showerror("Insufficient Funds",
                f"Balance:   Rs.{a['balance']:,.2f}\n"
                f"Requested: Rs.{amount:,.2f}")
            return

        a["balance"] -= amount
        self._refresh_accounts()
        self._add_log("WITHDRAW", acc_id, None, amount, "SUCCESS")
        self._term(f"  WITHDRAW acc-{acc_id} ({a['owner']})  -Rs.{amount:.2f}"
                   f"  bal=Rs.{a['balance']:.2f}\n", "ok")
        messagebox.showinfo("Withdrawal Successful",
            f"Withdrew Rs.{amount:,.2f} from {a['owner']}.\n"
            f"New balance: Rs.{a['balance']:,.2f}")
        self._status(f"✓  Withdrew Rs.{amount:,.2f} from {a['owner']}")

    # ─────────────────────────────────────────────────────────────────────
    #  TRANSFER
    # ─────────────────────────────────────────────────────────────────────
    def do_transfer(self):
        ds = AccPickDialog(self, self.accounts, "Transfer — Source Account")
        self.wait_window(ds)
        if ds.result is None:
            return
        if not self._verify_pin(ds.result):
            return

        dd = AccPickDialog(self, self.accounts,
                           "Transfer — Destination Account",
                           exclude_id=ds.result)
        self.wait_window(dd)
        if dd.result is None:
            return

        amt_d = AmountDialog(self, "Transfer Amount")
        self.wait_window(amt_d)
        if amt_d.result is None or amt_d.result <= 0:
            messagebox.showwarning("Invalid", "Please enter a valid amount.")
            return

        src_id, dst_id, amount = ds.result, dd.result, amt_d.result
        src = self._get_acc(src_id)
        dst = self._get_acc(dst_id)

        fraud = self._fraud_check(src_id, amount)
        if fraud == "FROZEN":
            self._add_log("TRANSFER", src_id, dst_id, amount, "FROZEN")
            self._term(f"  TRANSFER acc-{src_id}→{dst_id} → BLOCKED (source frozen)\n", "warn")
            messagebox.showerror("Blocked", "Source account is frozen.")
            return
        if fraud == "FRAUD":
            self._add_log("TRANSFER", src_id, dst_id, amount, "FRAUD-BLOCK")
            self._term(f"  [FRAUD] acc-{src_id}  Rs.{amount:.2f} exceeds limit → FROZEN\n", "fraud")
            messagebox.showerror("Fraud Detected",
                f"Amount Rs.{amount:,.2f} exceeds fraud limit.\nSource account frozen.")
            return

        if dst["frozen"]:
            self._add_log("TRANSFER", src_id, dst_id, amount, "FROZEN")
            self._term(f"  TRANSFER → BLOCKED (destination acc-{dst_id} frozen)\n", "warn")
            messagebox.showerror("Blocked", "Destination account is frozen.")
            return

        if src["balance"] < amount:
            self._add_log("TRANSFER", src_id, dst_id, amount, "INSUFFICIENT")
            self._term(f"  TRANSFER acc-{src_id}→{dst_id}  Rs.{amount:.2f}"
                       f" → INSUFFICIENT (bal=Rs.{src['balance']:.2f})\n", "warn")
            messagebox.showerror("Insufficient Funds",
                f"Source balance: Rs.{src['balance']:,.2f}\n"
                f"Requested:      Rs.{amount:,.2f}")
            return

        src["balance"] -= amount
        dst["balance"] += amount
        self._refresh_accounts()
        self._add_log("TRANSFER", src_id, dst_id, amount, "SUCCESS")
        self._term(
            f"  TRANSFER acc-{src_id}→acc-{dst_id}  Rs.{amount:.2f}\n"
            f"    {src['owner']}: Rs.{src['balance']:.2f}\n"
            f"    {dst['owner']}: Rs.{dst['balance']:.2f}\n", "ok")
        messagebox.showinfo("Transfer Successful",
            f"Transferred Rs.{amount:,.2f}\n\n"
            f"From: {src['owner']}  →  Rs.{src['balance']:,.2f}\n"
            f"To:   {dst['owner']}  →  Rs.{dst['balance']:,.2f}")
        self._status(f"✓  Transfer Rs.{amount:,.2f}: {src['owner']} → {dst['owner']}")

    # ─────────────────────────────────────────────────────────────────────
    #  FREEZE / UNFREEZE
    # ─────────────────────────────────────────────────────────────────────
    def do_freeze(self):
        if not self._verify_admin():
            return
        d = AccPickDialog(self, self.accounts, "Freeze / Unfreeze — Select Account")
        self.wait_window(d)
        if d.result is None:
            return
        a = self._get_acc(d.result)
        a["frozen"] = not a["frozen"]
        self._refresh_accounts()
        state = "FROZEN" if a["frozen"] else "ACTIVE"
        self._term(f"  ADMIN: {a['owner']} → {state}\n",
                   "fraud" if a["frozen"] else "ok")
        messagebox.showinfo("Done", f"{a['owner']} is now {state}.")
        self._status(f"✓  {a['owner']} set to {state}")

    # ─────────────────────────────────────────────────────────────────────
    #  CONSISTENCY CHECK
    # ─────────────────────────────────────────────────────────────────────
    def do_consistency(self):
        if not self._verify_admin():
            return

        initial   = sum(a["balance"] for a in INITIAL_ACCOUNTS)
        deposited = 0.0
        withdrawn = 0.0
        for iid in self.log_tree.get_children():
            vals = self.log_tree.item(iid)["values"]
            txn_type = vals[1]
            result   = vals[5]
            if result != "SUCCESS":
                continue
            raw_amount = str(vals[4]).replace("Rs.", "").replace(",", "").strip()
            try:
                amt = float(raw_amount)
            except ValueError:
                continue
            if txn_type == "DEPOSIT":
                deposited += amt
            elif txn_type == "WITHDRAW":
                withdrawn += amt

        actual   = sum(a["balance"] for a in self.accounts)
        expected = initial + deposited - withdrawn
        diff     = abs(actual - expected)
        ok       = diff < 0.01

        win = tk.Toplevel(self)
        win.title("Consistency Report")
        win.configure(bg=PANEL)
        win.geometry("420x300")
        win.grab_set()
        win.resizable(False, False)
        center_win(win, self, 420, 300)

        tk.Label(win, text="CONSISTENCY REPORT", bg=PANEL,
                 fg=ACCENT, font=F_HEAD).pack(pady=(18, 12))

        rows = [
            ("Initial Total",      f"Rs. {initial:>12,.2f}"),
            ("+ Total Deposited",  f"Rs. {deposited:>12,.2f}"),
            ("- Total Withdrawn",  f"Rs. {withdrawn:>12,.2f}"),
            ("Expected Total",     f"Rs. {expected:>12,.2f}"),
            ("Actual Total",       f"Rs. {actual:>12,.2f}"),
            ("Difference",         f"Rs. {diff:>12,.4f}"),
        ]
        for label, val in rows:
            r = tk.Frame(win, bg=PANEL)
            r.pack(fill="x", padx=30, pady=2)
            tk.Label(r, text=label, bg=PANEL, fg=MUTED,
                     font=F_MONO, width=22, anchor="w").pack(side="left")
            tk.Label(r, text=val,   bg=PANEL, fg=TEXT,
                     font=F_MONO).pack(side="right")

        result_clr = OK_CLR if ok else FREEZE_CLR
        result_txt = "✓  CONSISTENT — no discrepancy" if ok else "✗  DISCREPANCY DETECTED"
        tk.Label(win, text=result_txt, bg=PANEL, fg=result_clr,
                 font=("Courier New", 11, "bold")).pack(pady=14)
        mk_btn(win, "Close", win.destroy, ACCENT2, 12).pack()

    # ─────────────────────────────────────────────────────────────────────
    #  SIMULATION  (runs actual C binary, streams output to terminal)
    # ─────────────────────────────────────────────────────────────────────
    def do_simulation(self):
        if not self._verify_admin():
            return
        if self._sim_running:
            messagebox.showinfo("Simulation", "Already running…")
            return
        if not os.path.exists(BINARY):
            messagebox.showerror("Missing",
                f"'{BINARY}' not found.\n\nCompile with:\n  gcc -o banking banking.c -lpthread -lm")
            return

        ans = messagebox.askyesno("Run Simulation",
            "This runs the C binary's 8-thread concurrent simulation.\n"
            "Output will stream into the Live Output panel.\n\nContinue?")
        if not ans:
            return

        self._sim_running = True
        self._status("⚙  Simulation running…")
        self._term("\n─── SIMULATION STARTED ───\n", "head")

        def _run():
            try:
                proc = subprocess.Popen(
                    [BINARY],
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True, bufsize=0
                )
                time.sleep(0.6)
                # Navigate: menu choice 8 → admin pw → enter
                proc.stdin.write("8\n");             proc.stdin.flush(); time.sleep(0.3)
                proc.stdin.write(ADMIN_PW + "\n");   proc.stdin.flush(); time.sleep(0.2)
                proc.stdin.write("\n");              proc.stdin.flush()

                for line in proc.stdout:
                    self._q.put(("term", line))

                try:
                    proc.stdin.write("0\n"); proc.stdin.flush()
                except Exception:
                    pass
                proc.wait(timeout=5)
            except Exception as ex:
                self._q.put(("term", f"  [ERROR] {ex}\n"))
            finally:
                self._q.put(("sim_done", None))

        threading.Thread(target=_run, daemon=True).start()
        self._poll_sim()

    def _poll_sim(self):
        try:
            while True:
                kind, data = self._q.get_nowait()
                if kind == "term":
                    self._term(data)
                elif kind == "sim_done":
                    self._sim_running = False
                    self._term("\n─── SIMULATION COMPLETE ───\n", "head")
                    self._status("✓  Simulation complete.")
                    messagebox.showinfo("Done",
                        "Simulation finished!\nSee Live Output for the full transaction log.")
                    return
        except queue.Empty:
            pass
        if self._sim_running:
            self.after(80, self._poll_sim)

    # ─────────────────────────────────────────────────────────────────────
    #  OS CONCEPTS
    # ─────────────────────────────────────────────────────────────────────
    def do_concepts(self):
        win = tk.Toplevel(self)
        win.title("OS Concepts Used")
        win.configure(bg=PANEL)
        win.geometry("640x520")
        win.grab_set()
        center_win(win, self, 640, 520)

        tk.Label(win, text="OS CONCEPTS IN THIS PROJECT",
                 bg=PANEL, fg=ACCENT, font=F_HEAD).pack(pady=(16, 6))

        canvas = tk.Canvas(win, bg=PANEL, bd=0, highlightthickness=0)
        vsb    = ttk.Scrollbar(win, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        canvas.pack(fill="both", expand=True, padx=8)
        inner = tk.Frame(canvas, bg=PANEL)
        canvas.create_window((0, 0), window=inner, anchor="nw")

        items = [
            ("Mutexes  (pthread_mutex_t)",
             "Each account has its own mutex. Only one thread can modify a balance at a time,\n"
             "preventing race conditions on shared account data."),
            ("Semaphore  (sem_t, cap = 4)",
             "Limits concurrent transactions to 4 — like 4 teller windows.\n"
             "Other threads block and wait rather than overwhelming the system."),
            ("Deadlock Prevention",
             "Transfers always lock the lower-indexed account first (lock ordering).\n"
             "This breaks the circular-wait condition — one of Coffman's four requirements."),
            ("Race Condition Handling",
             "Without mutex: Thread A and B both read balance=5000, both withdraw 4000 → goes negative!\n"
             "With mutex: Thread B waits, sees updated balance of 1000, and correctly fails."),
            ("Fraud Detection  (Rs. 8000 limit)",
             "Any transaction over Rs.8,000 immediately flags and atomically freezes the account.\n"
             "The freeze happens inside the mutex to prevent concurrent bypass."),
            ("VIP Priority Scheduling",
             "VIP threads use a shorter usleep() before starting, giving them a scheduling head-start.\n"
             "Simulates priority queuing found in real banking and OS schedulers."),
            ("Atomic Transaction Logger",
             "All operations are recorded under log_mutex, serialising writes to the shared array.\n"
             "Ensures no two threads corrupt the log simultaneously."),
            ("Consistency Verification",
             "After simulation: initial + deposited − withdrawn must equal current total.\n"
             "Verifies no money was created or lost due to concurrency bugs."),
        ]

        for i, (title, body) in enumerate(items):
            tk.Label(inner, text=f"  {i+1}.  {title}", bg=PANEL, fg=VIP_CLR,
                     font=("Courier New", 10, "bold"), anchor="w").pack(
                     fill="x", padx=10, pady=(12, 2))
            tk.Label(inner, text=body, bg=PANEL, fg=TEXT,
                     font=F_SMALL, anchor="w", justify="left",
                     wraplength=590).pack(fill="x", padx=28, pady=(0, 4))
            tk.Frame(inner, bg=BORDER, height=1).pack(fill="x", padx=10)

        inner.update_idletasks()
        canvas.configure(scrollregion=canvas.bbox("all"))
        mk_btn(win, "Close", win.destroy, ACCENT2, 12).pack(pady=10)

    # ─────────────────────────────────────────────────────────────────────
    #  Utilities
    # ─────────────────────────────────────────────────────────────────────
    def _term(self, text, tag=""):
        self.terminal.configure(state="normal")
        if not tag:
            tag = ("vip"   if "[VIP]"   in text else
                   "fraud" if "[FRAUD]" in text or "FROZEN" in text else
                   "ok"    if "SUCCESS" in text else
                   "warn"  if "INSUFF"  in text or "FAIL"   in text else "")
        self.terminal.insert("end", text, tag)
        self.terminal.see("end")
        self.terminal.configure(state="disabled")

    def _status(self, msg):
        self._status_var.set(msg)

    def on_close(self):
        self.destroy()


# ── Entry point ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app = BankApp()
    app.protocol("WM_DELETE_WINDOW", app.on_close)
    app.mainloop()
