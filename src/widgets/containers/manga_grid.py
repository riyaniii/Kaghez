import asyncio

from gi.repository import Gtk, Adw, Gio, GLib
from ..manga import MangaCard
from ...integrations import models

@Gtk.Template(resource_path='/com/rini/kaghez/containers/manga_grid.ui')
class MangaGrid(Adw.BreakpointBin):
    __gtype_name__ = 'KaghezMangaGrid'

    grid = Gtk.Template.Child()

    widget = MangaCard
    model = models.Manga

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.search_text = ""
        self.suwayomi = Gio.Application.get_default().suwayomi

        self.store = Gio.ListStore(item_type=self.model)

        self.custom_filter = Gtk.CustomFilter.new(self.filter_func)
        self.filter_model = Gtk.FilterListModel(model=self.store, filter=self.custom_filter)

        selection = Gtk.NoSelection(model=self.filter_model)
        self.grid.set_model(selection)
        self.grid.connect('activate', self.on_activate)

        factory = Gtk.SignalListItemFactory()
        factory.connect('setup', self.on_setup)
        factory.connect('bind', self.on_bind)
        factory.connect('unbind', self.on_unbind)
        self.grid.set_factory(factory)

    def bind_store(self, store: Gio.ListStore):
        # Shows a store owned elsewhere (e.g. Suwayomi.library) instead of the
        # local one. After this, set_items/remove_all would change that store,
        # so use one or the other.
        self.store = store
        self.filter_model.set_model(store)

    def filter_func(self, item):
        title = (item.title or "").lower()
        return self.search_text in title

    def set_search_text(self, text: str):
        self.search_text = text.strip().lower()
        self.custom_filter.changed(Gtk.FilterChange.DIFFERENT)

    def on_setup(self, factory, list_item):
        child = self.widget()
        child.thumbnail_task = None
        list_item.set_child(child)

    def on_bind(self, factory, list_item):
        item = list_item.get_item()
        card = list_item.get_child()
        card.model = item

        if item.paintable is None and item.thumbnail_url:
            card.thumbnail_task = asyncio.create_task(self.load_thumbnail(item))

    def on_unbind(self, factory, list_item):
        card = list_item.get_child()
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

    def on_activate(self, grid_view, position):
        item = self.filter_model.get_item(position)
        grid_view.activate_action("app.show_manga", GLib.Variant("i", item.id))

    def remove_all(self):
        self.store.remove_all()

    def set_items(self, items: list):
        self.store.splice(0, self.store.get_n_items(), items)
