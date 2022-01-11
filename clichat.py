import datetime
import sys
import logging
import websockets
import asyncio
import json
import threading

import urwid
from urwid import MetaSignals

url = "ws://1f76-103-221-73-190.ngrok.io/ws"

user_name = input("Name: ")


def log(message):
    # log messages in logg.txt
    # with open("logg.txt", "a") as logg:
    #     logg.write(message)
    #     logg.write("\n")
    return


class ExtendedListBox(urwid.ListBox):
    """
    Listbow widget with embeded autoscroll
    """

    __metaclass__ = urwid.MetaSignals
    signals = ["set_auto_scroll"]

    def set_auto_scroll(self, switch):
        if type(switch) != bool:
            return
        self._auto_scroll = switch
        urwid.emit_signal(self, "set_auto_scroll", switch)

    auto_scroll = property(lambda s: s._auto_scroll, set_auto_scroll)

    def __init__(self, body):
        urwid.ListBox.__init__(self, body)
        self.auto_scroll = True

    def switch_body(self, body):
        if self.body:
            urwid.disconnect_signal(body, "modified", self._invalidate)

        self.body = body
        self._invalidate()

        urwid.connect_signal(body, "modified", self._invalidate)

    def keypress(self, size, key):
        urwid.ListBox.keypress(self, size, key)

        if key in ("page up", "page down"):
            logging.debug(
                "focus = %d, len = %d" % (self.get_focus()[1], len(self.body))
            )
            if self.get_focus()[1] == len(self.body) - 1:
                self.auto_scroll = True
            else:
                self.auto_scroll = False
            logging.debug("auto_scroll = %s" % (self.auto_scroll))

    def scroll_to_bottom(self):
        logging.debug(
            "current_focus = %s, len(self.body) = %d"
            % (self.get_focus()[1], len(self.body))
        )

        if self.auto_scroll:
            # at bottom -> scroll down
            self.set_focus(len(self.body) - 1)


class MainWindow(object):

    __metaclass__ = MetaSignals
    signals = ["quit", "keypress"]

    _palette = [
        ("divider", "black", "dark cyan", "standout"),
        ("text", "light gray", "default"),
        ("bold_text", "light gray", "default", "bold"),
        ("body", "text"),
        ("footer", "text"),
        ("header", "text"),
    ]

    for type, bg in (("div_fg_", "dark cyan"), ("", "default")):
        for name, color in (
            ("red", "dark red"),
            ("blue", "dark blue"),
            ("green", "dark green"),
            ("yellow", "yellow"),
            ("magenta", "dark magenta"),
            ("gray", "light gray"),
            ("white", "white"),
            ("black", "black"),
        ):
            _palette.append((type + name, color, bg))

    def __init__(self, sender="1234567890"):
        self.shall_quit = False
        self.sender = sender

    def main(self):
        """
        Entry point to start UI
        """

        self.ui = urwid.raw_display.Screen()
        self.ui.register_palette(self._palette)
        self.build_interface()
        self.ui.run_wrapper(self.run)

    def run(self):
        """
        Setup input handler, invalidate handler to
        automatically redraw the interface if needed.
        Start mainloop.
        """

        # I don't know what the callbacks are for yet,
        # it's a code taken from the nigiri project
        def input_cb(key):
            if self.shall_quit:
                raise urwid.ExitMainLoop
            self.keypress(self.size, key)

        self.size = self.ui.get_cols_rows()

        self.main_loop = urwid.MainLoop(
            self.context,
            screen=self.ui,
            handle_mouse=False,
            unhandled_input=input_cb,
        )

        def call_redraw(*x):
            self.draw_interface()
            invalidate.locked = False
            return True

        inv = urwid.canvas.CanvasCache.invalidate

        def invalidate(cls, *a, **k):
            inv(*a, **k)

            if not invalidate.locked:
                invalidate.locked = True
                self.main_loop.set_alarm_in(0, call_redraw)

        invalidate.locked = False
        urwid.canvas.CanvasCache.invalidate = classmethod(invalidate)

        try:
            self.main_loop.run()
        except KeyboardInterrupt:
            self.quit()

    def quit(self, exit=True):
        """
        Stops the ui, exits the application (if exit=True)
        """
        urwid.emit_signal(self, "quit")

        self.shall_quit = True

        if exit:
            sys.exit(0)

    def build_interface(self):
        """
        Call the widget methods to build the UI
        """

        self.header = urwid.Text("Chat")
        self.footer = urwid.Edit("> ")
        self.divider = urwid.Text("Initializing.")

        self.generic_output_walker = urwid.SimpleListWalker([])
        self.body = ExtendedListBox(self.generic_output_walker)

        self.header = urwid.AttrWrap(self.header, "divider")
        self.footer = urwid.AttrWrap(self.footer, "footer")
        self.divider = urwid.AttrWrap(self.divider, "divider")
        self.body = urwid.AttrWrap(self.body, "body")

        self.footer.set_wrap_mode("space")

        main_frame = urwid.Frame(self.body, header=self.header, footer=self.divider)

        self.context = urwid.Frame(main_frame, footer=self.footer)

        self.divider.set_text(("divider", ("Send message:")))

        self.context.set_focus("footer")

    def draw_interface(self):
        self.main_loop.draw_screen()

    def keypress(self, size, key):
        """
        Handle user inputs
        """

        urwid.emit_signal(self, "keypress", size, key)
        log("before")

        # scroll the top panel
        if key in ("page up", "page down"):
            self.body.keypress(size, key)

        # resize the main windows
        elif key == "window resize":
            self.size = self.ui.get_cols_rows()

        elif key in ("ctrl d", "ctrl c"):
            self.quit()

        elif key == "enter":
            # Parse data or (if parse failed)
            # send it to the current world
            text = self.footer.get_edit_text()

            self.footer.set_edit_text(" " * len(text))
            self.footer.set_edit_text("")

            if text in ("quit", "q"):
                self.quit()

            if text.strip():
                self.sync_print_sent_message(text)
                # receive_thread = threading.Thread(
                #     target=self.sync_print_sent_message, args=(text,)
                # )  # receiving multiple messages
                # receive_thread.start()
                # self.print_sent_message(text)
                # self.print_received_message("Answer")

        else:
            self.context.keypress(size, key)

    async def print_sent_message(self, text):
        """
        Print a received message
        """
        log("inside print_sent_message")
        async with websockets.connect(url, ping_interval=None) as ws:
            my_msg = {"code": "message", "name": user_name, "message": text}
            self.print_text("[%s] You:" % self.get_time())
            self.print_text(text)
            await ws.send(json.dumps(my_msg))

    def sync_print_sent_message(self, text):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(self.print_sent_message(text))
        loop.close()

    def print_received_message(self, name, message):
        """
        Print a sent message
        """
        log("inside print_received_message")
        header = urwid.Text("[%s] %s:" % (self.get_time(), name))
        header.set_align_mode("right")
        self.print_text(header)
        text = urwid.Text(message)
        text.set_align_mode("right")
        self.print_text(text)
        log("Over message")

    def print_text(self, text):
        """
        Print the given text in the _current_ window
        and scroll to the bottom.
        You can pass a Text object or a string
        """

        walker = self.generic_output_walker

        if not isinstance(text, urwid.Text):
            text = urwid.Text(text)

        walker.append(text)

        self.body.scroll_to_bottom()

    def get_time(self):
        """
        Return formated current datetime
        """
        return datetime.datetime.now().strftime("%H:%M:%S")

    async def listen(self):
        async with websockets.connect(url, ping_interval=None) as ws:
            while True:
                msg = await ws.recv()
                msg = json.loads(msg)
                log(str(msg))
                name = msg["name"]
                if name != user_name:
                    message = msg["message"]
                    # do this asychronously
                    self.print_received_message(name, message)

    def sync_listen(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(self.listen())
        loop.run_forever()


def except_hook(extype, exobj, extb, manual=False):
    if not manual:
        try:
            main_window.quit(exit=False)
        except NameError:
            pass

    message = "an error pccured"

    logging.error(message)


if __name__ == "__main__":
    main_window = MainWindow()

    sys.excepthook = except_hook
    always_receive = threading.Thread(target=main_window.sync_listen)
    always_receive.daemon = True
    always_receive.start()

    main_window.main()
