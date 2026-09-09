from __future__ import annotations

import re
import unittest

from voice_app.tunnel import CLOUDFLARED_QUICK_TUNNEL_PATTERN


class CloudflaredUrlTests(unittest.TestCase):
    def test_accepts_generated_quick_tunnel_hostname(self) -> None:
        line = (
            "Your quick Tunnel has been created! Visit it at "
            "https://jersey-healing-contacted-continent.trycloudflare.com"
        )
        match = re.search(CLOUDFLARED_QUICK_TUNNEL_PATTERN, line)
        self.assertIsNotNone(match)
        self.assertEqual(
            match.group(0),
            "https://jersey-healing-contacted-continent.trycloudflare.com",
        )

    def test_rejects_cloudflare_api_hostname(self) -> None:
        self.assertIsNone(
            re.search(
                CLOUDFLARED_QUICK_TUNNEL_PATTERN,
                "Requesting new quick Tunnel on https://api.trycloudflare.com",
            )
        )


if __name__ == "__main__":
    unittest.main()
