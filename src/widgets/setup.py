from gi.repository import Gtk, Adw, Gio

@Gtk.Template(resource_path='/com/rini/kaghez/setup.ui')
class SetupWindow(Adw.ApplicationWindow):
    __gtype_name__ = 'KaghezSetupWindow'

    url_row = Gtk.Template.Child()
    connect_button = Gtk.Template.Child()

    def __init__(self, on_complete=None, **kwargs):
        super().__init__(**kwargs)
        self.on_complete = on_complete

    @Gtk.Template.Callback()
    def on_url_changed(self, *_):
        self.connect_button.set_sensitive(bool(self.url_row.get_text().strip()))

    @Gtk.Template.Callback()
    def on_connect_clicked(self, *_):
        url = self.url_row.get_text().strip().rstrip('/')
        if not url:
            return
        if not url.startswith(('http://', 'https://')):
            url = f"http://{url}"

        app = Gio.Application.get_default()
        app.settings.set_string('suwayomi-url', url)

        if self.on_complete:
            self.on_complete(url)

        self.close()
