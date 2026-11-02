r"""Architettura Sprint 2, nello stesso formato diagrams dello Sprint 1.

Eseguire: python src/Arch_cargoservice_term.py (diagrams 0.25.1 e Graphviz).
Produce SVG autonomo, PNG e DOT nella stessa cartella dello script.
Il diagramma esplicita anche i collegamenti implementati nei blocchi Kotlin
e negli adattatori, non individuati dal solo parsing della sintassi QAK.
"""

from pathlib import Path
import os
import shutil
import sys
import base64
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
LOCAL_PACKAGES = ROOT / "build" / "architecture-python"
if LOCAL_PACKAGES.exists():
    sys.path.insert(0, str(LOCAL_PACKAGES))

# Graphviz puo essere installato nel sistema oppure estratto localmente dal setup.
if not shutil.which("dot"):
    candidates = [Path("C:/Program Files/Graphviz/bin")]
    candidates.extend(path.parent for path in (ROOT / "build" / "architecture-tools").glob("**/dot.exe"))
    for directory in candidates:
        if (directory / "dot.exe").is_file():
            os.environ["PATH"] = str(directory) + os.pathsep + os.environ.get("PATH", "")
            break

try:
    from diagrams import Cluster, Diagram, Edge, Node
    from diagrams.custom import Custom
except ImportError as error:
    raise SystemExit("Manca diagrams: installare diagrams==0.25.1 oppure impostare PYTHONPATH sulle dipendenze locali.") from error
if not shutil.which("dot"):
    raise SystemExit("Manca Graphviz: aggiungere la cartella contenente dot al PATH.")

ICONS = ROOT / "qakicons"
OUTPUT = Path(__file__).resolve().parent
OUTPUT.mkdir(parents=True, exist_ok=True)

graphattr = {
    "fontname": "Arial", "fontsize": "22", "pad": "0.5", "nodesep": "0.6",
    "ranksep": "0.9", "splines": "spline", "bgcolor": "white",
    "labelloc": "t", "dpi": "150",
}
nodeattr = {"fontname": "Arial", "fontsize": "14"}
clusterattr = {"fontname": "Arial", "fontsize": "15", "bgcolor": "#edf2f7", "margin": "20"}
plainattr = {"fixedsize": "false", "labelloc": "c", "width": "1.9", "height": "0.9", "margin": "0.16"}


def request_label(request, replies):
    """Magenta = richiesta, verde = risposte sulla stessa relazione."""
    return f'<<FONT COLOR="magenta">{request}</FONT><BR/><FONT COLOR="darkgreen">{replies}</FONT>>'


with Diagram(
    "CargoService - Sprint 2",
    filename=str(OUTPUT / "Arch_cargoservice_term"),
    show=False,
    outformat=["png", "svg"],
    direction="LR",
    graph_attr=graphattr,
    node_attr=nodeattr,
    edge_attr={"fontname": "Arial", "fontsize": "12", "arrowsize": "0.8"},
) as diag:
    browser = Node("Browser\nIOPort web-GUI", shape="box", style="rounded,filled", fillcolor="#e7f4e4", **plainattr)
    device = Node("Pico W esterno\nSonar + LED\noppure simulatore MQTT", shape="box", style="rounded,filled", fillcolor="#fff2de", **plainattr)
    with Cluster("Nodo applicativo - PC", graph_attr={"bgcolor": "#fafafa", "fontsize": "20"}):
        backend = Node("Adattatore web\nHTTP / WebSocket :8080", shape="box", style="rounded,filled", fillcolor="#e7f4e4", **plainattr)
        mqtt = Node("Broker MQTT\nMosquitto :1883", shape="cylinder", style="filled", fillcolor="#fff2de", **plainattr)
        with Cluster("ctxioport : 8022", graph_attr=clusterattr):
            ioportservice = Custom("ioportservice", str(ICONS / "symActorWithobjSmall.png"))
        with Cluster("ctxcargoservice : 8020", graph_attr=clusterattr):
            cargoservice = Custom("cargoservice", str(ICONS / "symActorWithobjSmall.png"))
        with Cluster("ctxsensor : 8023", graph_attr=clusterattr):
            sensorservice = Custom("sensorservice", str(ICONS / "symActorWithobjSmall.png"))
        with Cluster("ctxcargorobot : 8021", graph_attr=clusterattr):
            cargorobot = Custom("cargorobot", str(ICONS / "symActorWithobjSmall.png"))
    with Cluster("Navigazione esterna", graph_attr={"bgcolor": "#fff9ed", "fontsize": "18"}):
        with Cluster("ctxrobotsmart : 8019", graph_attr={**clusterattr, "bgcolor": "#fff2de"}):
            robotsmart = Custom("robotsmart\nExternalQActor", str(ICONS / "externalQActor.png"))
        wenv = Node("WEnv\nHTTP :8090 / WS :8091", shape="box", style="rounded,filled", fillcolor="#fff2de", **plainattr)

    browser >> Edge(color="#555555", fontcolor="#555555", reverse=True, label="POST /api/load\nWS /ws/state") >> backend
    backend >> Edge(color="magenta", label=request_label("load_request / get_ioport_status", "esito carico / ioport_status")) >> ioportservice

    ioportservice >> Edge(color="magenta", label=request_label("load_request", "load_accepted / retrylater / load_refused")) >> cargoservice
    ioportservice >> Edge(color="magenta", label=request_label("get_hold_status", "hold_state(DATA)"), constraint="false") >> cargoservice
    cargoservice >> Edge(color="blue", fontcolor="blue", label="display_update(DATA)", constraint="false") >> ioportservice

    device >> Edge(color="#b86100", fontcolor="#b86100", style="dashed", label="cargo/picow/sonar\nQoS 0, non retained") >> mqtt
    mqtt >> Edge(color="#b86100", fontcolor="#b86100", style="dashed", label="misure JSON", minlen="1") >> sensorservice
    sensorservice >> Edge(color="#b86100", fontcolor="#b86100", style="dashed", label="cargo/picow/led/set\nQoS 1, retained", constraint="false") >> mqtt
    mqtt >> Edge(color="#b86100", fontcolor="#b86100", style="dashed", label="mode: blink / off", constraint="false") >> device

    sensorservice >> Edge(color="blue", fontcolor="blue", label="sensor_state(free | present | anomaly)\nsensor_unavailable(none)") >> cargoservice
    cargoservice >> Edge(color="blue", fontcolor="blue", label="led_command(blink | off)", constraint="false") >> sensorservice

    cargoservice >> Edge(color="magenta", label=request_label("reach_target(TARGET)", "target_reached / target_failed")) >> cargorobot
    cargorobot >> Edge(color="magenta", label=request_label("moverobot(X,Y,STEPTIME)", "moverobotdone / moverobotfailed / failed")) >> robotsmart
    robotsmart >> Edge(color="#555555", fontcolor="#555555", reverse=True, label="comandi / esiti\nWebSocket") >> wenv

    diag.dot.attr(
        label="CargoService - Sprint 2\nMagenta: request/reply (risposte in verde) | Blu: dispatch QAK | Arancione tratteggiato: MQTT | Grigio: HTTP/WS"
    )

# Mantiene anche il sorgente DOT ispezionabile, oltre alle due immagini.
(OUTPUT / "Arch_cargoservice_term.dot").write_text(diag.dot.source, encoding="utf-8")
# SVG autonomo: incorpora le icone PNG invece di dipendere da percorsi del PC.
svg = OUTPUT / "Arch_cargoservice_term.svg"
ET.register_namespace("", "http://www.w3.org/2000/svg")
ET.register_namespace("xlink", "http://www.w3.org/1999/xlink")
tree = ET.parse(svg)
href_key = "{http://www.w3.org/1999/xlink}href"
for element in tree.iter("{http://www.w3.org/2000/svg}image"):
    icon = Path(element.get(href_key, ""))
    if icon.is_file():
        element.set(href_key, "data:image/png;base64," + base64.b64encode(icon.read_bytes()).decode("ascii"))
tree.write(svg, encoding="utf-8", xml_declaration=True)
print(f"PNG: {OUTPUT / 'Arch_cargoservice_term.png'}")
print(f"SVG: {svg}")
