import asyncio

from gi.repository import Gtk, GObject, Gio, GLib, Adw
from ..manga import MangaCard
from ...integrations import models

@Gtk.Template(resource_path='/com/rini/kaghez/containers/row.ui')
class MangaRow(Gtk.Box):
    __gtype_name__ = 'KaghezMangaRow'

    listview = Gtk.Template.Child()

    title = GObject.Property(type=str, default="")

    widget = MangaCard

    def __init__(self, title, **kwargs):
        super().__init__(**kwargs)
        self.title = title

        self.suwayomi = Gio.Application.get_default().suwayomi

        self.store = Gio.ListStore(item_type=models.Manga)

        selection = Gtk.NoSelection(model=self.store)
        self.listview.set_model(selection)
        self.listview.connect('activate', self.on_activate)

        factory = Gtk.SignalListItemFactory()
        factory.connect('setup', self.on_setup)
        factory.connect('bind', self.on_bind)
        factory.connect('unbind', self.on_unbind)
        self.listview.set_factory(factory)

    def on_setup(self, factory, list_item):
        card = self.widget()
        card.thumbnail_task = None

        clamp = Adw.Clamp(orientation=Gtk.Orientation.HORIZONTAL, maximum_size=200)
        clamp.set_child(card)

        list_item.set_child(clamp)

    def on_bind(self, factory, list_item):
        item = list_item.get_item()
        card = list_item.get_child().get_child()
        card.model = item

        if item.paintable is None and item.thumbnail_url:
            card.thumbnail_task = asyncio.create_task(self.load_thumbnail(item))

    def on_unbind(self, factory, list_item):
        card = list_item.get_child().get_child()
        if card.thumbnail_task:
            card.thumbnail_task.cancel()
            card.thumbnail_task = None

        item = list_item.get_item()
        # So that the paintable no longer takes up memory within loaded_models within Suwayomi
        item.paintable = None

        card.model = None

    async def load_thumbnail(self, item):
        paintable = await self.suwayomi.getPaintable(item.thumbnail_url)
        if paintable:
            item.paintable = paintable

    def on_activate(self, listview, position):
        item = self.store.get_item(position)
        listview.activate_action("app.show_manga", GLib.Variant("i", item.id))

    def remove_all(self):
        self.store.remove_all()

    def set_items(self, items: list):
        self.store.splice(0, self.store.get_n_items(), items)
