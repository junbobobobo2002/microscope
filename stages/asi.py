#!/usr/bin/env python3

## Copyright (C) 2020 David Miguel Susano Pinto <carandraug@gmail.com>
## Copyright (C) 2020 Ian Dobbie <ian.dobbie@bioch.ox.ac.uk>
## Copyright (C) 2020 Mick Phillips <mick.phillips@gmail.com>
## Copyright (C) 2020 Tiago Susano Pinto <tiagosusanopinto@gmail.com>
##
## This file is part of Microscope.
##
## Microscope is free software: you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published by
## the Free Software Foundation, either version 3 of the License, or
## (at your option) any later version.
##
## Microscope is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
## GNU General Public License for more details.
##
## You should have received a copy of the GNU General Public License
## along with Microscope.  If not, see <http://www.gnu.org/licenses/>.

import logging
import typing

import serial

import microscope._utils
import abc

_logger = logging.getLogger(__name__)

class SerialConnection:

    def __init__(self, 
                 which_port,
                 name) -> None:
        
        # set variables used for the Serial connection
        self.name = name

        print('%s: Opening...'%name, end='')
        try:
            # construct the serial connection
            self.port = serial.Serial(
                port=which_port, baudrate=9600, timeout=5)
        except serial.serialutil.SerialException:
            # raise an error if not able to connect
            raise IOError('%s: No connection on port %s'%(name, which_port))
        print(" done.")
        self.version = self._send('V').strip(':A \r\n')
        assert self.version == 'Version: USB-9.2n', (
            '%s: controller version not supported'%name)

    def _set_ttl_in_mode(self, mode):
        print("%s: setting ttl in mode = %s"%(self.name, mode))
        mode2code = {'disabled':'0', 'toggle_ttl_out':'10'}
        assert mode in mode2code, "mode '%s' not allowed"%mode
        self._ttl_in_mode = self._send(
            'TTL X=%s'%mode2code[mode], respond=False)
        assert self._get_ttl_in_mode() == mode
        print("%s: -> done setting ttl in mode."%self.name)
        return None

    def _set_ttl_out_mode(self, mode):
        print("%s: setting ttl out mode = %s"%(self.name, mode))
        mode2code = {'low':'0', 'high':'1', 'pwm':'9'}
        assert mode in mode2code, "mode '%s' not allowed"%mode
        self._ttl_out_mode = self._send(
            'TTL Y=%s'%mode2code[mode], respond=False)
        assert self._get_ttl_out_mode() == mode
        print("%s: -> done setting ttl out mode."%self.name)
        return None
    
    def _get_ttl_in_mode(self):
        print("%s: getting ttl in mode"%self.name)
        code2mode = {'0': 'disabled', '10': 'toggle_ttl_out'}
        code = self._send('TTL X?').rstrip().split('=')[1]
        self._ttl_in_mode = code2mode[code]
        print("%s: -> ttl in mode = %s"%(self.name, self._ttl_in_mode))
        return self._ttl_in_mode

    def _get_ttl_out_mode(self):
        print("%s: getting ttl out mode"%self.name)
        code2mode = {'0': 'low', '1': 'high', '9': 'pwm'}
        code = self._send('TTL Y?').rstrip().split('=')[1]
        self._ttl_out_mode = code2mode[code]
        print("%s: -> ttl out mode = %s"%(self.name, self._ttl_out_mode))
        return self._ttl_out_mode

    def _send(self, cmd, respond=True, parse_axes=False):
        print("%s: sending cmd = "%self.name, cmd)
        assert type(cmd) is str, 'command should be a string'
        cmd = bytes(cmd, encoding='ascii')
        self.port.write(cmd + b'\r')
        response = self.port.readline().decode('ascii').strip(':A \r\n')
        if respond:
            assert response != '', '%s: No response'%self.name
        else:
            response = None
        print("%s: -> response = "%self.name, response)
        assert self.port.in_waiting == 0
        return response



class ASIStageAxis(microscope.abc.StageAxis):

    def __init__(self, 
                 name, 
                 real_name,
                 upper_limit,
                 lower_limit,
                 serial_connection,
                 max_velocity_mmps,
                 min_acceleration_ms,
                 max_acceleration_ms,
                 max_settle_time_ms,
                 tol_settle_time_ms,
                 min_precision_um,
                 max_precision_um,
                 encoder_counts_per_um):
        self.axis_name = name
        self.real_name = real_name
        
        self.lower_limit = lower_limit
        self.upper_limit = upper_limit
        print("LOWER LIMIT FOR %s IS = %f"%(self.real_name, float(lower_limit)))
        print("UPPER LIMIT FOR %s IS = %f"%(self.real_name, float(upper_limit)))
        self.serial_connection = serial_connection
        self.max_velocity_mmps = max_velocity_mmps
        self.min_acceleration_ms = min_acceleration_ms
        self.max_acceleration_ms = max_acceleration_ms
        self.max_settle_time_ms = max_settle_time_ms
        self.tol_settle_time_ms = tol_settle_time_ms
        self.min_precision_um = min_precision_um
        self.max_precision_um = max_precision_um
        self.encoder_counts_per_um = encoder_counts_per_um

        # set axis parameters by sending commands to serial connection
        self._set_velocity(0.17 * max_velocity_mmps)
        self._set_acceleration(self.min_acceleration_ms)
        self._set_settle_time(0)
        self._set_precision(self.min_precision_um)
        self._moving = False

    def _set_velocity(self, velocity_mmps): # tuple i.e. (2, 5, None)
        print("%s: setting velocity = %s"%(self.real_name, velocity_mmps))
        #assert len(velocity_mmps) == len(self.axes)
        #for v in velocity_mmps: assert type(v) is int or type(v) is float
        assert type(velocity_mmps) is int or type(velocity_mmps) is float
        cmd_string = ['S ']

        assert 0 <= velocity_mmps <= self.max_velocity_mmps
        velocity_mmps = round(velocity_mmps, 6)
        cmd_string.append('V%s=%0.6f '%(self.real_name, velocity_mmps))

        self.serial_connection._send(''.join(cmd_string), respond=False)
        print(self._get_velocity())
        #print(tuple(velocity_mmps))
        print(velocity_mmps)
        #assert self._get_velocity() == tuple(velocity_mmps)
        assert self._get_velocity() == velocity_mmps
        print("%s: -> done setting velocity."%self.real_name)
        return None

    def _get_velocity(self):
        print("%s: getting velocity"%self.real_name)
        
        varia, self.velocity_mmps = (self.serial_connection._send(
            'S '+'? '.join(self.real_name)+'?', parse_axes=True)).split("=")
        print("%s: -> velocity (mm/s) = %f"%(self.real_name, float(self.velocity_mmps)))
        return float(self.velocity_mmps)
    
    def _set_acceleration(self, acceleration_ms): # tuple i.e. (2, 5, None)
        print("%s: setting acceleration = %s"%(self.real_name, acceleration_ms))
        #assert len(acceleration_ms) == len(self.axes)
        #for v in acceleration_ms: assert type(v) is int or type(v) is float
        assert type(acceleration_ms) is int or type(acceleration_ms) is float
        cmd_string = ['AC ']
        acceleration_ms = round(acceleration_ms)
        assert acceleration_ms >= self.min_acceleration_ms
        assert acceleration_ms <= self.max_acceleration_ms
        cmd_string.append('AC%s=%0.6f '%(self.real_name, acceleration_ms))

        self.serial_connection._send(''.join(cmd_string), respond=False)
        assert self._get_acceleration() == acceleration_ms
        print("%s: -> done setting acceleration."%self.real_name)
        return None

    def _get_acceleration(self): # acceleration or deceleration ramp time (ms)
        print("%s: getting acceleration"%self.real_name)
        varia, self.acceleration_ms = self.serial_connection._send(
            'AC '+'? '.join(self.real_name)+'?', parse_axes=True).split("=")
        print("%s: -> acceleration (ms) = %f"%(
                self.real_name, float(self.acceleration_ms)))
        return float(self.acceleration_ms)
    
    def _set_settle_time(self, settle_time_ms): # tuple i.e. (2, 5, None)
        print("%s: setting settle time = %s"%(self.real_name, settle_time_ms))
        #assert len(settle_time_ms) == len(self.axes)
        #for v in settle_time_ms: assert type(v) is int or type(v) is float
        assert type(settle_time_ms) is int or type(settle_time_ms) is float
        cmd_string = ['WT ']
        settle_time_ms = round(settle_time_ms)
        assert 0 <= settle_time_ms <= self.max_settle_time_ms
        cmd_string.append('WT%s=%0.6f '%(self.real_name, settle_time_ms))

        self.serial_connection._send(''.join(cmd_string), respond=False)
        self._get_settle_time()
        self.settle_time_ms = float(self.settle_time_ms)
        assert self.settle_time_ms >= settle_time_ms - self.tol_settle_time_ms
        assert settle_time_ms <= settle_time_ms + self.tol_settle_time_ms
        print("%s: -> done setting settle_time."%self.real_name)
        return None

    def _get_settle_time(self): # time spent at end of move (ms)
        print("%s: getting settle time"%self.real_name)
        varia, self.settle_time_ms = self.serial_connection._send(
            'WT '+'? '.join(self.real_name)+'?', parse_axes=True).split("=")
        print("%s: -> settle time (ms) = %f"%(
                self.real_name, float(self.settle_time_ms)))
        return float(self.settle_time_ms)
    

    def _set_precision(self, precision_um): # tuple i.e. (2, 5, None)
        print("%s: setting precision = %s"%(self.real_name, precision_um))
        #assert len(precision_um) == len(self.axes)
        #for v in precision_um: assert type(v) is int or type(v) is float
        assert type(precision_um) is int or type(precision_um) is float
        cmd_string = ['PC ']

        precision_um = round(precision_um)
        assert precision_um >= self.min_precision_um
        assert precision_um <= self.max_precision_um
        cmd_string.append(
                'PC%s=%0.6f '%(self.real_name, 1e-6 * precision_um))
        self.serial_connection._send(''.join(cmd_string), respond=False)
        assert self._get_precision() == precision_um
        print("%s: -> done setting precision."%self.real_name)
        return None


    def _get_precision(self): # acceptable error between target and actual (um)
        print("%s: getting precision"%self.real_name)
        varia, precision_mm = self.serial_connection._send(
            'PC '+'? '.join(self.real_name)+'?', parse_axes=True).split("=")
        #self.precision_um = tuple(round(1e6 * p) for p in precision_mm)
        self.precision_um = round(1e6 * float(precision_mm))
        print("%s: -> precision (um) = %f"%(
                self.real_name, self.precision_um))
        return self.precision_um

    def _counts2position(self, count):
        position_um = float(count[0]) / self.encoder_counts_per_um
        return position_um

    def _position2counts(self, position_um):

        count = round(position_um * self.encoder_counts_per_um)
        return count

    def _get_position(self):
        print("%s: getting position"%self.real_name)
        response = self.serial_connection._send('W '+' '.join(self.real_name)).strip(':A \r\n').split()
        self.position_um = self._counts2position(response)
        print("%s: -> position (um) = %f"%(self.real_name, self.position_um))
        return self.position_um

    def _finish_moving(self):
        if not self._moving:
            return None
        while True:
            status = self.serial_connection._send('/')
            if status == 'N':
                break
        self._get_position()
        print("FIRST")
        assert self.position_um >= self._target_move_um - self.precision_um
        print("SECOND")
        assert self.position_um <= self._target_move_um + self.precision_um
        self._moving = False
        print('%s: -> finished moving'%self.real_name)
        return None
    
    def move_um(self, move_um, relative=True, block=True):
        self._finish_moving()
        print(type(move_um))
        assert type(move_um) is int or type(move_um) is float or move_um is None
        print("hey from asi")
        if move_um is None:
            move_um = self.position_um
        if move_um is not None and relative:
            move_um = self.position_um + move_um
        assert move_um >= self.lower_limit
        assert move_um <= self.upper_limit

        #move_um = tuple(round(v, 3) for v in move_um) # round to nm
        move_um = round(move_um, 3)
        print("%s: moving to (um) = %f"%(self.real_name, move_um))
        cmd_string = ['M ']
        cmd_string.append('%s=%0.6f '%(self.real_name,
                                           self._position2counts(move_um)))
        self.serial_connection._send(''.join(cmd_string), respond=False)
        self._moving = True
        self._target_move_um = move_um
        if block:
            self._finish_moving()
        return None

    # FUNCTIONS INHERITED FROM THE STAGE AXIS CLASS (microscope.abc package)
    def move_by(self, delta: float) -> None:
        """Move axis by given amount."""
        self.move_um(delta, relative=True, block=True)
        return None

    def move_to(self, pos: float) -> None:
        """Move axis to specified position."""
        print("CALLING MOVE TO FOR %s: moving to = %f"%(self.real_name, pos))
        self.move_um(pos, relative=False, block=True)
        return None

    @property
    def position(self) -> float:
        """Current axis position."""
        return self._get_position()

    @property
    def name(self) -> str:
        """Stage axis name (X, Y or Z)"""
        return self.axis_name

    @property
    def limits(self) -> microscope.AxisLimits:
        """Upper and lower limits values for position."""
        limits = microscope.AxisLimits(self.lower_limit, self.upper_limit)
        return limits


class ASIStage(
    microscope._utils.OnlyTriggersBulbOnSoftwareMixin,
    microscope.abc.SerialDeviceMixin,
    microscope.abc.Stage,
):
    """ASI Stage."""
    # FUNCTIONS INHERITED FROM DEVICE CLASS
    def __init__(self, 
                 which_port,                # COM port for controller
                 axes=None,                 # ('X','Y'), ('Z',), ('X','Y','Z')
                 piezo_z=True,
                 lead_screws=None,          # 'UC', 'SC', 'S', 'F', 'XF' (tuple)
                 axes_min_mm=None,          # min range (tuple)
                 axes_max_mm=None,          # max range (tuple)
                 encoder_counts_per_um=None,# optional -> expert only (tuple)
                 use_pwm=False,             # optional pwm output for LED
                 name='MS-2000-500',     # optional name
                 verbose=True,              # False for max speed
                 very_verbose=False,
                 index: typing.Optional[int] = None) -> None:
        
            self.enabled = False
            self._settings: typing.Dict[str, microscope.abc._Setting] = {}
            self._index = index

            # set variables used for the Serial connection
            self.name = name
            print("setting verbose")
            self.verbose = verbose
            print("after setting verbose")
            self.very_verbose = very_verbose


            # the stage has a serial connection
            self.serial_connection = SerialConnection(which_port, name)
            self.serial_connection._set_ttl_in_mode('disabled')
            self.serial_connection._set_ttl_out_mode('low')
            
            # pmw state
            self.state = None
            
            if axes is not None:
                # check that the name and number of axes are correct
                assert axes == ('X','Y') or axes == ('Z',) or axes == ('X','Y','Z')

                # check lead screw values 
                assert lead_screws is not None, 'please choose lead screw options'
                assert len(lead_screws) == len(axes)
                screw2value = { # pitch (mm), res (nm), speed (mm/s)
                    'UC':(25.40, 88.0, 28.0),   # 'ultra-course'
                    'SC':(12.70, 44.0, 14.0),   # 'super-course'
                    'S' :(6.350, 22.0, 7.00),   # 'standard'
                    'F' :(1.590, 5.50, 1.75),   # 'fine'
                    'XF':(0.653, 2.20, 0.70)}   # 'extra-fine'

                # set pitch, resolution and max velocity mmps
                pitch_mm, resolution_nm, max_velocity_mmps = [], [], []
                for a in range(len(axes)):
                    pitch_mm.append(screw2value[lead_screws[a]][0])
                    resolution_nm.append(screw2value[lead_screws[a]][1])
                    max_velocity_mmps.append(screw2value[lead_screws[a]][2])
                self.pitch_mm = tuple(pitch_mm)
                self.resolution_nm = tuple(resolution_nm)
                self.max_velocity_mmps = tuple(max_velocity_mmps)

                # check if min/max values of axes were passed 
                assert axes_min_mm is not None, 'please specify min range of axes'
                assert axes_max_mm is not None, 'please specify max range of axes'
                # check if there is one mix/max value for each axis
                assert len(axes_min_mm) == len(axes)
                assert len(axes_max_mm) == len(axes)
                # check that the min/max values of axes are int or float
                for v in axes_min_mm: assert type(v) is int or type(v) is float
                for v in axes_max_mm: assert type(v) is int or type(v) is float

                self.encoder_counts_per_um = len(axes)*(10,)# default value
                if encoder_counts_per_um is not None:
                    assert len(encoder_counts_per_um) == len(axes)
                    for v in encoder_counts_per_um: assert type(v) is int
                    self.encoder_counts_per_um = encoder_counts_per_um

                axes_temp = []
                real_names = []
                for axis_name in axes:
                    if axis_name == 'Z' and piezo_z:
                        real_names.append('F')
                    else:
                        real_names.append(axis_name)
                # create instances of ASIStageAxis for each axis
                for axis_name, real_name, axis_min, axis_max, encoder_counts_per_um, max_velocity_mmps in zip(axes, real_names, axes_min_mm, axes_max_mm, self.encoder_counts_per_um, self.max_velocity_mmps):
                    print(axis_name)
                    axis = ASIStageAxis(name=axis_name, 
                    real_name=real_name,
                    upper_limit=1e3*axis_max,
                    lower_limit=1e3*axis_min,
                    serial_connection=self.serial_connection, # same serial connection as the stage
                    max_velocity_mmps=max_velocity_mmps,
                    min_acceleration_ms=25,
                    max_acceleration_ms=1e3,
                    max_settle_time_ms=1e3,
                    tol_settle_time_ms=1,
                    min_precision_um=1,
                    max_precision_um=1e6,
                    encoder_counts_per_um=encoder_counts_per_um) 
                    print("AFTER INSTANTIATING")
                    axes_temp.append(axis)
                self.stage_axes = tuple(axes_temp) # set axes of the stage

                self._moving = False
            if use_pwm:
                
                self.set_pwm_state('off')
                self.set_pwm_intensity(0)
            return None


    def _do_disable(self):
        """Do any device-specific work on disable.

        Subclasses should override this method rather than modify
        `disable`.

        """
        return True


    def _do_enable(self):
        """Do any device specific work on enable.

        Subclasses should override this method, rather than modify
        `enable`.

        """
        return True



    def _do_shutdown(self) -> None:
        """Private method - actual shutdown of the device.

        Users should be calling :meth:`shutdown` and not this method.
        Concrete implementations should implement this method instead
        of `shutdown`.

        """
        if self.verbose: print("%s: closing..."%self.name)
        if self.state != 'off':
            self.set_pwm_state('off')
        self.serial_connection.port.close()
        if self.verbose: print("%s: closed."%self.name)
        return None
    

    # FUNCTIONS to set/get PMW
    def get_pwm_intensity(self):
        if self.verbose:
            print("%s: getting pwm intensity"%self.name)
        response = self.serial_connection._send('LED X?') # non-standard answer: 'X=val :A'
        print((response.split('=')[1]).split(' ')[0])
        self.pwm_intensity = int((response.split('=')[1]).split(' ')[0])
        if self.verbose:
            print("%s: -> pwm intensity (%%) = %s"%(
                self.name, self.pwm_intensity))
        return self.pwm_intensity

    def set_pwm_intensity(self, intensity):
        if self.verbose:
            print("%s: setting pwm intensity = %s"%(self.name, intensity))
        
        assert type(intensity) is int or type(intensity) is float
        intensity = int(intensity)
        
        #assert 1 <= intensity <= 99
        assert 0 <= intensity <= 99
        self.serial_connection._send('LED X=%d :NA'%intensity, respond=False)
        assert self.get_pwm_intensity() == intensity
        if self.verbose:
            print("%s: -> done setting pwm intensity."%self.name)
        return None

    def set_pwm_state(self, state):
        if self.verbose:
            print("%s: setting pwm state = %s"%(self.name, state))
        assert state in ('off', 'on', 'pwm', 'external')
        if state == 'off':
            self.serial_connection._set_ttl_in_mode('disabled')
            self.serial_connection._set_ttl_out_mode('low')
        if state == 'on':
            self.serial_connection._set_ttl_in_mode('disabled')
            self.serial_connection._set_ttl_out_mode('high')
        if state == 'pwm':
            self.serial_connection._set_ttl_in_mode('disabled')
            self.serial_connection._set_ttl_out_mode('pwm')
        if state == 'external':
            self.serial_connection._set_ttl_in_mode('toggle_ttl_out')
            self.serial_connection._set_ttl_out_mode('low')
        self.state = state
        if self.verbose:
            print("%s: -> done setting pwm state."%self.name)
        return None

    # FUNCTIONS INHERITED FROM THE STAGE CLASS (microscope.abc package)
    @property
    def axes(self) -> typing.Mapping[str, ASIStageAxis]:
        """Map of axis names to the corresponding :class:`StageAxis`.

        .. code-block:: python

            for name, axis in stage.axes.items():
                print(f'moving axis named {name}')
                axis.move_by(1)

        If an axis is not available then it is not included, i.e.,
        given a stage with optional axes the missing axes will *not*
        appear on the returned dict with a value of `None` or some
        other special `StageAxis` instance.
        """
        return {axis.name: axis for axis in self.stage_axes}

    @property
    def position(self) -> typing.Mapping[str, float]:
        """Map of axis name to their current position.

        .. code-block:: python

            for name, position in stage.position.items():
                print(f'{name} axis is at position {position}')

        The units of the position is the same as the ones being
        currently used for the absolute move (:func:`move_to`)
        operations.
        """
        return {name: axis.position for name, axis in self.axes.items()}


    @property
    def limits(self) -> typing.Mapping[str, microscope.AxisLimits]:
        """Map of axis name to its upper and lower limits.

        .. code-block:: python

            for name, limits in stage.limits.items():
                print(f'{name} axis lower limit is {limits.lower}')
                print(f'{name} axis upper limit is {limits.upper}')

        These are the limits currently imposed by the device or
        underlying software and may change over the time of the
        `StageDevice` object.

        The units of the limits is the same as the ones being
        currently used for the move operations.

        """
        return {name: axis.limits for name, axis in self.axes.items()}

    def move_by(self, delta: typing.Mapping[str, float]) -> None:
        """Move axes by the corresponding amounts.

        Args:
            delta: map of axis name to the amount to be moved.

        .. code-block:: python

            # Move 'x' axis by 10.2 units and the y axis by -5 units:
            stage.move_by({'x': 10.2, 'y': -5})

            # The above is equivalent, but possibly faster than:
            stage.axes['x'].move_by(10.2)
            stage.axes['y'].move_by(-5)

        The axes will not move beyond :func:`limits`.  If `delta`
        would move an axis beyond it limit, no exception is raised.
        Instead, the stage will move until the axis limit.

        """

        for axis_name, axis_move in delta.items():
            self.axes[axis_name].move_by(axis_move)
        return None

    def move_to(self, position: typing.Mapping[str, float]) -> None:
        """Move axes to the corresponding positions.

        Args:
            position: map of axis name to the positions to move to.

        .. code-block:: python

            # Move 'x' axis to position 8 and the y axis to position -5.3
            stage.move_to({'x': 8, 'y': -5.3})

            # The above is equivalent to
            stage.axes['x'].move_to(8)
            stage.axes['y'].move_to(-5.3)

        The axes will not move beyond :func:`limits`.  If `positions`
        is beyond the limits, no exception is raised.  Instead, the
        stage will move until the axes limit.

        """
        for axis_name, axis_move in position.items():
            self.axes[axis_name].move_to(axis_move)
        return None



