import asyncio
from gi.repository import Gtk, GObject, Gio

from .base import ReaderBase


@Gtk.Template(resource_path='/com/rini/kaghez/reader/double.ui')
class DoublePageReader(ReaderBase):
    """Shows two pages side by side as a spread. `position` always refers
    to the earlier page of the currently-shown pair; setting it to any
    value snaps down to its pair boundary (0-1, 2-3, 4-5, ...). Under LTR
    direction the earlier page is drawn on the left; under RTL, on the
    right - matching manga reading order."""

    __gtype_name__ = "KaghezDoublePageReader"

    left_picture = Gtk.Template.Child()
    right_picture = Gtk.Template.Child()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.store = None
        self._position = 0
        self.left_task = None
        self.right_task = None

        self.connect("notify::direction", self.on_direction_changed)

    def bind_store(self, store: Gio.ListStore):
        self.store = store

    @GObject.Property(type=int, default=0)
    def position(self):
        return self._position

    @position.setter
    def position(self, value):
        n = self.chapter_model.page_count if self.chapter_model else 0
        if n == 0:
            self._position = 0
            return
        value = max(0, min(value, n - 1))
        self._position = value - (value % 2)
        self.show_current()

    def next_page(self):
        n = self.chapter_model.page_count if self.chapter_model else 0
        if n == 0:
            return
        if self._position + 2 >= n:  # already on the last spread
            self.emit("chapter-requested", 1)
        else:
            self.position += 2

    def previous_page(self):
        n = self.chapter_model.page_count if self.chapter_model else 0
        if n == 0:
            return
        if self._position == 0:
            self.emit("chapter-requested", -1)
        else:
            self.position -= 2

    def on_direction_changed(self, *_):
        if self.store:
            self.show_current()


    def cancel_tasks(self):
        if self.left_task:
            self.left_task.cancel()
            self.left_task = None
        if self.right_task:
            self.right_task.cancel()
            self.right_task = None

    def show_current(self):
        self.cancel_tasks()

        n = self.chapter_model.page_count if self.chapter_model else 0
        earlier_item = self.store.get_item(self._position) if self._position < n else None
        later_item = self.store.get_item(self._position + 1) if self._position + 1 < n else None

        if self.get_direction() == Gtk.TextDirection.RTL:
            earlier_picture, later_picture = self.right_picture, self.left_picture
        else:
            earlier_picture, later_picture = self.left_picture, self.right_picture

        earlier_picture.set_paintable(earlier_item.paintable if earlier_item else None)
        later_picture.set_paintable(later_item.paintable if later_item else None)

        if earlier_item and earlier_item.paintable is None and earlier_item.url:
            self.left_task = asyncio.create_task(
                self.load_paintable(earlier_item, earlier_picture)
            )
        if later_item and later_item.paintable is None and later_item.url:
            self.right_task = asyncio.create_task(
                self.load_paintable(later_item, later_picture)
            )

    async def load_paintable(self, item, picture):
        try:
            paintable = await self.suwayomi.getPaintable(item.url)
        except asyncio.CancelledError:
            raise
        except Exception:
            return
        if paintable:
            item.paintable = paintable
            n = self.chapter_model.page_count if self.chapter_model else 0
            current_earlier = self.store.get_item(self._position) if self._position < n else None
            current_later = self.store.get_item(self._position + 1) if self._position + 1 < n else None
            if item is current_earlier or item is current_later:
                picture.set_paintable(paintable)
