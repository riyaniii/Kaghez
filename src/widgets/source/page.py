import asyncio
from gi.repository import Gtk, Adw, Gio, GObject

from ..manga import MangaCard
from ..containers import MangaGrid
from .filter import SourceFilter

from ...integrations import models
from ...integrations.suwayomi import SourceMangaType

@Gtk.Template(resource_path='/com/rini/kaghez/source/page.ui')
class SourcePage(Adw.NavigationPage):
    __gtype_name__ = "KaghezSourcePage"

    model = GObject.Property(type=models.Source)

    search_entry = Gtk.Template.Child()
    filter_button = Gtk.Template.Child()

    popular_stack = Gtk.Template.Child()
    popular_grid = Gtk.Template.Child()
    popular_error = Gtk.Template.Child()

    latest_stack = Gtk.Template.Child()
    latest_grid = Gtk.Template.Child()
    latest_error = Gtk.Template.Child()

    search_stack = Gtk.Template.Child()
    search_grid = Gtk.Template.Child()
    search_error = Gtk.Template.Child()

    def __init__(self, model):
        super().__init__()
        self.model = model
        self.suwayomi = Gio.Application.get_default().suwayomi
        self.search_task = None
        self.latest_loaded = False

        # Cancelling a search on the client doesn't stop the server's scrape,
        # so wait longer before starting one.
        self.search_entry.set_search_delay(400)
        self.search_entry.connect("search-changed", self.on_search_changed)

        self.filter_changes = []
        self.filter_dialog = SourceFilter()
        self.filter_dialog.connect("applied", self.on_filters_applied)

        # Latest is loaded the first time its tab is shown, not on open.
        asyncio.create_task(self.load_popular())
        asyncio.create_task(self.load_filters())

    @Gtk.Template.Callback()
    def on_page_changed(self, stack, pspec):
        if stack.get_visible_child_name() == "latest" and not self.latest_loaded:
            self.latest_loaded = True
            asyncio.create_task(self.load_latest())

    async def load_popular(self):
        self.set_stack_page(self.popular_stack, "loading")
        try:
            popular = await self.suwayomi.getSourceManga(
                self.model.id, fetch_type=SourceMangaType.POPULAR
            )
        except Exception as e:
            self.show_error(self.popular_stack, self.popular_error, e)
            return
        self.popular_grid.set_items(popular)
        self.set_stack_page(self.popular_stack, "results" if popular else "empty")

    async def load_latest(self):
        self.set_stack_page(self.latest_stack, "loading")
        try:
            latest = await self.suwayomi.getSourceManga(
                self.model.id, fetch_type=SourceMangaType.LATEST
            )
        except Exception as e:
            self.show_error(self.latest_stack, self.latest_error, e)
            return
        self.latest_grid.set_items(latest)
        self.set_stack_page(self.latest_stack, "results" if latest else "empty")

    def set_stack_page(self, stack: Gtk.Stack, name: str):
        stack.set_visible_child_name(name)

    def show_error(self, stack: Gtk.Stack, status_page: Adw.StatusPage, error: Exception):
        status_page.set_description(str(error))
        stack.set_visible_child_name("error")

    @Gtk.Template.Callback()
    def is_search_page(self, obj, page_name):
        return page_name == "search"

    def on_search_changed(self, entry):
        self.search()

    def search(self):
        text = self.search_entry.get_text()
        if self.search_task is not None:
            self.search_task.cancel()
            self.search_task = None

        # Filters alone are a valid search, so an empty box only resets the
        # page when no filters are set either.
        if text or self.filter_changes:
            self.set_stack_page(self.search_stack, "loading")
            self.search_task = asyncio.create_task(self.load_search(text))
        else:
            self.set_stack_page(self.search_stack, "normal")
            self.search_grid.remove_all()

    async def load_search(self, query: str):
        try:
            results = await self.suwayomi.getSourceManga(
                self.model.id,
                fetch_type=SourceMangaType.SEARCH,
                query=query or None,
                filters=self.filter_changes,
            )
        except Exception as e:
            self.show_error(self.search_stack, self.search_error, e)
            return
        self.search_grid.set_items(results)
        self.set_stack_page(self.search_stack, "results" if results else "empty")

    async def load_filters(self):
        try:
            filters = await self.suwayomi.getSourceFilters(self.model.id)
        except Exception as e:
            print(f"[filters] load failed: {type(e).__name__}: {e}")
            filters = []
        self.filter_dialog.set_filters(filters)

    def on_filters_applied(self, dialog, changes):
        self.filter_changes = changes
        if changes:
            self.filter_button.add_css_class("suggested-action")
        else:
            self.filter_button.remove_css_class("suggested-action")
        self.search()

    @Gtk.Template.Callback()
    def on_filter_clicked(self, *_):
        self.filter_dialog.present(self)
