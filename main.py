import json
import uuid
import shutil
import shlex
import datetime
from pathlib import Path

from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.metrics import dp, sp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.filechooser import FileChooserListView
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.screenmanager import ScreenManager, Screen, NoTransition
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput

BG = (0.063, 0.075, 0.098, 1)
CARD = (0.102, 0.125, 0.165, 1)
BLUE = (0.15, 0.40, 0.90, 1)
RED = (0.55, 0.21, 0.25, 1)
GREY = (0.53, 0.57, 0.63, 1)
TRANSPARENT = (0, 0, 0, 0)

TEXT_EXTENSIONS = {
    ".txt", ".py", ".js", ".json", ".html", ".css", ".md", ".ini",
    ".cfg", ".xml", ".csv", ".log", ".bat", ".ps1", ".yml", ".yaml"
}
MAX_TEXT_SIZE = 2 * 1024 * 1024


# =========================
# UI HELPERS
# =========================

def lbl(text, size=14, bold=False, color=(1, 1, 1, 1), **kw):
    label = Label(
        text=text, font_size=sp(size), bold=bold, color=color,
        halign="left", valign="middle", **kw
    )
    label.bind(size=lambda inst, val: setattr(inst, "text_size", val))
    return label


def btn(text, callback, width=None, color=BLUE, **kw):
    b = Button(
        text=text, background_normal="", background_color=color,
        font_size=sp(14), **kw
    )
    if width:
        b.size_hint_x = None
        b.width = dp(width)
    b.bind(on_release=callback)
    return b


def list_grid():
    grid = GridLayout(cols=1, size_hint_y=None, spacing=dp(4), padding=dp(4))
    grid.bind(minimum_height=grid.setter("height"))
    return grid


def info(title, message):
    box = BoxLayout(orientation="vertical", padding=dp(12), spacing=dp(10))
    box.add_widget(lbl(message))
    popup = Popup(title=title, content=box, size_hint=(0.88, 0.4))
    box.add_widget(btn("OK", lambda *_: popup.dismiss(), size_hint_y=None, height=dp(44)))
    popup.open()


def confirm(title, message, on_yes):
    box = BoxLayout(orientation="vertical", padding=dp(12), spacing=dp(10))
    box.add_widget(lbl(message))
    row = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(8))
    popup = Popup(title=title, content=box, size_hint=(0.88, 0.4))

    def yes(*_):
        popup.dismiss()
        on_yes()

    row.add_widget(btn("Cancel", lambda *_: popup.dismiss(), color=GREY))
    row.add_widget(btn("Yes", yes, color=RED))
    box.add_widget(row)
    popup.open()


# =========================
# APP
# =========================

class HitboxApp(App):
    title = "Hitbox Workspaces"

    def build(self):
        self.base = Path(self.user_data_dir)
        self.ws_root = self.base / "HitboxWorkspaces"
        self.ws_root.mkdir(parents=True, exist_ok=True)
        self.data_file = self.base / "hitbox_data.json"

        self.data = self.read_data()
        self.current_workspace = None
        self.terminal_cwd = None
        self.editor_path = None

        Window.clearcolor = BG
        Window.softinput_mode = "below_target"
        Window.bind(on_keyboard=self.on_keyboard)

        self.sm = ScreenManager(transition=NoTransition())
        self.dash_screen = Screen(name="dash")
        self.ws_screen = Screen(name="ws")
        self.editor_screen = Screen(name="editor")
        for s in (self.dash_screen, self.ws_screen, self.editor_screen):
            self.sm.add_widget(s)

        self.request_android_permissions()
        self.show_dashboard()
        return self.sm

    def request_android_permissions(self):
        try:
            from android.permissions import request_permissions, Permission
            request_permissions([
                Permission.READ_EXTERNAL_STORAGE,
                Permission.WRITE_EXTERNAL_STORAGE,
            ])
        except Exception:
            pass  # not on Android

    def on_keyboard(self, window, key, *args):
        # Android back button (ESC = 27)
        if key == 27:
            if self.sm.current == "editor":
                self.close_editor()
                return True
            if self.sm.current == "ws":
                self.show_dashboard()
                return True
        return False

    # =========================
    # DATA
    # =========================

    def read_data(self):
        if self.data_file.exists():
            try:
                data = json.loads(self.data_file.read_text(encoding="utf-8"))
                if isinstance(data, dict) and isinstance(data.get("workspaces"), list):
                    return data
            except Exception:
                pass
        return {
            "workspaces": [{
                "id": "demo",
                "name": "My First Workspace",
                "description": "Your first Hitbox project.",
                "created": datetime.date.today().isoformat(),
            }],
            "active": "demo",
        }

    def write_data(self):
        self.data_file.write_text(
            json.dumps(self.data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def workspace_path(self, ws):
        folder = self.ws_root / ws["id"]
        folder.mkdir(parents=True, exist_ok=True)
        return folder

    # =========================
    # DASHBOARD
    # =========================

    def show_dashboard(self, *_):
        scr = self.dash_screen
        scr.clear_widgets()

        hour = datetime.datetime.now().hour
        if 5 <= hour < 12:
            greeting = "Good morning"
        elif 12 <= hour < 18:
            greeting = "Good afternoon"
        elif 18 <= hour < 22:
            greeting = "Good evening"
        else:
            greeting = "Good night"

        root = BoxLayout(orientation="vertical", padding=dp(14), spacing=dp(10))

        root.add_widget(lbl("HITBOX", size=26, bold=True, size_hint_y=None, height=dp(40)))
        root.add_widget(lbl(greeting, size=20, bold=True, size_hint_y=None, height=dp(32)))
        root.add_widget(lbl(
            "Everything you need for your projects, in one place.",
            color=GREY, size_hint_y=None, height=dp(24),
        ))
        root.add_widget(btn(
            "+ New workspace", self.create_workspace,
            size_hint_y=None, height=dp(48),
        ))
        root.add_widget(lbl(
            f"{len(self.data['workspaces'])} workspaces", size=18, bold=True,
            size_hint_y=None, height=dp(34),
        ))

        grid = list_grid()
        for ws in self.data["workspaces"]:
            card = BoxLayout(size_hint_y=None, height=dp(60), padding=dp(8), spacing=dp(8))
            from kivy.graphics import Color, RoundedRectangle
            with card.canvas.before:
                Color(*CARD)
                rect = RoundedRectangle(pos=card.pos, size=card.size, radius=[dp(12)])
            card.bind(
                pos=lambda i, v, r=rect: setattr(r, "pos", v),
                size=lambda i, v, r=rect: setattr(r, "size", v),
            )
            card.add_widget(lbl(ws["name"], size=16, bold=True))
            card.add_widget(btn("Open", lambda *_, w=ws: self.open_workspace(w), width=90))
            grid.add_widget(card)

        sv = ScrollView()
        sv.add_widget(grid)
        root.add_widget(sv)

        scr.add_widget(root)
        self.sm.current = "dash"

    # =========================
    # CREATE WORKSPACE
    # =========================

    def create_workspace(self, *_):
        box = BoxLayout(orientation="vertical", padding=dp(12), spacing=dp(10))
        name = TextInput(hint_text="Workspace name", multiline=False,
                         size_hint_y=None, height=dp(44))
        desc = TextInput(hint_text="Description", multiline=False,
                         size_hint_y=None, height=dp(44))
        box.add_widget(name)
        box.add_widget(desc)
        popup = Popup(title="New workspace", content=box, size_hint=(0.9, 0.45))

        def create(*_):
            ws = {
                "id": uuid.uuid4().hex,
                "name": name.text.strip() or "Untitled Workspace",
                "description": desc.text.strip() or "A new Hitbox workspace.",
                "created": datetime.date.today().isoformat(),
            }
            self.data["workspaces"].append(ws)
            self.write_data()
            popup.dismiss()
            self.open_workspace(ws)

        box.add_widget(btn("Create", create, size_hint_y=None, height=dp(46)))
        popup.open()

    # =========================
    # WORKSPACE
    # =========================

    def open_workspace(self, ws):
        self.current_workspace = ws
        self.terminal_cwd = self.workspace_path(ws)
        self.render_workspace()

    def render_workspace(self, *_):
        scr = self.ws_screen
        scr.clear_widgets()
        ws = self.current_workspace

        root = BoxLayout(orientation="vertical", padding=dp(8), spacing=dp(6))

        head = BoxLayout(size_hint_y=None, height=dp(46), spacing=dp(6))
        head.add_widget(btn("< Back", self.show_dashboard, width=80))
        head.add_widget(lbl(ws["name"], size=18, bold=True))
        root.add_widget(head)

        toolbar = BoxLayout(size_hint_y=None, height=dp(42), spacing=dp(4))
        toolbar.add_widget(btn("+ File", self.new_file))
        toolbar.add_widget(btn("+ Folder", self.new_folder))
        toolbar.add_widget(btn("Add files", self.add_files))
        toolbar.add_widget(btn("Refresh", self.render_workspace))
        root.add_widget(toolbar)

        self.file_list = list_grid()
        sv = ScrollView()
        sv.add_widget(self.file_list)
        root.add_widget(sv)

        # TERMINAL
        terminal = BoxLayout(orientation="vertical", size_hint_y=None,
                             height=dp(230), spacing=dp(4))
        terminal.add_widget(lbl("HITBOX TERMINAL", size=12, bold=True,
                                size_hint_y=None, height=dp(22)))
        self.terminal_output = TextInput(
            readonly=True, font_name="RobotoMono-Regular", font_size=sp(12),
            background_color=CARD, foreground_color=(1, 1, 1, 1),
            text="Safe built-in terminal. Type 'help' to see supported commands.\n",
        )
        terminal.add_widget(self.terminal_output)

        row = BoxLayout(size_hint_y=None, height=dp(42), spacing=dp(4))
        self.command_entry = TextInput(
            hint_text="Enter a command...", multiline=False,
            write_tab=False,
        )
        self.command_entry.bind(on_text_validate=self.run_terminal_command)
        row.add_widget(self.command_entry)
        row.add_widget(btn("Run", self.run_terminal_command, width=70))
        terminal.add_widget(row)
        root.add_widget(terminal)

        scr.add_widget(root)
        self.populate_files()
        self.sm.current = "ws"

    # =========================
    # FILE EXPLORER
    # =========================

    def populate_files(self):
        self.file_list.clear_widgets()
        root = self.workspace_path(self.current_workspace)
        self._add_tree_items(root, root, 0)

    def _add_tree_items(self, folder, root, depth):
        try:
            entries = sorted(
                folder.iterdir(),
                key=lambda p: (not p.is_dir(), p.name.lower()),
            )
        except OSError:
            return

        for path in entries:
            row = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(4))
            indent = "    " * depth

            if path.is_dir():
                b = btn(f"{indent}[DIR]  {path.name}/",
                        lambda *_, p=path: self.open_folder(p),
                        color=TRANSPARENT)
            else:
                b = btn(f"{indent}{path.name}",
                        lambda *_, p=path: self.open_file(p),
                        color=TRANSPARENT)
            b.halign = "left"
            b.bind(size=lambda inst, val: setattr(inst, "text_size", (val[0] - dp(12), val[1])))
            b.padding_x = dp(8)
            row.add_widget(b)

            if not path.is_dir():
                row.add_widget(btn("Del", lambda *_, p=path: self.delete_path(p),
                                   width=56, color=RED))

            self.file_list.add_widget(row)

            if path.is_dir():
                self._add_tree_items(path, root, depth + 1)

    def open_folder(self, path):
        try:
            root = self.workspace_path(self.current_workspace).resolve()
            if not path.resolve().is_relative_to(root):
                return
            count = len(list(path.iterdir()))
        except (OSError, ValueError):
            return
        info("Folder", f"Folder: {path.name}\nItems: {count}")

    # =========================
    # CREATE FILES AND FOLDERS
    # =========================

    def new_file(self, *_):
        self.ask_name("New file", "File name (for example notes.txt):", self.create_file)

    def new_folder(self, *_):
        self.ask_name("New folder", "Folder name:", self.create_folder)

    def ask_name(self, title, prompt, callback):
        box = BoxLayout(orientation="vertical", padding=dp(12), spacing=dp(10))
        box.add_widget(lbl(prompt, size_hint_y=None, height=dp(28)))
        entry = TextInput(multiline=False, size_hint_y=None, height=dp(44))
        box.add_widget(entry)
        popup = Popup(title=title, content=box, size_hint=(0.9, 0.4))

        def submit(*_):
            value = entry.text.strip()
            if value:
                popup.dismiss()
                callback(value)

        entry.bind(on_text_validate=submit)
        box.add_widget(btn("Create", submit, size_hint_y=None, height=dp(46)))
        popup.open()

    def create_file(self, name):
        if Path(name).name != name:
            info("Invalid name", "Use a file name, not a path.")
            return
        path = self.workspace_path(self.current_workspace) / name
        if path.exists():
            info("Already exists", "That name is already used.")
            return
        path.write_text("", encoding="utf-8")
        self.render_workspace()
        self.open_file(path)

    def create_folder(self, name):
        if Path(name).name != name:
            info("Invalid name", "Use a folder name, not a path.")
            return
        try:
            (self.workspace_path(self.current_workspace) / name).mkdir()
            self.render_workspace()
        except FileExistsError:
            info("Already exists", "That name is already used.")

    # =========================
    # ADD FILES
    # =========================

    def add_files(self, *_):
        try:
            from plyer import filechooser
            filechooser.open_file(
                on_selection=lambda sel: Clock.schedule_once(
                    lambda dt: self.copy_files(sel or []), 0),
                multiple=True,
            )
        except Exception:
            self.fallback_chooser()

    def fallback_chooser(self):
        start = "/storage/emulated/0" if Path("/storage/emulated/0").exists() else str(Path.home())
        box = BoxLayout(orientation="vertical", spacing=dp(6))
        chooser = FileChooserListView(path=start, multiselect=True)
        box.add_widget(chooser)
        popup = Popup(title="Add files to workspace", content=box, size_hint=(0.96, 0.9))

        def add(*_):
            popup.dismiss()
            self.copy_files(chooser.selection)

        row = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(6))
        row.add_widget(btn("Cancel", lambda *_: popup.dismiss(), color=GREY))
        row.add_widget(btn("Add", add))
        box.add_widget(row)
        popup.open()

    def copy_files(self, paths):
        if not paths:
            return
        dest = self.workspace_path(self.current_workspace)
        errors = []

        for item in paths:
            source = Path(item)
            if not source.is_file():
                continue
            target = dest / source.name
            n = 1
            while target.exists():  # no overwrite prompt: auto-rename
                target = dest / f"{source.stem} ({n}){source.suffix}"
                n += 1
            try:
                shutil.copy2(source, target)
            except OSError as exc:
                errors.append(str(exc))

        self.render_workspace()
        if errors:
            info("Copy failed", "\n".join(errors))

    # =========================
    # DELETE FILES
    # =========================

    def delete_path(self, path):
        root = self.workspace_path(self.current_workspace).resolve()
        try:
            resolved = path.resolve()
            if not resolved.is_relative_to(root) or resolved == root:
                return
        except (OSError, ValueError):
            return

        def do_delete():
            try:
                if path.is_dir():
                    shutil.rmtree(path)
                else:
                    path.unlink()
                self.render_workspace()
            except OSError as exc:
                info("Delete failed", str(exc))

        confirm("Delete", f"Delete '{path.name}'?", do_delete)

    # =========================
    # CODE EDITOR
    # =========================

    def open_file(self, path):
        try:
            root = self.workspace_path(self.current_workspace).resolve()
            path = path.resolve()

            if not path.is_relative_to(root) or not path.is_file():
                return

            if path.suffix.lower() not in TEXT_EXTENSIONS:
                info("File", "This file type is not supported by the text editor.\n"
                             "You can still keep it in the workspace.")
                return

            if path.stat().st_size > MAX_TEXT_SIZE:
                info("File too large", "Files larger than 2 MB are not opened in the editor.")
                return

            content = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            info("Cannot open file", str(exc))
            return

        self.editor_path = path
        scr = self.editor_screen
        scr.clear_widgets()

        root = BoxLayout(orientation="vertical")
        bar = BoxLayout(size_hint_y=None, height=dp(48), padding=dp(4), spacing=dp(6))
        bar.add_widget(btn("< Back", lambda *_: self.close_editor(), width=80, color=GREY))
        bar.add_widget(lbl(path.name, size=15, bold=True))
        self.editor_status = lbl("Ready", color=GREY, size_hint_x=None, width=dp(80))
        bar.add_widget(self.editor_status)
        bar.add_widget(btn("Save", self.save_file, width=70))
        root.add_widget(bar)

        self.editor = TextInput(
            text=content, font_name="RobotoMono-Regular", font_size=sp(14),
            background_color=CARD, foreground_color=(1, 1, 1, 1),
            cursor_color=(1, 1, 1, 1),
        )
        self.editor.bind(text=lambda *_: setattr(self.editor_status, "text", "Edited"))
        root.add_widget(self.editor)

        scr.add_widget(root)
        self.sm.current = "editor"

    def save_file(self, *_):
        try:
            self.editor_path.write_text(self.editor.text, encoding="utf-8")
            self.editor_status.text = "Saved"
            self.editor_status.color = (0.13, 0.77, 0.37, 1)
        except OSError as exc:
            info("Save failed", str(exc))

    def close_editor(self):
        self.render_workspace()

    # =========================
    # TERMINAL
    # =========================

    def terminal_print(self, text):
        out = self.terminal_output
        out.text += str(text) + "\n"
        Clock.schedule_once(
            lambda dt: setattr(out, "cursor", out.get_cursor_from_index(len(out.text))), 0
        )

    def run_terminal_command(self, *_):
        command = self.command_entry.text.strip()
        if not command:
            return
        self.command_entry.text = ""
        self.terminal_print(f"> {command}")
        try:
            result = self.safe_terminal(command)
            if result:
                self.terminal_print(result)
        except Exception as exc:
            self.terminal_print(f"Error: {exc}")
        Clock.schedule_once(lambda dt: setattr(self.command_entry, "focus", True), 0.1)

    def safe_terminal(self, command):
        try:
            parts = shlex.split(command, posix=False)
            parts = [p.strip('"') for p in parts]
        except ValueError:
            return "Could not parse command. Try: help"

        if not parts:
            return ""

        cmd = parts[0].lower()
        args = parts[1:]

        root = self.workspace_path(self.current_workspace).resolve()
        cwd = self.terminal_cwd or root

        if not cwd.resolve().is_relative_to(root):
            self.terminal_cwd = root
            cwd = root

        if cmd in ("help", "?"):
            return ("Commands: help, pwd, dir / ls, cd <folder>, echo <text>, "
                    "mkdir <folder>, touch <file>, clear")

        if cmd == "pwd":
            return str(cwd)

        if cmd in ("dir", "ls"):
            try:
                items = sorted(cwd.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
                return "\n".join(
                    (" <DIR>  " if p.is_dir() else "        ") + p.name for p in items
                ) or "(empty)"
            except OSError as exc:
                return str(exc)

        if cmd == "echo":
            return " ".join(args)

        if cmd == "clear":
            self.terminal_output.text = ""
            return ""

        if cmd == "cd":
            target = (cwd / (args[0] if args else str(root))).resolve()
            if target.is_dir() and target.is_relative_to(root):
                self.terminal_cwd = target
                return str(target)
            return "Folder not found or outside this workspace."

        if cmd == "mkdir" and args:
            target = (cwd / args[0]).resolve()
            if target.is_relative_to(root):
                target.mkdir(exist_ok=True)
                self.populate_files()
                return f"Created folder: {target.name}"
            return "You can only create folders inside this workspace."

        if cmd == "touch" and args:
            target = (cwd / args[0]).resolve()
            if target.is_relative_to(root):
                target.touch(exist_ok=True)
                self.populate_files()
                return f"Created file: {target.name}"
            return "You can only create files inside this workspace."

        return "Command not supported. Type 'help' for the available commands."


if __name__ == "__main__":
    HitboxApp().run()
