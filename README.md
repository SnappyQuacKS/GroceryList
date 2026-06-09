# GroceryList

A hierarchical grocery list data model. Lists can have parent lists and inherit their items; child lists can locally rename (fork), hide (mask), or check off inherited items without affecting the parent.

## Structure

```
model/
  grocery_model.py       # Entities (User, Item, ListEntry, GroceryList),
                         # Database (in-memory store), and the
                         # ListManager / ItemManager service controllers
  test_grocery_model.py  # Unit tests (18 tests)
```

## Key concepts

- **Inheritance**: a child list displays its own items plus everything from its ancestor chain (bottom-up compilation, deepest entry wins per item).
- **Forking**: editing or checking an inherited item creates a local `ListEntry` with a `customNameOverride` / local check state, leaving the parent untouched.
- **Masking**: removing an inherited item adds a hidden mask entry instead of deleting the parent's data.
- **Deletion repair**: deleting a list re-points its children to the grandparent and hard-copies anything they were inheriting from it, so child views are unchanged (custom names and masks preserved).
- **Decoupled duplication**: `duplicateAsDecoupledCopy` flattens a list's full view into a standalone copy with no inheritance link.

## Running the tests

```bash
cd model
python3 -m unittest test_grocery_model -v
```

## Notes

- `Database` is an in-memory store; swap it for real persistence later.
- `User.password` is stored in plain text in this model — hash it (e.g. bcrypt) before building a real backend on top of this.
