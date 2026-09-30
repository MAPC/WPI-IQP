"""Open the saved map through a local HTTP server with ordinary browser caching.

No data is uploaded. The service binds only to 127.0.0.1 and serves only the map
folder. HTTP lets the browser provide the Referer required by the street-tile
provider. A file:// copy remains fully usable in local/offline mode.
"""
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import argparse
import webbrowser


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()
    folder = Path(__file__).resolve().parents[1] / "output/maps"
    if not (folder / "MAPC_access_map.html").is_file():
        parser.error("Saved map is missing. Run the documented pipeline first.")
    server = ThreadingHTTPServer(("127.0.0.1", args.port), partial(SimpleHTTPRequestHandler, directory=str(folder)))
    url = f"http://127.0.0.1:{server.server_port}/MAPC_access_map.html"
    print(f"Map: {url}\nPress Ctrl+C to stop.", flush=True)
    if not args.no_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
