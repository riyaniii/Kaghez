from gi.repository import Gtk, Adw, Gio, GObject

from ...integrations import models


@Gtk.Template(resource_path='/com/rini/kaghez/reader/dialog.ui')
class SettingsDialog(Adw.Dialog):
    __gtype_name__ = "KaghezSettingsDialog"

    stack = GObject.Property(type=Gtk.Widget, default=None)

    orientation_row = Gtk.Template.Child()
    direction_row = Gtk.Template.Child()

    def __init__(self, stack):
        super().__init__()

        self.stack = stack

        webtoon_reader = self.stack.get_child_by_name("webtoon")

        self.updating = True
        if webtoon_reader.orientation == Gtk.Orientation.HORIZONTAL:
            self.orientation_row.set_selected(1)
        else:
            self.orientation_row.set_selected(0)

        if webtoon_reader.direction == Gtk.TextDirection.RTL:
            self.direction_row.set_selected(1)
        else:
            self.direction_row.set_selected(0)
        self.updating = False

    @Gtk.Template.Callback()
    def is_webtoon(self, obj, visible_child_name):
        return visible_child_name == "webtoon"

    @Gtk.Template.Callback()
    def on_orientation_changed(self, row, param):
        if self.updating:
            return
        webtoon_reader = self.stack.get_child_by_name("webtoon")
        webtoon_reader.orientation = (
            Gtk.Orientation.HORIZONTAL if row.get_selected() == 1
            else Gtk.Orientation.VERTICAL
        )

    @Gtk.Template.Callback()
    def on_direction_changed(self, row, param):
        if self.updating:
            return
        webtoon_reader = self.stack.get_child_by_name("webtoon")
        webtoon_reader.direction = (
            Gtk.TextDirection.RTL if row.get_selected() == 1
            else Gtk.TextDirection.LTR
        )
