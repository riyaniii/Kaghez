import re
import asyncio
from gi.repository import Gtk, Adw, GObject, Gio, GLib

from ...integrations import models


def markdown_to_pango(md: str) -> str:
    if md is None:
        return
    def inline(text: str) -> str:
        text = GLib.markup_escape_text(text or "")

        text = re.sub(
            r"`([^`]+)`",
            r'<tt>\1</tt>',
            text,
        )

        text = re.sub(
            r"\*\*(.+?)\*\*",
            r"<b>\1</b>",
            text,
        )

        text = re.sub(
            r"(?<!\*)\*(.+?)\*(?!\*)",
            r"<i>\1</i>",
            text,
        )

        text = re.sub(
            r"\[(.*?)\]\((.*?)\)",
            r'<a href="\2">\1</a>',
            text,
        )

        return text

    lines = md.splitlines()
    out = []

    for line in lines:
        stripped = line.strip()

        if not stripped:
            out.append("")
            continue

        m = re.match(r"^(#{1,6})\s+(.*)$", stripped)
        if m:
            level = len(m.group(1))
            size = {
                1: "xx-large",
                2: "x-large",
                3: "large",
                4: "medium",
                5: "small",
                6: "small",
            }[level]

            out.append(
                f'<span size="{size}" weight="bold">{inline(m.group(2))}</span>'
            )
            continue

        m = re.match(r"^[-*]\s+(.*)$", stripped)
        if m:
            out.append(f"• {inline(m.group(1))}")
            continue

        out.append(inline(line))

    return "\n".join(out)


@Gtk.Template(resource_path='/com/rini/kaghez/manga/page.ui')
class MangaPage(Adw.NavigationPage):
    __gtype_name__ = "KaghezMangaPage"

    model = GObject.Property(type=models.Manga)

    genres = Gtk.Template.Child()

    def __init__(self, model):
        super().__init__()
        self.model = model
        self.suwayomi = Gio.Application.get_default().suwayomi

    @Gtk.Template.Callback()
    def on_shown(self, *_):
        if self.model.initialized:
            asyncio.create_task(self.load_chapters())
        else:
            asyncio.create_task(self.load_manga())

    async def load_manga(self):
        await self.suwayomi.getManga(self.model.id)
        self.refresh_chapter_panel()

    async def load_chapters(self):
        await self.suwayomi.getChapters(self.model.id)
        self.refresh_chapter_panel()

    def refresh_chapter_panel(self):
        self.activate_action("app.set_chapters", GLib.Variant("i", self.model.id))

    @Gtk.Template.Callback()
    def populate_genres(self, obj, genre):
        while child := self.genres.get_first_child():
            self.genres.remove(child)
        for name in genre or []:
            self.genres.append(Gtk.Button(label=name))
        return bool(genre)

    @Gtk.Template.Callback()
    def get_read_button_label(self, obj, chapter):
        if chapter is None:
            return "..."
        if chapter.source_order > 1:
            return "Continue"
        return "Start"

    @Gtk.Template.Callback()
    def get_library_icon_name(self, obj, in_library):
        return "heart-filled-symbolic" if in_library else "heart-outline-thick-symbolic"

    @Gtk.Template.Callback()
    def get_library_button_tooltip(self, obj, in_library):
        return "Remove from library" if in_library else "Add to library"

    @Gtk.Template.Callback()
    def on_read_clicked(self, *_):
        if not self.model.last_read_chapter:
            return
        self.activate_action(
            "app.show_reader",
            GLib.Variant("(ii)", (self.model.id, self.model.last_read_chapter.id))
        )

    @Gtk.Template.Callback()
    def on_library_button_clicked(self, *_):
        self.activate_action("app.toggle_library", GLib.Variant("i", self.model.id))

    @Gtk.Template.Callback()
    def get_description(self, obj, description):
        return markdown_to_pango(description)
