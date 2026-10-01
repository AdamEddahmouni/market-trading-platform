"""An HTTP server that refuses a port another process already serves."""

from __future__ import annotations

import os
import socket
from http.server import ThreadingHTTPServer


class SingleBindHTTPServer(ThreadingHTTPServer):
    # On Windows SO_REUSEADDR lets a second process bind a port that is already being served,
    # and requests then land on either one. Exclusive use makes the second bind fail instead.
    allow_reuse_address = os.name != "nt"

    def server_bind(self) -> None:
        if os.name == "nt":
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()
