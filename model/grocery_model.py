import uuid
from typing import Dict, Optional, List as TypeList

# ==========================================
# 1. CORE ENTITIES (DATA OBJECTS)
# ==========================================

class User:
    """Represents an application user profile."""
    def __init__(self, username: str, password: str, firstName: str, lastName: str, zipCode: str):
        self.username: str = username
        self.password: str = password  # NOTE: hash this before persisting in a real backend
        self.firstName: str = firstName
        self.lastName: str = lastName
        self.zipCode: str = zipCode  # Kept as String to avoid dropping leading zeros


class Item:
    """Represents a master blueprint definition of a unique grocery product catalog entry."""
    def __init__(self, itemId: str, itemName: str):
        self.itemId: str = itemId
        self.itemName: str = itemName


class ListEntry:
    """
    Acts as the Junction Class mapping a single Item to a specific List container.
    Tracks state modifications unique to this specific list context.
    """
    def __init__(self, listId: str, itemId: str, isChecked: bool = False, isMaskedHidden: bool = False, customNameOverride: Optional[str] = None):
        self.listId: str = listId
        self.itemId: str = itemId
        self.isChecked: bool = isChecked
        self.isMaskedHidden: bool = isMaskedHidden
        self.customNameOverride: Optional[str] = customNameOverride  # Set when child customizes an inherited item name


class GroceryList:  # Named 'GroceryList' to avoid keyword conflicts with Python's native list type
    """Represents an individual grocery list node within the hierarchical tree structure."""
    def __init__(self, listName: str, listId: str, parentId: Optional[str] = None, userId: Optional[str] = None):
        self.listName: str = listName
        self.listId: str = listId
        self.parentId: Optional[str] = parentId  # None indicates a standalone root parent list
        self.userId: Optional[str] = userId      # None indicates a local device guest cache state


# ==========================================
# 2. STORAGE LAYER (IN-MEMORY DATABASE)
# ==========================================

class Database:
    """Simple in-memory store. Swap this out for a real persistence layer later."""
    def __init__(self):
        self.lists: Dict[str, GroceryList] = {}
        self.items: Dict[str, Item] = {}
        self.entries: TypeList[ListEntry] = []

    def clear(self) -> None:
        self.lists.clear()
        self.items.clear()
        self.entries.clear()


# ==========================================
# 3. MANAGEMENT LAYER (SERVICE CONTROLLERS)
# ==========================================

class ListManager:
    """Handles operational mutations and compilation routines for List tree schemas."""

    def __init__(self, db: Database):
        self.db = db

    def createList(self, name: str, listId: Optional[str] = None, optionalParentId: Optional[str] = None, userId: Optional[str] = None) -> GroceryList:
        """Instantiates a standard root list or an extended child branch."""
        if optionalParentId is not None and optionalParentId not in self.db.lists:
            raise ValueError(f"Parent list '{optionalParentId}' does not exist")
        if listId is None:
            listId = str(uuid.uuid4())
        if listId in self.db.lists:
            raise ValueError(f"List id '{listId}' already exists")

        if name == "":
            existing_names = {l.listName for l in self.db.lists.values()}
            n = 1
            while f"List{n}" in existing_names:
                n += 1
            name = f"List{n}"

        g_list = GroceryList(name, listId, optionalParentId, userId)
        self.db.lists[listId] = g_list
        return g_list

    def _compileDisplayMap(self, listId: str) -> Dict[str, dict]:
        """
        Bottom-Up Compilation Loop. Walks from the target list up through its
        ancestors; the first (deepest) entry seen for each itemId wins.
        Returns the full map including hidden/masked items.
        """
        display_map: Dict[str, dict] = {}
        ancestor_item_ids: set = set()  # itemIds present in any ancestor list
        current_pointer: Optional[str] = listId
        visited = set()  # guards against accidental parent-pointer cycles

        while current_pointer is not None and current_pointer not in visited:
            visited.add(current_pointer)
            is_ancestor = current_pointer != listId
            current_entries = [e for e in self.db.entries if e.listId == current_pointer]

            for entry in current_entries:
                if is_ancestor:
                    ancestor_item_ids.add(entry.itemId)
                if entry.itemId in display_map:
                    continue
                if entry.isMaskedHidden:
                    display_map[entry.itemId] = {"itemId": entry.itemId, "hidden": True}
                    continue

                master_item = self.db.items.get(entry.itemId)
                item_name = entry.customNameOverride if entry.customNameOverride else (master_item.itemName if master_item else "Unknown")

                display_map[entry.itemId] = {
                    "itemId": entry.itemId,
                    "name": item_name,
                    "isChecked": entry.isChecked,
                    "isInherited": is_ancestor,
                    "customNameOverride": entry.customNameOverride,
                    "hidden": False,
                }

            g_list = self.db.lists.get(current_pointer)
            current_pointer = g_list.parentId if g_list else None

        # A forked item (local entry overriding an ancestor's item) is still inherited.
        # Without this pass, renaming/toggling an inherited item would silently drop its
        # inherited status because the fork entry carries listId == listId.
        for item_id, data in display_map.items():
            if not data.get("hidden") and item_id in ancestor_item_ids:
                data["isInherited"] = True

        return display_map

    def readListDisplayItems(self, listId: str) -> TypeList[dict]:
        """Resolves the visible items for a list (masked/hidden items excluded)."""
        if listId not in self.db.lists:
            raise ValueError(f"List '{listId}' does not exist")
        display_map = self._compileDisplayMap(listId)
        return [v for v in display_map.values() if not v.get("hidden", False)]

    def readAllLists(self) -> TypeList[GroceryList]:
        """Returns all lists currently in the database."""
        return list(self.db.lists.values())

    def readDirectItems(self, listId: str) -> TypeList[dict]:
        """Returns only items with a direct entry in this list (not inherited from ancestors)."""
        if listId not in self.db.lists:
            raise ValueError(f"List '{listId}' does not exist")
        return [item for item in self.readListDisplayItems(listId) if not item.get("isInherited")]

    def readAllItems(self, listId: str) -> TypeList[dict]:
        """Returns all visible items for a list (inherited + direct), excluding masked entries."""
        if listId not in self.db.lists:
            raise ValueError(f"List '{listId}' does not exist")
        return self.readListDisplayItems(listId)

    def renameList(self, listId: str, newName: str) -> None:
        """Alters a list's display name."""
        target = self.db.lists.get(listId)
        if not target:
            raise ValueError(f"List '{listId}' does not exist")
        if newName == "":
            raise ValueError("List name cannot be empty")
        target.listName = newName

    def deleteList(self, listId: str) -> None:
        """
        Safely removes a list node. Immediate children are re-pointed to the
        grandparent (pointer repair). Any items the children were inheriting
        from the deleted list are hard-copied into them so their visible
        contents do not change, with custom name overrides preserved.
        """
        target_list = self.db.lists.get(listId)
        if not target_list:
            return

        grandparent_id = target_list.parentId
        immediate_children = [l for l in self.db.lists.values() if l.parentId == listId]

        # 1. Snapshot each child's full compiled view while the parent is intact
        child_snapshots = {child.listId: self._compileDisplayMap(child.listId) for child in immediate_children}

        # 2. Pointer repair: promote children to the grandparent (or root)
        for child in immediate_children:
            child.parentId = grandparent_id

        # 3. Purge the deleted list's records
        self.db.entries = [e for e in self.db.entries if e.listId != listId]
        del self.db.lists[listId]

        # 4. Reconcile each child against its snapshot so its view is unchanged
        for child in immediate_children:
            before = child_snapshots[child.listId]
            after = self._compileDisplayMap(child.listId)

            for item_id, snap in before.items():
                now = after.get(item_id)

                if not snap.get("hidden", False):
                    # Item was visible before; restore it if it vanished or changed
                    if now is None or now.get("hidden", False) or now.get("name") != snap["name"] or now.get("isChecked") != snap["isChecked"]:
                        master = self.db.items.get(item_id)
                        override = snap["name"] if (master is None or master.itemName != snap["name"]) else None
                        self.db.entries = [e for e in self.db.entries if not (e.listId == child.listId and e.itemId == item_id)]
                        self.db.entries.append(ListEntry(listId=child.listId, itemId=item_id, isChecked=snap["isChecked"], customNameOverride=override))
                else:
                    # Item was hidden before; re-mask it if it resurfaced via the grandparent
                    if now is not None and not now.get("hidden", False):
                        self.db.entries.append(ListEntry(listId=child.listId, itemId=item_id, isMaskedHidden=True))

    def duplicateAsDecoupledCopy(self, listId: str, newListId: Optional[str] = None) -> GroceryList:
        """Snapshot Extraction -> Flattened Generation -> Hard-Copy Instantiation."""
        source = self.db.lists.get(listId)
        if not source:
            raise ValueError(f"List '{listId}' does not exist")

        snapshot = self.readListDisplayItems(listId)
        copy = self.createList(name=f"Copy of {source.listName}", listId=newListId, optionalParentId=None, userId=source.userId)

        for snap in snapshot:
            master = self.db.items.get(snap["itemId"])
            override = snap["name"] if (master is None or master.itemName != snap["name"]) else None
            self.db.entries.append(ListEntry(listId=copy.listId, itemId=snap["itemId"], isChecked=snap["isChecked"], customNameOverride=override))

        return copy


class ItemManager:
    """Governs item-to-list mapping modifications and scope forking logic."""

    def __init__(self, db: Database):
        self.db = db

    def _entryInList(self, listId: str, itemId: str) -> Optional[ListEntry]:
        return next((e for e in self.db.entries if e.listId == listId and e.itemId == itemId), None)

    def _inheritedFromAncestor(self, listId: str, itemId: str) -> bool:
        """True if any ancestor of listId contributes a visible entry for itemId."""
        g_list = self.db.lists.get(listId)
        pointer = g_list.parentId if g_list else None
        visited = {listId}
        while pointer is not None and pointer not in visited:
            visited.add(pointer)
            entry = self._entryInList(pointer, itemId)
            if entry is not None:
                return not entry.isMaskedHidden
            ancestor = self.db.lists.get(pointer)
            pointer = ancestor.parentId if ancestor else None
        return False

    def _findItemIdByName(self, listId: str, itemName: str) -> Optional[str]:
        """
        Looks up an existing itemId whose display name matches itemName.
        Masked entries in this list are checked first (by override or master name)
        so that re-adding a deleted inherited item reuses the same id and unmasks it.
        """
        for entry in self.db.entries:
            if entry.listId == listId and entry.isMaskedHidden:
                master = self.db.items.get(entry.itemId)
                display = entry.customNameOverride or (master.itemName if master else None)
                if display == itemName:
                    return entry.itemId
        for item in self.db.items.values():
            if item.itemName == itemName:
                return item.itemId
        return None

    def addItemToList(self, listId: str, itemId: Optional[str] = None, itemName: str = "") -> ListEntry:
        """Appends a fresh line entry localized to the targeted list scope."""
        if listId not in self.db.lists:
            raise ValueError(f"List '{listId}' does not exist")
        if itemName == "" and (itemId is None or itemId not in self.db.items):
            raise ValueError("Item name cannot be empty for a new item")

        # When adding by name only, reuse an existing itemId if one matches so that
        # re-adding a masked inherited item unmasks it rather than creating a duplicate.
        if itemId is None and itemName:
            itemId = self._findItemIdByName(listId, itemName)

        if itemId is None:
            itemId = str(uuid.uuid4())
        if itemId not in self.db.items:
            self.db.items[itemId] = Item(itemId, itemName)

        existing = self._entryInList(listId, itemId)
        if existing is not None:
            existing.isMaskedHidden = False  # re-adding un-hides a previously masked item
            return existing

        entry = ListEntry(listId=listId, itemId=itemId)
        self.db.entries.append(entry)
        return entry

    def toggleItemChecked(self, listId: str, itemId: str) -> bool:
        """Flips the checked-off state of an item within this list's scope, forking if inherited."""
        entry = self._entryInList(listId, itemId)
        if entry is None:
            if not self._inheritedFromAncestor(listId, itemId):
                raise ValueError(f"Item '{itemId}' is not in list '{listId}'")
            # Fork so the check state is local to this list
            entry = ListEntry(listId=listId, itemId=itemId, isChecked=True)
            self.db.entries.append(entry)
            return True
        entry.isChecked = not entry.isChecked
        return entry.isChecked

    def editItemInList(self, listId: str, itemId: str, newName: str) -> None:
        """
        Determines whether the edit alters a native master string or forks an
        inherited item. Re-editing an existing fork updates the fork's override
        (it never touches the master item, fixing cross-list name corruption).
        """
        if newName == "":
            raise ValueError("Item name cannot be empty")

        entry = self._entryInList(listId, itemId)

        if entry is not None:
            if entry.customNameOverride is not None or self._inheritedFromAncestor(listId, itemId):
                # This entry is a local fork of an inherited item: keep the edit local
                entry.customNameOverride = newName
                entry.isMaskedHidden = False
            else:
                # Truly native to this list: edit the master definition
                master_item = self.db.items.get(itemId)
                if master_item:
                    master_item.itemName = newName
        elif self._inheritedFromAncestor(listId, itemId):
            # Inherited with no local entry yet: create a fork
            self.db.entries.append(ListEntry(listId=listId, itemId=itemId, customNameOverride=newName))
        else:
            raise ValueError(f"Item '{itemId}' is not in list '{listId}'")

    def _purgeDescendantForks(self, listId: str, itemId: str) -> None:
        """Remove orphaned local entries (forks, masks, re-adds) for itemId in all
        descendants of listId when the item no longer has an ancestor providing it."""
        for child in [l for l in self.db.lists.values() if l.parentId == listId]:
            local_entry = self._entryInList(child.listId, itemId)
            if local_entry is not None and not self._inheritedFromAncestor(child.listId, itemId):
                self.db.entries.remove(local_entry)
            self._purgeDescendantForks(child.listId, itemId)

    def removeItemFromList(self, listId: str, itemId: str) -> None:
        """
        Hard-deletes native items, or applies an exclusion mask for inherited
        ones. Removing a local fork of an inherited item also masks it so the
        ancestor's version does not resurface. Repeated removals are no-ops
        rather than stacking duplicate masks.
        When a native item is deleted, any descendant forks/masks for the same
        itemId are also purged since their ancestry source is gone.
        """
        entry = self._entryInList(listId, itemId)
        inherited = self._inheritedFromAncestor(listId, itemId)

        if entry is not None:
            if entry.isMaskedHidden:
                return  # already removed/masked: no-op
            if inherited:
                # Convert the local fork into a mask so the parent's copy stays hidden
                entry.isMaskedHidden = True
                entry.customNameOverride = None
                entry.isChecked = False
            else:
                self.db.entries.remove(entry)
                self._purgeDescendantForks(listId, itemId)
        elif inherited:
            self.db.entries.append(ListEntry(listId=listId, itemId=itemId, isMaskedHidden=True))
