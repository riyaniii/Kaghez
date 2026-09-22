from gi.repository import Adw, Gtk, GObject, Gio

from ...integrations import models


class ReaderBase(Adw.Bin):
    __gtype_name__ = "KaghezReaderBase"

    chapter_model = GObject.Property(type=models.Chapter, default=None)
    manga_model = GObject.Property(type=models.Manga, default=None)

    @GObject.Signal(arg_types=(int,))
    def chapter_requested(self, direction):
        pass

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.suwayomi = Gio.Application.get_default().suwayomi

    @GObject.Property(type=Gtk.TextDirection, default=Gtk.TextDirection.LTR)
    def direction(self):
        return self.get_direction()

    @direction.setter
    def direction(self, value):
        self.set_direction(value)

    def bind_store(self, store: Gio.ListStore) -> None:
        raise NotImplementedError

    def next_page(self) -> None:
        self.position += 1

    def previous_page(self) -> None:
        self.position -= 1
