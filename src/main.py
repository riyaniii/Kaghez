import sys
import gi
import asyncio

from gettext import gettext as _

gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.events import GLibEventLoopPolicy
asyncio.set_event_loop_policy(GLibEventLoopPolicy())

from gi.repository import Gtk, Gio, Adw, GObject
from .widgets import KaghezWindow, build_shortcuts
from .widgets.preferences import KaghezPreferences
from .widgets.setup import SetupWindow

from .integrations import Suwayomi

class KaghezApplication(Adw.Application):
    """The main application singleton class."""

    settings = GObject.Property(type=Gio.Settings, default=Gio.Settings(schema_id="com.rini.kaghez"))
    suwayomi = GObject.Property(type=Suwayomi, default=Suwayomi())

    def __init__(self):
        super().__init__(application_id='com.rini.kaghez.Devel',
                         flags=Gio.ApplicationFlags.DEFAULT_FLAGS,
                         resource_base_path='/com/rini/kaghez')
        self.create_action('quit', lambda *_: self.quit(), ['<control>q'])
        self.create_action('preferences', self.on_preferences_action, ['<control>comma'])
        self.create_action('shortcuts', self.on_shortcuts_action, ['<control>question', '<control>slash'])
        self.create_action('about', self.on_about_action)


    def do_activate(self):
        """Called when the application is activated.

        We raise the application's main window, creating it if
        necessary.
        """
        win = self.props.active_window
        if not win:
            url = self.settings.get_string('suwayomi-url')
            if not url:
                self.show_setup_window()
                return
            self.suwayomi.reconnect(url)
            win = KaghezWindow(application=self)
        win.present()

    def show_setup_window(self):
        window = SetupWindow(application=self, on_complete=self.on_setup_complete)
        window.present()

    def on_setup_complete(self, url):
        self.suwayomi.reconnect(url)
        win = KaghezWindow(application=self)
        win.present()

    def do_shutdown(self):
        """Called right before the application exits."""
        self.suwayomi.cache.close()
        Adw.Application.do_shutdown(self)

    def on_about_action(self, *args):
        """Callback for the app.about action."""
        about = Adw.AboutDialog(application_name='Kaghez',
                                application_icon='com.rini.kaghez',
                                developer_name='Riyan Parvez',
                                version='0.8.7',
                                translator_credits = _('translator-credits'),
                                developers=['Riyan Parvez (rini)'],
                                copyright='© 2026 Riyan Parvez')
        about.present(self.props.active_window)

    def on_preferences_action(self, widget, _):
        preferences = KaghezPreferences()
        preferences.present(self.props.active_window)

    def on_shortcuts_action(self, widget, _):
        shortcuts = build_shortcuts()
        shortcuts.present(self.props.active_window)

    def create_action(self, name, callback, shortcuts=None, parameter_type=None):
        """Add an application action.
        Args:
            name: the name of the action
            callback: the function to be called when the action is
              activated
            shortcuts: an optional list of accelerators
            parameter_type: an optional GLib.VariantType for the action's parameter
        """
        action = Gio.SimpleAction.new(name, parameter_type)
        action.connect("activate", callback)
        self.add_action(action)
        if shortcuts:
            self.set_accels_for_action(f"app.{name}", shortcuts)

def main(version):
    """The application's entry point."""
    app = KaghezApplication()
    return app.run(sys.argv)
