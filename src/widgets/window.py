from gi.repository import Gtk, Adw, Gio, GLib, Gdk, Pango, GObject

import asyncio

from .. import actions

from .download import DownloadsPage
from .updates import UpdatesPage
from .history import HistoryPage
from .search import SearchPage
from .library import LibraryPage, CategoryPanel

from .chapter import ChapterPanel
from .manga import MangaPage
from .reader import ReaderPage

from ..constants import NAME

SWIPE_COMMIT_DISTANCE = 40.0
SWIPE_COMMIT_VELOCITY = 600.0

NO_READER = (-1, -1)


def find_title_label(widget):
    child = widget.get_first_child()
    while child is not None:
        if isinstance(child, Gtk.Label) and child.has_css_class("title"):
            return child
        found = find_title_label(child)
        if found is not None:
            return found
        child = child.get_next_sibling()
    return None


@Gtk.Template(resource_path='/io/github/riyaniii/Kaori/window.ui')
class KaoriWindow(Adw.ApplicationWindow):
    __gtype_name__ = 'KaoriWindow'

    name = GObject.Property(type=str)
    downloads = GObject.Property(type=Gio.ListStore)
    downloading = GObject.Property(type=bool, default=False)

    main_stack = Gtk.Template.Child()
    category_split_view = Gtk.Template.Child()
    category_panel = Gtk.Template.Child()
    overlay_split_view = Gtk.Template.Child()
    main_nav_view = Gtk.Template.Child()
    toast_overlay = Gtk.Template.Child()

    header_bar = Gtk.Template.Child()
    chapter_panel = Gtk.Template.Child()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        app = Gio.Application.get_default()
        suwayomi = app.suwayomi
        self.settings = app.settings
        self.name = NAME
        self.downloads = suwayomi.download_queue
        suwayomi.bind_property(
            'downloader-state', self, 'downloading',
            GObject.BindingFlags.SYNC_CREATE,
            lambda binding, state: state == 'STARTED')

        title_label = find_title_label(self.header_bar)
        if title_label is not None:
            title_label.set_ellipsize(Pango.EllipsizeMode.NONE)

        self.create_action(actions.show_manga, parameter_type="i")
        self.create_action(actions.show_reader, parameter_type="(ii)")
        self.create_action(actions.set_chapters, parameter_type="i")

        self.create_action(actions.toggle_chapter_panel, ['<control>s'], parameter_type=None)

        self.create_action(actions.show_source)
        self.create_action(actions.show_extension)
        self.create_action(actions.switch_page)
        self.create_action(actions.show_toast)

        self.create_action(actions.open_search_page, ['<control>f', '<control>k'], parameter_type=None)
        self.create_action(actions.open_downloads_page, ['<control>j'], parameter_type=None)
        self.create_action(actions.open_library_page, ['<control>l'], parameter_type=None)
        self.create_action(actions.edit_categories, parameter_type="i")
        self.create_action(actions.manage_categories, parameter_type=None)
        self.add_action(Gio.PropertyAction.new(
            "show-categories", self.category_split_view, "show-sidebar"))
        self.category_panel.connect(
            "activated", lambda *_: self.category_split_view.set_show_sidebar(False))

        scroll_controller = Gtk.EventControllerScroll(
            flags=Gtk.EventControllerScrollFlags.HORIZONTAL
        )
        scroll_controller.connect("scroll-begin", self.on_swipe_begin)
        scroll_controller.connect("scroll", self.on_swipe_scroll)
        scroll_controller.connect("scroll-end", self.on_swipe_scroll_end)
        self.overlay_split_view.add_controller(scroll_controller)
        self.swipe_accum = 0.0
        self.swipe_start_time = 0.0

        self.main_stack.set_visible_child_name(self.settings.get_string('startup-page'))

        self.main_nav_view.connect("popped", self.on_nav_popped)
        if self.settings.get_boolean('resume-last-chapter'):
            task = asyncio.create_task(self.restore_last_chapter())
            task.add_done_callback(
                lambda t: t.exception() and print("Restoring last chapter failed:", t.exception())
            )

    def create_action(self, callback: callable, shortcuts: list | None = None, parameter_type: str = "s"):
        shortcuts = shortcuts or []
        def call_action(action, variant):
            app = self.get_application()
            if variant is None:
                result = callback(app)
            else:
                value = variant.unpack()
                if callback is actions.show_reader:
                    self.remember_reader(value)
                result = callback(app, *value) if isinstance(value, tuple) else callback(app, value)
            if asyncio.iscoroutine(result):
                task = asyncio.create_task(result)
                task.add_done_callback(
                    lambda t: t.exception() and print(f"Action '{callback.__name__}' failed:", t.exception())
                )
        self.get_application().create_action(
            name=callback.__name__,
            callback=call_action,
            shortcuts=shortcuts,
            parameter_type=GLib.VariantType.new(parameter_type) if parameter_type else None
        )


    def remember_reader(self, args):
        self.settings.set_value('last-reader', GLib.Variant('(ii)', tuple(args)))

    def on_nav_popped(self, nav_view, page):
        if isinstance(page, ReaderPage) and not isinstance(nav_view.get_visible_page(), ReaderPage):
            self.remember_reader(NO_READER)

    async def restore_last_chapter(self):
        manga_id, chapter_id = self.settings.get_value('last-reader').unpack()
        if (manga_id, chapter_id) == NO_READER:
            return

        app = self.get_application()
        suwayomi = app.suwayomi

        def cached(model_id, kind):
            try:
                return suwayomi.getModel(model_id, kind)
            except Exception:
                return None

        if cached(chapter_id, 'Chapter') is None:
            for _ in range(20):
                if cached(manga_id, 'Manga') is not None:
                    break
                await asyncio.sleep(0.5)
            else:
                print(f"[kaori] resume: manga {manga_id} never became available")
                return

            app.activate_action('show_manga', GLib.Variant('i', manga_id))

            for _ in range(40):
                if cached(chapter_id, 'Chapter') is not None:
                    break
                await asyncio.sleep(0.25)
            else:
                print(f"[kaori] resume: chapter {chapter_id} never became available")
                return

        app.activate_action('show_reader', GLib.Variant('(ii)', (manga_id, chapter_id)))


    def on_swipe_begin(self, controller):
        self.swipe_accum = 0.0
        self.swipe_start_time = GLib.get_monotonic_time() / 1_000_000

    def on_swipe_scroll(self, controller, dx, dy):
        self.swipe_accum += dx

        if self.overlay_split_view.get_show_sidebar():
            return Gdk.EVENT_STOP

        return Gdk.EVENT_PROPAGATE

    def on_swipe_scroll_end(self, controller):
        now = GLib.get_monotonic_time() / 1_000_000
        elapsed = max(now - self.swipe_start_time, 1e-3)
        velocity = self.swipe_accum / elapsed

        far_enough = abs(self.swipe_accum) > SWIPE_COMMIT_DISTANCE
        fast_enough = abs(velocity) > SWIPE_COMMIT_VELOCITY

        if far_enough or fast_enough:
            opening = self.swipe_accum > 0 if far_enough else velocity > 0

            current_page = self.main_stack.get_visible_child().get_visible_page()
            maybe_reader = self.main_nav_view.get_visible_page()

            if isinstance(current_page, MangaPage) and not isinstance(maybe_reader, ReaderPage):
                self.overlay_split_view.set_show_sidebar(opening)
            else:
                return

        self.swipe_accum = 0.0
