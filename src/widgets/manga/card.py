from gi.repository import Gtk, Adw, Gio, GObject

from ...integrations import models

@Gtk.Template(resource_path='/com/rini/kaghez/manga/card.ui')
class MangaCard(Gtk.Box):
    __gtype_name__ = "KaghezMangaCard"

    model = GObject.Property(type=models.Manga)

    def __init__(self, model=None):
        super().__init__()
        if model is not None:
            self.model = model
