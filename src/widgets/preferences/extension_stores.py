import asyncio
from gi.repository import Adw, Gio, Gtk


@Gtk.Template(resource_path='/com/rini/kaghez/preferences/extension_stores.ui')
class ExtensionStoresDialog(Adw.Dialog):
    __gtype_name__ = "KaghezExtensionStoresDialog"

    url_entry = Gtk.Template.Child()
    stores_group = Gtk.Template.Child()

    def __init__(self):
        super().__init__()
        self.suwayomi = Gio.Application.get_default().suwayomi
        self.rows = {}

        asyncio.create_task(self.load())

    async def load(self):
        for url in await self.suwayomi.getExtensionStores():
            self.add_row(url)

    def add_row(self, url):
        row = Adw.ActionRow(title=url, title_selectable=True)
        button = Gtk.Button(
            icon_name="user-trash-symbolic",
            valign=Gtk.Align.CENTER,
            css_classes=["flat"],
        )
        button.connect("clicked", self.on_remove_clicked, url)
        row.add_suffix(button)

        self.stores_group.add(row)
        self.rows[url] = row

    def save(self):
        asyncio.create_task(self.suwayomi.setExtensionStores(list(self.rows)))

    @Gtk.Template.Callback()
    def on_add(self, entry):
        url = entry.get_text().strip()
        if not url.startswith(("http://", "https://")) or url in self.rows:
            entry.add_css_class("error")
            return

        entry.remove_css_class("error")
        entry.set_text("")
        self.add_row(url)
        self.save()

    def on_remove_clicked(self, button, url):
        self.stores_group.remove(self.rows.pop(url))
        self.save()
