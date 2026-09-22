import asyncio
from gi.repository import Gtk, GObject, Gio

from .base import ReaderBase


@Gtk.Template(resource_path='/com/rini/kaghez/reader/single.ui')
class SinglePageReader(ReaderBase):
    __gtype_name__ = "KaghezSinglePageReader"

    picture = Gtk.Template.Child()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.store = None
        self._position = 0
        self.paintable_task = None

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
        self._position = max(0, min(value, n - 1))
        self.show_current()

    def next_page(self):
        n = self.chapter_model.page_count if self.chapter_model else 0
        if n == 0:
            return
        if self._position >= n - 1:
            self.emit("chapter-requested", 1)
        else:
            self.position += 1

    def previous_page(self):
        n = self.chapter_model.page_count if self.chapter_model else 0
        if n == 0:
            return
        if self._position <= 0:
            self.emit("chapter-requested", -1)
        else:
            self.position -= 1


    def show_current(self):
        if self.paintable_task:
            self.paintable_task.cancel()
            self.paintable_task = None

        item = self.store.get_item(self._position)
        if item is None:
            self.picture.set_paintable(None)
            return

        self.picture.set_paintable(item.paintable)
        if item.paintable is None and item.url:
            self.paintable_task = asyncio.create_task(self.load_paintable(item))

    async def load_paintable(self, item):
        try:
            paintable = await self.suwayomi.getPaintable(item.url)
        except asyncio.CancelledError:
            raise
        except Exception:
            return
        if paintable:
            item.paintable = paintable
            if self.store.get_item(self._position) is item:
                self.picture.set_paintable(paintable)
