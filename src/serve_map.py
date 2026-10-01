"""Serve the generated map locally and open the default browser."""
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import webbrowser


class MapRequestHandler(SimpleHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def end_headers(self):
        # A subsequent run must never display a cached, older HTML inventory.
        self.send_header("Cache-Control", "no-cache")
        super().end_headers()


def serve_map(root: Path) -> None:
    folder = Path(root).resolve() / "output/maps"
    if not (folder / "MAPC_access_map.html").is_file():
        raise FileNotFoundError("The map was not generated. Run the MAPC launcher again.")
    handler = partial(MapRequestHandler, directory=str(folder))
    # An OS-assigned port avoids collisions with another project or older run.
    with ThreadingHTTPServer(("127.0.0.1", 0), handler) as server:
        url = f"http://127.0.0.1:{server.server_port}/MAPC_access_map.html"
        print(f"Opening map in your browser...\nMap: {url}\nKeep this window open while using the map. Press Ctrl+C to stop.", flush=True)
        if not webbrowser.open(url, new=2):
            raise RuntimeError("The map was generated, but the default browser could not open. Set a default web browser in your computer settings and run again.")
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("\nMAPC map server stopped.", flush=True)
