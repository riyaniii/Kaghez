import asyncio
from datetime import datetime, timezone

from gi.repository import Gtk, Gdk, Gio, GObject, GLib

from ...integrations import models

@Gtk.Template(resource_path='/com/rini/kaghez/chapter/row.ui')
class ChapterRow(Gtk.Box):
    __gtype_name__ = "KaghezChapterRow"

    model = GObject.Property(type=models.Chapter)

    chapter_menu = Gtk.Template.Child()

    def __init__(self, model=None):
        super().__init__()
        self.model = model
        self.suwayomi = Gio.Application.get_default().suwayomi

        self.context_menu = Gtk.PopoverMenu.new_from_model(self.chapter_menu)
        self.context_menu.set_has_arrow(False)
        self.context_menu.set_parent(self)

        self.actions = Gio.SimpleActionGroup()
        self.insert_action_group("chapter", self.actions)
        self.add_chapter_action("add_bookmark", self.on_add_bookmark)
        self.add_chapter_action("remove_bookmark", self.on_remove_bookmark)
        self.add_chapter_action("mark_read", self.on_mark_read)
        self.add_chapter_action("mark_unread", self.on_mark_unread)
        self.add_chapter_action("download", self.on_download)
        self.add_chapter_action("delete_download", self.on_delete_download)

    def do_dispose(self):
        self.context_menu.unparent()
        Gtk.Box.do_dispose(self)

    def add_chapter_action(self, name, callback):
        action = Gio.SimpleAction.new(name, None)
        action.connect("activate", callback)
        self.actions.add_action(action)

    def set_action_enabled(self, name, enabled):
        self.actions.lookup_action(name).set_enabled(enabled)

    def open_menu(self, x, y):
        chapter = self.model
        self.set_action_enabled("add_bookmark", not chapter.is_bookmarked)
        self.set_action_enabled("remove_bookmark", chapter.is_bookmarked)
        self.set_action_enabled("mark_read", not chapter.is_read)
        self.set_action_enabled("mark_unread", chapter.is_read)
        self.set_action_enabled("download", not chapter.is_downloaded)
        self.set_action_enabled("delete_download", chapter.is_downloaded)

        area = Gdk.Rectangle()
        area.x, area.y, area.width, area.height = int(x), int(y), 1, 1
        self.context_menu.set_pointing_to(area)
        self.context_menu.popup()

    @Gtk.Template.Callback()
    def on_right_click(self, gesture, n_press, x, y):
        self.open_menu(x, y)

    @Gtk.Template.Callback()
    def on_long_press(self, gesture, x, y):
        self.open_menu(x, y)

    @Gtk.Template.Callback()
    def get_opacity(self, obj, is_read):
        return 0.5 if is_read else 1.0

    @Gtk.Template.Callback()
    def get_formatted_upload_date(self, obj, upload_date):
        if not upload_date:
            return ""
        dt = datetime.fromtimestamp(int(upload_date) / 1000, tz=timezone.utc)
        return dt.strftime("%m/%d/%Y")

    @Gtk.Template.Callback()
    def get_formatted_read_count(self, obj, last_page_read, page_count):
        return f"{last_page_read}/{page_count}"

    @Gtk.Template.Callback()
    def get_is_reading(self, obj, last_page_read):
        return last_page_read != 0

    def on_add_bookmark(self, *args):
        asyncio.create_task(self.suwayomi.updateChapter(self.model.id, is_bookmarked=True))

    def on_remove_bookmark(self, *args):
        asyncio.create_task(self.suwayomi.updateChapter(self.model.id, is_bookmarked=False))

    def on_mark_read(self, *args):
        asyncio.create_task(self.suwayomi.updateChapter(self.model.id, is_read=True))

    def on_mark_unread(self, *args):
        asyncio.create_task(self.suwayomi.updateChapter(self.model.id, is_read=False))

    def on_download(self, *args):
        self.activate_action("app.download_chapter", GLib.Variant("i", self.model.id))

    def on_delete_download(self, *args):
        self.activate_action("app.delete_chapter_download", GLib.Variant("i", self.model.id))
