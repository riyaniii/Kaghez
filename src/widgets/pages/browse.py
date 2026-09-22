from gi.repository import Gtk, Adw, Gio

from .sources import SourcesPage
from .extensions import ExtensionsPage

@Gtk.Template(resource_path='/com/rini/kaghez/pages/browse.ui')
class BrowsePage(Adw.NavigationPage):
    __gtype_name__ = "KaghezBrowsePage"

    search_bar = Gtk.Template.Child()
    sources_entry = Gtk.Template.Child()
    extensions_entry = Gtk.Template.Child()
    sources_page = Gtk.Template.Child()
    extensions_page = Gtk.Template.Child()

    def __init__(self):
        super().__init__()

    @Gtk.Template.Callback()
    def on_sources_search_changed(self, entry):
        self.sources_page.set_search_text(entry.get_text())

    @Gtk.Template.Callback()
    def on_extensions_search_changed(self, entry):
        self.extensions_page.set_search_text(entry.get_text())

    @Gtk.Template.Callback()
    def on_search_mode_changed(self, search_bar, *_):
        # Closing the bar clears both searches, so a hidden filter
        # can't keep hiding items.
        if not search_bar.get_search_mode():
            self.sources_entry.set_text("")
            self.extensions_entry.set_text("")
