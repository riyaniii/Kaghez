from gi.repository import Gtk, GLib, Gio, GObject

from ...integrations import models

@Gtk.Template(resource_path='/com/rini/kaghez/extension/card.ui')
class ExtensionCard(Gtk.Box):
    __gtype_name__ = "KaghezExtensionCard"

    model = GObject.Property(type=models.Extension)

    def __init__(self):
        super().__init__()

    @Gtk.Template.Callback()
    def get_action_button_tooltip(self, obj, is_installed, has_update):
        if has_update:
            return "Update"
        elif is_installed:
            return "Uninstall"
        else:
            return "Install"

    @Gtk.Template.Callback()
    def get_action_button_icon_name(self, obj, is_installed, has_update):
        if has_update:
            return "up-symbolic"
        elif is_installed:
            return "list-remove-symbolic"
        else:
            return "list-add-symbolic"

    @Gtk.Template.Callback()
    def get_not(self, obj, value):
        return not value

    @Gtk.Template.Callback()
    def on_button_clicked(self, *_):
        self.activate_action("app.extension_action", GLib.Variant("s", self.model.pkg_name))
