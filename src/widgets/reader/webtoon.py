import asyncio
from dataclasses import dataclass
from gi.repository import Gtk, GObject, Gio

from ...integrations import models
from .base import ReaderBase
from .canvas import Canvas

PREFETCH_PAGES = 5
BANNER_RATIO = 2.2


class TransitionPage(models.Page):
    """Synthetic page announcing the chapter that follows it in the strip."""

    def __init__(self, chapter):
        super().__init__()
        self.chapter = chapter


@dataclass
class ChapterRange:
    """Where one chapter's pages sit within the continuous store."""

    model: models.Chapter
    start: int
    count: int

    @property
    def end(self):
        return self.start + self.count


@Gtk.Template(resource_path='/com/rini/kaghez/reader/webtoon.ui')
class WebtoonReader(ReaderBase):
    """Webtoon-style reader that scrolls seamlessly across chapter
    boundaries. Keeps its own continuous store spanning as many chapters as
    are currently loaded, unlike the other readers which only ever see one
    chapter at a time. A banner page announces each boundary."""

    __gtype_name__ = "KaghezWebtoonReader"

    orientation = GObject.Property(type=Gtk.Orientation, default=Gtk.Orientation.VERTICAL)

    canvas = Gtk.Template.Child()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.current_position = 0

        self.store = Gio.ListStore(item_type=models.Page)
        self.chapters = []  # ChapterRange, in store order
        self.loading_before = False
        self.loading_after = False

        self.canvas.bind_store(self.store)
        self.bind_property(
            "orientation", self.canvas, "orientation", GObject.BindingFlags.SYNC_CREATE
        )
        self.bind_property(
            "direction", self.canvas, "direction", GObject.BindingFlags.SYNC_CREATE
        )
        self.canvas.connect("page-changed", self.on_page_changed)

        self.connect("notify::chapter-model", self.on_chapter_model_changed)


    def bind_store(self, store: Gio.ListStore):
        pass

    @GObject.Property(type=int, default=0)
    def position(self):
        return self.current_position

    @position.setter
    def position(self, value):
        page_count = self.chapter_model.page_count if self.chapter_model else 0
        self.current_position = max(0, min(value, page_count - 1)) if page_count else 0
        index = self.global_index(self.chapter_model, self.current_position)
        if index is not None:
            self.canvas.scroll_to_index(index)


    def on_chapter_model_changed(self, reader, param):
        chapter = self.chapter_model
        if chapter is None or self.find_range(chapter) is not None:
            return
        self.chapters = []
        self.store.remove_all()
        self.queue_chapter_load(chapter, prepend=False)

    def find_range(self, chapter):
        for chapter_range in self.chapters:
            if chapter_range.model.id == chapter.id:
                return chapter_range
        return None

    def range_at(self, index):
        for chapter_range in self.chapters:
            if chapter_range.start <= index < chapter_range.end:
                return chapter_range
        return None

    def global_index(self, chapter, position):
        chapter_range = self.find_range(chapter)
        return None if chapter_range is None else chapter_range.start + position

    def adjacent_chapter(self, chapter, direction):
        found, index = self.manga_model.chapters.find(chapter)
        if not found:
            return None
        index += direction
        if 0 <= index < self.manga_model.chapters.get_n_items():
            return self.manga_model.chapters.get_item(index)
        return None


    def queue_chapter_load(self, chapter, prepend: bool):
        asyncio.create_task(self.load_chapter_pages(chapter, prepend))

    async def load_chapter_pages(self, chapter, prepend: bool):
        if prepend:
            self.loading_before = True
        else:
            self.loading_after = True
        try:
            pages = await self.suwayomi.getChapterPages(chapter.id)
        except Exception:
            return
        finally:
            if prepend:
                self.loading_before = False
            else:
                self.loading_after = False

        banner = [TransitionPage(chapter)] if self.chapters else []
        block = banner + pages

        if prepend:
            for chapter_range in self.chapters:
                chapter_range.start += len(block)
            self.chapters.insert(0, ChapterRange(chapter, len(banner), len(pages)))
            self.store.splice(0, 0, block)
            banner_index = 0
        else:
            start = self.store.get_n_items() + len(banner)
            self.chapters.append(ChapterRange(chapter, start, len(pages)))
            self.store.splice(self.store.get_n_items(), 0, block)
            banner_index = start - 1

        if banner:
            self.canvas.set_ratio(banner_index, BANNER_RATIO)

        self.position = self.current_position

    def maybe_prefetch(self, index):
        if not self.chapters:
            return

        leading, trailing = self.chapters[0], self.chapters[-1]

        if not self.loading_before and index - leading.start < PREFETCH_PAGES:
            previous_chapter = self.adjacent_chapter(leading.model, -1)
            if previous_chapter:
                self.queue_chapter_load(previous_chapter, prepend=True)

        if not self.loading_after and trailing.end - index <= PREFETCH_PAGES:
            next_chapter = self.adjacent_chapter(trailing.model, 1)
            if next_chapter:
                self.queue_chapter_load(next_chapter, prepend=False)


    def on_page_changed(self, canvas, index):
        self.maybe_prefetch(index)

        chapter_range = self.range_at(index)
        if chapter_range is None:  # sitting on a banner page, between chapters
            return

        if chapter_range.model.id != self.chapter_model.id:
            self.mark_chapter_read(self.chapter_model)
            self.chapter_model = chapter_range.model

        position = index - chapter_range.start
        if position != self.current_position:
            self.current_position = position
            self.notify("position")

    def mark_chapter_read(self, chapter):
        if chapter.is_read:
            return
        asyncio.create_task(
            self.suwayomi.updateChapter(
                chapter_id=chapter.id,
                is_read=True,
                last_page_read=chapter.page_count,
            )
        )
