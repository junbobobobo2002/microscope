from microscope.device_server import device
from microscope.cameras.pco import pcoPandaCamera
from microscope.lights.coboltskyra import CoboltSkyra
host = "127.0.0.1"

DEVICES = [
    # device(pcoPandaCamera, host=host, port=7701),
    device(CoboltSkyra, host=host, port=7702, conf={"com": "COM4"})
]

# [pco camera]
# type: cockpit.devices.microscopeCamera.MicroscopeCamera
# uri: PYRO:pcoPandaCamera@127.0.0.1:7701
