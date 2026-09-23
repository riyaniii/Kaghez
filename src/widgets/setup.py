import asyncio
from gi.repository import Gtk, Adw, Gio

DEFAULT_DESCRIPTION = "Run Suwayomi locally or connect to an existing server"

@Gtk.Template(resource_path='/com/rini/kaghez/setup.ui')
class SetupWindow(Adw.ApplicationWindow):
    __gtype_name__ = 'KaghezSetupWindow'

    status_page = Gtk.Template.Child()
    local_row = Gtk.Template.Child()
    remote_row = Gtk.Template.Child()

    def __init__(self, error: str | None = None, **kwargs):
        super().__init__(**kwargs)
        self.app = Gio.Application.get_default()
        if error:
            self.status_page.set_description(error)

    @Gtk.Template.Callback()
    def on_local_activated(self, row):
        self.begin_connect("local", "")

    @Gtk.Template.Callback()
    def on_remote_activated(self, row):
        self.show_remote_dialog()

    def show_remote_dialog(self):
        url_row = Adw.EntryRow(title="Server URL", input_purpose=Gtk.InputPurpose.URL)
        url_row.set_text("http://localhost:4567")

        list_box = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE)
        list_box.add_css_class("boxed-list")
        list_box.append(url_row)

        connect_button = Gtk.Button(label="Continue", sensitive=False, halign=Gtk.Align.CENTER)
        connect_button.add_css_class("suggested-action")
        connect_button.add_css_class("pill")

        content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        content_box.set_margin_start(12)
        content_box.set_margin_end(12)
        content_box.set_margin_bottom(12)
        content_box.append(list_box)
        content_box.append(connect_button)

        clamp = Adw.Clamp(maximum_size=340)
        clamp.set_child(content_box)

        header_bar = Adw.HeaderBar()

        toolbar_view = Adw.ToolbarView()
        toolbar_view.add_top_bar(header_bar)
        toolbar_view.set_content(clamp)

        dialog = Adw.Dialog(title="Remote Server", content_width=360)
        dialog.set_child(toolbar_view)

        def update_sensitivity(*_):
            connect_button.set_sensitive(bool(url_row.get_text().strip()))

        def do_connect(*_):
            url = url_row.get_text().strip().rstrip('/')
            if not url:
                return
            if not url.startswith(('http://', 'https://')):
                url = f"http://{url}"
            dialog.close()
            self.begin_connect("remote", url)

        update_sensitivity()
        url_row.connect("changed", update_sensitivity)
        url_row.connect("entry-activated", do_connect)
        connect_button.connect("clicked", do_connect)

        dialog.present(self)

    def begin_connect(self, mode: str, url: str):
        # Nothing is shown while we try to connect; no window means no
        # chance of the rest of the app touching the API prematurely.
        self.set_visible(False)
        asyncio.create_task(self.try_connect(mode, url))

    async def try_connect(self, mode: str, url: str):
        success = await self.app.launch(mode, url)
        if success:
            self.close()
        else:
            self.set_visible(True)
            self.status_page.set_description(
                "Couldn't connect. Check the address and try again."
                if mode == "remote" else
                "Couldn't start the local server. Check the logs and try again."
            )
