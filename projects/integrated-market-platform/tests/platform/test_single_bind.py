from __future__ import annotations

import unittest
from http.server import BaseHTTPRequestHandler

from tools.platform.single_bind import SingleBindHTTPServer


class SingleBindTests(unittest.TestCase):
    def test_a_second_server_cannot_bind_a_served_port(self) -> None:
        first = SingleBindHTTPServer(("127.0.0.1", 0), BaseHTTPRequestHandler)
        try:
            with self.assertRaises(OSError):
                SingleBindHTTPServer(("127.0.0.1", first.server_address[1]), BaseHTTPRequestHandler)
        finally:
            first.server_close()


if __name__ == "__main__":
    unittest.main()
