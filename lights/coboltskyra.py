import logging

import serial
import time
import Pyro4
import microscope._utils
import microscope.abc

LASER_1 = 532
LASER_2 = 638
LASER_3 = 488
LASER_4 = 405

_logger = logging.getLogger(__name__)
_logger.setLevel(logging.INFO)

@Pyro4.expose
class CoboltSkyra(
    microscope._utils.OnlyTriggersBulbOnSoftwareMixin,
    microscope.abc.SerialDeviceMixin,
    microscope.abc.LightSource,
):
    """Cobolt Skyra.

    Cobolt Skyra™ is an extremely compact, permanently aligned, plug & play, 
    multi-line laser with up to 4 laser lines and control electronics integrated
    into one single, temperature-controlled package, small enough to fit in the 
    palm of your hand!

    """

    def __init__(self, com=None, baud=115200, timeout=0.1, **kwargs):
        super().__init__(**kwargs)
        self.wavelength_to_output = {LASER_1: 1, LASER_2: 2, LASER_3: 3, LASER_4: 4}
        self.current_wavelength = None  # Track the current wavelength being controlled
        self._max_power_mw = 120

        self.connection = serial.Serial(
            port=com,
            baudrate=baud,
            timeout=timeout,
            stopbits=serial.STOPBITS_ONE,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
        )
        # Start a logger.
        response = self.send(b"sn?")
        _logger.info("Cobolt laser serial number: [%s]", response.decode())
        # We need to ensure that autostart is disabled so that we can switch emission
        # on/off remotely.
        response = self.send(b"@cobas 0")
        _logger.info("Response to @cobas 0 [%s]", response.decode())

        self.initialize()

    def send(self, command):
        """Send command and retrieve response."""
        success = False
        while not success:
            self._write(command)
            response = self._readline()
            # Catch zero-length responses to queries and retry.
            # if not command.endswith(b"?"):
            #     success = True
            # elif len(response) > 0:
            #     success = True
            if len(response) > 0:
                success = True
        return response

    @microscope.abc.SerialDeviceMixin.lock_comms
    def clearFault(self):
        self.send(b"cf")
        return self.get_status()

    @microscope.abc.SerialDeviceMixin.lock_comms
    def get_status(self):
        result = []
        for cmd, stat in [
            (b"?", "Laser Status:"),
            (b"gom?", "Operating Mode:"),
            (b"@cobasks?", "Key Switch State:"),
            (b"f?", "Fault?"),
            (b"hrs?", "Head operating hours:"),
        ]:
            response = self.send(cmd)
            result.append(stat + " " + response.decode())
        return result

    def _do_shutdown(self) -> None:
        # Disable laser.
        self.send(b"@cob0")
        self.connection.flushInput()

    #  Initialization to do when cockpit connects.
    @microscope.abc.SerialDeviceMixin.lock_comms
    def initialize(self):
        self.connection.flushInput()
        # We don't want 'direct control' mode.
        self.send(b"@cob1")
        # Force laser into autostart mode.
        self.send(b"@cob0")

    def enable(self, wavelength=None) -> None:
        """Enable the laser at a specific wavelength."""
        try:
            self.enabled = self._do_enable(wavelength=wavelength)
        except Exception as err:
            _logger.debug(f"Error in _do_enable with wavelength {wavelength}: ", exc_info=err)
    
    # Turn the laser ON. Return True if we succeeded, False otherwise.
    @microscope.abc.SerialDeviceMixin.lock_comms
    def _do_enable(self, wavelength=None):
        if wavelength is None:
            _logger.error("Wavelength not specified.")
            return False
        if wavelength not in self.wavelength_to_output:
            _logger.error(f"In enable(): Wavelength {wavelength} not supported.")
            return False
        
        output_number = self.wavelength_to_output[wavelength]
        command = f"{output_number}l1".encode() # Converts to bytes using default UTF-8 encoding
        response = self.send(command)
        _logger.info(f"Attempt to enable laser for wavelength {wavelength} nm. Response: {response.decode()}")
        time.sleep(1)
        if not self.get_is_on(output_number):
            # Something went wrong.
            _logger.error("Failed to turn on. Current status:\r\n")
            _logger.error(self.get_status())
            return False
        return True

    # Turn the laser OFF.
    @microscope.abc.SerialDeviceMixin.lock_comms
    def disable(self, wavelength=None):
        if wavelength is None:
            _logger.error("In disable(): Wavelength not specified.")
            return False
        if wavelength not in self.wavelength_to_output:
            _logger.error(f"In disable(): Wavelength {wavelength} not supported.")
            return False
        output_number = self.wavelength_to_output[wavelength]
        command = f"{output_number}l0".encode()  # Command to disable laser at specified output
        response = self.send(command)
        _logger.info(f"Attempt to disable {wavelength} nm laser: {response.decode()}")
        return True

    # Return True if the laser is currently able to produce light.
    @microscope.abc.SerialDeviceMixin.lock_comms
    def get_is_on(self, line):
        command = f"{line}l?".encode()
        response = self.send(command)
        return response == b"1"

    def set_power(self, power: float, wavelength=None) -> None:
        if wavelength not in self.wavelength_to_output:
            _logger.error(f"Wavelength {wavelength} nm is not supported.")
            return False
        
        clipped_power = max(min(power, 1.0), 0.0)
    
        output_number = self.wavelength_to_output[wavelength]
        W_str = f"{clipped_power*self._max_power_mw/ 1000.0:.4f}"  # Convert mW to W and format as a string with 4 decimal places.
        _logger.info(f"Setting {wavelength} nm laser power to {W_str} W.")

        # The command should be like "1p 0.0500" for setting 50mW on laser output 1.
        command = f"{output_number}p {W_str}".encode()  # Convert the command to bytes
        response = self.send(command)
        _logger.info(f"Power set command response: {response.decode()}")

        self._set_point = clipped_power
        return True

    def get_power(self, wavelength=None) -> float:
        if wavelength not in self.wavelength_to_output:
            _logger.error(f"Wavelength {wavelength} nm is not supported.")
            return False
        output_number = self.wavelength_to_output[wavelength]
        command = f"{output_number}pa?".encode()  # Convert the command to bytes
        response = self.send(command)
        _logger.info(f"Power get command response: {response}")
        try:
            power = float(response.decode())
        except:
            power = 0.0
        return 1000 * power / self._max_power_mw

    def _do_set_power(self, power: float) -> None:
        pass

    def _do_get_power(self) -> float:
        pass
