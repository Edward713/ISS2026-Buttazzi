r"""Architettura Sprint1, nello stesso formato diagrams dello script Arch_sistemasqak.py.

Eseguire: python Arch_cargoservice_term.py
Preparazione locale delle dipendenze: .\scripts\generate-architecture.ps1 -Setup
"""

from pathlib import Path
import os
import shutil
import sys
import base64
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parent
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
    from diagrams import Cluster, Diagram, Edge
    from diagrams.custom import Custom
except ImportError as error:
    raise SystemExit("Manca diagrams. Eseguire .\\scripts\\generate-architecture.ps1 -Setup") from error
if not shutil.which("dot"):
    raise SystemExit("Manca Graphviz. Eseguire .\\scripts\\generate-architecture.ps1 -Setup")

ICONS = ROOT / "qakicons"
OUTPUT = ROOT / "docs" / "architecture"
OUTPUT.mkdir(parents=True, exist_ok=True)

graphattr = {
    "fontname": "Arial", "fontsize": "22", "pad": "0.6", "nodesep": "0.9",
    "ranksep": "1.2", "splines": "spline", "bgcolor": "white",
    "labelloc": "t", "dpi": "150",
}
nodeattr = {"fontname": "Arial", "fontsize": "16"}
clusterattr = {"fontname": "Arial", "fontsize": "17", "bgcolor": "#edf2f7", "margin": "24"}


def request_label(request, replies):
    """Magenta = richiesta, verde = risposte sulla stessa relazione."""
    return f'<<FONT COLOR="magenta">{request}</FONT><BR/><FONT COLOR="darkgreen">{replies}</FONT>>'


with Diagram(
    "CargoService - Sprint 1",
    filename=str(OUTPUT / "cargoservice_sprint1"),
    show=False,
    outformat=["png", "svg"],
    direction="LR",
    graph_attr=graphattr,
    node_attr=nodeattr,
    edge_attr={"fontname": "Arial", "fontsize": "14", "arrowsize": "0.8"},
) as diag:
    with Cluster("env", graph_attr={"bgcolor": "#fafafa", "fontsize": "20"}):
        system = Custom("Pulsante / simulatore sonar", str(ICONS / "system.PNG"))

        with Cluster("ctxioport : 8022", graph_attr=clusterattr):
            ioportservice = Custom("ioportservice", str(ICONS / "symActorWithobjSmall.png"))
        with Cluster("ctxcargoservice : 8020", graph_attr=clusterattr):
            cargoservice = Custom("cargoservice", str(ICONS / "symActorWithobjSmall.png"))
        with Cluster("ctxsensor : 8023", graph_attr=clusterattr):
            sensorservice = Custom("sensorservice", str(ICONS / "symActorWithobjSmall.png"))
        with Cluster("ctxcargorobot : 8021", graph_attr=clusterattr):
            cargorobot = Custom("cargorobot", str(ICONS / "symActorWithobjSmall.png"))
        with Cluster("ctxrobotsmart : 8019", graph_attr={**clusterattr, "bgcolor": "#fff2de"}):
            robotsmart = Custom("robotsmart\nExternalQActor", str(ICONS / "externalQActor.png"))

        system >> Edge(color="blue", fontcolor="blue", label="button_pressed") >> ioportservice
        system >> Edge(color="red", fontcolor="red", style="dotted", label="sonar_sample(D)") >> sensorservice

        ioportservice >> Edge(
            color="magenta", label=request_label("load_request", "load_accepted / retrylater / load_refused")
        ) >> cargoservice
        cargoservice >> Edge(color="blue", fontcolor="blue", label="display_update(DATA)", constraint="false") >> ioportservice

        sensorservice >> Edge(color="blue", fontcolor="blue", label="sensor_state(present | free)") >> cargoservice
        cargoservice >> Edge(color="blue", fontcolor="blue", label="led_command(blink | off)", constraint="false") >> sensorservice

        cargoservice >> Edge(
            color="magenta", label=request_label("reach_target(TARGET)", "target_reached / target_failed")
        ) >> cargorobot
        cargorobot >> Edge(
            color="magenta", label=request_label("moverobot(X,Y,STEPTIME)", "moverobotdone / moverobotfailed / failed")
        ) >> robotsmart

    diag.dot.attr(
        label="CargoService - Sprint 1\nMagenta: request/reply (risposte in verde)   |   Blu: dispatch   |   Rosso puntinato: event"
    )

# Mantiene anche il sorgente DOT ispezionabile, oltre alle due immagini.
(OUTPUT / "cargoservice_sprint1.dot").write_text(diag.dot.source, encoding="utf-8")
# SVG autonomo: incorpora le icone PNG invece di dipendere da percorsi del PC.
svg = OUTPUT / "cargoservice_sprint1.svg"
ET.register_namespace("", "http://www.w3.org/2000/svg")
ET.register_namespace("xlink", "http://www.w3.org/1999/xlink")
tree = ET.parse(svg)
href_key = "{http://www.w3.org/1999/xlink}href"
for element in tree.iter("{http://www.w3.org/2000/svg}image"):
    icon = Path(element.get(href_key, ""))
    if icon.is_file():
        element.set(href_key, "data:image/png;base64," + base64.b64encode(icon.read_bytes()).decode("ascii"))
tree.write(svg, encoding="utf-8", xml_declaration=True)
print(f"PNG: {OUTPUT / 'cargoservice_sprint1.png'}")
print(f"SVG: {OUTPUT / 'cargoservice_sprint1.svg'}")
