"""Diagnostica minima: server trame + PyVista con una singola sfera
colorata, niente satellite/DEM. Se questo non mostra nulla nel browser,
il problema e' nella base (trame+PyVista+il tuo sistema), non nella
logica dell'app 3D+satellite.

Uso:
    python -m scripts.diagnose_trame_minimal
"""
import pyvista as pv
from pyvista.trame.ui import plotter_ui
from trame.app import get_server
from trame.ui.vuetify3 import SinglePageLayout
from trame.widgets import vuetify3

print("1. Creo il plotter PyVista...")
plotter = pv.Plotter(off_screen=True, window_size=[1000, 700])
plotter.add_mesh(pv.Sphere(), color="red")
plotter.add_mesh(pv.Cube(center=(3, 0, 0)), color="blue")
plotter.camera_position = "iso"
plotter.set_background("white")
# Forza un render esplicito PRIMA di avvolgere il plotter nel widget
# trame: se il render window VTK non è mai stato inizializzato una prima
# volta, il widget può montarsi correttamente ma non avere mai
# un'immagine valida da mostrare.
plotter.render()
print("   OK")

import pyvista, vtk
from importlib.metadata import version as pkg_version
print(f"\n   Versioni: pyvista={pyvista.__version__}  vtk={vtk.VTK_VERSION}  "
      f"trame={pkg_version('trame')}  trame-vtk={pkg_version('trame-vtk')}  "
      f"trame-vuetify={pkg_version('trame-vuetify')}")

print("2. Provo uno screenshot off-screen (verifica che il rendering di base funzioni)...")
plotter.screenshot("diagnose_screenshot.png")
import os
print(f"   OK — screenshot salvato in diagnose_screenshot.png ({os.path.getsize('diagnose_screenshot.png')} bytes)")
print("   Apri questo file: se vedi una sfera rossa e un cubo blu, il rendering di base funziona.")

print("3. Creo il server trame...")
server = get_server("diagnose", client_type="vue3")
ctrl = server.controller
print("   OK")

print("4. Costruisco il layout...")
with SinglePageLayout(server) as layout:
    layout.title.set_text("Diagnostica minima")
    with layout.content:
        with vuetify3.VContainer(fluid=True, style="height: 500px;"):
            view = plotter_ui(plotter, mode="server")
            ctrl.view_update = view.update
print("   OK")

@ctrl.on_server_ready.add
def _initial_render(**kwargs):
    print("   >>> Client connesso, forzo il render iniziale <<<")
    ctrl.view_update()

print("\n5. Avvio il server. Apri http://localhost:8080 nel browser.")
print("   Se vedi 'Client connesso' apparire qui sotto quando apri la pagina,")
print("   la connessione funziona; se la vista resta comunque bianca, il")
print("   problema e' nel trasferimento dell'immagine renderizzata al browser.\n")
server.start(open_browser=True)
