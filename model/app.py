import tkinter as tk
from tkinter import ttk, simpledialog, messagebox
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))
from grocery_model import Database, ListManager, ItemManager, UserManager

class GroceryApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Grocery List Manager")
        self.root.resizable(True, True)

        self.db = Database.load()
        self.user_manager = UserManager(self.db)
        self.list_manager = ListManager(self.db)
        self.item_manager = ItemManager(self.db)
        self.current_user = None
        self.selected_list_id = None

        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self._show_login()

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _on_close(self):
        self.db.save()
        self.root.destroy()

    def _save(self):
        self.db.save()

    # ------------------------------------------------------------------
    # Screen switching
    # ------------------------------------------------------------------

    def _clear(self):
        for w in self.root.winfo_children():
            w.destroy()
        self.root.unbind("<Return>")

    # ------------------------------------------------------------------
    # Login screen
    # ------------------------------------------------------------------

    def _show_login(self, message: str = ""):
        self._clear()
        self.root.geometry("360x280")
        self.root.title("Grocery List Manager")

        outer = tk.Frame(self.root, padx=40, pady=30)
        outer.pack(expand=True)

        tk.Label(outer, text="Grocery List Manager", font=("Arial", 15, "bold")).grid(
            row=0, column=0, columnspan=2, pady=(0, 18)
        )

        tk.Label(outer, text="Username:", anchor="e").grid(row=1, column=0, sticky="e", pady=5)
        username_var = tk.StringVar()
        username_entry = tk.Entry(outer, textvariable=username_var, width=22)
        username_entry.grid(row=1, column=1, pady=5)

        tk.Label(outer, text="Password:", anchor="e").grid(row=2, column=0, sticky="e", pady=5)
        password_var = tk.StringVar()
        password_entry = tk.Entry(outer, textvariable=password_var, show="*", width=22)
        password_entry.grid(row=2, column=1, pady=5)

        # Success message (e.g. "Account created") or error message
        msg_var = tk.StringVar(value=message)
        msg_color = "#27ae60" if message else "#c0392b"
        msg_label = tk.Label(outer, textvariable=msg_var, fg=msg_color, font=("Arial", 9))
        msg_label.grid(row=3, column=0, columnspan=2, pady=(2, 0))

        def sign_in():
            username = username_var.get().strip()
            password = password_var.get()
            if not username or not password:
                msg_var.set("Please enter a username and password.")
                msg_label.config(fg="#c0392b")
                return
            user = self.user_manager.authenticate(username, password)
            if user:
                self.current_user = user
                # Schedule after current event is fully processed
                self.root.after(10, self._show_main)
            else:
                password_var.set("")
                msg_var.set("Incorrect username or password.")
                msg_label.config(fg="#c0392b")
                username_entry.focus_force()

        btn_row = tk.Frame(outer)
        btn_row.grid(row=4, column=0, columnspan=2, pady=(14, 0))
        tk.Button(btn_row, text="Sign In", width=10, command=sign_in).pack(side=tk.LEFT, padx=(0, 10))
        tk.Button(btn_row, text="Create Account", command=self._open_signup).pack(side=tk.LEFT)

        self.root.bind("<Return>", lambda _: sign_in())
        # Delay focus so tkinter finishes rendering the frame first
        self.root.after(50, username_entry.focus_force)

    # ------------------------------------------------------------------
    # Sign-up dialog
    # ------------------------------------------------------------------

    def _open_signup(self):
        dlg = tk.Toplevel(self.root)
        dlg.title("Create Account")
        dlg.geometry("320x340")
        dlg.resizable(False, False)
        dlg.grab_set()

        frame = tk.Frame(dlg, padx=24, pady=20)
        frame.pack(fill=tk.BOTH, expand=True)

        tk.Label(frame, text="Create Account", font=("Arial", 12, "bold")).grid(
            row=0, column=0, columnspan=2, pady=(0, 12)
        )

        fields_def = [
            ("Username *",       "username",  False),
            ("Password *",       "password",  True),
            ("Confirm password *","confirm",  True),
            ("First name",       "firstName", False),
            ("Last name",        "lastName",  False),
            ("Zip code",         "zipCode",   False),
        ]
        vars_ = {}
        for i, (label, key, secret) in enumerate(fields_def, start=1):
            tk.Label(frame, text=f"{label}:", anchor="e").grid(row=i, column=0, sticky="e", pady=3)
            v = tk.StringVar()
            vars_[key] = v
            tk.Entry(frame, textvariable=v, width=20, show="*" if secret else "").grid(
                row=i, column=1, pady=3, sticky="w"
            )

        error_var = tk.StringVar()
        tk.Label(frame, textvariable=error_var, fg="#c0392b", font=("Arial", 9),
                 wraplength=270).grid(row=len(fields_def) + 1, column=0, columnspan=2)

        def submit():
            username  = vars_["username"].get().strip()
            password  = vars_["password"].get()
            confirm   = vars_["confirm"].get()
            firstName = vars_["firstName"].get().strip()
            lastName  = vars_["lastName"].get().strip()
            zipCode   = vars_["zipCode"].get().strip()

            if password != confirm:
                error_var.set("Passwords do not match.")
                return
            try:
                user = self.user_manager.createUser(username, password, firstName, lastName, zipCode)
                self._save()
                self.current_user = user
                # Destroy dialog first, then schedule transition so the event loop
                # is fully clear before we rebuild the root window
                dlg.destroy()
                self.root.after(10, self._show_main)
            except ValueError as e:
                error_var.set(str(e))

        tk.Button(frame, text="Create Account", width=16, command=submit).grid(
            row=len(fields_def) + 2, column=0, columnspan=2, pady=(10, 0)
        )
        dlg.bind("<Return>", lambda _: submit())

    # ------------------------------------------------------------------
    # Sign-out
    # ------------------------------------------------------------------

    def _sign_out(self):
        self._save()
        self.current_user = None
        self.selected_list_id = None
        self.root.after(10, self._show_login)

    # ------------------------------------------------------------------
    # Main screen
    # ------------------------------------------------------------------

    def _show_main(self):
        self._clear()
        self.root.geometry("740x520")
        name_display = (
            f"{self.current_user.firstName} {self.current_user.lastName}".strip()
            or self.current_user.username
        )
        self.root.title(f"Grocery List Manager  —  {name_display}")
        self._build_main_ui()

    def _build_main_ui(self):
        # ---- Header bar ----
        header = tk.Frame(self.root, bg="#2c3e50", padx=10, pady=6)
        header.pack(fill=tk.X)
        name_display = (
            f"{self.current_user.firstName} {self.current_user.lastName}".strip()
            or self.current_user.username
        )
        tk.Label(
            header,
            text=f"Signed in as  {name_display}  (@{self.current_user.username})",
            bg="#2c3e50", fg="white", font=("Arial", 10),
        ).pack(side=tk.LEFT)
        tk.Button(
            header, text="Sign Out", command=self._sign_out,
            bg="#e74c3c", fg="white", activebackground="#c0392b",
            relief=tk.FLAT, padx=10, pady=2,
        ).pack(side=tk.RIGHT)

        # ---- Main content ----
        main = tk.Frame(self.root, padx=10, pady=10)
        main.pack(fill=tk.BOTH, expand=True)

        # Left panel: list box
        left = tk.Frame(main, width=280)
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=False)
        left.pack_propagate(False)

        tk.Label(left, text="Lists", font=("Arial", 11, "bold")).pack(anchor="w")

        btn_row = tk.Frame(left)
        btn_row.pack(fill=tk.X, pady=(2, 2))
        tk.Button(btn_row, text="Add List", width=9,  command=self.cmd_add_list).pack(side=tk.LEFT, padx=(0, 2))
        tk.Button(btn_row, text="Extend",   width=7,  command=self.cmd_extend_list).pack(side=tk.LEFT, padx=(0, 2))
        tk.Button(btn_row, text="Rename",   width=7,  command=self.cmd_rename_list).pack(side=tk.LEFT, padx=(0, 2))
        tk.Button(btn_row, text="Delete",   width=7,  command=self.cmd_delete_list).pack(side=tk.LEFT)

        list_frame = tk.Frame(left)
        list_frame.pack(fill=tk.BOTH, expand=True, pady=(4, 0))
        self.list_box = tk.Listbox(list_frame, font=("Arial", 10), activestyle="dotbox", selectmode="browse")
        vsb = ttk.Scrollbar(list_frame, orient="vertical", command=self.list_box.yview)
        self.list_box.configure(yscrollcommand=vsb.set)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        self.list_box.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.list_box.bind("<<ListboxSelect>>", self._on_list_select)

        # Divider
        ttk.Separator(main, orient="vertical").pack(side=tk.LEFT, fill=tk.Y, padx=8)

        # Right panel: items
        right = tk.Frame(main)
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.list_title = tk.Label(right, text="Select a list", font=("Arial", 11, "bold"), anchor="w")
        self.list_title.pack(fill=tk.X)

        btn_row2 = tk.Frame(right)
        btn_row2.pack(fill=tk.X, pady=(2, 2))
        tk.Button(btn_row2, text="Add Item",    width=9,  command=self.cmd_add_item).pack(side=tk.LEFT, padx=(0, 2))
        tk.Button(btn_row2, text="Rename Item", width=11, command=self.cmd_rename_item).pack(side=tk.LEFT, padx=(0, 2))
        tk.Button(btn_row2, text="Remove Item", width=11, command=self.cmd_remove_item).pack(side=tk.LEFT)

        item_frame = tk.Frame(right)
        item_frame.pack(fill=tk.BOTH, expand=True, pady=(4, 0))
        self.item_listbox = tk.Listbox(item_frame, font=("Courier", 10), activestyle="dotbox", selectmode="browse")
        vsb2 = ttk.Scrollbar(item_frame, orient="vertical", command=self.item_listbox.yview)
        self.item_listbox.configure(yscrollcommand=vsb2.set)
        vsb2.pack(side=tk.RIGHT, fill=tk.Y)
        self.item_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Status bar
        self.status_var = tk.StringVar(value="Ready")
        tk.Label(self.root, textvariable=self.status_var, anchor="w",
                 relief=tk.SUNKEN, font=("Arial", 9)).pack(side=tk.BOTTOM, fill=tk.X)

        self._refresh_lists()

    # ------------------------------------------------------------------
    # Refresh helpers
    # ------------------------------------------------------------------

    def _user_lists(self):
        return [l for l in self.list_manager.readAllLists() if l.userId == self.current_user.username]

    def _list_label(self, lst):
        if lst.parentId and lst.parentId in self.db.lists:
            parent_name = self.db.lists[lst.parentId].listName
            return f"{lst.listName}  (extends '{parent_name}')"
        return lst.listName

    def _refresh_lists(self):
        self.list_box.delete(0, tk.END)
        self._list_order = []

        for lst in self._user_lists():
            self.list_box.insert(tk.END, self._list_label(lst))
            self._list_order.append(lst.listId)

        if self.selected_list_id and self.selected_list_id in self.db.lists:
            try:
                idx = self._list_order.index(self.selected_list_id)
                self.list_box.selection_set(idx)
                self.list_box.see(idx)
            except ValueError:
                pass

        self.status_var.set(f"{len(self._list_order)} list(s)")

    def _refresh_items(self):
        self.item_listbox.delete(0, tk.END)
        if not self.selected_list_id or self.selected_list_id not in self.db.lists:
            self.list_title.config(text="Select a list")
            return

        g_list = self.db.lists[self.selected_list_id]
        parent_name = (
            self.db.lists[g_list.parentId].listName
            if g_list.parentId and g_list.parentId in self.db.lists
            else None
        )
        ext = f"  (extends '{parent_name}')" if parent_name else "  (root)"
        self.list_title.config(text=f"'{g_list.listName}'{ext}")

        items = self.list_manager.readListDisplayItems(self.selected_list_id)
        for item in items:
            check = "[x]" if (item.get("isChecked") and not item.get("isInherited")) else "[ ]"
            tag = "  (inherited)" if item.get("isInherited") else ""
            self.item_listbox.insert(tk.END, f"{check}  {item['name']}{tag}")

        direct_count = len(self.list_manager.readDirectItems(self.selected_list_id))
        self.status_var.set(
            f"'{g_list.listName}'  —  {len(items)} visible item(s)  ({direct_count} direct)"
        )

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def _on_list_select(self, _event):
        sel = self.list_box.curselection()
        if sel:
            self.selected_list_id = self._list_order[sel[0]]
            self._refresh_items()

    # ------------------------------------------------------------------
    # Commands: lists
    # ------------------------------------------------------------------

    def cmd_add_list(self):
        name = simpledialog.askstring("Add List", "List name (leave blank to auto-name):", parent=self.root)
        if name is None:
            return
        self.list_manager.createList(name=name.strip(), userId=self.current_user.username)
        self._save()
        self._refresh_lists()

    def cmd_extend_list(self):
        if not self.selected_list_id or self.selected_list_id not in self.db.lists:
            messagebox.showwarning("No Selection", "Select a list to extend first.")
            return
        parent_name = self.db.lists[self.selected_list_id].listName
        name = simpledialog.askstring(
            "Extend List",
            f"Name for child list\n(extending '{parent_name}'):\n\nLeave blank to auto-name.",
            parent=self.root,
        )
        if name is None:
            return
        self.list_manager.createList(
            name=name.strip(),
            optionalParentId=self.selected_list_id,
            userId=self.current_user.username,
        )
        self._save()
        self._refresh_lists()

    def cmd_rename_list(self):
        if not self.selected_list_id or self.selected_list_id not in self.db.lists:
            messagebox.showwarning("No Selection", "Select a list to rename first.")
            return
        current = self.db.lists[self.selected_list_id].listName
        new_name = simpledialog.askstring("Rename List", "New name:", initialvalue=current, parent=self.root)
        if new_name and new_name.strip():
            try:
                self.list_manager.renameList(self.selected_list_id, new_name.strip())
            except ValueError as e:
                messagebox.showerror("Error", str(e))
                return
            self._save()
            self._refresh_lists()
            self._refresh_items()

    def cmd_delete_list(self):
        if not self.selected_list_id or self.selected_list_id not in self.db.lists:
            messagebox.showwarning("No Selection", "Select a list to delete first.")
            return
        name = self.db.lists[self.selected_list_id].listName
        if not messagebox.askyesno(
            "Delete List",
            f"Delete '{name}'?\n\nChildren will be re-pointed to its parent and their visible contents preserved.",
        ):
            return
        self.list_manager.deleteList(self.selected_list_id)
        self.selected_list_id = None
        self._save()
        self._refresh_lists()
        self._refresh_items()

    # ------------------------------------------------------------------
    # Commands: items
    # ------------------------------------------------------------------

    def cmd_add_item(self):
        if not self.selected_list_id or self.selected_list_id not in self.db.lists:
            messagebox.showwarning("No Selection", "Select a list first.")
            return
        name = simpledialog.askstring("Add Item", "Item name:", parent=self.root)
        if name and name.strip():
            self.item_manager.addItemToList(listId=self.selected_list_id, itemName=name.strip())
            self._save()
            self._refresh_items()

    def cmd_rename_item(self):
        if not self.selected_list_id:
            return
        sel = self.item_listbox.curselection()
        if not sel:
            messagebox.showwarning("No Selection", "Select an item to rename first.")
            return
        idx = sel[0]
        items = self.list_manager.readListDisplayItems(self.selected_list_id)
        item = items[idx]
        new_name = simpledialog.askstring("Rename Item", "New name:", initialvalue=item["name"], parent=self.root)
        if new_name and new_name.strip():
            try:
                self.item_manager.editItemInList(self.selected_list_id, item["itemId"], new_name.strip())
            except ValueError as e:
                messagebox.showerror("Error", str(e))
                return
            self._save()
            self._refresh_items()

    def cmd_remove_item(self):
        if not self.selected_list_id:
            return
        sel = self.item_listbox.curselection()
        if not sel:
            messagebox.showwarning("No Selection", "Select an item to remove first.")
            return
        idx = sel[0]
        items = self.list_manager.readListDisplayItems(self.selected_list_id)
        item = items[idx]
        self.item_manager.removeItemFromList(self.selected_list_id, item["itemId"])
        self._save()
        self._refresh_items()


# ------------------------------------------------------------------
# Entry point
# ------------------------------------------------------------------

if __name__ == "__main__":
    root = tk.Tk()
    GroceryApp(root)
    root.mainloop()
