import os
import unittest
import shutil
import tempfile
import threading

try:
    import SocketServer as socketserver
except ImportError:
    import socketserver

import qmp


class QMPServerUnix(socketserver.ThreadingMixIn,
                    socketserver.UnixStreamServer):
    pass


class QMP(unittest.TestCase):

    GREETING = (b'{"QMP": {"version": {"qemu": {"micro": 0, "minor": 99, '
                b'"major": 9}, "package": "v9.99.0"}, "capabilities": []}}')

    def _start_server_client(self, handler_class):
        address = os.path.join(self.tmpdir, 'mon.sock')
        server = QMPServerUnix(address, handler_class)
        thread = threading.Thread(target=server.serve_forever)
        thread.demon = True
        thread.start()
        client = qmp.QEMUMonitorProtocol(address)
        return (server, client)

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.server = None

    def tearDown(self):
        if self.server is not None:
            self.server.shutdown()
            self.server.server_close()
        shutil.rmtree(self.tmpdir)

    def test_no_json(self):
        class Handler(socketserver.BaseRequestHandler):
            def handle(self):
                self.request.sendall(b'__DATA__THAT_IS_NOT_JSON__')
        self.server, client = self._start_server_client(Handler)
        self.assertRaises(qmp.QMPDataError, client.connect)

    def test_no_greeting(self):
        class Handler(socketserver.BaseRequestHandler):
            def handle(self):
                self.request.sendall(b'{}')
        self.server, client = self._start_server_client(Handler)
        self.assertRaises(qmp.QMPConnectError, client.connect, True)

    def test_greeting(self):
        class Handler(socketserver.BaseRequestHandler):
            def handle(self):
                self.request.sendall(QMP.GREETING)
        self.server, client = self._start_server_client(Handler)
        try:
            greeting = client.connect(False)
        except qmp.QMPConnectError:
            self.fail("No QMP greeting recognized by the client")
        self.assertIn(u"QMP", greeting)

    def test_greeting_no_capabilities(self):
        class Handler(socketserver.BaseRequestHandler):
            def handle(self):
                self.request.sendall(QMP.GREETING)
        self.server, client = self._start_server_client(Handler)
        self.assertRaises(qmp.QMPCapabilitiesError, client.connect, True)


if __name__ == '__main__':
    unittest.main()
