"""Adattatore HTTP/WebSocket, solo libreria standard Python 3.11.

Tutte le richieste applicative passano da ioportservice, anche il recupero
dello stato dopo una riconnessione. Ogni POST possiede una connessione QAK.
"""
import argparse
import base64
import hashlib
import itertools
import json
from pathlib import Path
import select
import socket
import struct
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

IDS = itertools.count(1)


def qak(host, port, message):
    seq = next(IDS)
    wire = f"msg({message},request,web{seq},ioportservice,{message}(none),{seq})\n"
    with socket.create_connection((host, port), timeout=3) as conn:
        conn.settimeout(8)
        conn.sendall(wire.encode())
        line = conn.makefile('rb').readline(65537)
        if not line or len(line) > 65536:
            raise OSError('Risposta QAK assente o troppo grande')
        return line.decode().strip()


def read_state(host, port):
    line = qak(host, port, 'get_ioport_status')
    data = json.loads(line[line.index('{'):line.rindex('}') + 1])
    if not data.get('connected', True):
        raise OSError('Coordinatore non raggiungibile')
    return json.loads(data['display'])


def ws_frame(payload, opcode=1):
    payload = payload if isinstance(payload, bytes) else payload.encode()
    size = len(payload)
    prefix = bytes([0x80 | opcode])
    if size < 126:
        return prefix + bytes([size]) + payload
    if size <= 65535:
        return prefix + b'\x7e' + struct.pack('!H', size) + payload
    return prefix + b'\x7f' + struct.pack('!Q', size) + payload


def receive_frame(stream):
    def exact(size):
        data = stream.read(size)
        if len(data) != size:
            raise OSError('WebSocket chiuso')
        return data
    first, second = exact(2)
    size = second & 127
    if size == 126:
        size = struct.unpack('!H', exact(2))[0]
    elif size == 127:
        size = struct.unpack('!Q', exact(8))[0]
    if not second & 128 or size > 4096:
        raise OSError('Frame client non valido')
    mask = exact(4)
    data = exact(size)
    return first & 15, bytes(value ^ mask[i % 4] for i, value in enumerate(data))


class Handler(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'

    def respond(self, status, body, content_type='application/json; charset=utf-8'):
        data = body.encode() if isinstance(body, str) else body
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Connection', 'close')
        self.end_headers()
        self.wfile.write(data)
        self.close_connection = True

    def same_origin(self):
        origin = self.headers.get('Origin')
        return origin is None or origin == 'http://' + self.headers.get('Host', '')

    def do_POST(self):
        if self.path != '/api/load':
            self.respond(404, '{}'); return
        if not self.same_origin():
            self.respond(403, '{}'); return
        try:
            line = qak(self.server.qak_host, self.server.qak_port, 'load_request')
            import re
            result = re.search(r',(load_accepted|retrylater|load_refused)\((slot[1-4]|none)\),', line)
            if result is None:
                raise ValueError('Risposta di carico non riconosciuta')
            self.respond(200, json.dumps({'response': result[1], 'slot': result[2]}))
        except (OSError, ValueError) as ex:
            # Nessun retry automatico del POST: la richiesta potrebbe essere gia stata accettata.
            self.respond(503, json.dumps({'error': 'Esito non disponibile; controllare lo stato prima di riprovare.'}))

    def do_GET(self):
        if self.path == '/':
            self.respond(200, Path(__file__).with_name('index.html').read_bytes(), 'text/html; charset=utf-8')
        elif self.path == '/api/state':
            try:
                self.respond(200, json.dumps(read_state(self.server.qak_host, self.server.qak_port)))
            except (OSError, ValueError, KeyError):
                self.respond(503, '{"error":"Collegamento applicativo non disponibile"}')
        elif self.path == '/ws/state':
            self.websocket()
        else:
            self.respond(404, '{}')

    def websocket(self):
        if not self.same_origin() or self.headers.get('Upgrade', '').lower() != 'websocket' or self.headers.get('Sec-WebSocket-Version') != '13':
            self.respond(400, '{}'); return
        key = self.headers.get('Sec-WebSocket-Key', '')
        try:
            if len(base64.b64decode(key, validate=True)) != 16:
                raise ValueError()
        except ValueError:
            self.respond(400, '{}'); return
        accept = base64.b64encode(hashlib.sha1((key + '258EAFA5-E914-47DA-95CA-C5AB0DC85B11').encode()).digest()).decode()
        self.send_response(101)
        self.send_header('Upgrade', 'websocket')
        self.send_header('Connection', 'Upgrade')
        self.send_header('Sec-WebSocket-Accept', accept)
        self.end_headers()
        self.connection.settimeout(10)
        self.close_connection = True
        previous = None
        sent = 0
        try:
            while True:
                if select.select([self.connection], [], [], 0)[0]:
                    opcode, payload = receive_frame(self.rfile)
                    if opcode == 8:
                        self.wfile.write(ws_frame(payload, 8)); return
                    if opcode == 9:
                        self.wfile.write(ws_frame(payload, 10))
                try:
                    payload = json.dumps({'connected': True, 'state': read_state(self.server.qak_host, self.server.qak_port)})
                except (OSError, ValueError, KeyError):
                    payload = json.dumps({'connected': False})
                # Aggiornamento per variazione, heartbeat per rilevare anche connessioni bloccate.
                if payload != previous or time.monotonic() - sent > 1:
                    self.wfile.write(ws_frame(payload))
                    self.wfile.flush()
                    previous, sent = payload, time.monotonic()
                time.sleep(0.25)
        except OSError:
            pass


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--bind', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=8080)
    parser.add_argument('--qak-host', default='127.0.0.1')
    parser.add_argument('--qak-port', type=int, default=8022)
    args = parser.parse_args()
    with ThreadingHTTPServer((args.bind, args.port), Handler) as server:
        server.qak_host, server.qak_port = args.qak_host, args.qak_port
        print(f'IOPort: http://{args.bind}:{args.port}', flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == '__main__':
    main()
