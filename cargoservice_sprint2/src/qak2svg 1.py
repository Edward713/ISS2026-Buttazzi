#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
qak2svg.py  -  Genera la rappresentazione architetturale (SVG) di un modello qak.

Uso:
    python qak2svg.py modello.qak                 -> modello_arch.svg
    python qak2svg.py modello.qak -o fig.svg
    python qak2svg.py src/*.qak                   (piu' modelli in un colpo)
    python qak2svg.py modello.qak --no-table      (senza tabella degli eventi)
    python qak2svg.py modello.qak --png           (anche PNG, se e' installato cairosvg)

Solo libreria standard Python (>= 3.8). Nessuna dipendenza da Graphviz.

Simboli grafici
---------------
  QActor          rettangolo arrotondato con "mailbox" (coda di messaggi) sul lato
                  sinistro e glifo di automa a stati finiti (FSM) in alto a destra
  CodedQActor     come QActor, con glifo { } al posto della FSM
  ExternalQActor  come QActor, bordo tratteggiato e fondo grigio
  QActor hidden   come QActor, bordo tratteggiato fine (stesso fondo), dentro il
                  riquadro del suo contesto; stereotipo \u00abQActor hidden\u00bb
                  [Claude, Oct 2026] HIDDEN QActor
  POJO            icona (mini-classe) con il solo nome, DENTRO il QActor che lo
                  possiede [withobj]; nessuna indicazione di metodi
                  [Claude, Oct 2026] POJO locali
  WebService      box con glifo a globo, stereotipo <<WebService>>
  Processo OS     box con angolo ripiegato, stereotipo <<OS process>>  [Runtime.exec]
  MQTT broker     box con glifo a "hub"

Colori  [Claude, Oct 2026]
------
Fondi chiari (adatti alla stampa) e diversi per QActor, CodedQActor, ExternalQActor,
POJO, servizi Web e broker; un colore distinto per ciascun tipo di messaggio
(dispatch, request, reply, event, ...), usato sia per gli archi sia nelle tabelle.
La palette e' in FILL (nodi) e MSGCOLOR / STYLE (messaggi).

Tabelle  [Claude, Oct 2026]
-------
  Messaggi : ogni Dispatch / Request / Reply / Signal / Token / Invitation con
             chi lo invia (mittente -> destinatario) e chi lo riceve (transizioni);
  Eventi   : chi li emette e chi li percepisce.
  --no-table omette entrambe le tabelle.

Riconoscimento dei servizi Web
------------------------------
Il linguaggio qak non ha un costrutto esplicito per i servizi Web, per cui:
  1) ogni stringa "http(s)://...", "ws(s)://...", "coap://..." presente nel codice
     Kotlin [# ... #] di un attore produce un nodo <<WebService>> collegato all'attore;
  2) annotazione esplicita in un commento del modello:
         // @WebService nome ["url"] [usedby attore1,attore2]
     Se 'nome' e' un ExternalQActor, l'attore viene disegnato come servizio Web
     all'interno del suo contesto; altrimenti si crea un nodo autonomo.
  3) un attore che esegue updateResource e' marcato come risorsa CoAP osservabile.
"""

import argparse
import glob
import html
import math
import os
import re
import sys

# =====================================================================
# 1. PARSING
# =====================================================================

def strip_comments(text):
    """Rimuove commenti // e /* */ rispettando le stringhe "...".
    Restituisce (testo_senza_commenti, lista_commenti)."""
    out, comments = [], []
    i, n = 0, len(text)
    in_str = False
    while i < n:
        c = text[i]
        if in_str:
            out.append(c)
            if c == '\\' and i + 1 < n:
                out.append(text[i + 1]); i += 2; continue
            if c == '"':
                in_str = False
            i += 1
            continue
        if c == '"':
            in_str = True; out.append(c); i += 1; continue
        if text.startswith('//', i):
            j = text.find('\n', i)
            j = n if j < 0 else j
            comments.append(text[i + 2:j]); i = j; continue
        if text.startswith('/*', i):
            j = text.find('*/', i + 2)
            j = n if j < 0 else j + 2
            seg = text[i:j]
            comments.append(seg)
            out.append('\n' * seg.count('\n')); i = j; continue
        out.append(c); i += 1
    return ''.join(out), comments


KCODE = re.compile(r'\[#.*?#\]', re.S)
STR = r'"(?:[^"\\]|\\.)*"'


class Model:
    def __init__(self):
        self.name = '?'
        self.broker = None            # (host, port, topic)
        self.messages = {}            # name -> dict(kind, sig, for)
        self.contexts = {}            # name -> dict(host, port)
        self.ctx_order = []
        self.actors = {}              # name -> dict
        self.actor_order = []
        self.webservices = {}         # id -> dict(label, url, users:set)
        self.ws_annot = {}            # name -> dict(url, users)


def new_actor(name, kind, ctx):
    return dict(name=name, kind=kind, ctx=ctx, pojos=[], procs=[], kb=[],
                className=None, coap=False, mqtt=None, dynamic=False,
                hidden=False,      # [Claude, Oct 2026] HIDDEN QActor
                requests=[], forwards=[], autodisp=[], delegates=[],
                emits=[], perceives=[], replies=[], observes=[],
                publishes=[], subscribes=[], webservice=False, urls=[])


def parse(text):
    m = Model()
    code, comments = strip_comments(text)

    # --- annotazioni @WebService nei commenti
    for c in comments:
        for a in re.finditer(r'@WebService\s+(\w+)(?:\s+"([^"]*)")?(?:\s+usedby\s+([\w ,]+))?', c):
            users = [u.strip() for u in (a.group(3) or '').split(',') if u.strip()]
            m.ws_annot[a.group(1)] = dict(url=a.group(2) or '', users=users)

    r = re.search(r'\bSystem\s+(?:-\w+\s+)*(\w+)', code)
    if r: m.name = r.group(1)
    r = re.search(r'\bmqttBroker\s+"([^"]*)"\s*:\s*(\d+)\s+eventTopic\s+"([^"]*)"', code)
    if r: m.broker = (r.group(1), r.group(2), r.group(3))

    # --- separa la parte dichiarativa dagli attori
    decl_re = re.compile(r'^\s*(QActor|ExternalQActor|CodedQActor)\b', re.M)
    starts = [x.start() for x in decl_re.finditer(code)]
    head = code[:starts[0]] if starts else code

    for r in re.finditer(r'\b(Event|Dispatch|Request|Reply|Signal|Token|Invitation)\s+(\w+)\s*:\s*'
                         r'(\w+\s*(?:\([^\n]*?\))?)(?:\s+for\s+(\w+))?', head):
        kind, name, sig, forr = r.groups()
        m.messages.setdefault(name, dict(kind=kind, sig=sig.strip(), forr=forr))
        if kind == 'Reply':
            m.messages[name] = dict(kind=kind, sig=sig.strip(), forr=forr)
    for r in re.finditer(r'\bContext\s+(\w+)\s+ip\s*\[\s*host\s*=\s*"([^"]*)"\s+port\s*=\s*(\d+)\s*\]', head):
        m.contexts[r.group(1)] = dict(host=r.group(2), port=r.group(3))
        m.ctx_order.append(r.group(1))

    # --- attori
    bounds = starts + [len(code)]
    for k in range(len(starts)):
        chunk = code[bounds[k]:bounds[k + 1]]
        # [Claude, Oct 2026] HIDDEN QActor: flag opzionale 'hidden' subito dopo il contesto
        r = re.match(r'\s*(QActor|ExternalQActor|CodedQActor)\s+(\w+)\s+context\s+(\w+)(\s+hidden\b)?', chunk)
        if not r:
            continue
        kind, name, ctx, hid = r.groups()
        a = new_actor(name, kind, ctx)
        a['hidden'] = bool(hid) and kind != 'ExternalQActor'
        if kind == 'CodedQActor':
            c = re.search(r'className\s+"([^"]*)"', chunk)
            a['className'] = c.group(1) if c else None
        if kind == 'QActor':
            brace = chunk.find('{')
            header = chunk[:brace if brace >= 0 else len(chunk)]
            for w in re.finditer(r'withobj\s+(\w+)\s+using\s+(' + STR + ')', header):
                a['pojos'].append(dict(name=w.group(1), using=w.group(2)[1:-1].replace('\\"', '"')))
            a['dynamic'] = 'dynamicOnly' in header
            body = chunk[brace:] if brace >= 0 else ''
            parse_body(a, body)
        m.actors[name] = a
        m.actor_order.append(name)

    # --- servizi web (euristica URL + annotazioni)
    for a in m.actors.values():
        for url in a['urls']:
            host = re.sub(r'^\w+://', '', url).split('/')[0]
            wid = 'ws:' + host
            ws = m.webservices.setdefault(wid, dict(label=host, url=url, users=set()))
            ws['users'].add(a['name'])
    for name, ann in m.ws_annot.items():
        if name in m.actors:
            m.actors[name]['webservice'] = True
            m.actors[name]['wsurl'] = ann['url']
        else:
            wid = 'ws:' + name
            ws = m.webservices.setdefault(wid, dict(label=name, url=ann['url'], users=set()))
            ws['users'].update(ann['users'])
    return m


def parse_body(a, body):
    kcode = ' '.join(KCODE.findall(body))
    q = KCODE.sub(' ', body)          # parte qak "pura"

    # risorse dal codice Kotlin
    for u in re.findall(r'"((?:https?|wss?|coap)://[^"\s$]+[^"\s]*)"', kcode):
        a['urls'].append(u)
    for p in re.findall(r'exec\s*\(\s*(' + STR + ')', kcode):
        cmd = p[1:-1]
        if cmd not in a['procs']: a['procs'].append(cmd)
    for p in re.findall(r'\bmachineExec\s+(' + STR + ')', q):
        if p[1:-1] not in a['procs']: a['procs'].append(p[1:-1])
    for f in re.findall(r'consult\s*\(\s*"([^"]+)"', body):
        if f not in a['kb']: a['kb'].append(f)

    add = lambda lst, v: lst.append(v) if v not in lst else None
    for d, msg in re.findall(r'\brequest\s+(\w+)\s+-m\s+(\w+)', q): add(a['requests'], (d, msg))
    for d, msg in re.findall(r'\bforward\s+(\w+)\s+-m\s+(\w+)', q): add(a['forwards'], (d, msg))
    for msg in re.findall(r'\bautodispatch\s+(\w+)', q): add(a['autodisp'], msg)
    for msg in re.findall(r'\bautorequest\s+(\w+)', q): add(a['autodisp'], msg)
    for msg, d in re.findall(r'\bdelegate\s+(\w+)\s+to\s+(\w+)', q): add(a['delegates'], (d, msg))
    for msg in re.findall(r'\bdelegateCurrentMsgTo\s+(\w+)', q): add(a['delegates'], (msg, '*current*'))
    for mode, ev in re.findall(r'\b(emit|emitlocal|emitlocalstream)\s+(\w+)\s*:', q): add(a['emits'], (ev, mode))
    for top, ev in re.findall(r'\bpublish\s+"([^"]*)"\s+-m\s+(\w+)', q):
        add(a['emits'], (ev, 'publish')); add(a['publishes'], (top, ev))
    for kind, msg in re.findall(r'\b(whenEvent|whenInterruptEvent)\s+(\w+)', q): add(a['perceives'], (msg, kind))
    for who, ev in re.findall(r'\bsubscribeTo\s+(\w+)(?:\s*_\s*' + STR + r')?\s+for\s+(\w+)', q):
        add(a['perceives'], (ev, 'subscribeTo'))
    for req, rep in re.findall(r'\breplyTo\s+(\w+)\s+(?:ofsender\s+\S+\s+)?with\s+(\w+)', q): add(a['replies'], (req, rep))
    for res in re.findall(r'\bobserveResource\s+(\w+)', q): add(a['observes'], res)
    for t in re.findall(r'\bsubscribe\s+"([^"]*)"', q): add(a['subscribes'], t)
    r = re.search(r'\bconnectToMqttBroker\s+"([^"]*)"', q)
    if r: a['mqtt'] = r.group(1)
    a['coap'] = bool(re.search(r'\bupdateResource\b', q))
    a['inmsgs'] = sorted(set(re.findall(r'\b(?:whenMsg|whenRequest|whenInterrupt)\s+(\w+)', q)))
    # [Claude, Oct 2026] tabella dei messaggi: reply attese dall'attore
    a['inreplies'] = sorted(set(re.findall(r'\bwhenReply\s+(\w+)', q)))


# =====================================================================
# 2. GEOMETRIA / UTILITA' SVG
# =====================================================================

def esc(s):
    return html.escape(str(s), quote=True)


def tw(s, fs, mono=False):
    return len(s) * fs * (0.61 if mono else 0.56)


def trunc(s, n):
    return s if len(s) <= n else s[:n - 1] + '\u2026'


class Box:
    def __init__(self, x=0, y=0, w=0, h=0):
        self.x, self.y, self.w, self.h = x, y, w, h

    @property
    def cx(self): return self.x + self.w / 2

    @property
    def cy(self): return self.y + self.h / 2

    def right(self): return self.x + self.w

    def bottom(self): return self.y + self.h

    def border(self, px, py):
        """Punto sul bordo del box lungo la retta centro -> (px,py)."""
        dx, dy = px - self.cx, py - self.cy
        if dx == 0 and dy == 0:
            return self.cx, self.cy
        sx = (self.w / 2) / abs(dx) if dx else 1e9
        sy = (self.h / 2) / abs(dy) if dy else 1e9
        s = min(sx, sy)
        return self.cx + dx * s, self.cy + dy * s

    def overlaps(self, o, pad=2):
        return not (self.x + self.w + pad < o.x or o.x + o.w + pad < self.x or
                    self.y + self.h + pad < o.y or o.y + o.h + pad < self.y)


# [Claude, Oct 2026] COLORI
# Colore (tratto) per tipo di messaggio, usato per archi, etichette e tabelle.
MSGCOLOR = {
    'Dispatch':   '#2e7d32',   # verde
    'Request':    '#1565c0',   # blu
    'Reply':      '#00838f',   # ciano scuro
    'Event':      '#e65100',   # arancio
    'Signal':     '#6d4c41',   # bruno
    'Token':      '#6d4c41',
    'Invitation': '#6d4c41',
}

STYLE = {   # kind -> (colore, dasharray, legenda)
    'request':  (MSGCOLOR['Request'],  '',          'request  (etichetta: richiesta \u2192 reply previste)'),
    'dispatch': (MSGCOLOR['Dispatch'], '7 4',       'dispatch (forward)'),
    'delegate': ('#8d6e00',            '10 3 2 3',  'delegate'),
    'observe':  ('#8e24aa',            '2 3',       'observeResource (CoAP)'),
    'http':     ('#ad1457',            '5 3',       'interazione HTTP / WS / CoAP (dal codice)'),
    'exec':     ('#546e7a',            '2 3',       'esecuzione processo OS'),
    'mqtt':     ('#c62828',            '4 2',       'eventi via MQTT (eventTopic / publish)'),
    # [Claude, Oct 2026] 'rail' = linea DOPPIA (binario): distinguibile dalla linea continua
    # delle request anche in una stampa in bianco/nero
    'event':    (MSGCOLOR['Event'],    'rail',      'emette (\u2192 canale) / percepisce (canale \u2192)'),
}

# [Claude, Oct 2026] COLORI: fondi chiari (stampabili) per i nodi -> (fondo, bordo)
FILL = {
    'QActor':         ('#e3f0fc', '#1f3b5c'),   # azzurro
    'CodedQActor':    ('#efe6fa', '#3e2a5c'),   # lilla
    'ExternalQActor': ('#eeeeee', '#555555'),   # grigio
    'pojo':           ('#fff3cd', '#a07800'),   # giallo chiaro
    'webservice':     ('#e6f6ea', '#2a5c36'),   # verde chiaro
    'broker':         ('#fde8ec', '#7a2333'),   # rosa chiaro
    'proc':           ('#f1f3f4', '#555555'),
    'context':        ('#fbfbfb', '#222222'),
    'extcontext':     ('#ffffff', '#555555'),
    'evband':         ('#fff1e6', '#e65100'),   # canale eventi (colore Event)
}


def rail(layer, points, color, mk_start=None, mk_end=None):
    """[Claude, Oct 2026] Linea doppia ('binario') lungo una polilinea: tratto largo colorato,
    tratto bianco sottile sopra, poi una polilinea invisibile che porta solo le frecce
    (cosi' le frecce restano della dimensione normale)."""
    pts = ' '.join('%.1f,%.1f' % p for p in points)
    layer.append('<polyline points="%s" fill="none" stroke="%s" stroke-width="4.2" stroke-linejoin="round"/>' % (pts, color))
    layer.append('<polyline points="%s" fill="none" stroke="#ffffff" stroke-width="1.6" stroke-linejoin="round"/>' % pts)
    if mk_start or mk_end:
        layer.append('<polyline points="%s" fill="none" stroke="none" stroke-width="1.4"%s%s/>'
                     % (pts, ' marker-start="url(#%s)"' % mk_start if mk_start else '',
                        ' marker-end="url(#%s)"' % mk_end if mk_end else ''))


def tint(color, f=0.88):
    """[Claude, Oct 2026] Versione chiara di un colore #rrggbb (mescolato al bianco)."""
    c = color.lstrip('#')
    r, g, b = (int(c[i:i + 2], 16) for i in (0, 2, 4))
    r, g, b = (round(v + (255 - v) * f) for v in (r, g, b))
    return '#%02x%02x%02x' % (r, g, b)


# =====================================================================
# 3. LAYOUT
# =====================================================================

AW_MIN, AH_BASE = 190, 66
CHILD_GAP_Y = 40
COL_GAP, ROW_GAP = 190, 120
CTX_PAD, CTX_TOP = 36, 58


class Layout:
    pass


CHIP_H, CHIP_GAP = 20, 8     # [Claude, Oct 2026] POJO locali: icone dentro il QActor


def chip_w(name):
    return tw(name, 10) + 30


def pojo_rows(a, w):
    """[Claude, Oct 2026] Dispone le icone dei POJO su righe larghe al massimo w-40."""
    rows, cur, cw = [], [], 0
    for p in a['pojos']:
        cwid = chip_w(p['name'])
        if cur and cw + CHIP_GAP + cwid > w - 40:
            rows.append(cur); cur, cw = [], 0
        cur.append((p, cwid)); cw += (CHIP_GAP if cw else 0) + cwid
    if cur: rows.append(cur)
    return rows


def actor_size(a):
    lines = actor_badges(a)
    w = max(AW_MIN, tw(a['name'], 14) + 80, *[tw(l, 9.5) + 46 for l in lines] or [0])
    # [Claude, Oct 2026] POJO locali: spazio per le icone (al piu' 3 per riga)
    if a['pojos']:
        w = max(w, max(chip_w(p['name']) for p in a['pojos']) + 40,
                min(sum(chip_w(p['name']) + CHIP_GAP for p in a['pojos'][:3]) + 40, 460))
    nrows = len(pojo_rows(a, w))
    return w, AH_BASE + 13 * len(lines) + (nrows * (CHIP_H + 6) + 6 if nrows else 0)


def actor_badges(a):
    b = []
    if a['kind'] == 'CodedQActor' and a['className']:
        b.append('class ' + trunc(a['className'], 34))
    if a.get('webservice') and a.get('wsurl'):
        b.append(trunc(a['wsurl'], 36))
    if a['kb']:
        b.append('KB: ' + trunc(', '.join(a['kb']), 34))
    if a['coap']:
        b.append('risorsa CoAP (updateResource)')
    if a['mqtt']:
        b.append('MQTT: ' + trunc(a['mqtt'], 30))
    if a['dynamic']:
        b.append('dynamicOnly')
    return b


def child_size(kind, title, sub):
    if kind == 'pojo':
        w = max(150, tw(title, 11) + 24, tw(sub, 9.5, True) + 20)
        return min(w, 300), 54
    w = max(150, tw(sub, 9.5, True) + 22)
    return min(w, 300), 46


def build_layout(m):
    L = Layout()
    L.nodes = {}        # id -> (Box, kind, data)
    L.ctxboxes = {}     # ctx -> Box
    L.bands = {}        # ctx -> Box
    L.children = []     # (parent_id, child_id, kind)
    L.blocks = {}       # actor -> (Box block, row)

    internal = [c for c in m.ctx_order if any(
        m.actors[a]['ctx'] == c and m.actors[a]['kind'] != 'ExternalQActor' for a in m.actor_order)]
    external = [c for c in m.ctx_order if c not in internal and any(
        m.actors[a]['ctx'] == c for a in m.actor_order)]
    # attori con contesto non dichiarato
    orphan = sorted({m.actors[a]['ctx'] for a in m.actor_order} - set(m.ctx_order))
    for c in orphan:
        m.contexts[c] = dict(host='?', port='?')
        (internal if any(m.actors[a]['ctx'] == c and m.actors[a]['kind'] != 'ExternalQActor'
                         for a in m.actor_order) else external).append(c)

    top = 60
    if m.broker:
        bw = max(240, tw('eventTopic "%s"' % m.broker[2], 11) + 40)
        L.nodes['__broker'] = (Box(0, top, bw, 70), 'broker', m.broker)
        top += 70 + 70
    else:
        top += 20

    # ---- contesti interni
    x = 40
    row_bottom = top
    for c in internal:
        names = [a for a in m.actor_order if m.actors[a]['ctx'] == c]
        names.sort(key=lambda nm: ext_links(m, nm, c))
        n = len(names)
        cols = 1 if n == 1 else (2 if n <= 4 else 3)
        # misura blocchi
        blocks = []
        for nm in names:
            a = m.actors[nm]
            aw, ah = actor_size(a)
            kids = []
            # [Claude, Oct 2026] POJO locali: non piu' box separati, ma icone dentro
            # l'attore (vedi actor_size / draw_pojo_chips)
            for cmd in a['procs']:
                sub = trunc(cmd, 44)
                kids.append(('proc', 'OS process', sub) + child_size('proc', '', sub))
            kw = sum(k[3] for k in kids) + 24 * max(0, len(kids) - 1)
            bw = max(aw, kw)
            bh = ah + ((CHILD_GAP_Y + max(k[4] for k in kids)) if kids else 0)
            blocks.append((nm, aw, ah, kids, bw, bh))
        rows = [blocks[i:i + cols] for i in range(0, n, cols)]
        colw = [max((r[j][4] for r in rows if j < len(r)), default=0) for j in range(cols)]
        rowh = [max(b[5] for b in r) for r in rows]
        has_ev = any(m.actors[nm]['emits'] or m.actors[nm]['perceives'] for nm in names)
        cw = sum(colw) + COL_GAP * (cols - 1) + 2 * CTX_PAD + (30 if has_ev else 0)
        cw = max(cw, tw('Context %s' % c, 13) + 2 * CTX_PAD, 300)
        y = top + CTX_TOP + 26          # spazio per eventuali self-loop
        for ri, r in enumerate(rows):
            xx = x + CTX_PAD
            for ci, (nm, aw, ah, kids, bw, bh) in enumerate(r):
                bx = xx + (colw[ci] - bw) / 2
                ab = Box(bx + (bw - aw) / 2, y, aw, ah)
                L.nodes[nm] = (ab, 'actor', m.actors[nm])
                L.blocks[nm] = (Box(bx, y, bw, bh), ri, xx + colw[ci])
                kx = bx + (bw - (sum(k[3] for k in kids) + 24 * max(0, len(kids) - 1))) / 2
                for i, (kind, title, sub, kw_, kh) in enumerate(kids):
                    cid = '%s#%s%d' % (nm, kind, i)
                    L.nodes[cid] = (Box(kx, y + ah + CHILD_GAP_Y, kw_, kh), kind, dict(title=title, sub=sub))
                    L.children.append((nm, cid, kind))
                    kx += kw_ + 24
                xx += colw[ci] + COL_GAP
            y += rowh[ri] + (ROW_GAP + 26 if ri < len(rows) - 1 else 0)
        y += 30
        if has_ev:
            L.bands[c] = Box(x + 20, y, cw - 40, 34)
            y += 34 + 24
        L.ctxboxes[c] = Box(x, top, cw, y - top)
        row_bottom = max(row_bottom, y)
        x += cw + 110

    # ---- contesti esterni + servizi web, ordinati per vicinanza agli attori interni
    def mean_x(targets):
        xs = []
        for a in m.actors.values():
            if a['name'] not in L.nodes: continue
            outs = [d for d, _ in a['requests'] + a['forwards'] + a['delegates']] + a['observes']
            if any(t in outs for t in targets):
                xs.append(L.nodes[a['name']][0].cx)
            for t in targets:
                if t in m.actors and any(d == a['name'] for d, _ in m.actors[t]['requests'] + m.actors[t]['forwards']):
                    xs.append(L.nodes[a['name']][0].cx)
        return sum(xs) / len(xs) if xs else 1e9
    external.sort(key=lambda c: mean_x([a for a in m.actor_order if m.actors[a]['ctx'] == c]))
    y2 = row_bottom + 130
    x2 = 40
    ext_h = 0
    for c in external:
        names = [a for a in m.actor_order if m.actors[a]['ctx'] == c]
        xx = x2 + 28
        hmax = 0
        for nm in names:
            aw, ah = actor_size(m.actors[nm])
            L.nodes[nm] = (Box(xx, y2 + 50, aw, ah), 'actor', m.actors[nm])
            xx += aw + 60
            hmax = max(hmax, ah)
        cw = max(xx - 60 + 28 - x2, tw('Context ' + c, 12) + 56)
        L.ctxboxes[c] = Box(x2, y2, cw, hmax + 50 + 26)
        ext_h = max(ext_h, hmax + 76)
        x2 += cw + 70
    wsx = {wid: (sum(L.nodes[u][0].cx for u in ws['users'] if u in L.nodes) / max(1, len([u for u in ws['users'] if u in L.nodes])))
           for wid, ws in m.webservices.items()}
    for wid, ws in sorted(m.webservices.items(), key=lambda kv: wsx[kv[0]]):
        lab = trunc(ws['label'], 30)
        url = trunc(ws['url'], 40)
        w = max(190, tw(lab, 13) + 70, tw(url, 9.5, True) + 60)
        L.nodes[wid] = (Box(x2, y2 + 20, w, 74), 'webservice', ws)
        ext_h = max(ext_h, 94)
        x2 += w + 70
    # attori referenziati ma non dichiarati
    unknown = set()
    for a in m.actors.values():
        for d, _ in a['requests'] + a['forwards'] + a['delegates']:
            if d not in m.actors and d != '*current*':
                unknown.add(d)
        for d in a['observes']:
            if d not in m.actors: unknown.add(d)
    for u in sorted(unknown):
        w = max(170, tw(u, 13) + 70)
        L.nodes[u] = (Box(x2, y2 + 20, w, 66), 'unknown', dict(name=u))
        ext_h = max(ext_h, 86)
        x2 += w + 70

    L.width = max([b.right() for b in L.ctxboxes.values()] +
                  [b.right() for b, _, _ in L.nodes.values()] + [700]) + 40
    if '__broker' in L.nodes:
        b = L.nodes['__broker'][0]
        b.x = (L.width - b.w) / 2
    L.diagram_bottom = (y2 + ext_h) if ext_h else row_bottom
    L.internal, L.external = internal, external
    return L


def ext_links(m, nm, ctx):
    """Numero di interazioni dell'attore con nodi esterni al suo contesto."""
    a = m.actors[nm]
    outs = [d for d, _ in a['requests'] + a['forwards'] + a['delegates']] + a['observes']
    n = sum(1 for d in outs if d not in m.actors or m.actors[d]['ctx'] != ctx)
    n += sum(1 for ws in m.webservices.values() if nm in ws['users'])
    # anche chi viene invocato da attori esterni
    n += sum(1 for b in m.actors.values() if b['ctx'] != ctx and
             any(d == nm for d, _ in b['requests'] + b['forwards']))
    return n


def pojo_type(using):
    t = re.split(r'[\(]', using)[0]
    parts = t.split('.')
    if len(parts) >= 2 and parts[-1][:1].islower() and parts[-1] not in ('',):
        # es. SlotServiceLogic.getSingleton -> SlotServiceLogic
        return parts[-2]
    return parts[-1]


# =====================================================================
# 4. DISEGNO
# =====================================================================

class SVG:
    def __init__(self):
        self.defs, self.back, self.mid, self.front, self.labels = [], [], [], [], []
        self.label_boxes = []
        self.colors = set()

    def marker(self, color):
        mid = 'm' + color.strip('#')
        if color not in self.colors:
            self.colors.add(color)
            self.defs.append(
                '<marker id="%s" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" '
                'orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="%s"/></marker>' % (mid, color))
            self.defs.append(
                '<marker id="d%s" viewBox="0 0 14 10" refX="1" refY="5" markerWidth="12" markerHeight="9" '
                'orient="auto-start-reverse"><path d="M1,5 L7,1 L13,5 L7,9 z" fill="%s"/></marker>' % (mid, color))
        return mid

    def text(self, layer, x, y, s, fs=11, anchor='start', weight='normal', fill='#111', italic=False, mono=False):
        layer.append('<text x="%.1f" y="%.1f" font-size="%s" text-anchor="%s" font-weight="%s" fill="%s"%s%s>%s</text>'
                     % (x, y, fs, anchor, weight, fill, ' font-style="italic"' if italic else '',
                        ' font-family="Courier New, monospace"' if mono else '', esc(s)))


def draw_actor(S, b, a):
    ext = a['kind'] == 'ExternalQActor'
    ws = a.get('webservice')
    # [Claude, Oct 2026] COLORI: fondo/bordo per tipo di attore
    fill, stroke = FILL['webservice'] if ws else FILL[a['kind']]
    dash = ' stroke-dasharray="6 4"' if ext else ''
    if a.get('hidden'):                       # [Claude, Oct 2026] HIDDEN QActor
        dash = ' stroke-dasharray="3 3"'
    L = S.front
    L.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" rx="9" fill="%s" stroke="%s" stroke-width="1.6"%s/>'
             % (b.x, b.y, b.w, b.h, fill, stroke, dash))
    if ws:
        draw_globe(L, b.x + 22, b.y + 26, 11)
    else:
        # mailbox: coda di messaggi sul lato sinistro
        for i in range(4):
            L.append('<rect x="%.1f" y="%.1f" width="12" height="7" fill="#fff" stroke="#444" stroke-width="0.9"/>'
                     % (b.x + 8, b.y + 14 + i * 8.5))
        L.append('<path d="M%.1f,%.1f l0,6 m-3,-3 l3,3 l3,-3" fill="none" stroke="#444" stroke-width="0.9"/>'
                 % (b.x + 14, b.y + 50))
    # glifo in alto a destra
    gx, gy = b.right() - 34, b.y + 12
    if a['kind'] == 'CodedQActor':
        S.text(L, gx + 13, gy + 13, '{ }', 13, 'middle', 'bold', '#333', mono=True)
    elif not ws:
        L.append('<circle cx="%.1f" cy="%.1f" r="5" fill="#fff" stroke="#333"/>' % (gx + 5, gy + 9))
        L.append('<circle cx="%.1f" cy="%.1f" r="5" fill="#fff" stroke="#333"/>' % (gx + 24, gy + 9))
        L.append('<circle cx="%.1f" cy="%.1f" r="2.4" fill="#333"/>' % (gx + 24, gy + 9))
        L.append('<path d="M%.1f,%.1f L%.1f,%.1f" stroke="#333" marker-end="url(#%s)"/>'
                 % (gx + 10, gy + 9, gx + 18.5, gy + 9, S.marker('#333333')))
    stereo = {'QActor': '\u00abQActor\u00bb', 'CodedQActor': '\u00abCodedQActor\u00bb',
              'ExternalQActor': '\u00abExternalQActor\u00bb'}[a['kind']]
    if ws:
        stereo = '\u00abWebService\u00bb ' + ('(ExternalQActor)' if ext else '')
    if a.get('hidden'):                       # [Claude, Oct 2026] HIDDEN QActor
        stereo = stereo[:-1] + ' hidden\u00bb'
    S.text(L, b.cx + 6, b.y + 22, stereo, 9.5, 'middle', fill='#555')
    S.text(L, b.cx + 6, b.y + 41, a['name'], 14, 'middle', 'bold')
    badges = actor_badges(a)
    for i, line in enumerate(badges):
        S.text(L, b.cx + 6, b.y + 58 + 13 * i, line, 9.5, 'middle', fill='#333')
    draw_pojo_chips(S, b, a, b.y + AH_BASE + 13 * len(badges) - 2)


def pojo_icon(L, x, y, s=1.0):
    """[Claude, Oct 2026] Glifo 'mini-classe' (rettangolo con intestazione) per un POJO."""
    fill, stroke = FILL['pojo']
    L.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" rx="1.5" fill="#fff" stroke="%s" stroke-width="1"/>'
             % (x, y, 10 * s, 12 * s, stroke))
    L.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" fill="%s"/>' % (x, y, 10 * s, 4 * s, stroke))
    for k in (7, 9.5):
        L.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="%s" stroke-width="0.7"/>'
                 % (x + 2 * s, y + k * s, x + 8 * s, y + k * s, stroke))


def draw_pojo_chips(S, b, a, y0):
    """[Claude, Oct 2026] POJO locali: icona + nome DENTRO il QActor (nessun metodo).
    Il tipo del POJO e' disponibile come tooltip (<title>)."""
    L = S.front
    fill, stroke = FILL['pojo']
    for r, row in enumerate(pojo_rows(a, b.w)):
        roww = sum(w for _, w in row) + CHIP_GAP * (len(row) - 1)
        x = max(b.x + 12, b.cx + 6 - roww / 2)
        y = y0 + r * (CHIP_H + 6)
        for p, w in row:
            L.append('<g><title>%s : %s</title>' % (esc(p['name']), esc(pojo_type(p['using']))))
            L.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%s" rx="5" fill="%s" stroke="%s" stroke-width="1"/>'
                     % (x, y, w, CHIP_H, fill, stroke))
            pojo_icon(L, x + 6, y + 4)
            S.text(L, x + 22, y + 14, p['name'], 10, weight='bold', fill='#3d2e00')
            L.append('</g>')
            x += w + CHIP_GAP


def draw_globe(L, cx, cy, r):
    L.append('<circle cx="%.1f" cy="%.1f" r="%s" fill="#fff" stroke="#222" stroke-width="1.2"/>' % (cx, cy, r))
    L.append('<ellipse cx="%.1f" cy="%.1f" rx="%.1f" ry="%s" fill="none" stroke="#222" stroke-width="0.9"/>' % (cx, cy, r * 0.45, r))
    L.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="#222" stroke-width="0.9"/>' % (cx - r, cy, cx + r, cy))
    for dy in (-r * 0.55, r * 0.55):
        hw = math.sqrt(max(r * r - dy * dy, 0))
        L.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="#222" stroke-width="0.7"/>' % (cx - hw, cy + dy, cx + hw, cy + dy))


def draw_webservice(S, b, ws):
    L = S.front
    L.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" rx="16" fill="%s" stroke="%s" stroke-width="1.6"/>'
             % ((b.x, b.y, b.w, b.h) + FILL['webservice']))     # [Claude, Oct 2026] COLORI
    draw_globe(L, b.x + 26, b.cy, 14)
    S.text(L, b.cx + 18, b.y + 22, '\u00abWebService\u00bb', 9.5, 'middle', fill='#555')
    S.text(L, b.cx + 18, b.y + 41, trunc(ws['label'], 30), 13, 'middle', 'bold')
    if ws['url']:
        S.text(L, b.cx + 18, b.y + 59, trunc(ws['url'], 40), 9.5, 'middle', fill='#333', mono=True)


# [Claude, Oct 2026] POJO locali: draw_pojo (box UML separato) sostituita da draw_pojo_chips


def draw_proc(S, b, d):
    L = S.front
    f = 10
    L.append('<path d="M%.1f,%.1f h%.1f l%s,%s v%.1f h%.1f z" fill="%s" stroke="%s" stroke-width="1.1"/>'
             % ((b.x, b.y, b.w - f, f, f, b.h - f, -b.w) + FILL['proc']))   # [Claude, Oct 2026] COLORI
    L.append('<path d="M%.1f,%.1f v%s h%s" fill="none" stroke="#555"/>' % (b.right() - f, b.y, f, f))
    S.text(L, b.cx, b.y + 17, '\u00abOS process\u00bb', 9, 'middle', fill='#555')
    S.text(L, b.cx, b.y + 34, d['sub'], 9.5, 'middle', fill='#111', mono=True)


def draw_broker(S, b, br):
    L = S.front
    L.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" rx="8" fill="%s" stroke="%s" stroke-width="1.4"/>'
             % ((b.x, b.y, b.w, b.h) + FILL['broker']))      # [Claude, Oct 2026] COLORI
    hx, hy = b.x + 24, b.cy
    for ang in range(0, 360, 60):
        r = math.radians(ang)
        L.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="#333"/>' % (hx, hy, hx + 11 * math.cos(r), hy + 11 * math.sin(r)))
        L.append('<circle cx="%.1f" cy="%.1f" r="2.4" fill="#fff" stroke="#333"/>' % (hx + 11 * math.cos(r), hy + 11 * math.sin(r)))
    L.append('<circle cx="%.1f" cy="%.1f" r="4" fill="#333"/>' % (hx, hy))
    S.text(L, b.cx + 14, b.y + 22, '\u00abMQTT broker\u00bb', 9.5, 'middle', fill='#555')
    S.text(L, b.cx + 14, b.y + 40, '%s : %s' % (br[0], br[1]), 12, 'middle', 'bold')
    S.text(L, b.cx + 14, b.y + 57, 'eventTopic "%s"' % br[2], 10.5, 'middle', italic=True)


def place_label(S, lines, x1, y1, x2, y2, color, obstacles):
    fs = 9.8
    w = max(tw(l, fs) for l in lines) + 8
    h = 12.5 * len(lines) + 4
    cands = [0.5, 0.38, 0.62, 0.28, 0.72, 0.2, 0.8]
    ln = math.hypot(x2 - x1, y2 - y1) or 1
    px, py = -(y2 - y1) / ln, (x2 - x1) / ln
    best = None
    for k in (0, 1, -1, 2, -2, 3, -3):
        for t in cands:
            d = k * (abs(px) * w + abs(py) * h) * 0.6
            mx, my = x1 + (x2 - x1) * t + px * d, y1 + (y2 - y1) * t + py * d
            bx = Box(mx - w / 2, my - h / 2, w, h)
            if not any(bx.overlaps(o) for o in S.label_boxes + obstacles):
                best = bx; break
        if best: break
    if best is None:
        mx, my = (x1 + x2) / 2, (y1 + y2) / 2
        best = Box(mx - w / 2, my - h / 2, w, h)
    S.label_boxes.append(best)
    # [Claude, Oct 2026] COLORI: etichetta con fondo tenue del colore del messaggio
    S.labels.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" rx="3" fill="%s" fill-opacity="0.95" stroke="%s" stroke-width="0.6"/>'
                    % (best.x, best.y, best.w, best.h, tint(color, 0.9), color))
    for i, l in enumerate(lines):
        S.text(S.labels, best.cx, best.y + 13 + 12.5 * i, l, fs, 'middle', fill=color)


def draw_edge(S, b1, b2, kind, lines, offset, obstacles, diamond=False, both=False):
    color, dash, _ = STYLE[kind]
    mk = S.marker(color)
    x1, y1 = b1.border(b2.cx, b2.cy)
    x2, y2 = b2.border(b1.cx, b1.cy)
    if offset:
        dx, dy = x2 - x1, y2 - y1
        ln = math.hypot(dx, dy) or 1
        ox, oy = -dy / ln * offset, dx / ln * offset
        x1, y1, x2, y2 = x1 + ox, y1 + oy, x2 + ox, y2 + oy
    start = ' marker-start="url(#d%s)"' % mk if diamond else (' marker-start="url(#%s)"' % mk if both else '')
    S.mid.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="%s" stroke-width="1.4"%s%s marker-end="url(#%s)"/>'
                 % (x1, y1, x2, y2, color, ' stroke-dasharray="%s"' % dash if dash else '', start, mk))
    if lines:
        place_label(S, lines, x1, y1, x2, y2, color, obstacles)


def render(m, with_table=True):
    L = build_layout(m)
    if with_table:   # [Claude, Oct 2026] la figura e' larga almeno quanto la tabella dei messaggi
        L.width = max(L.width, message_table_width(m) + 40)
    S = SVG()
    obstacles = [b for b, k, _ in L.nodes.values()]

    # ---------- contesti
    for c, b in L.ctxboxes.items():
        ext = c in L.external
        S.back.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" rx="12" fill="%s" stroke="%s" stroke-width="%s"%s/>'
                      % ((b.x, b.y, b.w, b.h) + FILL['extcontext' if ext else 'context'] +   # [Claude, Oct 2026]
                         (1.2 if ext else 1.6, ' stroke-dasharray="7 4"' if ext else '')))
        ci = m.contexts.get(c, {})
        S.text(S.back, b.x + 14, b.y + 22, 'Context ' + c, 13 if not ext else 12, weight='bold')
        S.text(S.back, b.x + 14, b.y + 38, '%s : %s' % (ci.get('host', '?'), ci.get('port', '?')), 10.5, fill='#333')

    # ---------- canali eventi
    for c, b in L.bands.items():
        S.back.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" rx="6" fill="%s" stroke="%s"/>'
                      % ((b.x, b.y, b.w, b.h) + FILL['evband']))     # [Claude, Oct 2026] COLORI
        S.text(S.back, b.cx, b.y + 21, 'canale degli eventi del contesto %s' % c, 11, 'middle', 'bold', fill='#7a2e00')
        for nm, (blk, row, colr) in L.blocks.items():
            a = m.actors[nm]
            if a['ctx'] != c or not (a['emits'] or a['perceives']):
                continue
            ab = L.nodes[nm][0]
            xr = colr + 14 + 9 * row
            ys = ab.y + ab.h - 14
            col = STYLE['event'][0]
            mk = S.marker(col)
            em, pe = bool(a['emits']), bool(a['perceives'])
            # [Claude, Oct 2026] linea doppia per gli eventi (vedi rail)
            rail(S.mid, [(ab.right(), ys), (xr, ys), (xr, b.y)], col,
                 mk if pe else None, mk if em else None)
        if m.broker and '__broker' in L.nodes and any(
                mode in ('emit', 'publish') for a in m.actors.values() if a['ctx'] == c for _, mode in a['emits']) \
                or (m.broker and any(not emitted_by(m, ev) for ev in perceived_events(m, c))):
            bb = L.nodes['__broker'][0]
            col = STYLE['mqtt'][0]; mk = S.marker(col)
            cb = L.ctxboxes[c]
            xb = cb.right() - 18
            S.mid.append('<polyline points="%.1f,%.1f %.1f,%.1f %.1f,%.1f %.1f,%.1f" fill="none" stroke="%s" stroke-width="1.4" '
                         'stroke-dasharray="4 2" marker-start="url(#%s)" marker-end="url(#%s)"/>'
                         % (b.right(), b.cy, xb, b.cy, xb, bb.cy, bb.x if xb < bb.x else bb.right(), bb.cy, col, mk, mk)
                         if (xb < bb.x or xb > bb.right()) else
                         '<polyline points="%.1f,%.1f %.1f,%.1f %.1f,%.1f" fill="none" stroke="%s" stroke-width="1.4" '
                         'stroke-dasharray="4 2" marker-start="url(#%s)" marker-end="url(#%s)"/>'
                         % (b.right(), b.cy, xb, b.cy, xb, bb.bottom(), col, mk, mk))

    # ---------- composizione / processi
    for parent, cid, kind in L.children:
        pb, cb = L.nodes[parent][0], L.nodes[cid][0]
        if kind == 'proc':      # [Claude, Oct 2026] i POJO non sono piu' figli separati
            color, dash, _ = STYLE['exec']; mk = S.marker(color)
            sx = min(max(cb.cx, pb.x + 20), pb.right() - 20)
            S.mid.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="%s" stroke-width="1.3" stroke-dasharray="%s" marker-end="url(#%s)"/>'
                         % (sx, pb.bottom(), cb.cx, cb.y - 1, color, dash, mk))
            S.text(S.labels, (sx + cb.cx) / 2 + 5, (pb.bottom() + cb.y) / 2 + 4, 'exec', 9.5, fill=color, italic=True)

    # ---------- archi tra attori
    edges = {}   # (src,dst,kind) -> [lines]
    def add(src, dst, kind, line):
        lst = edges.setdefault((src, dst, kind), [])
        if line not in lst: lst.append(line)
    selfl = {}
    for a in m.actors.values():
        s = a['name']
        for d, msg in a['requests']:
            reps = [r for r, md in m.messages.items() if md['kind'] == 'Reply' and md['forr'] == msg]
            line = msg + ('  \u2192 ' + ' | '.join(reps) if reps else '')
            if d == s: selfl.setdefault(s, []).append(line)
            else: add(s, d, 'request', line)
        for d, msg in a['forwards']:
            if d == s: selfl.setdefault(s, []).append(msg)
            else: add(s, d, 'dispatch', msg)
        for msg in a['autodisp']:
            selfl.setdefault(s, []).append(msg)
        for d, msg in a['delegates']:
            if d in ('*current*',): continue
            add(s, d, 'delegate', 'delegate ' + msg)
        for res in a['observes']:
            add(s, res, 'observe', 'observe')
        for wid, ws in m.webservices.items():
            if s in ws['users']:
                add(s, wid, 'http', 'HTTP')

    done = set()
    for (src, dst, kind), lines in edges.items():
        if src not in L.nodes or dst not in L.nodes:
            continue
        b1, b2 = L.nodes[src][0], L.nodes[dst][0]
        rev = [k for k in edges if k[0] == dst and k[1] == src]
        same = [k for k in edges if k[0] == src and k[1] == dst]
        idx = same.index((src, dst, kind))
        off = (idx - (len(same) - 1) / 2) * 16
        if rev:
            off += 10 if src < dst else -10
        draw_edge(S, b1, b2, kind, lines, off, obstacles)

    for s, lines in selfl.items():
        b = L.nodes[s][0]
        col = STYLE['dispatch'][0]; mk = S.marker(col)
        x0, x1 = b.right() - 70, b.right() - 30
        S.mid.append('<path d="M%.1f,%.1f C%.1f,%.1f %.1f,%.1f %.1f,%.1f" fill="none" stroke="%s" stroke-width="1.3" '
                     'stroke-dasharray="7 4" marker-end="url(#%s)"/>' % (x0, b.y, x0, b.y - 30, x1, b.y - 30, x1, b.y - 1, col, mk))
        txt = 'self: ' + ', '.join(l.split('  ')[0] for l in lines)
        S.text(S.labels, (x0 + x1) / 2, b.y - 34, trunc(txt, 60), 9.5, 'middle', fill=col, italic=True)

    # ---------- nodi
    for nid, (b, kind, d) in L.nodes.items():
        if kind == 'actor': draw_actor(S, b, d)
        elif kind == 'proc': draw_proc(S, b, d)
        elif kind == 'webservice': draw_webservice(S, b, d)
        elif kind == 'broker': draw_broker(S, b, d)
        elif kind == 'unknown':
            S.front.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" rx="9" fill="#fff" stroke="#999" stroke-dasharray="3 3"/>'
                           % (b.x, b.y, b.w, b.h))
            S.text(S.front, b.cx, b.y + 26, '\u00abnon dichiarato\u00bb', 9.5, 'middle', fill='#777')
            S.text(S.front, b.cx, b.y + 45, d['name'], 13, 'middle', 'bold', '#555')

    # ---------- legenda + tabella
    y = L.diagram_bottom + 50
    used_kinds = {k for (_, _, k) in edges} | ({'dispatch'} if selfl else set())
    if L.bands: used_kinds.add('event')
    if any(k == 'proc' for _, k, _ in L.nodes.values()): used_kinds.add('exec')
    if m.broker: used_kinds.add('mqtt')
    y = draw_legend(S, m, L, y, used_kinds)
    if with_table:
        y = draw_message_table(S, m, y + 30, L.width)    # [Claude, Oct 2026] tabella dei messaggi
        y = draw_event_table(S, m, y + 30, L.width)
    H = y + 30

    title = '<text x="20" y="34" font-size="19" font-weight="bold" fill="#111">System %s</text>' % esc(m.name)
    return ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w:.0f} {h:.0f}" width="{w:.0f}" height="{h:.0f}" '
            'font-family="Helvetica, Arial, sans-serif">\n<defs>{defs}</defs>\n<rect width="100%" height="100%" fill="#fff"/>\n'
            '{title}\n{back}\n{mid}\n{front}\n{labels}\n</svg>\n').format(
        w=L.width, h=H, defs=''.join(S.defs), title=title, back='\n'.join(S.back), mid='\n'.join(S.mid),
        front='\n'.join(S.front), labels='\n'.join(S.labels))


def emitted_by(m, ev):
    return [(a['name'], mode) for a in m.actors.values() for e, mode in a['emits'] if e == ev]


def perceived_events(m, ctx):
    return {e for a in m.actors.values() if a['ctx'] == ctx for e, _ in a['perceives']}


def draw_legend(S, m, L, y, used):
    L_ = S.front
    items_sym = [('actor', '\u00abQActor\u00bb: mailbox + automa a stati')]
    if any(a['pojos'] for a in m.actors.values()):        # [Claude, Oct 2026] POJO locali
        items_sym.append(('pojo', 'POJO locale al QActor (withobj)'))
    if any(a['kind'] == 'CodedQActor' for a in m.actors.values()): items_sym.append(('coded', '\u00abCodedQActor\u00bb'))
    if any(a['kind'] == 'ExternalQActor' for a in m.actors.values()): items_sym.append(('ext', '\u00abExternalQActor\u00bb'))
    if any(a.get('hidden') for a in m.actors.values()):   # [Claude, Oct 2026] HIDDEN QActor
        items_sym.append(('hidden', '\u00abQActor hidden\u00bb: invocabile solo dal suo contesto'))
    if m.webservices or any(a.get('webservice') for a in m.actors.values()): items_sym.append(('ws', '\u00abWebService\u00bb'))
    if any(a['procs'] for a in m.actors.values()): items_sym.append(('proc', '\u00abOS process\u00bb'))
    kinds = [k for k in STYLE if k in used]
    rows = max(len(items_sym), len(kinds))
    h = 36 + 26 * rows
    w = min(L.width - 40, 1000)
    L_.append('<rect x="20" y="%.1f" width="%.1f" height="%.1f" rx="6" fill="#fff" stroke="#999"/>' % (y, w, h))
    S.text(L_, 34, y + 22, 'Legenda', 12, weight='bold')
    for i, (k, lab) in enumerate(items_sym):
        yy = y + 40 + 26 * i
        x = 36
        if k in ('actor', 'coded', 'ext', 'hidden'):   # 'hidden': [Claude, Oct 2026] HIDDEN QActor
            fl, st = FILL[{'actor': 'QActor', 'hidden': 'QActor', 'coded': 'CodedQActor',
                           'ext': 'ExternalQActor'}[k]]          # [Claude, Oct 2026] COLORI
            L_.append('<rect x="%s" y="%.1f" width="46" height="20" rx="4" fill="%s" stroke="%s"%s/>'
                      % (x, yy - 13, fl, st,
                         ' stroke-dasharray="4 3"' if k == 'ext' else (' stroke-dasharray="2 2"' if k == 'hidden' else '')))
            for j in range(2):
                L_.append('<rect x="%s" y="%.1f" width="7" height="5" fill="#fff" stroke="#444" stroke-width="0.7"/>' % (x + 4, yy - 10 + j * 6.5))
            if k == 'coded':
                S.text(L_, x + 32, yy + 1, '{}', 10, 'middle', 'bold', mono=True)
            else:
                L_.append('<circle cx="%s" cy="%.1f" r="3" fill="#fff" stroke="#333"/><circle cx="%s" cy="%.1f" r="3" fill="#333"/>'
                          % (x + 26, yy - 3, x + 38, yy - 3))
        elif k == 'pojo':       # [Claude, Oct 2026] POJO locali: icona con nome
            L_.append('<rect x="%s" y="%.1f" width="46" height="20" rx="5" fill="%s" stroke="%s"/>'
                      % ((x, yy - 13) + FILL['pojo']))
            pojo_icon(L_, x + 5, yy - 9)
            S.text(L_, x + 19, yy + 1, 'obj', 9.5, weight='bold', fill='#3d2e00')
        elif k == 'ws':
            L_.append('<rect x="%s" y="%.1f" width="46" height="20" rx="9" fill="%s" stroke="%s"/>' % ((x, yy - 13) + FILL['webservice']))
            draw_globe(L_, x + 12, yy - 3, 7)
        elif k == 'proc':
            L_.append('<path d="M%s,%.1f h40 l6,6 v14 h-46 z" fill="%s" stroke="%s"/>' % ((x, yy - 13) + FILL['proc']))
        S.text(L_, x + 58, yy + 1, lab, 10.5)
    x0 = 420
    for i, k in enumerate(kinds):
        color, dash, lab = STYLE[k]
        yy = y + 40 + 26 * i - 4
        mk = S.marker(color)
        if dash == 'rail':      # [Claude, Oct 2026] eventi: linea doppia
            rail(L_, [(x0, yy), (x0 + 60, yy)], color, None, mk)
        else:
            L_.append('<line x1="%s" y1="%.1f" x2="%s" y2="%.1f" stroke="%s" stroke-width="1.4"%s marker-end="url(#%s)"/>'
                      % (x0, yy, x0 + 60, yy, color, ' stroke-dasharray="%s"' % dash if dash else '', mk))
        S.text(L_, x0 + 72, yy + 4, lab, 10.5)
    return y + h


def message_rows(m):
    """[Claude, Oct 2026] Per ogni messaggio (non evento) dichiarato:
    (nome, firma, tipo, for, mittenti, riceventi)."""
    order = ['Dispatch', 'Request', 'Reply', 'Signal', 'Token', 'Invitation']
    rows = []
    for kind in order:
        for name, md in m.messages.items():
            if md['kind'] != kind:
                continue
            snd, rcv = [], []
            add = lambda lst, v: lst.append(v) if v not in lst else None
            for a in m.actors.values():
                s = a['name']
                for d, msg in a['forwards'] + a['requests']:
                    if msg == name: add(snd, '%s \u2192 %s' % (s, d))
                if name in a['autodisp']: add(snd, '%s (auto)' % s)
                for req, rep in a['replies']:
                    if rep == name: add(snd, s)
                if name in a.get('inmsgs', []) or name in a.get('inreplies', []):
                    add(rcv, s)
                for d, msg in a['delegates']:
                    if msg == name and d != '*current*': add(rcv, '%s (delegato da %s)' % (d, s))
            rows.append((name, md['sig'], kind, md.get('forr'), snd, rcv))
    return rows


def message_cells(row):
    """[Claude, Oct 2026] Testi delle celle di una riga della tabella dei messaggi."""
    name, sig, kind, forr, snd, rcv = row
    s_txt = ', '.join(snd) if snd else '\u2014 esterno al modello'
    if rcv:
        r_txt = ', '.join(rcv)
    else:
        r_txt = '\u2014 chiamante (anche esterno al modello)' if kind == 'Reply' else '\u2014 nessun attore del modello'
    return [name + (' : ' + sig if sig else ''), kind + (' for %s' % forr if forr else ''), s_txt, r_txt]


MSG_COL_CAP = [330, 230, 560, 560]   # [Claude, Oct 2026] larghezza massima (px) delle colonne


def message_col_widths(m):
    """[Claude, Oct 2026] Larghezze delle colonne calcolate dal contenuto (con tetto)."""
    heads = ['Messaggio', 'Tipo', 'Inviato da (mittente \u2192 destinatario)', 'Ricevuto da']
    ws = [tw(h, 10.5) + 18 for h in heads]
    for row in message_rows(m):
        for i, c in enumerate(message_cells(row)):
            ws[i] = max(ws[i], min(tw(c, 10.5) + 18, MSG_COL_CAP[i]))
    return ws


def message_table_width(m):
    return 30 + sum(message_col_widths(m)) if message_rows(m) else 0


def draw_message_table(S, m, y, W):
    """[Claude, Oct 2026] Tabella dei messaggi del sistema (analoga a quella degli eventi)."""
    rows = message_rows(m)
    if not rows:
        return y
    L_ = S.front
    S.text(L_, 20, y, 'Messaggi: chi li invia e chi li riceve', 13, weight='bold')
    y += 10
    rh = 18
    W = W - 40
    # colonne dimensionate sul contenuto; l'ultima si allarga fino al bordo
    cols = [20, 50]
    for wcol in message_col_widths(m)[:-1]:
        cols.append(cols[-1] + wcol)
    cols.append(20 + W)
    cap = lambda i: max(8, int((cols[i + 1] - cols[i] - 10) / (10.5 * 0.56)))
    L_.append('<rect x="20" y="%.1f" width="%.1f" height="20" fill="#ececec" stroke="#999"/>' % (y, W))
    for x, t in zip(cols, ['#', 'Messaggio', 'Tipo', 'Inviato da (mittente \u2192 destinatario)', 'Ricevuto da']):
        S.text(L_, x + 8 if t == '#' else x, y + 14, t, 10.5, weight='bold')
    y0 = y
    y += 20
    for i, (name, sig, kind, forr, snd, rcv) in enumerate(rows):
        color = MSGCOLOR.get(kind, '#555555')
        top = y + rh * i
        L_.append('<rect x="20" y="%.1f" width="%.1f" height="%s" fill="%s"/>' % (top, W, rh, tint(color, 0.93)))
        yy = top + 13
        S.text(L_, cols[0] + 8, yy, str(i + 1), 10.5)
        m_txt, k_txt, s_txt, r_txt = message_cells((name, sig, kind, forr, snd, rcv))
        S.text(L_, cols[1], yy, trunc(m_txt, cap(1)), 10.5)
        S.text(L_, cols[2], yy, trunc(k_txt, cap(2)), 10.5, weight='bold', fill=color)
        S.text(L_, cols[3], yy, trunc(s_txt, cap(3)), 10.5, fill='#111' if snd else '#8a1c1c')
        S.text(L_, cols[4], yy, trunc(r_txt, cap(4)), 10.5,
               fill='#111' if rcv else ('#555' if kind == 'Reply' else '#8a1c1c'))
    y += rh * len(rows) + 4
    L_.append('<rect x="20" y="%.1f" width="%.1f" height="%.1f" fill="none" stroke="#999"/>' % (y0, W, y - y0))
    return y


def draw_event_table(S, m, y, W):
    evs = []
    for name, md in m.messages.items():
        if md['kind'] != 'Event': continue
        em = emitted_by(m, name)
        pe = [(a['name'], k) for a in m.actors.values() for e, k in a['perceives'] if e == name]
        if em or pe:
            evs.append((name, md['sig'], em, pe))
    # eventi usati ma non dichiarati
    declared = set(m.messages)
    for a in m.actors.values():
        for e, _ in a['emits'] + a['perceives']:
            if e not in declared and e not in [x[0] for x in evs]:
                evs.append((e + ' (non dichiarato)', '', emitted_by(m, e),
                            [(b['name'], k) for b in m.actors.values() for ee, k in b['perceives'] if ee == e]))
    if not evs:
        return y
    L_ = S.front
    S.text(L_, 20, y, 'Eventi: chi li emette e chi li percepisce', 13, weight='bold')
    y += 10
    rh = 18
    W = W - 40
    cols = [20, 50, 20 + W * 0.30, 20 + W * 0.58]
    L_.append('<rect x="20" y="%.1f" width="%.1f" height="20" fill="#ececec" stroke="#999"/>' % (y, W))
    for x, t in zip(cols, ['#', 'Evento', 'Emesso da (modalit\u00e0)', 'Percepito da']):
        S.text(L_, x + 8 if t == '#' else x, y + 14, t, 10.5, weight='bold')
    y0 = y
    y += 20
    for i, (name, sig, em, pe) in enumerate(evs):
        # [Claude, Oct 2026] COLORI: righe con il colore (tenue) degli eventi
        L_.append('<rect x="20" y="%.1f" width="%.1f" height="%s" fill="%s"/>' % (y + rh * i, W, rh, tint(MSGCOLOR['Event'], 0.93)))
        yy = y + rh * i + 13
        S.text(L_, cols[0] + 8, yy, str(i + 1), 10.5)
        S.text(L_, cols[1], yy, trunc(name + (' : ' + sig if sig else ''), 52), 10.5)
        e_txt = ', '.join('%s (%s)' % x for x in em) if em else '\u2014 esterno al modello (es. via MQTT)'
        p_txt = ', '.join('%s%s' % (n, '' if k == 'whenEvent' else ' (%s)' % k) for n, k in pe) if pe else '\u2014 nessun attore del modello'
        S.text(L_, cols[2], yy, trunc(e_txt, 60), 10.5, fill='#111' if em else '#8a1c1c')
        S.text(L_, cols[3], yy, trunc(p_txt, 80), 10.5, fill='#111' if pe else '#8a1c1c')
    y += rh * len(evs) + 4
    L_.append('<rect x="20" y="%.1f" width="%.1f" height="%.1f" fill="none" stroke="#999"/>' % (y0, W, y - y0))
    return y


# =====================================================================
# 5. MAIN
# =====================================================================

def main(argv=None):
    ap = argparse.ArgumentParser(description='Genera la figura architetturale (SVG) di modelli qak.')
    ap.add_argument('files', nargs='+', help='file .qak (anche pattern glob)')
    ap.add_argument('-o', '--out', help='file SVG di uscita (solo con un unico modello)')
    ap.add_argument('--no-table', action='store_true', help='non generare la tabella degli eventi')
    ap.add_argument('--png', action='store_true', help='genera anche PNG (richiede cairosvg)')
    ap.add_argument('--dump', action='store_true', help='stampa il modello estratto (debug)')
    args = ap.parse_args(argv)

    files = []
    for f in args.files:
        files += glob.glob(f) or [f]
    for f in files:
        with open(f, encoding='utf-8', errors='replace') as fh:
            m = parse(fh.read())
        if args.dump:
            import pprint
            pprint.pprint(dict(name=m.name, broker=m.broker, contexts=m.contexts,
                               actors=m.actors, webservices=m.webservices))
        svg = render(m, with_table=not args.no_table)
        out = args.out if (args.out and len(files) == 1) else os.path.splitext(f)[0] + '_arch.svg'
        with open(out, 'w', encoding='utf-8') as fh:
            fh.write(svg)
        print('%s -> %s' % (f, out))
        if args.png:
            try:
                import cairosvg
                cairosvg.svg2png(url=out, write_to=os.path.splitext(out)[0] + '.png', output_width=None)
                print('   + PNG')
            except ImportError:
                print('   (PNG non generato: pip install cairosvg)')


if __name__ == '__main__':
    main()
