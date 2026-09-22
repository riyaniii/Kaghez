import asyncio
from gi.repository import Gtk, Adw, Gio, GObject

from ..containers import MangaRow
from ...integrations.suwayomi import SourceMangaType


@Gtk.Template(resource_path='/com/rini/kaghez/pages/search.ui')
class SearchPage(Adw.NavigationPage):
    __gtype_name__ = "KaghezSearchPage"

    main_box = Gtk.Template.Child()

    state = GObject.Property(type=str, default="greeter")
    completed_sources = GObject.Property(type=int, default=0)
    total_sources = GObject.Property(type=int, default=0)

    def __init__(self):
        super().__init__()
        self.suwayomi = Gio.Application.get_default().suwayomi
        self.search_task = None

    def clear_results(self):
        for child in list(self.main_box):
            self.main_box.remove(child)

    def reset_progress(self):
        self.completed_sources = 0
        self.total_sources = 0

    @Gtk.Template.Callback()
    def get_progress(self, obj, completed, total):
        return completed / total if total > 0 else 0.0

    async def search_source(self, source, row, query):
        try:
            mangas = await self.suwayomi.getSourceManga(
                source.id, fetch_type=SourceMangaType.SEARCH, page=1, query=query
            )
        except Exception as e:
            print(f"[search] source {source.name!r} ({source.id}) failed: {e!r}")
            self.main_box.remove(row)
            return
        finally:
            self.completed_sources += 1

        if mangas:
            row.set_items(mangas)
            row.set_visible(True)
        else:
            self.main_box.remove(row)

    async def search(self, query):
        self.reset_progress()
        self.state = "result"

        try:
            sources = await self.suwayomi.getSources()
        except Exception as e:
            print(f"[search] getSources failed: {e!r}")
            self.state = "empty"
            return

        if len(sources) == 0:
            self.state = "empty"
            return

        self.total_sources = len(sources)

        tasks = []
        for source in sources:
            row = MangaRow(source.name)
            row.set_visible(False)
            self.main_box.append(row)
            tasks.append(self.search_source(source, row, query))

        await asyncio.gather(*tasks, return_exceptions=True)
        self.reset_progress()
        if len(list(self.main_box)) == 0:
            self.state = "empty"

    @Gtk.Template.Callback()
    def on_search_entry_activate(self, entry):
        text = entry.get_text()
        if self.search_task is not None:
            self.search_task.cancel()
            self.search_task = None

        self.clear_results()
        self.reset_progress()

        if text:
            self.search_task = asyncio.create_task(self.search(text))
        else:
            self.state = "greeter"
