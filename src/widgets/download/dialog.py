import asyncio
from gettext import gettext as _, ngettext

from gi.repository import Adw, Gio, GLib, GObject, Gtk


def chapter_title(name, number):
    if name:
        return name
    return _("Chapter {}").format(f"{number:g}")


@Gtk.Template(resource_path='/io/github/riyaniii/Kaori/download/dialog.ui')
class DownloadDialog(Adw.Dialog):
    __gtype_name__ = "KaoriDownloadDialog"

    # Properties bound from the blueprint
    names = GObject.Property(type=Gtk.StringList)
    summary = GObject.Property(type=str, default="")
    can_download = GObject.Property(type=bool, default=False)

    # Class-level defaults so bindings can read them during template init
    chapters = ()
    first_unread = 0
    _from_index = 0
    _to_index = 0
    _skip_read = False

    # --- bound state -------------------------------------------------------

    @GObject.Property(type=int)
    def from_index(self):
        return self._from_index

    @from_index.setter
    def from_index(self, value):
        self._from_index = value
        if value > self._to_index:
            self.to_index = value
        self.refresh()

    @GObject.Property(type=int)
    def to_index(self):
        return self._to_index

    @to_index.setter
    def to_index(self, value):
        self._to_index = value
        if value < self._from_index:
            self.from_index = value
        self.refresh()

    @GObject.Property(type=bool, default=False)
    def skip_read(self):
        return self._skip_read

    @skip_read.setter
    def skip_read(self, value):
        self._skip_read = value
        self.refresh()

    # --- setup -------------------------------------------------------------

    def __init__(self, model):
        super().__init__()
        self.chapters = list(model.chapters)

        unread = model.first_unread_chapter
        self.first_unread = next(
            (i for i, c in enumerate(self.chapters) if unread is not None and c.id == unread.id),
            0,
        )

        self.names = Gtk.StringList.new(
            [chapter_title(c.name, c.chapter_number) for c in self.chapters]
        )

        actions = Gio.SimpleActionGroup()
        preset = Gio.SimpleAction.new("preset", GLib.VariantType("i"))
        preset.connect("activate", self.on_preset)
        actions.add_action(preset)
        download = Gio.SimpleAction.new("download", None)
        download.connect("activate", self.on_download)
        actions.add_action(download)
        self.insert_action_group("dialog", actions)

        self.select_range(self.first_unread, self.first_unread + 4)

    @staticmethod
    def show_toast(message):
        Gio.Application.get_default().activate_action("show_toast", GLib.Variant("s", message))

    @staticmethod
    async def start(model, parent):
        suwayomi = Gio.Application.get_default().suwayomi
        await suwayomi.getChapters(model.id)
        if model.chapters.get_n_items() == 0:
            DownloadDialog.show_toast(_("No chapters to download"))
            return
        DownloadDialog(model).present(parent)

    # --- logic -------------------------------------------------------------

    def select_range(self, start, end):
        last = len(self.chapters) - 1
        end = max(0, min(end, last))
        start = max(0, min(start, end))
        # "to" first so the from/to clamping in the setters never fights us
        self.to_index = end
        self.from_index = start

    def get_pending(self):
        selected = self.chapters[self._from_index:self._to_index + 1]
        return [
            c for c in selected
            if not c.is_downloaded and not (self._skip_read and c.is_read)
        ]

    def refresh(self):
        if not self.chapters:
            return
        count = len(self.get_pending())
        if count:
            text = ngettext("{} chapter will be downloaded", "{} chapters will be downloaded", count)
            self.summary = text.format(count)
        else:
            self.summary = _("Nothing to download")
        self.can_download = count > 0

    async def submit(self):
        chapters = self.get_pending()
        if not chapters:
            self.show_toast(_("Nothing to download"))
            return

        suwayomi = Gio.Application.get_default().suwayomi
        for chapter in chapters:
            await suwayomi.enqueueChapterDownload(chapter.id)

        count = len(chapters)
        message = ngettext("Downloading {} chapter", "Downloading {} chapters", count)
        self.show_toast(message.format(count))

    # --- actions -----------------------------------------------------------

    def on_preset(self, action, param):
        count = param.get_int32()
        if count < 0:                      # All
            self.select_range(0, len(self.chapters) - 1)
        elif count == 0:                   # Unread
            self.select_range(self.first_unread, len(self.chapters) - 1)
        else:                              # Next N
            self.select_range(self.first_unread, self.first_unread + count - 1)

    def on_download(self, action, param):
        self.close()
        asyncio.create_task(self.submit())
