import asyncio

from gi.repository import Gtk, Pango, GLib, GObject, Gio

from ...integrations import models

@Gtk.Template(resource_path='/com/rini/kaghez/manga/overview.ui')
class MangaOverview(Gtk.Box):
    __gtype_name__ = "KaghezMangaOverview"

    model = GObject.Property(type=models.Manga)

    genres = Gtk.Template.Child()

    def __init__(self, model):
        super().__init__()
        self.model = model
        self.populate_genres()

        if self.model.paintable is None and self.model.thumbnail_url:
            self.suwayomi = Gio.Application.get_default().suwayomi
            asyncio.create_task(self.load_thumbnail())

    async def load_thumbnail(self):
        paintable = await self.suwayomi.getPaintable(self.model.thumbnail_url)
        if paintable:
            self.model.paintable = paintable

    def populate_genres(self):
        for genre in self.model.genre[:6]:
            button = Gtk.Button(
                child=Gtk.Label(
                    label=genre,
                    ellipsize=Pango.EllipsizeMode.END
                )
            )
            self.genres.append(button)

    @Gtk.Template.Callback()
    def get_shortened_description(self, obj, description):
        first_paragraph = description.strip().split("\n\n")[0].split("\n")[0].strip()
        l = 600
        if len(first_paragraph) <= l:
            return first_paragraph
        return first_paragraph[:l].rstrip() + "…"

    @Gtk.Template.Callback()
    def on_overview_clicked(self, *_args):
        manga_id = self.model.id
        self.activate_action("app.show_manga", GLib.Variant("i", manga_id))
        self.activate_action("app.set_chapters", GLib.Variant("i", manga_id))
