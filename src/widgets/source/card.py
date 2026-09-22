from gi.repository import Gtk, Adw, Gio, GObject

from ...integrations import models

@Gtk.Template(resource_path='/com/rini/kaghez/source/card.ui')
class SourceCard(Gtk.Box):
    __gtype_name__ = "KaghezSourceCard"

    model = GObject.Property(type=models.Source)

    def __init__(self, model=None):
        super().__init__()
        self.model = model
