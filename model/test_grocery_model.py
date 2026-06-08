# test_grocery_model.py
import unittest
from typing import Optional, List as TypeList

# Import the core entity data structural blueprints from your original file
from grocery_model import User, Item, ListEntry, GroceryList

# ==========================================
# SIMULATED DATABASE ENGINE (FOR TESTING STATE)
# ==========================================
class MockDatabase:
    def __init__(self):
        self.lists = {}
        self.items = {}
        self.entries = []

    def clear(self):
        self.lists.clear()
        self.items.clear()
        self.entries.clear()

db = MockDatabase()


# ==========================================
# WORKING TEST IMPLEMENTATION OF CONTROLLERS
# ==========================================
class ConcreteListManager:
    def createList(self, name: str, listId: str, optionalParentId: Optional[str] = None, userId: Optional[str] = None) -> GroceryList:
        if optionalParentId and name == "":
            parent = db.lists.get(optionalParentId)
            name = f"Copy of {parent.listName}" if parent else "Copy of List"
        elif name == "":
            name = f"List{len(db.lists) + 1}"
            
        g_list = GroceryList(name, listId, optionalParentId, userId)
        db.lists[listId] = g_list
        return g_list

    def readListDisplayItems(self, listId: str) -> TypeList[dict]:
        """Runs the Bottom-Up Compilation Loop specified in the model design."""
        display_map = {}
        current_pointer = listId
        
        while current_pointer is not None:
            current_entries = [e for e in db.entries if e.listId == current_pointer]
            
            for entry in current_entries:
                if entry.itemId in display_map:
                    continue
                if entry.isMaskedHidden:
                    display_map[entry.itemId] = {"hidden": True}
                    continue
                
                master_item = db.items.get(entry.itemId)
                item_name = entry.customNameOverride if entry.customNameOverride else (master_item.itemName if master_item else "Unknown")
                
                display_map[entry.itemId] = {
                    "itemId": entry.itemId,
                    "name": item_name,
                    "isChecked": entry.isChecked,
                    "isInherited": entry.listId != listId,
                    "hidden": False
                }
            
            g_list = db.lists.get(current_pointer)
            current_pointer = g_list.parentId if g_list else None
            
        return [v for k, v in display_map.items() if not v.get("hidden", False)]

    def deleteList(self, listId: str) -> None:
        """Safely removes a node, running Dynamic Relationship Repair and Hard-Copy captures."""
        target_list = db.lists.get(listId)
        if not target_list:
            return
            
        grandparent_id = target_list.parentId
        immediate_children = [l for l in db.lists.values() if l.parentId == listId]
        
        # 1. Gather snapshots and upgrade child structural pointers while parent data is intact
        child_snapshots = {}
        for child in immediate_children:
            child_snapshots[child.listId] = self.readListDisplayItems(child.listId)
            
            if grandparent_id:
                child.parentId = grandparent_id
            else:
                child.parentId = None

        # 2. Safely purge the deleted parent list's native records
        db.entries = [e for e in db.entries if e.listId != listId]
        
        # 3. Commit hard-copy snapshot injections for orphaned standalone lists
        for child in immediate_children:
            if not grandparent_id:
                db.entries = [e for e in db.entries if e.listId != child.listId]
                
                for snap_item in child_snapshots[child.listId]:
                    new_entry = ListEntry(listId=child.listId, itemId=snap_item["itemId"], isChecked=snap_item["isChecked"])
                    db.entries.append(new_entry)
                    
        if listId in db.lists:
            del db.lists[listId]


class ConcreteItemManager:
    def addItemToList(self, listId: str, itemId: str, itemName: str) -> None:
        if itemId not in db.items:
            db.items[itemId] = Item(itemId, itemName)
        entry = ListEntry(listId=listId, itemId=itemId)
        db.entries.append(entry)

    def editItemInList(self, listId: str, itemId: str, newName: str) -> None:
        native_entry = next((e for e in db.entries if e.listId == listId and e.itemId == itemId), None)
        
        if native_entry:
            master_item = db.items.get(itemId)
            if master_item:
                master_item.itemName = newName
        else:
            forked_entry = ListEntry(listId=listId, itemId=itemId, customNameOverride=newName)
            db.entries.append(forked_entry)

    def removeItemFromList(self, listId: str, itemId: str) -> None:
        native_entry = next((e for e in db.entries if e.listId == listId and e.itemId == itemId), None)
        
        if native_entry:
            db.entries.remove(native_entry)
        else:
            mask_entry = ListEntry(listId=listId, itemId=itemId, isMaskedHidden=True)
            db.entries.append(mask_entry)


# ==========================================
# 4. AUTOMATED SYSTEM TEST CASES
# ==========================================
class TestGroceryDataModel(unittest.TestCase):

    def setUp(self):
        db.clear()
        self.list_manager = ConcreteListManager()
        self.item_manager = ConcreteItemManager()

    def test_create_and_read_hierarchy(self):
        self.list_manager.createList(name="Weekly Grocery", listId="L1")
        self.item_manager.addItemToList(listId="L1", itemId="I1", itemName="Whole Milk")
        self.list_manager.createList(name="", listId="L2", optionalParentId="L1")
        
        child_items = self.list_manager.readListDisplayItems("L2")
        self.assertEqual(len(child_items), 1)
        self.assertEqual(child_items[0]["name"], "Whole Milk")
        self.assertTrue(child_items[0]["isInherited"])  

    def test_item_editing_and_forking(self):
        self.list_manager.createList(name="Master List", listId="L1")
        self.item_manager.addItemToList(listId="L1", itemId="I1", itemName="Apples")
        self.list_manager.createList(name="Child List", listId="L2", optionalParentId="L1")
        
        self.item_manager.editItemInList(listId="L2", itemId="I1", newName="Organic Green Apples")
        
        parent_view = self.list_manager.readListDisplayItems("L1")
        child_view = self.list_manager.readListDisplayItems("L2")
        
        self.assertEqual(parent_view[0]["name"], "Apples")
        self.assertEqual(child_view[0]["name"], "Organic Green Apples")

    def test_inherited_item_deletion_masking(self):
        self.list_manager.createList(name="Master List", listId="L1")
        self.item_manager.addItemToList(listId="L1", itemId="I1", itemName="Banana")
        self.list_manager.createList(name="Child List", listId="L2", optionalParentId="L1")
        
        self.item_manager.removeItemFromList(listId="L2", itemId="I1")
        
        parent_view = self.list_manager.readListDisplayItems("L1")
        child_view = self.list_manager.readListDisplayItems("L2")
        
        self.assertEqual(len(parent_view), 1)
        self.assertEqual(len(child_view), 0)

    def test_cascading_deletion_with_grandparent(self):
        self.list_manager.createList(name="Grandparent", listId="L1")
        self.list_manager.createList(name="Parent", listId="L2", optionalParentId="L1")
        self.list_manager.createList(name="Child", listId="L3", optionalParentId="L2")
        
        self.list_manager.deleteList("L2")
        
        child_list = db.lists.get("L3")
        self.assertEqual(child_list.parentId, "L1")

    def test_cascading_deletion_orphan_upgrade(self):
        self.list_manager.createList(name="Root Parent", listId="L1")
        self.item_manager.addItemToList(listId="L1", itemId="I1", itemName="Cereal")
        self.list_manager.createList(name="Child", listId="L2", optionalParentId="L1")
        
        self.list_manager.deleteList("L1")
        
        child_list = db.lists.get("L2")
        child_view = self.list_manager.readListDisplayItems("L2")
        
        self.assertIsNone(child_list.parentId)
        self.assertEqual(len(child_view), 1)
        self.assertEqual(child_view[0]["name"], "Cereal")
        self.assertFalse(child_view[0]["isInherited"])  

    def test_user_profile_list_binding(self):
        """Verifies the User domain properties and cross-entity relational ownership."""
        # 1. Initialize user with a string-based zip code profile matching requirements
        mock_user = User(
            username="ethan99", 
            password="securePassword123", 
            firstName="Ethan", 
            lastName="Project", 
            zipCode="02108"  # String type preserves critical leading zeros
        )
        
        # Assert user initialization variables mapped properly
        self.assertEqual(mock_user.username, "ethan99")
        self.assertEqual(mock_user.zipCode, "02108")
        
        # 2. Create a list explicitly associated with this authenticated user
        user_list = self.list_manager.createList(
            name="My Private List", 
            listId="UL_99", 
            optionalParentId=None, 
            userId=mock_user.username
        )
        
        # Verify the list data entity successfully maps back to our User owner
        self.assertEqual(user_list.userId, "ethan99")
        self.assertIsNone(user_list.parentId)


if __name__ == "__main__":
    unittest.main()