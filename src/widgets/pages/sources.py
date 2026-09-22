import asyncio
from gi.repository import Gtk, Adw, Gio, GLib, GObject

from ..source import SourceCard
from ...integrations import models

@Gtk.Template(resource_path='/com/rini/kaghez/pages/sources.ui')
class SourcesPage(Adw.NavigationPage):
    __gtype_name__ = "KaghezSourcesPage"

    store = Gtk.Template.Child()

    search_text = GObject.Property(type=str)

    def __init__(self):
        super().__init__()
        self.suwayomi = Gio.Application.get_default().suwayomi

        asyncio.create_task(self.load())

    def set_search_text(self, text: str):
        self.search_text = text.strip()

    @Gtk.Template.Callback()
    def get_page(self, obj, count):
        return "sources" if count > 0 else "greeter"

    @Gtk.Template.Callback()
    def on_setup(self, factory, list_item):
        list_item.set_child(SourceCard())

    @Gtk.Template.Callback()
    def on_bind(self, factory, list_item):
        item = list_item.get_item()
        card = list_item.get_child()
        card.model = item

        if item.paintable is None and item.icon_url:
            card.icon_task = asyncio.create_task(self.load_icon(item, card))

    @Gtk.Template.Callback()
    def on_unbind(self, factory, list_item):

        card = list_item.get_child()
        if task := getattr(card, 'icon_task', None):
            task.cancel()
            card.icon_task = None

        item = list_item.get_item()
        item.paintable = None

        card.model = None

    @Gtk.Template.Callback()
    def on_header_setup(self, factory, header):
        label = Gtk.Label(xalign=0)
        label.add_css_class("heading")
        label.set_margin_top(12)
        label.set_margin_bottom(6)
        label.set_margin_start(12)
        header.set_child(label)

    @Gtk.Template.Callback()
    def on_header_bind(self, factory, header):
        lang = header.get_item().lang
        if lang == "all":
            title = "All languages"
        elif lang:
            title = lang.upper()
        else:
            title = "Other"
        header.get_child().set_label(title)

    async def load_icon(self, item, card):
        paintable = await self.suwayomi.getPaintable(item.icon_url)
        if paintable and card.model is item:
            item.paintable = paintable

    @Gtk.Template.Callback()
    def on_activate(self, listview, position):
        item = listview.get_model().get_item(position)
        listview.activate_action("app.show_source", GLib.Variant("s", item.id))

    async def load(self):
        sources = await self.suwayomi.getSources()
        self.store.splice(0, 0, sources)
