import asyncio
from gi.repository import Gtk, Adw, Gio, GObject

from ..manga import MangaOverview
from ..containers import MangaRow

from ...integrations import SourceMangaType

@Gtk.Template(resource_path='/com/rini/kaghez/pages/home.ui')
class HomePage(Adw.NavigationPage):
    __gtype_name__ = "KaghezHomePage"

    manga_carousel = Gtk.Template.Child()
    main_box = Gtk.Template.Child()

    state = GObject.Property(type=str, default="home")

    def __init__(self):
        super().__init__()
        self.suwayomi = Gio.Application.get_default().suwayomi
        self.shown_rows = 0

        asyncio.create_task(self.load())

    async def load(self):
        try:
            await asyncio.gather(self.load_library(), self.load_sources())
        finally:
            if self.shown_rows == 0 and self.manga_carousel.get_n_pages() == 0:
                self.state = "greeter"

    async def load_library(self):
        await self.suwayomi.refreshLibrary()
        for manga in self.suwayomi.library[:6]:
            self.manga_carousel.append(MangaOverview(manga))

    async def load_sources(self):
        sources = await self.suwayomi.getSources(first=5)

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
