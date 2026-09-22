from gi.repository import GObject, Gio, Gdk

from . import models


class BasicList(Gio.ListStore):
    __gtype_name__ = 'KaghezBasicList'

    def __init__(self, item_type, batch_size=10):
        super().__init__(item_type)
        self.batch_size = batch_size

    def fetch(self):
        """
        Fetches self.batch_size number of new items
        """
        pass

    def update(self):
        """
        Updates the fetched items, so that the UI updates with changes to the server
        """
        pass

class ExtensionList(BasicList):
    def __init__(self):
        super.__init__(item_type = models.Extension, batch_size=10)

    def fetch(self):
        
