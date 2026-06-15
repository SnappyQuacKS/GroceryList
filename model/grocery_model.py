import hashlib
import uuid
from typing import Dict, Optional, List as TypeList

try:
    import psycopg2
except ImportError:
    raise ImportError("psycopg2 is required: pip install psycopg2-binary")

# ==========================================
# DATABASE CONNECTION CONFIG
# ==========================================

DB_CONFIG = {
    "host":     "localhost",
    "port":     5432,
    "dbname":   "grocerylist",
    "user":     "postgres",
    "password": "user123",
}

def _connect():
    return psycopg2.connect(**DB_CONFIG)


# ==========================================
# 1. CORE ENTITIES (DATA OBJECTS)
# ==========================================

class User:
    """Represents an application user profile."""
    def __init__(self, username: str, password: str, firstName: str, lastName: str, zipCode: str):
        self.username: str = username
        self.password: str = password
        self.firstName: str = firstName
        self.lastName: str = lastName
        self.zipCode: str = zipCode  # Kept as str to avoid dropping leading zeros


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
    def __init__(self, listId: str, itemId: str, isChecked: bool = False,
                 isMaskedHidden: bool = False, customNameOverride: Optional[str] = None):
        self.listId: str = listId
        self.itemId: str = itemId
        self.isChecked: bool = isChecked
        self.isMaskedHidden: bool = isMaskedHidden
        self.customNameOverride: Optional[str] = customNameOverride


class GroceryList:
    """Represents an individual grocery list node within the hierarchical tree structure."""
    def __init__(self, listName: str, listId: str,
                 parentId: Optional[str] = None, userId: Optional[str] = None):
        self.listName: str = listName
        self.listId: str = listId
        self.parentId: Optional[str] = parentId
        self.userId: Optional[str] = userId


# ==========================================
# 2. STORAGE LAYER
# ==========================================

def _topo_sort_lists(lists_dict: Dict[str, "GroceryList"]) -> TypeList["GroceryList"]:
    """Return lists sorted so every parent appears before its children."""
    sorted_out: TypeList[GroceryList] = []
    remaining = dict(lists_dict)
    while remaining:
        done_ids = {l.listId for l in sorted_out}
        ready = [l for l in remaining.values() if l.parentId is None or l.parentId in done_ids]
        if not ready:
            # Circular or orphaned refs — append remainder as-is
            sorted_out.extend(remaining.values())
            break
        for lst in ready:
            sorted_out.append(lst)
            del remaining[lst.listId]
    return sorted_out


class Database:
    """In-memory store that syncs to PostgreSQL on save/load."""

    def __init__(self):
        self.users:   Dict[str, User]        = {}
        self.lists:   Dict[str, GroceryList] = {}
        self.items:   Dict[str, Item]        = {}
        self.entries: TypeList[ListEntry]    = []

    def clear(self) -> None:
        self.users.clear()
        self.lists.clear()
        self.items.clear()
        self.entries.clear()

    # ── Persistence ────────────────────────────────────────────────────────────

    def save(self) -> None:
        """Persist the full in-memory state to PostgreSQL (replace-all strategy)."""
        conn = _connect()
        cur = conn.cursor()
        try:
            # Defer FK checks so we can delete/insert in any order
            cur.execute("SET CONSTRAINTS ALL DEFERRED")

            cur.execute("DELETE FROM list_entries")
            cur.execute("DELETE FROM grocery_lists")
            cur.execute("DELETE FROM items")
            cur.execute("DELETE FROM users")

            for u in self.users.values():
                cur.execute(
                    "INSERT INTO users (username, password_hash, first_name, last_name, zip_code) "
                    "VALUES (%s, %s, %s, %s, %s)",
                    (u.username, u.password, u.firstName, u.lastName, u.zipCode),
                )

            for i in self.items.values():
                cur.execute(
                    "INSERT INTO items (item_id, item_name) VALUES (%s, %s)",
                    (i.itemId, i.itemName),
                )

            for lst in _topo_sort_lists(self.lists):
                cur.execute(
                    "INSERT INTO grocery_lists (list_id, list_name, parent_id, user_id) "
                    "VALUES (%s, %s, %s, %s)",
                    (lst.listId, lst.listName, lst.parentId, lst.userId),
                )

            for e in self.entries:
                cur.execute(
                    "INSERT INTO list_entries "
                    "(list_id, item_id, is_checked, is_masked_hidden, custom_name_override) "
                    "VALUES (%s, %s, %s, %s, %s)",
                    (e.listId, e.itemId, e.isChecked, e.isMaskedHidden, e.customNameOverride),
                )

            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            cur.close()
            conn.close()

    @classmethod
    def load(cls) -> "Database":
        """Load the full state from PostgreSQL into memory."""
        db = cls()
        conn = _connect()
        cur = conn.cursor()
        try:
            cur.execute("SELECT username, password_hash, first_name, last_name, zip_code FROM users")
            for username, password_hash, first_name, last_name, zip_code in cur.fetchall():
                u = User(username=username, password=password_hash,
                         firstName=first_name, lastName=last_name, zipCode=zip_code)
                db.users[u.username] = u

            cur.execute("SELECT item_id, item_name FROM items")
            for item_id, item_name in cur.fetchall():
                i = Item(itemId=item_id, itemName=item_name)
                db.items[i.itemId] = i

            cur.execute("SELECT list_id, list_name, parent_id, user_id FROM grocery_lists")
            for list_id, list_name, parent_id, user_id in cur.fetchall():
                lst = GroceryList(listName=list_name, listId=list_id,
                                  parentId=parent_id, userId=user_id)
                db.lists[lst.listId] = lst

            cur.execute(
                "SELECT list_id, item_id, is_checked, is_masked_hidden, custom_name_override "
                "FROM list_entries"
            )
            for list_id, item_id, is_checked, is_masked_hidden, custom_name_override in cur.fetchall():
                e = ListEntry(listId=list_id, itemId=item_id, isChecked=is_checked,
                              isMaskedHidden=is_masked_hidden, customNameOverride=custom_name_override)
                db.entries.append(e)

            return db
        finally:
            cur.close()
            conn.close()


# ==========================================
# 3. MANAGEMENT LAYER (SERVICE CONTROLLERS)
# ==========================================

class ListManager:
    """Handles operational mutations and compilation routines for List tree schemas."""

    def __init__(self, db: Database):
        self.db = db

    def createList(self, name: str, listId: Optional[str] = None,
                   optionalParentId: Optional[str] = None, userId: Optional[str] = None) -> GroceryList:
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
        """
        display_map: Dict[str, dict] = {}
        ancestor_item_ids: set = set()
        current_pointer: Optional[str] = listId
        visited = set()

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
                item_name = entry.customNameOverride if entry.customNameOverride else (
                    master_item.itemName if master_item else "Unknown"
                )

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
        """Returns only items with a direct entry in this list (not inherited)."""
        if listId not in self.db.lists:
            raise ValueError(f"List '{listId}' does not exist")
        return [item for item in self.readListDisplayItems(listId) if not item.get("isInherited")]

    def readAllItems(self, listId: str) -> TypeList[dict]:
        """Returns all visible items for a list (inherited + direct), excluding masked entries."""
        if listId not in self.db.lists:
            raise ValueError(f"List '{listId}' does not exist")
        return self.readListDisplayItems(listId)

    def renameList(self, listId: str, newName: str) -> None:
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

        child_snapshots = {child.listId: self._compileDisplayMap(child.listId) for child in immediate_children}

        for child in immediate_children:
            child.parentId = grandparent_id

        self.db.entries = [e for e in self.db.entries if e.listId != listId]
        del self.db.lists[listId]

        for child in immediate_children:
            before = child_snapshots[child.listId]
            after = self._compileDisplayMap(child.listId)

            for item_id, snap in before.items():
                now = after.get(item_id)

                if not snap.get("hidden", False):
                    if now is None or now.get("hidden", False) or now.get("name") != snap["name"] or now.get("isChecked") != snap["isChecked"]:
                        master = self.db.items.get(item_id)
                        override = snap["name"] if (master is None or master.itemName != snap["name"]) else None
                        self.db.entries = [e for e in self.db.entries if not (e.listId == child.listId and e.itemId == item_id)]
                        self.db.entries.append(ListEntry(listId=child.listId, itemId=item_id, isChecked=snap["isChecked"], customNameOverride=override))
                else:
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
        if listId not in self.db.lists:
            raise ValueError(f"List '{listId}' does not exist")
        if itemName == "" and (itemId is None or itemId not in self.db.items):
            raise ValueError("Item name cannot be empty for a new item")

        if itemId is None and itemName:
            itemId = self._findItemIdByName(listId, itemName)

        if itemId is None:
            itemId = str(uuid.uuid4())
        if itemId not in self.db.items:
            self.db.items[itemId] = Item(itemId, itemName)

        existing = self._entryInList(listId, itemId)
        if existing is not None:
            existing.isMaskedHidden = False
            return existing

        entry = ListEntry(listId=listId, itemId=itemId)
        self.db.entries.append(entry)
        return entry

    def toggleItemChecked(self, listId: str, itemId: str) -> bool:
        entry = self._entryInList(listId, itemId)
        if entry is None:
            if not self._inheritedFromAncestor(listId, itemId):
                raise ValueError(f"Item '{itemId}' is not in list '{listId}'")
            entry = ListEntry(listId=listId, itemId=itemId, isChecked=True)
            self.db.entries.append(entry)
            return True
        entry.isChecked = not entry.isChecked
        return entry.isChecked

    def editItemInList(self, listId: str, itemId: str, newName: str) -> None:
        if newName == "":
            raise ValueError("Item name cannot be empty")

        entry = self._entryInList(listId, itemId)

        if entry is not None:
            if entry.customNameOverride is not None or self._inheritedFromAncestor(listId, itemId):
                entry.customNameOverride = newName
                entry.isMaskedHidden = False
            else:
                master_item = self.db.items.get(itemId)
                if master_item:
                    master_item.itemName = newName
        elif self._inheritedFromAncestor(listId, itemId):
            self.db.entries.append(ListEntry(listId=listId, itemId=itemId, customNameOverride=newName))
        else:
            raise ValueError(f"Item '{itemId}' is not in list '{listId}'")

    def _purgeDescendantForks(self, listId: str, itemId: str) -> None:
        for child in [l for l in self.db.lists.values() if l.parentId == listId]:
            local_entry = self._entryInList(child.listId, itemId)
            if local_entry is not None and not self._inheritedFromAncestor(child.listId, itemId):
                self.db.entries.remove(local_entry)
            self._purgeDescendantForks(child.listId, itemId)

    def removeItemFromList(self, listId: str, itemId: str) -> None:
        entry = self._entryInList(listId, itemId)
        inherited = self._inheritedFromAncestor(listId, itemId)

        if entry is not None:
            if entry.isMaskedHidden:
                return
            if inherited:
                entry.isMaskedHidden = True
                entry.customNameOverride = None
                entry.isChecked = False
            else:
                self.db.entries.remove(entry)
                self._purgeDescendantForks(listId, itemId)
        elif inherited:
            self.db.entries.append(ListEntry(listId=listId, itemId=itemId, isMaskedHidden=True))


# ==========================================
# 4. USER MANAGEMENT
# ==========================================

class UserManager:
    """Handles account creation and authentication."""

    def __init__(self, db: Database):
        self.db = db

    @staticmethod
    def _hash(password: str) -> str:
        return hashlib.sha256(password.encode()).hexdigest()

    def createUser(self, username: str, password: str,
                   firstName: str = "", lastName: str = "", zipCode: str = "") -> User:
        if not username.strip():
            raise ValueError("Username cannot be empty")
        if username in self.db.users:
            raise ValueError(f"Username '{username}' is already taken")
        if not password:
            raise ValueError("Password cannot be empty")
        user = User(
            username=username,
            password=self._hash(password),
            firstName=firstName,
            lastName=lastName,
            zipCode=zipCode,
        )
        self.db.users[username] = user
        return user

    def authenticate(self, username: str, password: str) -> Optional[User]:
        user = self.db.users.get(username)
        if user and user.password == self._hash(password):
            return user
        return None
