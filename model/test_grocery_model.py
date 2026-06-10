# test_grocery_model.py
import unittest

from grocery_model import User, Database, ListManager, ItemManager


def _sep(name):
    print(f"\n{'=' * 60}")
    print(f"  {name}")
    print(f"{'=' * 60}")


class TestGroceryDataModel(unittest.TestCase):

    def setUp(self):
        self.db = Database()
        self.list_manager = ListManager(self.db)
        self.item_manager = ItemManager(self.db)

    def _show(self, list_id, label=None):
        g_list = self.db.lists[list_id]
        items = self.list_manager.readListDisplayItems(list_id)
        parent_name = (
            self.db.lists[g_list.parentId].listName
            if g_list.parentId and g_list.parentId in self.db.lists
            else None
        )
        ext = f"  extends '{parent_name}'" if parent_name else "  (root)"
        prefix = f"[{label}]  " if label else ""
        print(f"  {prefix}'{g_list.listName}'{ext}:")
        print("  {")
        if items:
            for item in items:
                check = "[ ]" if item.get("isInherited") else ("[x]" if item.get("isChecked") else "[ ]")
                tag = "  (inherited)" if item.get("isInherited") else ""
                print(f"    {check} {item['name']}{tag}")
        else:
            print("    (empty)")
        print("  }")

    # ------------------------------------------
    # Original behavioral tests
    # ------------------------------------------

    def test_create_and_read_hierarchy(self):
        _sep("test_create_and_read_hierarchy")

        self.list_manager.createList(name="Weekly Grocery", listId="L1")
        self.item_manager.addItemToList(listId="L1", itemId="I1", itemName="Whole Milk")
        print("After creating 'Weekly Grocery' and adding 'Whole Milk':")
        self._show("L1")

        self.list_manager.createList(name="", listId="L2", optionalParentId="L1")
        print(f"\nAfter creating child list (auto-named '{self.db.lists['L2'].listName}'):")
        self._show("L1", "parent")
        self._show("L2", "child")

        child_items = self.list_manager.readListDisplayItems("L2")
        self.assertEqual(len(child_items), 1)
        self.assertEqual(child_items[0]["name"], "Whole Milk")
        self.assertTrue(child_items[0]["isInherited"])
        self.assertEqual(self.db.lists["L2"].listName, "List1")

    def test_item_editing_and_forking(self):
        _sep("test_item_editing_and_forking")

        self.list_manager.createList(name="Master List", listId="L1")
        self.item_manager.addItemToList(listId="L1", itemId="I1", itemName="Apples")
        self.list_manager.createList(name="Child List", listId="L2", optionalParentId="L1")
        print("Before fork:")
        self._show("L1", "parent")
        self._show("L2", "child")

        self.item_manager.editItemInList(listId="L2", itemId="I1", newName="Organic Green Apples")
        print("\nAfter forking 'Apples' -> 'Organic Green Apples' in child:")
        self._show("L1", "parent")
        self._show("L2", "child")

        parent_view = self.list_manager.readListDisplayItems("L1")
        child_view = self.list_manager.readListDisplayItems("L2")
        self.assertEqual(parent_view[0]["name"], "Apples")
        self.assertEqual(child_view[0]["name"], "Organic Green Apples")

    def test_inherited_item_deletion_masking(self):
        _sep("test_inherited_item_deletion_masking")

        self.list_manager.createList(name="Master List", listId="L1")
        self.item_manager.addItemToList(listId="L1", itemId="I1", itemName="Banana")
        self.list_manager.createList(name="Child List", listId="L2", optionalParentId="L1")
        print("Before removal:")
        self._show("L1", "parent")
        self._show("L2", "child")

        self.item_manager.removeItemFromList(listId="L2", itemId="I1")
        print("\nAfter removing 'Banana' from child (masked, not deleted from parent):")
        self._show("L1", "parent")
        self._show("L2", "child")

        parent_view = self.list_manager.readListDisplayItems("L1")
        child_view = self.list_manager.readListDisplayItems("L2")
        self.assertEqual(len(parent_view), 1)
        self.assertEqual(len(child_view), 0)

    def test_cascading_deletion_with_grandparent(self):
        _sep("test_cascading_deletion_with_grandparent")

        self.list_manager.createList(name="Grandparent", listId="L1")
        self.list_manager.createList(name="Parent", listId="L2", optionalParentId="L1")
        self.list_manager.createList(name="Child", listId="L3", optionalParentId="L2")
        print("Before deletion (3-level chain: Grandparent -> Parent -> Child):")
        self._show("L1", "L1")
        self._show("L2", "L2")
        self._show("L3", "L3")

        self.list_manager.deleteList("L2")
        child_list = self.db.lists.get("L3")
        grandparent_name = self.db.lists[child_list.parentId].listName if child_list.parentId else "none"
        print("\nAfter deleting 'Parent' (L2):")
        print("  'Parent' (L2)  ->  deleted")
        self._show("L1", "L1")
        self._show("L3", "L3")
        print(f"  'Child' re-pointed to: '{grandparent_name}'")

        self.assertEqual(child_list.parentId, "L1")

    def test_cascading_deletion_orphan_upgrade(self):
        _sep("test_cascading_deletion_orphan_upgrade")

        self.list_manager.createList(name="Root Parent", listId="L1")
        self.item_manager.addItemToList(listId="L1", itemId="I1", itemName="Cereal")
        self.list_manager.createList(name="Child", listId="L2", optionalParentId="L1")
        print("Before deletion:")
        self._show("L1", "L1")
        self._show("L2", "L2")

        self.list_manager.deleteList("L1")
        print("\nAfter deleting 'Root Parent' (L1):")
        print("  'Root Parent' (L1)  ->  deleted")
        self._show("L2", "L2")
        print("  ('Cereal' hard-copied into child; now a root list)")

        child_list = self.db.lists.get("L2")
        child_view = self.list_manager.readListDisplayItems("L2")
        self.assertIsNone(child_list.parentId)
        self.assertEqual(len(child_view), 1)
        self.assertEqual(child_view[0]["name"], "Cereal")
        self.assertFalse(child_view[0]["isInherited"])

    def test_user_profile_list_binding(self):
        _sep("test_user_profile_list_binding")

        mock_user = User(
            username="ethan99",
            password="securePassword123",
            firstName="Ethan",
            lastName="Project",
            zipCode="02108"
        )
        print(f"User: {mock_user.firstName} {mock_user.lastName}  (@{mock_user.username},  zip: {mock_user.zipCode})")

        self.assertEqual(mock_user.username, "ethan99")
        self.assertEqual(mock_user.zipCode, "02108")

        user_list = self.list_manager.createList(
            name="My Private List",
            listId="UL_99",
            optionalParentId=None,
            userId=mock_user.username
        )
        print(f"\nList created and bound to '{mock_user.username}':")
        self._show("UL_99")

        self.assertEqual(user_list.userId, "ethan99")
        self.assertIsNone(user_list.parentId)

    # ------------------------------------------
    # Regression tests for fixed bugs
    # ------------------------------------------

    def test_reediting_fork_does_not_corrupt_parent(self):
        _sep("test_reediting_fork_does_not_corrupt_parent")

        self.list_manager.createList(name="Parent", listId="L1")
        self.item_manager.addItemToList(listId="L1", itemId="I1", itemName="Apples")
        self.list_manager.createList(name="Child", listId="L2", optionalParentId="L1")

        self.item_manager.editItemInList("L2", "I1", "Green Apples")
        print("After 1st fork edit ('Apples' -> 'Green Apples' in child):")
        self._show("L1", "parent")
        self._show("L2", "child")

        self.item_manager.editItemInList("L2", "I1", "Organic Green Apples")
        print("\nAfter 2nd fork edit ('Green Apples' -> 'Organic Green Apples' in child):")
        self._show("L1", "parent")
        self._show("L2", "child")
        print("  (parent 'Apples' unchanged -- fork edits stay local)")

        self.assertEqual(self.list_manager.readListDisplayItems("L1")[0]["name"], "Apples")
        self.assertEqual(self.list_manager.readListDisplayItems("L2")[0]["name"], "Organic Green Apples")

    def test_custom_name_survives_parent_deletion(self):
        _sep("test_custom_name_survives_parent_deletion")

        self.list_manager.createList(name="Parent", listId="L1")
        self.item_manager.addItemToList(listId="L1", itemId="I1", itemName="Apples")
        self.list_manager.createList(name="Child", listId="L2", optionalParentId="L1")
        self.item_manager.editItemInList("L2", "I1", "Organic Apples")
        print("Before parent deletion (child has forked name 'Organic Apples'):")
        self._show("L1", "parent")
        self._show("L2", "child")

        self.list_manager.deleteList("L1")
        print("\nAfter deleting 'Parent' (L1):")
        print("  'Parent' (L1)  ->  deleted")
        self._show("L2", "child")
        print("  (forked name 'Organic Apples' preserved in hard-copy)")

        child_view = self.list_manager.readListDisplayItems("L2")
        self.assertEqual(len(child_view), 1)
        self.assertEqual(child_view[0]["name"], "Organic Apples")

    def test_removing_fork_does_not_resurrect_parent_item(self):
        _sep("test_removing_fork_does_not_resurrect_parent_item")

        self.list_manager.createList(name="Parent", listId="L1")
        self.item_manager.addItemToList(listId="L1", itemId="I1", itemName="Apples")
        self.list_manager.createList(name="Child", listId="L2", optionalParentId="L1")
        self.item_manager.editItemInList("L2", "I1", "Organic Apples")
        print("After fork ('Organic Apples' in child):")
        self._show("L1", "parent")
        self._show("L2", "child")

        self.item_manager.removeItemFromList("L2", "I1")
        print("\nAfter removing forked item from child:")
        self._show("L1", "parent")
        self._show("L2", "child")
        print("  (parent item intact; parent's version did not resurface in child)")

        self.assertEqual(len(self.list_manager.readListDisplayItems("L2")), 0)
        self.assertEqual(len(self.list_manager.readListDisplayItems("L1")), 1)

    def test_repeated_removal_does_not_stack_masks(self):
        _sep("test_repeated_removal_does_not_stack_masks")

        self.list_manager.createList(name="Parent", listId="L1")
        self.item_manager.addItemToList(listId="L1", itemId="I1", itemName="Apples")
        self.list_manager.createList(name="Child", listId="L2", optionalParentId="L1")
        print("Initial state:")
        self._show("L2", "child")

        for i in range(1, 4):
            self.item_manager.removeItemFromList("L2", "I1")
            masks = [e for e in self.db.entries if e.listId == "L2" and e.isMaskedHidden]
            print(f"\nAfter removal #{i}  (mask entries in L2: {len(masks)}):")
            self._show("L2", "child")

        masks = [e for e in self.db.entries if e.listId == "L2" and e.isMaskedHidden]
        self.assertEqual(len(masks), 1)
        self.assertEqual(len(self.list_manager.readListDisplayItems("L2")), 0)

    def test_masked_item_stays_hidden_after_middle_list_deleted(self):
        _sep("test_masked_item_stays_hidden_after_middle_list_deleted")

        self.list_manager.createList(name="Grandparent", listId="L1")
        self.item_manager.addItemToList(listId="L1", itemId="I1", itemName="Milk")
        self.list_manager.createList(name="Parent", listId="L2", optionalParentId="L1")
        self.list_manager.createList(name="Child", listId="L3", optionalParentId="L2")
        self.item_manager.removeItemFromList("L3", "I1")
        print("After masking 'Milk' in grandchild (Grandparent -> Parent -> Child):")
        self._show("L1", "L1")
        self._show("L2", "L2")
        self._show("L3", "L3")

        self.list_manager.deleteList("L2")
        print("\nAfter deleting 'Parent' (L2):")
        print("  'Parent' (L2)  ->  deleted")
        self._show("L1", "L1")
        self._show("L3", "L3")
        print("  (mask on 'Milk' survived deletion repair)")

        self.assertEqual(len(self.list_manager.readListDisplayItems("L3")), 0)

    def test_child_view_unchanged_after_middle_list_deleted(self):
        _sep("test_child_view_unchanged_after_middle_list_deleted")

        self.list_manager.createList(name="Grandparent", listId="L1")
        self.item_manager.addItemToList(listId="L1", itemId="I1", itemName="Milk")
        self.list_manager.createList(name="Parent", listId="L2", optionalParentId="L1")
        self.item_manager.addItemToList(listId="L2", itemId="I2", itemName="Eggs")
        self.list_manager.createList(name="Child", listId="L3", optionalParentId="L2")
        print("Before deletion (Grandparent -> Parent -> Child):")
        self._show("L1", "L1")
        self._show("L2", "L2")
        self._show("L3", "L3")

        self.list_manager.deleteList("L2")
        print("\nAfter deleting 'Parent' (L2):")
        print("  'Parent' (L2)  ->  deleted")
        self._show("L1", "L1")
        self._show("L3", "L3")
        print("  ('Eggs' hard-copied into 'Child'; pointer re-aimed at 'Grandparent')")

        names = sorted(i["name"] for i in self.list_manager.readListDisplayItems("L3"))
        self.assertEqual(names, ["Eggs", "Milk"])
        self.assertEqual(self.db.lists["L3"].parentId, "L1")

    # ------------------------------------------
    # Newly implemented functionality
    # ------------------------------------------

    def test_rename_list(self):
        _sep("test_rename_list")

        self.list_manager.createList(name="Old Name", listId="L1")
        print("Before rename:")
        self._show("L1")

        self.list_manager.renameList("L1", "New Name")
        print("\nAfter rename:")
        self._show("L1")

        self.assertEqual(self.db.lists["L1"].listName, "New Name")

        with self.assertRaises(ValueError):
            self.list_manager.renameList("L1", "")
        print("\n  [ok] ValueError: empty name rejected")

        with self.assertRaises(ValueError):
            self.list_manager.renameList("NOPE", "Anything")
        print("  [ok] ValueError: non-existent list rejected")

    def test_duplicate_as_decoupled_copy(self):
        _sep("test_duplicate_as_decoupled_copy")

        self.list_manager.createList(name="Parent", listId="L1")
        self.item_manager.addItemToList(listId="L1", itemId="I1", itemName="Apples")
        self.list_manager.createList(name="Child", listId="L2", optionalParentId="L1")
        self.item_manager.editItemInList("L2", "I1", "Organic Apples")
        self.item_manager.addItemToList(listId="L2", itemId="I2", itemName="Bread")
        print("Original lists before copy:")
        self._show("L1", "L1")
        self._show("L2", "L2")

        copy = self.list_manager.duplicateAsDecoupledCopy("L2", newListId="L3")
        print(f"\nDecoupled copy of 'Child' created as '{copy.listName}':")
        self._show("L3", "copy")

        self.assertEqual(copy.listName, "Copy of Child")
        self.assertIsNone(copy.parentId)

        copy_names = sorted(i["name"] for i in self.list_manager.readListDisplayItems("L3"))
        self.assertEqual(copy_names, ["Bread", "Organic Apples"])

        self.item_manager.removeItemFromList("L3", "I2")
        print("\nAfter removing 'Bread' from copy only:")
        self._show("L2", "original")
        self._show("L3", "copy")
        print("  (original 'Child' unaffected)")

        original_names = sorted(i["name"] for i in self.list_manager.readListDisplayItems("L2"))
        self.assertEqual(original_names, ["Bread", "Organic Apples"])

    def test_toggle_item_checked(self):
        _sep("test_toggle_item_checked")

        self.list_manager.createList(name="Parent", listId="L1")
        self.item_manager.addItemToList(listId="L1", itemId="I1", itemName="Milk")
        self.list_manager.createList(name="Child", listId="L2", optionalParentId="L1")
        print("Initial state:")
        self._show("L1", "parent")
        self._show("L2", "child")

        result = self.item_manager.toggleItemChecked("L1", "I1")
        self.assertTrue(result)
        print("\nAfter checking 'Milk' in parent:")
        self._show("L1", "parent")
        self._show("L2", "child")

        result = self.item_manager.toggleItemChecked("L1", "I1")
        self.assertFalse(result)
        print("\nAfter unchecking 'Milk' in parent:")
        self._show("L1", "parent")
        self._show("L2", "child")

        result = self.item_manager.toggleItemChecked("L2", "I1")
        self.assertTrue(result)
        print("\nAfter checking inherited 'Milk' in child (forks locally):")
        self._show("L1", "parent")
        self._show("L2", "child")
        print("  (parent unchecked; child independently checked via local fork)")

        self.assertFalse(self.list_manager.readListDisplayItems("L1")[0]["isChecked"])
        self.assertTrue(self.list_manager.readListDisplayItems("L2")[0]["isChecked"])

    def test_readding_masked_item_unhides_it(self):
        _sep("test_readding_masked_item_unhides_it")

        self.list_manager.createList(name="Parent", listId="L1")
        self.item_manager.addItemToList(listId="L1", itemId="I1", itemName="Milk")
        self.list_manager.createList(name="Child", listId="L2", optionalParentId="L1")
        print("Initial state:")
        self._show("L1", "parent")
        self._show("L2", "child")

        self.item_manager.removeItemFromList("L2", "I1")
        print("\nAfter masking 'Milk' in child:")
        self._show("L2", "child")

        self.item_manager.addItemToList(listId="L2", itemId="I1", itemName="Milk")
        print("\nAfter re-adding 'Milk' to child (mask lifted):")
        self._show("L2", "child")

        self.assertEqual(len(self.list_manager.readListDisplayItems("L2")), 1)

    # ------------------------------------------
    # Validation / error handling
    # ------------------------------------------

    def test_input_validation(self):
        _sep("test_input_validation")

        with self.assertRaises(ValueError):
            self.list_manager.createList(name="X", listId="L1", optionalParentId="MISSING")
        print("  [ok] ValueError: createList with non-existent parent")

        self.list_manager.createList(name="X", listId="L1")
        with self.assertRaises(ValueError):
            self.list_manager.createList(name="Dup", listId="L1")
        print("  [ok] ValueError: createList with duplicate id")

        with self.assertRaises(ValueError):
            self.item_manager.addItemToList(listId="MISSING", itemId="I1", itemName="Milk")
        print("  [ok] ValueError: addItemToList with non-existent list")

        with self.assertRaises(ValueError):
            self.item_manager.addItemToList(listId="L1", itemName="")
        print("  [ok] ValueError: addItemToList with empty item name")

        with self.assertRaises(ValueError):
            self.list_manager.readListDisplayItems("MISSING")
        print("  [ok] ValueError: readListDisplayItems with non-existent list")

        with self.assertRaises(ValueError):
            self.item_manager.editItemInList("L1", "GHOST", "Name")
        print("  [ok] ValueError: editItemInList with item not in list")

    def test_auto_generated_ids(self):
        _sep("test_auto_generated_ids")

        g_list = self.list_manager.createList(name="Auto")
        print(f"  Created list 'Auto'  ->  id: {g_list.listId}")
        self.assertIn(g_list.listId, self.db.lists)

        entry = self.item_manager.addItemToList(listId=g_list.listId, itemName="Milk")
        print(f"  Added item 'Milk'    ->  id: {entry.itemId}")
        self.assertIn(entry.itemId, self.db.items)
        self.assertEqual(self.db.items[entry.itemId].itemName, "Milk")
        print()
        self._show(g_list.listId, "Auto")


    def test_read_all_lists(self):
        _sep("test_read_all_lists")

        self.list_manager.createList(name="Weekday Groceries", listId="L1")
        self.list_manager.createList(name="Weekend Groceries", listId="L2")
        self.list_manager.createList(name="Party Snacks", listId="L3", optionalParentId="L1")

        all_lists = self.list_manager.readAllLists()
        print(f"readAllLists() -- {len(all_lists)} lists:")
        for g in all_lists:
            parent_name = self.db.lists[g.parentId].listName if g.parentId else None
            ext = f"  extends '{parent_name}'" if parent_name else "  (root)"
            print(f"  '{g.listName}'{ext}")

        self.assertEqual(len(all_lists), 3)
        names = sorted(g.listName for g in all_lists)
        self.assertEqual(names, ["Party Snacks", "Weekday Groceries", "Weekend Groceries"])

    def test_read_direct_items(self):
        _sep("test_read_direct_items")

        self.list_manager.createList(name="Parent", listId="L1")
        self.item_manager.addItemToList(listId="L1", itemId="I1", itemName="Milk")
        self.item_manager.addItemToList(listId="L1", itemId="I2", itemName="Butter")
        self.list_manager.createList(name="Child", listId="L2", optionalParentId="L1")
        self.item_manager.addItemToList(listId="L2", itemId="I3", itemName="Eggs")
        print("Parent owns Milk + Butter; Child directly adds Eggs (inherits Milk + Butter):")
        self._show("L1", "parent")
        self._show("L2", "child")

        direct = self.list_manager.readDirectItems("L2")
        print(f"\nreadDirectItems('L2'): {[i['name'] for i in direct]}")
        print("  (inherited Milk + Butter excluded)")

        self.assertEqual(len(direct), 1)
        self.assertEqual(direct[0]["name"], "Eggs")
        self.assertFalse(direct[0]["isInherited"])

        direct_parent = self.list_manager.readDirectItems("L1")
        print(f"\nreadDirectItems('L1'): {[i['name'] for i in direct_parent]}")
        self.assertEqual(sorted(i["name"] for i in direct_parent), ["Butter", "Milk"])

    def test_read_all_items(self):
        _sep("test_read_all_items")

        self.list_manager.createList(name="Parent", listId="L1")
        self.item_manager.addItemToList(listId="L1", itemId="I1", itemName="Milk")
        self.item_manager.addItemToList(listId="L1", itemId="I2", itemName="Butter")
        self.list_manager.createList(name="Child", listId="L2", optionalParentId="L1")
        self.item_manager.addItemToList(listId="L2", itemId="I3", itemName="Eggs")
        self.item_manager.removeItemFromList("L2", "I2")
        print("Child inherits Milk, owns Eggs, masks Butter:")
        self._show("L1", "parent")
        self._show("L2", "child")

        all_items = self.list_manager.readAllItems("L2")
        names = sorted(i["name"] for i in all_items)
        print(f"\nreadAllItems('L2'): {names}")
        print("  (Butter masked -- excluded; Milk inherited + Eggs direct both included)")

        self.assertEqual(names, ["Eggs", "Milk"])
        inherited = [i for i in all_items if i.get("isInherited")]
        direct = [i for i in all_items if not i.get("isInherited")]
        self.assertEqual([i["name"] for i in inherited], ["Milk"])
        self.assertEqual([i["name"] for i in direct], ["Eggs"])


if __name__ == "__main__":
    unittest.main()
