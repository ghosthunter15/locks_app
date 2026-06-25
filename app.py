import sqlite3

from textual.app import App, ComposeResult
from textual.widgets import (
    DataTable, Button, Input, Static
)
from textual.containers import Vertical
from textual.message import Message

DB_PATH = "locks.db"

def get_db():
    return sqlite3.connect(DB_PATH)


class LockForm(Vertical):
    """Form for add/edit/search"""

    class Submitted(Message):
        def __init__(self, sender, values):
            super().__init__()
            self.sender = sender
            self.values = values

    def compose(self) -> ComposeResult:
        yield Input(placeholder="Name", id="name")
        yield Input(placeholder="Type", id="type")
        yield Input(placeholder="Picked (yes/no)", id="picked")
        yield Button("Submit", id="submit")

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "submit":
            values = {
                "name": self.query_one("#name", Input).value.strip(),
                "type": self.query_one("#type", Input).value.strip(),
                "picked": self.query_one("#picked", Input).value.strip(),
            }
            self.post_message(self.Submitted(self, values))


class LocksApp(App):
    CSS_PATH = "app.css"

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("a", "add", "Add"),
        ("e", "edit", "Edit"),
        ("d", "delete", "Delete"),
        ("p", "toggle_picked", "Toggle Picked"),
        ("/", "search", "Search"),
        ("r", "reload", "Reload"),
    ]

    def compose(self) -> ComposeResult:
        yield DataTable(id="table")
        yield Static(id="status")

    def on_mount(self):
        table = self.query_one(DataTable)
        table.add_columns("ID", "Name", "Type", "Picked")
        self.load_data()

    # ---------------- Database ----------------

    def load_data(self, where=None, params=()):
        table = self.query_one(DataTable)
        table.clear()

        db = get_db()
        cur = db.cursor()

        query = "SELECT id, name, type, picked FROM locks"
        if where:
            query += f" WHERE {where}"

        for row in cur.execute(query, params):
            picked = "✔" if row[3].lower() in ("yes", "true", "1") else "✘"
            table.add_row(str(row[0]), row[1], row[2], picked)

        db.close()
        self.set_status("Loaded records")

    def set_status(self, msg):
        self.query_one("#status", Static).update(msg)

    # ---------------- Actions ----------------

    def action_reload(self):
        self.load_data()

    def action_add(self):
        table = self.query_one(DataTable)
        table.display = False
        self.mount(LockForm(id="form"))

    def action_edit(self):
        table = self.query_one(DataTable)
        if table.cursor_row is None:
            self.set_status("No row selected")
            return

        row = table.get_row_at(table.cursor_row)

        table.display = False
        form = LockForm(id="form")
        self.mount(form)

        form.query_one("#name", Input).value = row[1]
        form.query_one("#type", Input).value = row[2]
        form.query_one("#picked", Input).value = "yes" if row[3] == "✔" else "no"

        form.edit_id = int(row[0])

    def action_delete(self):
        table = self.query_one(DataTable)
        if table.cursor_row is None:
            self.set_status("No row selected")
            return

        row = table.get_row_at(table.cursor_row)
        db = get_db()
        db.execute("DELETE FROM locks WHERE id = ?", (row[0],))
        db.commit()
        db.close()

        self.load_data()
        self.set_status(f"Deleted lock ID {row[0]}")

    def action_search(self):
        table = self.query_one(DataTable)
        table.display = False
        self.mount(LockForm(id="form"))
        self.set_status("Search (blank fields ignored)")

    # ---------------- Toggle Picked ----------------

    def action_toggle_picked(self):
        table = self.query_one(DataTable)

        if table.cursor_row is None:
            self.set_status("No row selected")
            return

        row = table.get_row_at(table.cursor_row)
        lock_id = row[0]

        # Flip value
        new_value = "no" if row[3] == "✔" else "yes"

        db = get_db()
        db.execute(
            "UPDATE locks SET picked=? WHERE id=?",
            (new_value, lock_id),
        )
        db.commit()
        db.close()

        self.load_data()
        self.set_status(f"Picked set to {new_value} for ID {lock_id}")

    # ---------------- Form Handler ----------------

    def on_lock_form_submitted(self, msg: LockForm.Submitted):
        self.query_one("#form").remove()
        self.query_one(DataTable).display = True

        values = msg.values
        db = get_db()

        # Edit
        if hasattr(msg.sender, "edit_id"):
            db.execute(
                "UPDATE locks SET name=?, type=?, picked=? WHERE id=?",
                (
                    values["name"],
                    values["type"],
                    values["picked"],
                    msg.sender.edit_id,
                ),
            )
            db.commit()
            db.close()
            self.load_data()
            self.set_status("Updated lock")
            return

        # Search
        if any(values.values()):
            where = []
            params = []
            for col, val in values.items():
                if val:
                    where.append(f"{col} LIKE ?")
                    params.append(f"%{val}%")

            self.load_data(" AND ".join(where), params)
            db.close()
            self.set_status("Search results")
            return

        # Add
        db.execute(
            "INSERT INTO locks (name, type, picked) VALUES (?, ?, ?)",
            (
                values["name"],
                values["type"],
                values["picked"],
            ),
        )
        db.commit()
        db.close()
        self.load_data()
        self.set_status("Added lock")


if __name__ == "__main__":
    LocksApp().run()
