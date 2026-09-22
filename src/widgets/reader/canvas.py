import asyncio
import bisect
import math

from gi.repository import Gtk, Adw, Gio, Gsk, Graphene, GObject

DEFAULT_RATIO = 0.68
ZOOM_MIN = 0.5
ZOOM_MAX = 4.0
PRELOAD = 0.5
POOL_MAX = 6

class Panel(Gtk.Stack):
    """One page: its picture, a spinner until it loads, or a chapter banner."""

    __gtype_name__ = "KaghezPanel"

    def __init__(self):
        super().__init__()
        self.page = None
        self.picture = Gtk.Picture(content_fit=Gtk.ContentFit.FILL)
        spinner = Adw.Spinner(
            halign=Gtk.Align.CENTER,
            valign=Gtk.Align.CENTER,
            width_request=48,
            height_request=48,
        )

        self.banner_title = Gtk.Label(css_classes=["title-1"])
        banner = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=6,
            halign=Gtk.Align.CENTER,
            valign=Gtk.Align.CENTER,
        )
        banner.append(self.banner_title)

        self.add_named(self.picture, "picture")
        self.add_named(spinner, "spinner")
        self.add_named(banner, "banner")
        self.set_paintable(None)

    def set_paintable(self, paintable):
        self.picture.set_paintable(paintable)
        self.set_visible_child_name("picture" if paintable else "spinner")

    def set_banner(self, chapter):
        self.banner_title.set_label(chapter.name)
        self.set_visible_child_name("banner")

class Canvas(Gtk.Widget, Gtk.Scrollable):
    __gtype_name__ = "KaghezCanvas"

    orientation = GObject.Property(type=Gtk.Orientation, default=Gtk.Orientation.VERTICAL)

    @GObject.Signal(arg_types=(int,))
    def page_changed(self, index):
        pass

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.suwayomi = Gio.Application.get_default().suwayomi
        self.store = None

        self.ratios = []
        self.starts = []   # where each page starts along the scroll axis
        self.sizes = []    # how long each page is along the scroll axis
        self.extent = 0.0  # the whole strip along the scroll axis
        self.cross = 0     # viewport size across the scroll axis, pages are fit to it

        self.zoom = 1.0
        self.zoom_start = 1.0
        self.zoom_center_x = 0.0
        self.zoom_center_y = 0.0

        self.hadj = None
        self.hadj_handler = None
        self.vadj = None
        self.vadj_handler = None
        self.hpolicy = Gtk.ScrollablePolicy.NATURAL
        self.vpolicy = Gtk.ScrollablePolicy.NATURAL

        self.realized = {}  # index -> panel
        self.tasks = {}     # index -> image load
        self.pool = []
        self.current_index = -1
        self.pending_index = None

        zoom_gesture = Gtk.GestureZoom()
        zoom_gesture.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        zoom_gesture.connect("begin", self.on_zoom_begin)
        zoom_gesture.connect("scale-changed", self.on_zoom_scale_changed)
        self.add_controller(zoom_gesture)

        double_tap = Gtk.GestureClick()
        double_tap.set_button(0)
        double_tap.connect("pressed", self.on_double_tap)
        self.add_controller(double_tap)

        self.connect("notify::orientation", self.on_orientation_changed)

    def do_dispose(self):
        for task in self.tasks.values():
            task.cancel()
        while child := self.get_first_child():
            child.unparent()
        super().do_dispose()


    @GObject.Property(type=Gtk.TextDirection, default=Gtk.TextDirection.LTR)
    def direction(self):
        return self.get_direction()

    @direction.setter
    def direction(self, value):
        left = self.scroll_value(self.hadj) if self.hadj else 0
        self.set_direction(value)
        if self.hadj:
            self.set_scroll_value(self.hadj, left)
        self.queue_allocate()

    @property
    def vertical(self):
        return self.orientation == Gtk.Orientation.VERTICAL

    @property
    def mirrored(self):
        return not self.vertical and self.get_direction() == Gtk.TextDirection.RTL


    @property
    def main_adjustment(self):
        return self.vadj if self.vertical else self.hadj

    @property
    def content_width(self):
        return self.cross if self.vertical else self.extent

    @property
    def content_height(self):
        return self.extent if self.vertical else self.cross

    def scroll_value(self, adjustment):
        value = adjustment.get_value()
        if adjustment is self.hadj and self.mirrored:
            return adjustment.get_upper() - adjustment.get_page_size() - value
        return value

    def set_scroll_value(self, adjustment, value):
        if adjustment is self.hadj and self.mirrored:
            value = adjustment.get_upper() - adjustment.get_page_size() - value
        adjustment.set_value(value)


    def bind_store(self, store: Gio.ListStore):
        self.store = store
        store.connect("items-changed", self.on_items_changed)

    def on_items_changed(self, store, position, removed, added):
        for index in list(self.realized):
            self.unrealize_panel(index)
        self.ratios = [DEFAULT_RATIO] * store.get_n_items()
        self.current_index = -1
        self.relayout()
        self.configure_adjustments()
        self.set_scroll_value(self.hadj, 0)
        self.set_scroll_value(self.vadj, 0)
        self.queue_allocate()

    def scroll_to_index(self, index: int):
        if self.cross == 0:
            self.pending_index = index
            return
        self.pending_index = None
        if 0 <= index < len(self.starts):
            self.set_scroll_value(self.main_adjustment, self.starts[index] * self.zoom)

    def on_orientation_changed(self, *_):
        if self.cross == 0:  # nothing is laid out yet
            return
        self.pending_index = self.current_index
        self.cross = 0
        self.set_scroll_value(self.hadj, 0)
        self.set_scroll_value(self.vadj, 0)
        self.queue_allocate()


    def relayout(self):
        self.starts = []
        self.sizes = []
        position = 0.0
        for ratio in self.ratios:
            size = self.cross / ratio if self.vertical else self.cross * ratio
            self.starts.append(position)
            self.sizes.append(size)
            position += size
        self.extent = position

    def set_ratio(self, index, ratio):
        if abs(ratio - self.ratios[index]) < 0.001:
            return

        start = self.starts[index]
        old_size = self.sizes[index]
        self.ratios[index] = ratio
        self.relayout()
        self.configure_adjustments()

        adjustment = self.main_adjustment
        value = self.scroll_value(adjustment)
        if start + old_size <= value / self.zoom:
            change = (self.sizes[index] - old_size) * self.zoom
            self.set_scroll_value(adjustment, value + change)

        self.queue_allocate()

    def visible_range(self):
        if not self.starts:
            return 0, -1
        adjustment = self.main_adjustment
        top = self.scroll_value(adjustment) / self.zoom
        size = adjustment.get_page_size() / self.zoom
        low = top - size * PRELOAD
        high = top + size * (1 + PRELOAD)
        first = max(0, bisect.bisect_right(self.starts, low) - 1)
        last = min(len(self.starts) - 1, bisect.bisect_left(self.starts, high))
        return first, last

    def update_current_index(self):
        if not self.starts:
            return
        adjustment = self.main_adjustment
        middle = (self.scroll_value(adjustment) + adjustment.get_page_size() / 2) / self.zoom
        index = max(0, bisect.bisect_right(self.starts, middle) - 1)
        if index != self.current_index:
            self.current_index = index
            self.emit("page-changed", index)


    def update_realized(self):
        first, last = self.visible_range()
        wanted = set(range(first, last + 1))

        for index in list(self.realized):
            if index not in wanted:
                self.unrealize_panel(index)
        for index in sorted(wanted):
            if index not in self.realized:
                self.realize_panel(index)

    def realize_panel(self, index):
        if self.pool:
            panel = self.pool.pop()
            panel.set_visible(True)
        else:
            panel = Panel()
            panel.set_parent(self)

        page = self.store.get_item(index)
        panel.page = page
        self.realized[index] = panel

        if getattr(page, "chapter", None) is not None:
            panel.set_banner(page.chapter)
        elif page.paintable is not None:
            self.show_paintable(index, page.paintable)
        else:
            panel.set_paintable(None)
            if page.url:
                self.tasks[index] = asyncio.create_task(self.load_page(index, page))

    def unrealize_panel(self, index):
        panel = self.realized.pop(index)
        if task := self.tasks.pop(index, None):
            task.cancel()

        panel.page.paintable = None
        panel.page = None
        panel.set_paintable(None)

        panel.set_visible(False)
        if len(self.pool) < POOL_MAX:
            self.pool.append(panel)
        else:
            panel.unparent()

    async def load_page(self, index, page):
        try:
            paintable = await self.suwayomi.getPaintable(page.url)
        except asyncio.CancelledError:
            raise
        except Exception:
            return
        if paintable:
            page.paintable = paintable
            self.show_paintable(index, paintable)

    def show_paintable(self, index, paintable):
        self.realized[index].set_paintable(paintable)
        self.set_ratio(index, paintable.get_intrinsic_aspect_ratio() or DEFAULT_RATIO)

    def place_panels(self, width, height):
        left = self.scroll_value(self.hadj) / self.zoom
        top = self.scroll_value(self.vadj) / self.zoom

        offset_x = self.centering_offset(self.content_width, self.zoom, width)
        offset_y = self.centering_offset(self.content_height, self.zoom, height)

        for index, panel in self.realized.items():
            x = offset_x - left
            y = offset_y - top
            if self.vertical:
                y += self.starts[index]
                panel_width, panel_height = self.cross, self.sizes[index]
            else:
                x += self.starts[index]
                panel_width, panel_height = self.sizes[index], self.cross
            if self.mirrored:
                x = width / self.zoom - x - panel_width

            transform = Gsk.Transform.new().translate(Graphene.Point().init(x, y))
            panel.allocate(math.ceil(panel_width), math.ceil(panel_height), -1, transform)


    def centering_offset(self, content_size, zoom, viewport_size):
        return max(0.0, (viewport_size / zoom - content_size) / 2)

    def anchored_scroll(self, adjustment, content_size, viewport_size, anchor, old_zoom, new_zoom):
        old_offset = self.centering_offset(content_size, old_zoom, viewport_size)
        new_offset = self.centering_offset(content_size, new_zoom, viewport_size)
        point = (self.scroll_value(adjustment) - old_offset * old_zoom + anchor) / old_zoom
        return point * new_zoom + new_offset * new_zoom - anchor

    def set_zoom_anchored(self, new_zoom, anchor_x, anchor_y):
        old_zoom = self.zoom
        new_zoom = max(ZOOM_MIN, min(ZOOM_MAX, new_zoom))
        if abs(new_zoom - old_zoom) < 1e-6:
            return

        if self.mirrored:
            anchor_x = self.get_width() - anchor_x

        left = self.anchored_scroll(
            self.hadj, self.content_width, self.get_width(), anchor_x, old_zoom, new_zoom
        )
        top = self.anchored_scroll(
            self.vadj, self.content_height, self.get_height(), anchor_y, old_zoom, new_zoom
        )

        self.zoom = new_zoom
        self.configure_adjustments()
        self.set_scroll_value(self.hadj, left)
        self.set_scroll_value(self.vadj, top)
        self.queue_allocate()

    def on_zoom_begin(self, gesture, sequence):
        gesture.set_state(Gtk.EventSequenceState.CLAIMED)
        self.zoom_start = self.zoom
        ok, x, y = gesture.get_bounding_box_center()
        if ok:
            self.zoom_center_x = x
            self.zoom_center_y = y

    def on_zoom_scale_changed(self, gesture, scale):
        self.set_zoom_anchored(self.zoom_start * scale, self.zoom_center_x, self.zoom_center_y)

    def on_double_tap(self, gesture, n_press, x, y):
        if n_press == 2:
            self.set_zoom_anchored(1.0, x, y)


    def scroll_fractions(self):
        return (
            self.fraction(self.hadj, self.content_width),
            self.fraction(self.vadj, self.content_height),
        )

    def fraction(self, adjustment, content_size):
        if content_size <= 0:
            return 0.0
        return self.scroll_value(adjustment) / self.zoom / content_size

    def restore_scroll_fractions(self, fractions):
        fraction_x, fraction_y = fractions
        self.configure_adjustments()
        self.set_scroll_value(self.hadj, fraction_x * self.content_width * self.zoom)
        self.set_scroll_value(self.vadj, fraction_y * self.content_height * self.zoom)

    def on_scrolled(self, *_):
        self.queue_allocate()


    def do_measure(self, orientation, for_size):
        return 0, 0, -1, -1

    def do_snapshot(self, snapshot):
        snapshot.scale(self.zoom, self.zoom)
        for panel in self.realized.values():
            self.snapshot_child(panel, snapshot)

    def do_size_allocate(self, width, height, baseline):
        cross = width if self.vertical else height
        if cross != self.cross:
            fractions = self.scroll_fractions()
            self.cross = cross
            self.relayout()
            self.restore_scroll_fractions(fractions)
        self.configure_adjustments()

        if self.pending_index is not None:
            self.scroll_to_index(self.pending_index)

        self.update_current_index()
        self.update_realized()
        self.place_panels(width, height)


    @GObject.Property(type=Gtk.Adjustment, default=None)
    def hadjustment(self):
        return self.hadj

    @hadjustment.setter
    def hadjustment(self, adjustment):
        if self.hadj_handler is not None:
            self.hadj.disconnect(self.hadj_handler)
            self.hadj_handler = None
        self.hadj = adjustment
        if adjustment is not None:
            self.hadj_handler = adjustment.connect("value-changed", self.on_scrolled)
        self.configure_adjustments()

    @GObject.Property(type=Gtk.Adjustment, default=None)
    def vadjustment(self):
        return self.vadj

    @vadjustment.setter
    def vadjustment(self, adjustment):
        if self.vadj_handler is not None:
            self.vadj.disconnect(self.vadj_handler)
            self.vadj_handler = None
        self.vadj = adjustment
        if adjustment is not None:
            self.vadj_handler = adjustment.connect("value-changed", self.on_scrolled)
        self.configure_adjustments()

    @GObject.Property(type=Gtk.ScrollablePolicy, default=Gtk.ScrollablePolicy.NATURAL)
    def hscroll_policy(self):
        return self.hpolicy

    @hscroll_policy.setter
    def hscroll_policy(self, value):
        self.hpolicy = value

    @GObject.Property(type=Gtk.ScrollablePolicy, default=Gtk.ScrollablePolicy.NATURAL)
    def vscroll_policy(self):
        return self.vpolicy

    @vscroll_policy.setter
    def vscroll_policy(self, value):
        self.vpolicy = value

    def configure_adjustments(self):
        self.configure_adjustment(self.hadj, self.content_width, self.get_width(), self.mirrored)
        self.configure_adjustment(self.vadj, self.content_height, self.get_height(), False)

    def configure_adjustment(self, adjustment, content_size, viewport_size, flipped):
        if adjustment is None:
            return
        upper = max(content_size * self.zoom, viewport_size)
        if (
            abs(adjustment.get_upper() - upper) < 0.01
            and abs(adjustment.get_page_size() - viewport_size) < 0.01
        ):
            return
        value = adjustment.get_value()
        if flipped:
            old_end = adjustment.get_upper() - adjustment.get_page_size()
            value = upper - viewport_size - (old_end - value)
        adjustment.configure(value, 0.0, upper, 40.0, viewport_size * 0.9, viewport_size)
