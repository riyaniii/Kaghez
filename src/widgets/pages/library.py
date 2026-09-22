import asyncio
from gi.repository import Gtk, Adw, Gio, GObject

from ..manga import MangaCard
from ..containers import MangaGrid

from ...integrations import Suwayomi

@Gtk.Template(resource_path='/com/rini/kaghez/pages/library.ui')
class LibraryPage(Adw.NavigationPage):
    __gtype_name__ = "KaghezLibraryPage"

    manga_grid = Gtk.Template.Child()

    library_size = GObject.Property(type=int, default=0)

    def __init__(self):
        super().__init__()
        self.suwayomi = Gio.Application.get_default().suwayomi

        library = self.suwayomi.library
        self.manga_grid.bind_store(library)
        library.bind_property("n-items", self, "library_size", GObject.BindingFlags.SYNC_CREATE)

        asyncio.create_task(self.suwayomi.refreshLibrary())

    @Gtk.Template.Callback()
    def get_page(self, obj, size):
        return "grid" if size > 0 else "greeter"

    @Gtk.Template.Callback()
    def on_search_changed(self, entry):
        self.manga_grid.set_search_text(entry.get_text())
