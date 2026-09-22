import asyncio
from gi.repository import Gtk, Adw, Gio, GLib, Pango

from .row import DownloadRow

@Gtk.Template(resource_path='/com/rini/kaghez/download/page.ui')
class DownloadsPage(Adw.NavigationPage):
    __gtype_name__ = "KaghezDownloadsPage"

    download_stack = Gtk.Template.Child()
    download_list = Gtk.Template.Child()
    search_entry = Gtk.Template.Child()
    toggle_button = Gtk.Template.Child()

    def __init__(self):
        super().__init__()
        self.suwayomi = Gio.Application.get_default().suwayomi
        self.poll_id = 0
        self.refreshing = False

        self.filter = Gtk.CustomFilter.new(self.filter_download)
        self.filtered = Gtk.FilterListModel.new(self.suwayomi.download_queue, self.filter)

        # One section per manga. Sections are ordered by where the manga first
        # appears in the queue, so the one downloading now stays on top.
        self.manga_rank = {}
        self.update_manga_rank()
        self.section_sorter = Gtk.CustomSorter.new(self.compare_manga)
        self.sectioned = Gtk.SortListModel(model=self.filtered, section_sorter=self.section_sorter)
        self.download_list.set_model(Gtk.NoSelection.new(self.sectioned))

        header_factory = Gtk.SignalListItemFactory()
        header_factory.connect("setup", self.on_header_setup)
        header_factory.connect("bind", self.on_header_bind)
        self.download_list.set_header_factory(header_factory)

        factory = Gtk.SignalListItemFactory()
        factory.connect("setup", self.on_factory_setup)
        factory.connect("bind", self.on_factory_bind)
        factory.connect("unbind", self.on_factory_unbind)
        self.download_list.set_factory(factory)

        self.search_entry.connect("search-changed", self.on_search_changed)
        self.suwayomi.download_queue.connect("items-changed", self.on_queue_changed)
        self.suwayomi.connect("notify::downloader-state", self.on_downloader_state_changed)

        self.update_stack()
        self.update_toggle_button()

        asyncio.create_task(self.refresh())
        GLib.timeout_add_seconds(1, self.on_poll)

    def on_poll(self):
        asyncio.create_task(self.refresh())
        return GLib.SOURCE_CONTINUE

    async def refresh(self):
        # Skip a tick if the previous request is still in flight.
        if self.refreshing:
            return
        self.refreshing = True
        try:
            await self.suwayomi.getDownloadStatus()
        finally:
            self.refreshing = False

    def on_factory_setup(self, factory, list_item):
        list_item.set_selectable(False)
        list_item.set_activatable(False)
        row = DownloadRow()
        row.connect("reorder-requested", self.on_reorder_requested)
        row.connect("remove-requested", self.on_remove_requested)
        row.connect("retry-requested", self.on_retry_requested)
        list_item.set_child(row)

    def on_factory_bind(self, factory, list_item):
        list_item.get_child().model = list_item.get_item()

    def on_factory_unbind(self, factory, list_item):
        list_item.get_child().model = None

    def filter_download(self, download):
        text = self.search_entry.get_text().strip().lower()
        if not text:
            return True
        return text in download.manga_title.lower() or text in download.chapter_name.lower()

    def on_search_changed(self, entry):
        self.filter.changed(Gtk.FilterChange.DIFFERENT)

    def on_queue_changed(self, store, position, removed, added):
        self.update_stack()
        self.update_manga_rank()
        self.section_sorter.changed(Gtk.SorterChange.DIFFERENT)

    def update_manga_rank(self):
        self.manga_rank = {}
        for download in self.suwayomi.download_queue:
            self.manga_rank.setdefault(download.manga_id, len(self.manga_rank))

    def compare_manga(self, a, b, *_):
        # Items of one manga compare equal, which is what makes them a section.
        rank_a = self.manga_rank.get(a.manga_id, len(self.manga_rank))
        rank_b = self.manga_rank.get(b.manga_id, len(self.manga_rank))
        return (rank_a > rank_b) - (rank_a < rank_b)

    def on_header_setup(self, factory, header):
        label = Gtk.Label(xalign=0.0, ellipsize=Pango.EllipsizeMode.END)
        label.add_css_class("heading")
        label.set_margin_start(12)
        label.set_margin_end(12)
        label.set_margin_top(12)
        label.set_margin_bottom(6)
        header.set_child(label)
        # The section's first item can change (reordering) without a re-bind.
        header.connect("notify::item", lambda h, _: self.update_header(h))

    def on_header_bind(self, factory, header):
        self.update_header(header)

    def update_header(self, header):
        item = header.get_item()  # first download of the section
        header.get_child().set_label(item.manga_title if item else "")

    def update_stack(self):
        if self.suwayomi.download_queue.get_n_items() == 0:
            self.download_stack.set_visible_child_name("greeter")
        else:
            self.download_stack.set_visible_child_name("downloads")

    def on_downloader_state_changed(self, *_):
        self.update_toggle_button()

    def update_toggle_button(self):
        if self.suwayomi.downloader_state == "STARTED":
            self.toggle_button.set_icon_name("media-playback-pause-symbolic")
            self.toggle_button.set_tooltip_text("Pause downloads")
        else:
            self.toggle_button.set_icon_name("media-playback-start-symbolic")
            self.toggle_button.set_tooltip_text("Start downloads")

    def on_reorder_requested(self, row, dragged_chapter_id, target_chapter_id):
        # The list may be filtered, so the target index comes from the real
        # queue store, which is what the server's `to` refers to.
        for index, download in enumerate(self.suwayomi.download_queue):
            if download.chapter_id == target_chapter_id:
                asyncio.create_task(
                    self.suwayomi.reorderChapterDownload(dragged_chapter_id, index)
                )
                return

    def on_remove_requested(self, row, chapter_id):
        asyncio.create_task(self.suwayomi.dequeueChapterDownload(chapter_id))

    def on_retry_requested(self, row, chapter_id):
        asyncio.create_task(self.retry(chapter_id))

    async def retry(self, chapter_id):
        # Dequeue first so the server starts the chapter over with fresh tries.
        await self.suwayomi.dequeueChapterDownload(chapter_id)
        await self.suwayomi.enqueueChapterDownload(chapter_id)

    @Gtk.Template.Callback()
    def on_toggle_clicked(self, *_):
        if self.suwayomi.downloader_state == "STARTED":
            asyncio.create_task(self.suwayomi.stopDownloader())
        else:
            asyncio.create_task(self.suwayomi.startDownloader())

    @Gtk.Template.Callback()
    def on_clear_clicked(self, *_):
        dialog = Adw.AlertDialog(
            heading="Clear download queue?",
            body="Every queued chapter will be removed. Chapters already downloaded stay on the server.",
        )
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("clear", "Clear")
        dialog.set_response_appearance("clear", Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.set_default_response("cancel")
        dialog.set_close_response("cancel")
        dialog.connect("response", self.on_clear_response)
        dialog.present(self)

    def on_clear_response(self, dialog, response):
        if response == "clear":
            asyncio.create_task(self.suwayomi.clearDownloader())
