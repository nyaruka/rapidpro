import os
import sys
import termios
import threading
import time
import tty

import requests
from colorama import Fore, init as colorama_init
from requests.exceptions import ConnectionError

from django.core.management.base import BaseCommand, CommandError

from temba.contacts.models import URN
from temba.orgs.models import Org
from temba.tests.integration import Messenger

COURIER_URL = os.environ.get("COURIER_URL", "http://localhost:8080")
DEFAULT_ORG = "1"
DEFAULT_URN = "tel:+250788123123"

# how often we send typing indicators while the user is typing (courier's marker lasts 10 seconds)
TYPING_THROTTLE = 4

# how long a received typing indicator stays visible, matching courier's marker TTL
TYPING_DISPLAY = 10

# animation frames for the typing indicator shown after the user's input
TYPING_FRAMES = ["·  ", "·· ", "···", "   "]

# Host courier uses to reach our send callback, and the port it listens on. Defaults let everything run on
# localhost; when courier runs in another container, set CALLBACK_HOST to a name it can resolve (e.g. the
# container running this command) so MT replies are delivered back here.
DEFAULT_CALLBACK_HOST = os.environ.get("MSG_CONSOLE_CALLBACK_HOST") or None
DEFAULT_PORT = int(os.environ.get("MSG_CONSOLE_PORT", "49999"))


class Command(BaseCommand):  # pragma: no cover
    def add_arguments(self, parser):
        parser.add_argument(
            "--org",
            type=str,
            action="store",
            dest="org",
            default=DEFAULT_ORG,
            help="The id or name of the workspace to send messages to",
        )

        parser.add_argument(
            "--urn", type=str, action="store", dest="urn", default=DEFAULT_URN, help="The URN to send messages from"
        )

        parser.add_argument(
            "--callback-host",
            type=str,
            action="store",
            dest="callback_host",
            default=DEFAULT_CALLBACK_HOST,
            help="Host courier uses to reach this console's send callback (default: this host's hostname)",
        )

        parser.add_argument(
            "--port",
            type=int,
            action="store",
            dest="port",
            default=DEFAULT_PORT,
            help="Port for this console's send callback server to listen on",
        )

    def handle(self, *args, **options):
        colorama_init()
        org = self.get_org(options["org"])
        user = org.get_admins().first()
        scheme, path, *rest = URN.to_parts(options["urn"])

        self.prompt = f"📱 {Fore.CYAN}{path}{Fore.RESET}> "

        try:
            requests.get(COURIER_URL)
            self.stdout.write(f"✅ Courier running at️ {Fore.CYAN}{COURIER_URL}{Fore.RESET}")
        except ConnectionError:
            raise CommandError(f"Unable to connect to courier at {COURIER_URL}")

        try:
            self.messenger = Messenger.create(
                org,
                user,
                COURIER_URL,
                callback=self.response_callback,
                scheme=scheme,
                port=options["port"],
                callback_host=options["callback_host"],
            )
            self.stdout.write(f"✅ Messenger started at️ {Fore.CYAN}{self.messenger.server.base_url}{Fore.RESET}")
        except Exception as e:
            raise CommandError(f"Unable to start messenger: {str(e)}")

        self.stdout.write(
            f"\nSending messages to {Fore.CYAN}{org.name}{Fore.RESET} as {Fore.CYAN}{scheme}:{path}{Fore.RESET}. "
            "Typing indicators are sent as you type. Use Ctrl+C to quit."
        )

        self.path = path
        self.buffer = []
        self.last_typing = 0  # last time we sent a typing indicator
        self.typing_until = 0  # when the typing indicator we're showing expires
        self.frame = 0
        self.reading = False
        self.term_lock = threading.Lock()  # the input loop, callback server and animator all draw

        threading.Thread(target=self.animate_typing, daemon=True).start()

        try:
            while True:
                line = self.read_line()
                if not line:
                    continue

                self.messenger.incoming(path, line)

        except KeyboardInterrupt:
            self.messenger.release(release_channel=False)
            self.stdout.write("🛑 Messenger stopped")

    def read_line(self) -> str:
        """
        Like input() but reads a character at a time so we can send typing indicators as the user types.
        """
        if not sys.stdin.isatty():
            return input(self.prompt)

        fd = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
        self.buffer = []
        with self.term_lock:
            self.reading = True
            self.redraw_prompt()
        try:
            # unlike raw mode, cbreak leaves Ctrl+C working.. and TCSADRAIN doesn't discard anything
            # typed while the last message was sending
            tty.setcbreak(fd, termios.TCSADRAIN)

            while True:
                ch = sys.stdin.read(1)
                if ch in ("\n", "\r"):
                    with self.term_lock:
                        self.reading = False
                        print("\033[0K")  # erase any typing indicator to the right of the input
                    return "".join(self.buffer)
                elif ch == "\x04":  # Ctrl+D quits like Ctrl+C
                    raise KeyboardInterrupt()
                elif ch == "\x1b":  # swallow escape sequences (e.g. arrow keys)
                    if sys.stdin.read(1) == "[":
                        sys.stdin.read(1)
                elif ch in ("\x7f", "\x08"):  # backspace
                    if self.buffer:
                        self.buffer.pop()
                        with self.term_lock:
                            self.redraw_prompt()
                elif ch.isprintable():
                    self.buffer.append(ch)
                    self.send_typing()
                    with self.term_lock:
                        self.redraw_prompt()
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)
            self.reading = False
            self.buffer = []

    def send_typing(self):
        """
        Sends a typing indicator if we haven't sent one recently.
        """
        if time.time() - self.last_typing >= TYPING_THROTTLE:
            self.last_typing = time.time()
            self.messenger.typing(self.path)

    def redraw_prompt(self):
        """
        Redraws the prompt line: the prompt, the current input and an animated typing indicator if one
        is active. Callers must hold the terminal lock.
        """
        print("\033[2K\033[1G", end="")
        print(self.prompt + "".join(self.buffer), end="", flush=True)

        if time.time() < self.typing_until:
            dots = TYPING_FRAMES[self.frame % len(TYPING_FRAMES)]
            # draw the indicator after the input, then move the cursor back to the input
            print(f"  {Fore.YELLOW}typing{dots}{Fore.RESET}\033[{8 + len(dots)}D", end="", flush=True)

    def animate_typing(self):
        """
        Advances the typing indicator animation and clears it when it expires.
        """
        while True:
            time.sleep(0.3)
            with self.term_lock:
                if not self.typing_until:
                    continue
                self.frame += 1
                if time.time() >= self.typing_until:
                    self.typing_until = 0
                if self.reading:
                    self.redraw_prompt()

    def response_callback(self, data):
        with self.term_lock:
            print("\033[2K\033[1G", end="")  # erase current line and move cursor to start of line
            if data.get("type") == "typing":
                self.typing_until = time.time() + TYPING_DISPLAY
            else:
                # a message takes the place of any typing indicator
                self.typing_until = 0
                print(f"📠 {Fore.GREEN}{self.messenger.channel.address}{Fore.RESET}> {data['text']}")
            # reprint the prompt along with anything the user has typed so far
            if self.reading:
                self.redraw_prompt()

    def get_org(self, id_or_name):
        """
        Gets an org by its id or name. If more than one org has the name, first org is returned
        """
        try:
            org_id = int(id_or_name)
            try:
                return Org.objects.get(id=org_id)
            except Org.DoesNotExist:
                raise CommandError(f"No such org with id {org_id}")
        except ValueError:
            org = Org.objects.filter(name=id_or_name).first()
            if not org:
                raise CommandError(f"No such org with name '{id_or_name}'")
            return org
