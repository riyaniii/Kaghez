from gi.repository import Gtk, Adw, Gio, GObject

from ...integrations import models

@Gtk.Template(resource_path='/com/rini/kaghez/extension/dialog.ui')
class ExtensionDialog(Adw.Dialog):
    __gtype_name__ = "KaghezExtensionDialog"

    model = GObject.Property(type=models.Extension)

    def __init__(self, model):
        super().__init__()
        self.model = model

    @Gtk.Template.Callback()
    def get_age_rating(self, obj, is_nsfw):
        return "NSFW" if is_nsfw else "SAFE"
