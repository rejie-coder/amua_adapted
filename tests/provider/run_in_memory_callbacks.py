"""Run provider tests where a sandbox denies loopback bind().

Only the callback transport is replaced. The actual BaseHTTPRequestHandler parses
HTTP request bytes and the production Broker completes authorization. Remote
services and keys remain synthetic as in the normal suite. This is NOT a real
socket, browser, provider, or real-account acceptance test.
"""
import email.parser
import io
import itertools
from pathlib import Path
import queue
import sys
import threading
import urllib.error
import urllib.parse
import urllib.request
from unittest.mock import patch
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'src/provider'))
import broker

servers = {}
ports = itertools.count(41000)
real_open = urllib.request.urlopen

class Socket:
    def __init__(self, path):
        self.input = io.BytesIO(('GET '+path+' HTTP/1.0\r\nHost: 127.0.0.1\r\n\r\n').encode())
        self.output = io.BytesIO()
    def settimeout(self, timeout): pass
    def makefile(self, mode, *args): return self.input
    def sendall(self, data): self.output.write(data)

class Server:
    def __init__(self, address, handler):
        self.server_port = next(ports)
        self.server_name = '127.0.0.1'
        self.handler = handler
        self.jobs = queue.Queue()
        self.timeout = .2
        servers[self.server_port] = self
    def handle_request(self):
        try: sock, done, failures = self.jobs.get(timeout=self.timeout)
        except queue.Empty: return
        try: self.handler(sock, ('127.0.0.1', 12345), self)
        except BaseException as error: failures.append(error)
        finally: done.set()
    def server_close(self): servers.pop(self.server_port, None)

class Response(io.BytesIO):
    def __init__(self, body, headers):
        super().__init__(body)
        self.headers = headers

def callback_open(url, *args, **kwargs):
    if not isinstance(url, str): return real_open(url, *args, **kwargs)
    parsed = urllib.parse.urlsplit(url)
    server = servers.get(parsed.port)
    if parsed.hostname != '127.0.0.1' or server is None:
        return real_open(url, *args, **kwargs)
    sock = Socket(parsed.path+('?' + parsed.query if parsed.query else ''))
    done = threading.Event()
    failures = []
    server.jobs.put((sock, done, failures))
    if not done.wait(kwargs.get('timeout', 5)): raise TimeoutError('Synthetic callback timed out')
    if failures: raise failures[0]
    header, body = sock.output.getvalue().split(b'\r\n\r\n', 1)
    lines = header.decode().split('\r\n')
    code = int(lines[0].split()[1])
    headers = email.parser.Parser().parsestr('\r\n'.join(lines[1:]))
    if code >= 400: raise urllib.error.HTTPError(url, code, 'Synthetic callback', headers, io.BytesIO(body))
    return Response(body, headers)

if __name__ == '__main__':
    with patch.object(broker.http.server, 'HTTPServer', Server), patch.object(urllib.request, 'urlopen', side_effect=callback_open):
        suite = unittest.defaultTestLoader.discover(str(Path(__file__).parent))
        result = unittest.TextTestRunner(verbosity=2).run(suite)
    print('Callback transport: in-memory HTTP bytes; no real loopback/browser/account acceptance.')
    sys.exit(not result.wasSuccessful())
