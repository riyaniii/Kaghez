import asyncio
from gi.repository import Gtk, Adw, Gio, GObject

from ..manga import MangaOverview
from ..containers import MangaRow

from ...integrations import SourceMangaType

@Gtk.Template(resource_path='/com/rini/kaghez/pages/home.ui')
class HomePage(Adw.NavigationPage):
    __gtype_name__ = "KaghezHomePage"

    manga_carousel = Gtk.Template.Child()
    carousel_stack = Gtk.Template.Child()
    main_box = Gtk.Template.Child()

    state = GObject.Property(type=str, default="home")

    def __init__(self):
        super().__init__()
        self.suwayomi = Gio.Application.get_default().suwayomi
        self.shown_rows = 0
        self.carousel_children = []

        self.library_handler = self.suwayomi.library.connect(
            "items-changed", self.on_library_changed
        )
        self.connect("destroy", self.on_destroy)

        asyncio.create_task(self.load())

    def on_destroy(self, *_):
        if self.library_handler is not None:
            self.suwayomi.library.disconnect(self.library_handler)
            self.library_handler = None

    async def load(self):
        try:
            await asyncio.gather(self.load_library(), self.load_sources())
        finally:
            if self.shown_rows == 0 and not self.carousel_children:
                self.state = "greeter"

    async def load_library(self):
        await self.suwayomi.refreshLibrary()
        self.sync_carousel()

    def on_library_changed(self, store, position, removed, added):
        self.sync_carousel()
        if self.carousel_children and self.state == "greeter":
            self.state = "home"

    def sync_carousel(self):
        while self.carousel_children:
            child = self.carousel_children.pop()
            self.manga_carousel.remove(child)

        for manga in list(self.suwayomi.library)[:6]:
            child = MangaOverview(manga)
            self.manga_carousel.append(child)
            self.carousel_children.append(child)

        self.carousel_stack.set_visible_child_name(
            "carousel" if self.carousel_children else "empty"
        )

    async def load_sources(self):
        await self.suwayomi.refreshSources()
        sources = list(self.suwayomi.sources)[:5]

        tasks = []

        for source in sources:
            row = MangaRow(source.name)
            row.set_visible(False)
            self.main_box.append(row)
            tasks.append(self.get_popular(source, row))

        await asyncio.gather(*tasks, return_exceptions=True)

    async def get_popular(self, source, row):
        try:
            mangas = await self.suwayomi.getSourceManga(
                source.id, fetch_type=SourceMangaType.POPULAR
            )
        except Exception as e:
            print(f"source {source.name!r} ({source.id}) failed: {e!r}")
            return

        if mangas:
            mangas = mangas[:8]
            row.set_items(mangas)
            row.set_visible(True)
            self.shown_rows += 1
        else:
            self.main_box.remove(row)
