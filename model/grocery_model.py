from typing import Optional, List as TypeList

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
# 2. MANAGEMENT LAYER (SERVICE CONTROLLERS)
# ==========================================

class ListManager:
    """Handles operational mutations and compilation routines for List tree schemas."""
    
    def createList(self, name: str, optionalParentId: Optional[str] = None) -> GroceryList:
        """Instantiates a standard root list or an extended child branch."""
        pass

    def readListDisplayItems(self, listId: str) -> TypeList[ListEntry]:
        """Runs the Bottom-Up Compilation Loop to resolve visible and overridden items."""
        pass

    def renameList(self, listId: str, newName: str) -> None:
        """Alters a list identity while gracefully propagating title cascades."""
        pass

    def deleteList(self, listId: str) -> None:
        """Safely removes a list node, initiating pointer repair or orphan hard-copy captures."""
        pass

    def duplicateAsDecoupledCopy(self, listId: str) -> GroceryList:
        """Executes Snapshot Extraction -> Flattened Generation -> Hard-Copy Instantiation."""
        pass


class ItemManager:
    """Governs item-to-list mapping modifications and scope forking logic."""

    def addItemToList(self, listId: str, itemName: str) -> None:
        """Appends a fresh line entry localized to the targeted list scope."""
        pass

    def editItemInList(self, listId: str, itemId: str, newName: str) -> None:
        """Determines if the edit alters a native parent string or forks an inherited item."""
        pass

    def removeItemFromList(self, listId: str, itemId: str) -> None:
        """Executes a hard deletion for native items, or applies an exclusion mask on inherited ones."""
        pass