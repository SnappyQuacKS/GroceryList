# test_grocery_model.py
import unittest

# The managers under test now live in the model itself (no more concrete
# re-implementations inside the test file).
from grocery_model import User, Database, ListManager, ItemManager


class TestGroceryDataModel(unittest.TestCase):

    def setUp(self):
        self.db = Database()
        self.list_manager = ListManager(self.db)
        self.item_manager = ItemManager(self.db)

    # ------------------------------------------
    # Original behavioral tests
    # ------------------------------------------

    def test_create_and_read_hierarchy(self):
        self.list_manager.createList(name="Weekly Grocery", listId="L1")
        self.item_manager.addItemToList(listId="L1", itemId="I1", itemName="Whole Milk")
        self.list_manager.createList(name="", listId="L2", optionalParentId="L1")

        child_items = self.list_manager.readListDisplayItems("L2")
        self.assertEqual(len(child_items), 1)
        self.assertEqual(child_items[0]["name"], "Whole Milk")
        self.assertTrue(child_items[0]["isInherited"])

        # Empty name with a parent should auto-name as a copy
        self.assertEqual(self.db.lists["L2"].listName, "Copy of Weekly Grocery")

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

        child_list = self.db.lists.get("L3")
        self.assertEqual(child_list.parentId, "L1")

    def test_cascading_deletion_orphan_upgrade(self):
        self.list_manager.createList(name="Root Parent", listId="L1")
        self.item_manager.addItemToList(listId="L1", itemId="I1", itemName="Cereal")
        self.list_manager.createList(name="Child", listId="L2", optionalParentId="L1")

        self.list_manager.deleteList("L1")

        child_list = self.db.lists.get("L2")
        child_view = self.list_manager.readListDisplayItems("L2")

        self.assertIsNone(child_list.parentId)
        self.assertEqual(len(child_view), 1)
        self.assertEqual(child_view[0]["name"], "Cereal")
        self.assertFalse(child_view[0]["isInherited"])

    def test_user_profile_list_binding(self):
        """Verifies the User domain properties and cross-entity relational ownership."""
        mock_user = User(
            username="ethan99",
            password="securePassword123",
            firstName="Ethan",
            lastName="Project",
            zipCode="02108"  # String type preserves critical leading zeros
        )

        self.assertEqual(mock_user.username, "ethan99")
        self.assertEqual(mock_user.zipCode, "02108")

        user_list = self.list_manager.createList(
            name="My Private List",
            listId="UL_99",
            optionalParentId=None,
            userId=mock_user.username
        )

        self.assertEqual(user_list.userId, "ethan99")
        self.assertIsNone(user_list.parentId)

    # ------------------------------------------
    # Regression tests for fixed bugs
    # ------------------------------------------

    def test_reediting_fork_does_not_corrupt_parent(self):
        """Editing a forked item twice must not overwrite the master item name."""
        self.list_manager.createList(name="Parent", listId="L1")
        self.item_manager.addItemToList(listId="L1", itemId="I1", itemName="Apples")
        self.list_manager.createList(name="Child", listId="L2", optionalParentId="L1")

        self.item_manager.editItemInList("L2", "I1", "Green Apples")
        self.item_manager.editItemInList("L2", "I1", "Organic Green Apples")  # second edit

        self.assertEqual(self.list_manager.readListDisplayItems("L1")[0]["name"], "Apples")
        self.assertEqual(self.list_manager.readListDisplayItems("L2")[0]["name"], "Organic Green Apples")

    def test_custom_name_survives_parent_deletion(self):
        """Hard-copy snapshots must preserve customNameOverride."""
        self.list_manager.createList(name="Parent", listId="L1")
        self.item_manager.addItemToList(listId="L1", itemId="I1", itemName="Apples")
        self.list_manager.createList(name="Child", listId="L2", optionalParentId="L1")
        self.item_manager.editItemInList("L2", "I1", "Organic Apples")

        self.list_manager.deleteList("L1")

        child_view = self.list_manager.readListDisplayItems("L2")
        self.assertEqual(len(child_view), 1)
        self.assertEqual(child_view[0]["name"], "Organic Apples")

    def test_removing_fork_does_not_resurrect_parent_item(self):
        """Deleting a forked item in a child must not make the parent version reappear."""
        self.list_manager.createList(name="Parent", listId="L1")
        self.item_manager.addItemToList(listId="L1", itemId="I1", itemName="Apples")
        self.list_manager.createList(name="Child", listId="L2", optionalParentId="L1")
        self.item_manager.editItemInList("L2", "I1", "Organic Apples")  # fork

        self.item_manager.removeItemFromList("L2", "I1")

        self.assertEqual(len(self.list_manager.readListDisplayItems("L2")), 0)
        self.assertEqual(len(self.list_manager.readListDisplayItems("L1")), 1)

    def test_repeated_removal_does_not_stack_masks(self):
        self.list_manager.createList(name="Parent", listId="L1")
        self.item_manager.addItemToList(listId="L1", itemId="I1", itemName="Apples")
        self.list_manager.createList(name="Child", listId="L2", optionalParentId="L1")

        self.item_manager.removeItemFromList("L2", "I1")
        self.item_manager.removeItemFromList("L2", "I1")
        self.item_manager.removeItemFromList("L2", "I1")

        masks = [e for e in self.db.entries if e.listId == "L2" and e.isMaskedHidden]
        self.assertEqual(len(masks), 1)
        self.assertEqual(len(self.list_manager.readListDisplayItems("L2")), 0)

    def test_masked_item_stays_hidden_after_middle_list_deleted(self):
        """A child's mask of a grandparent item must survive deleting the middle list."""
        self.list_manager.createList(name="Grandparent", listId="L1")
        self.item_manager.addItemToList(listId="L1", itemId="I1", itemName="Milk")
        self.list_manager.createList(name="Parent", listId="L2", optionalParentId="L1")
        self.list_manager.createList(name="Child", listId="L3", optionalParentId="L2")
        self.item_manager.removeItemFromList("L3", "I1")  # mask the inherited grandparent item

        self.list_manager.deleteList("L2")

        self.assertEqual(len(self.list_manager.readListDisplayItems("L3")), 0)

    def test_child_view_unchanged_after_middle_list_deleted(self):
        """Items contributed by a deleted middle list are hard-copied into children."""
        self.list_manager.createList(name="Grandparent", listId="L1")
        self.item_manager.addItemToList(listId="L1", itemId="I1", itemName="Milk")
        self.list_manager.createList(name="Parent", listId="L2", optionalParentId="L1")
        self.item_manager.addItemToList(listId="L2", itemId="I2", itemName="Eggs")
        self.list_manager.createList(name="Child", listId="L3", optionalParentId="L2")

        self.list_manager.deleteList("L2")

        names = sorted(i["name"] for i in self.list_manager.readListDisplayItems("L3"))
        self.assertEqual(names, ["Eggs", "Milk"])
        self.assertEqual(self.db.lists["L3"].parentId, "L1")

    # ------------------------------------------
    # Newly implemented functionality
    # ------------------------------------------

    def test_rename_list(self):
        self.list_manager.createList(name="Old Name", listId="L1")
        self.list_manager.renameList("L1", "New Name")
        self.assertEqual(self.db.lists["L1"].listName, "New Name")

        with self.assertRaises(ValueError):
            self.list_manager.renameList("L1", "")
        with self.assertRaises(ValueError):
            self.list_manager.renameList("NOPE", "Anything")

    def test_duplicate_as_decoupled_copy(self):
        self.list_manager.createList(name="Parent", listId="L1")
        self.item_manager.addItemToList(listId="L1", itemId="I1", itemName="Apples")
        self.list_manager.createList(name="Child", listId="L2", optionalParentId="L1")
        self.item_manager.editItemInList("L2", "I1", "Organic Apples")
        self.item_manager.addItemToList(listId="L2", itemId="I2", itemName="Bread")

        copy = self.list_manager.duplicateAsDecoupledCopy("L2", newListId="L3")

        self.assertEqual(copy.listName, "Copy of Child")
        self.assertIsNone(copy.parentId)  # decoupled: no inheritance link

        copy_names = sorted(i["name"] for i in self.list_manager.readListDisplayItems("L3"))
        self.assertEqual(copy_names, ["Bread", "Organic Apples"])

        # Mutating the copy must not affect the original
        self.item_manager.removeItemFromList("L3", "I2")
        original_names = sorted(i["name"] for i in self.list_manager.readListDisplayItems("L2"))
        self.assertEqual(original_names, ["Bread", "Organic Apples"])

    def test_toggle_item_checked(self):
        self.list_manager.createList(name="Parent", listId="L1")
        self.item_manager.addItemToList(listId="L1", itemId="I1", itemName="Milk")
        self.list_manager.createList(name="Child", listId="L2", optionalParentId="L1")

        self.assertTrue(self.item_manager.toggleItemChecked("L1", "I1"))
        self.assertFalse(self.item_manager.toggleItemChecked("L1", "I1"))

        # Checking an inherited item forks locally instead of mutating the parent
        self.assertTrue(self.item_manager.toggleItemChecked("L2", "I1"))
        self.assertFalse(self.list_manager.readListDisplayItems("L1")[0]["isChecked"])
        self.assertTrue(self.list_manager.readListDisplayItems("L2")[0]["isChecked"])

    def test_readding_masked_item_unhides_it(self):
        self.list_manager.createList(name="Parent", listId="L1")
        self.item_manager.addItemToList(listId="L1", itemId="I1", itemName="Milk")
        self.list_manager.createList(name="Child", listId="L2", optionalParentId="L1")

        self.item_manager.removeItemFromList("L2", "I1")
        self.assertEqual(len(self.list_manager.readListDisplayItems("L2")), 0)

        self.item_manager.addItemToList(listId="L2", itemId="I1", itemName="Milk")
        self.assertEqual(len(self.list_manager.readListDisplayItems("L2")), 1)

    # ------------------------------------------
    # Validation / error handling
    # ------------------------------------------

    def test_input_validation(self):
        with self.assertRaises(ValueError):
            self.list_manager.createList(name="X", listId="L1", optionalParentId="MISSING")

        self.list_manager.createList(name="X", listId="L1")
        with self.assertRaises(ValueError):
            self.list_manager.createList(name="Dup", listId="L1")  # duplicate id

        with self.assertRaises(ValueError):
            self.item_manager.addItemToList(listId="MISSING", itemId="I1", itemName="Milk")

        with self.assertRaises(ValueError):
            self.item_manager.addItemToList(listId="L1", itemName="")  # empty new item name

        with self.assertRaises(ValueError):
            self.list_manager.readListDisplayItems("MISSING")

        with self.assertRaises(ValueError):
            self.item_manager.editItemInList("L1", "GHOST", "Name")  # item not in list

    def test_auto_generated_ids(self):
        g_list = self.list_manager.createList(name="Auto")
        self.assertIn(g_list.listId, self.db.lists)

        entry = self.item_manager.addItemToList(listId=g_list.listId, itemName="Milk")
        self.assertIn(entry.itemId, self.db.items)
        self.assertEqual(self.db.items[entry.itemId].itemName, "Milk")


if __name__ == "__main__":
    unittest.main()
