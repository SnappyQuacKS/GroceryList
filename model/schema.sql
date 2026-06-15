-- Run this once to set up the database.
-- psql -U postgres -f schema.sql

CREATE DATABASE grocerylist;
\c grocerylist

CREATE TABLE users (
    username        TEXT PRIMARY KEY,
    password_hash   TEXT NOT NULL,
    first_name      TEXT NOT NULL DEFAULT '',
    last_name       TEXT NOT NULL DEFAULT '',
    zip_code        TEXT NOT NULL DEFAULT ''
);

CREATE TABLE items (
    item_id     TEXT PRIMARY KEY,
    item_name   TEXT NOT NULL
);

-- Self-referential FK: parent_id deferred so we can insert in any order
CREATE TABLE grocery_lists (
    list_id     TEXT PRIMARY KEY,
    list_name   TEXT NOT NULL,
    parent_id   TEXT REFERENCES grocery_lists(list_id) ON DELETE SET NULL DEFERRABLE INITIALLY DEFERRED,
    user_id     TEXT REFERENCES users(username) ON DELETE SET NULL
);

CREATE TABLE list_entries (
    list_id             TEXT NOT NULL REFERENCES grocery_lists(list_id) ON DELETE CASCADE,
    item_id             TEXT NOT NULL REFERENCES items(item_id) ON DELETE CASCADE,
    is_checked          BOOLEAN NOT NULL DEFAULT FALSE,
    is_masked_hidden    BOOLEAN NOT NULL DEFAULT FALSE,
    custom_name_override TEXT,
    PRIMARY KEY (list_id, item_id)
);
