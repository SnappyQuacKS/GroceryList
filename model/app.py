import tkinter as tk
from tkinter import ttk, simpledialog, messagebox
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))
from grocery_model import Database, ListManager, ItemManager


class GroceryApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Grocery List Manager")
        self.root.geometry("720x480")
        self.root.resizable(True, True)

        self.db = Database()
        self.list_manager = ListManager(self.db)
        self.item_manager = ItemManager(self.db)
        self.selected_list_id = None

        self._build_ui()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        main = tk.Frame(self.root, padx=10, pady=10)
        main.pack(fill=tk.BOTH, expand=True)

        # ---- Left panel: flat list ----
        left = tk.Frame(main, width=280)
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=False)
        left.pack_propagate(False)

        tk.Label(left, text="Lists", font=("Arial", 11, "bold")).pack(anchor="w")

        btn_row = tk.Frame(left)
        btn_row.pack(fill=tk.X, pady=(2, 2))
        tk.Button(btn_row, text="Add List", width=9, command=self.cmd_add_list).pack(side=tk.LEFT, padx=(0, 2))
        tk.Button(btn_row, text="Extend",   width=7, command=self.cmd_extend_list).pack(side=tk.LEFT, padx=(0, 2))
        tk.Button(btn_row, text="Rename",   width=7, command=self.cmd_rename_list).pack(side=tk.LEFT, padx=(0, 2))
        tk.Button(btn_row, text="Delete",   width=7, command=self.cmd_delete_list).pack(side=tk.LEFT)

        list_frame = tk.Frame(left)
        list_frame.pack(fill=tk.BOTH, expand=True, pady=(4, 0))
        self.list_box = tk.Listbox(list_frame, font=("Arial", 10), activestyle="dotbox", selectmode="browse")
        vsb = ttk.Scrollbar(list_frame, orient="vertical", command=self.list_box.yview)
        self.list_box.configure(yscrollcommand=vsb.set)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        self.list_box.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.list_box.bind("<<ListboxSelect>>", self._on_list_select)

        # ---- Divider ----
        ttk.Separator(main, orient="vertical").pack(side=tk.LEFT, fill=tk.Y, padx=8)

        # ---- Right panel: items ----
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

        # ---- Status bar ----
        self.status_var = tk.StringVar(value="Ready")
        tk.Label(self.root, textvariable=self.status_var, anchor="w",
                 relief=tk.SUNKEN, font=("Arial", 9)).pack(side=tk.BOTTOM, fill=tk.X)

        self._refresh_lists()

    # ------------------------------------------------------------------
    # Refresh helpers
    # ------------------------------------------------------------------

    def _list_label(self, lst):
        if lst.parentId and lst.parentId in self.db.lists:
            parent_name = self.db.lists[lst.parentId].listName
            return f"{lst.listName}  (extends '{parent_name}')"
        return lst.listName

    def _refresh_lists(self):
        # Remember scroll position and selection
        prev_sel_id = self.selected_list_id

        self.list_box.delete(0, tk.END)
        self._list_order = []  # parallel list of listIds matching each row

        for lst in self.list_manager.readAllLists():
            self.list_box.insert(tk.END, self._list_label(lst))
            self._list_order.append(lst.listId)

        # Restore selection
        if prev_sel_id and prev_sel_id in self.db.lists:
            try:
                idx = self._list_order.index(prev_sel_id)
                self.list_box.selection_set(idx)
                self.list_box.see(idx)
            except ValueError:
                pass

        total = len(self._list_order)
        self.status_var.set(f"{total} list(s) total")

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
            f"'{g_list.listName}'  --  {len(items)} visible item(s)  ({direct_count} direct)"
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
        self.list_manager.createList(name=name.strip())
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
        self.list_manager.createList(name=name.strip(), optionalParentId=self.selected_list_id)
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
        self._refresh_items()


# ------------------------------------------------------------------
# Entry point
# ------------------------------------------------------------------

if __name__ == "__main__":
    root = tk.Tk()
    GroceryApp(root)
    root.mainloop()
