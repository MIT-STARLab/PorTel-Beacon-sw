import datetime
from cobs import cobs
import io
import select
import serial
import struct
import threading
from simple_pid import PID
import time
import numpy as np
from constants import PACKET_RECV_FORMAT, PACKET_SEND_FORMAT, PACKET_RECV_KEYS, ALERT_MESSAGES, LASER_MESSAGES,\
    COMM_MESSAGES, POWER_MESSAGES, TEC_ENABLE_MESSAGES, LASER_ENABLE_MESSAGES, METRICS_LIST, OUTPUT_LIMIT,\
    MAX_OPTICAL_POWER, AUDIO_PACKET_SIZE, USE_PID


class Metric:
    def __init__(self, length=10000):
        self.length = length
        self.data = np.zeros(length, dtype='d')
        self.time = np.zeros(length, dtype='d')
        self.init = False

    def push(self, ptime, pdata):
        if self.init:
            if ptime < self.time[-1]:
                error('Data pushed to metric with decreasing time, %d < %d' % (ptime, self.time[-1]))
                return False
            self.data = np.roll(self.data, -1)
            self.time = np.roll(self.time, -1)
            self.data[-1] = pdata
            self.time[-1] = ptime
            return True
        else:
            self.init = True
            self.time = np.ones(self.length, dtype='d') * ptime
            self.data = np.ones(self.length, dtype='d') * pdata

    def get(self, start, stop, step):
        if step:
            requested_times = np.linspace(start, stop, int((stop - start) / step + 1))
        else:
            requested_times = start
        if self.init:
            return np.interp(requested_times, self.time, self.data, left=0.0, right=0.0)
        else:
            return requested_times * 0

class Controller:
    def __init__(self):
        self.microcontroller=Microcontroller('COM5') #TBR

        #PID Controllers
        self.pidAVG = PID(1,0.1,0.05, output_limits=(0, OUTPUT_LIMIT), setpoint=0)
        self.pidMod = PID(1, 0.1, 0.05, output_limits=(0, OUTPUT_LIMIT), setpoint=0)

        #Status for uC
        self.laserOn=False
        self.TECOn=False
        self.tempSet=25
        self.driveAmplitude=0 #0 to 1
        self.driveOffset=0    #0 to 1

        self.requestAmplitude=0 #Watts 0-5
        self.requestAVG=0       #Watts 0-5

        self.sockets = []

        self.metrics = {}
        for k in METRICS_LIST:
            self.metrics[k] = Metric()

        self.MessageCounter=0

    def AddSocket(self, ws):
        self.sockets.append(ws)

    def RemoveSocket(self, ws):
        self.sockets.remove(ws)

    def StepControllers(self,status):
        if USE_PID:
            self.pidAVG.setpoint = self.requestAVG/MAX_OPTICAL_POWER
            self.pidMod.setpoint = self.requestAmplitude/MAX_OPTICAL_POWER
            pdavg, pdamp = self.getPDstats(status["PDQueue"])
            self.driveAmplitude = self.pidAVG(pdavg)
            self.driveOffset = self.pidMod(pdamp)
        else:
            self.driveOffset = self.requestAVG/MAX_OPTICAL_POWER
            self.driveAmplitude = self.requestAmplitude/MAX_OPTICAL_POWER

    #Updates the color and message of the four status buttons
    def UpdateIndicators(self,status):
        for ws in self.sockets:
            alertStatus=int(status["Alert"])
            ws.set_indicator('alert_indicator', ALERT_MESSAGES[alertStatus], alertStatus != 0)
            laserStatus=int.from_bytes(status["laserStatus"],'big')
            ws.set_indicator('laser_indicator', LASER_MESSAGES[laserStatus], laserStatus != 0)
            powerStatus=int.from_bytes(status["powerStatus"],'big')
            ws.set_indicator('power_indicator', POWER_MESSAGES[powerStatus], powerStatus != 0)
            alertStatus = int(status["commLoss"])
            ws.set_indicator('comm_indicator', COMM_MESSAGES[alertStatus], alertStatus != 0)

    #Extracts average and peak of the PD waveform
    def getPDstats(self,PDqueue):
        scale = (2**15)/6.25
        return np.mean(PDqueue)*scale, (max(PDqueue)-min(PDqueue))*scale

    def UpdateMetrics(self, status):
        pdavg, pdamp = self.getPDstats(status["PDQueue"])
        mytime=time.time()*1000 #Metrics work in ms for some reason?
        self.metrics["LaserPDAVG"].push(mytime, pdavg)
        self.metrics["LaserPDModulation"].push(mytime, pdamp)
        self.metrics["LaserIPeak"].push(mytime, status["LaserIAVG"] + status["LaserIModulation"]/2)
        print("Laser I AVG", status["LaserIAVG"])
        for k in ("LaserIAVG","temp","TECI","TECV"):
            self.metrics[k].push(mytime, status[k])

    #Updates the color and message of the input buttons
    def UpdateButtons(self):
        for ws in self.sockets:
            ws.set_indicator('laser_switch',LASER_ENABLE_MESSAGES[int(self.laserOn)],int(self.laserOn))
            ws.set_indicator('TEC_switch', TEC_ENABLE_MESSAGES[int(self.TECOn)], int(self.TECOn))


    #Gets called by GUI message, updates the message that will be sent to the uC
    def ToggleLaser(self):
        self.laserOn= not self.laserOn
        self.UpdateButtons()
    def ToggleTEC(self):
        self.TECOn = not self.TECOn
        self.UpdateButtons()

    def TempSet(self):
        return

    def GeneralUpdate(self):
        toSend = (self.laserOn,self.TECOn,b'0',b'0',self.tempSet,self.driveAmplitude,self.driveOffset)
        #print("Sending " , toSend)
        res = self.microcontroller.transferData(toSend)

        resdict = dict(zip(PACKET_RECV_KEYS, res))
        resdict["PDQueue"] = res[-AUDIO_PACKET_SIZE * 2:-AUDIO_PACKET_SIZE]
        resdict["driverQueue"] = res[-AUDIO_PACKET_SIZE:]

        #print("Got ", resdict)

        self.UpdateIndicators(resdict)
        self.UpdateMetrics(resdict)
        self.StepControllers(resdict)

        self.MessageCounter += 1

        print("Temp Set: ", self.tempSet)


#Microcontroller object adapter from https://github.com/igor47/spaceboard/blob/master/spaceteam.py
class Microcontroller(object):
  """interface to an on-board microcontroller"""

  # Timeout for buffered serial I/O in seconds.
  IO_TIMEOUT_SEC = 2

  def __init__(self, port, baud_rate=115200):
    """Connects to the microcontroller on a serial port.
    Args:
        port: The serial port or path to a serial device.
        baud_rate: The bit rate for serial communication.
    Raises:
        ValueError: There is an error opening the port.
        SerialError: There is a configuration error.
    """
    # Build the serial wrapper.
    self._serial = serial.Serial(
        port=port,
        baudrate=baud_rate,
        bytesize=8,
        parity='N',
        stopbits=1,
        timeout=self.IO_TIMEOUT_SEC)
    if not self._serial.isOpen():
      raise ValueError("Couldn't open %s" % port)

    # holds reads until we encounter a 0-byte (COBS!!!)
    self._read_buf = [None] * ((struct.calcsize(PACKET_RECV_FORMAT))+300)
    self._read_buf_pos = 0

  def stop(self):
    """Shuts down communication to the microcontroller."""
    self._serial.close()

  def _send_packet(self, packet):
    """Sends a packet to microcontroller"""
    encoded = cobs.encode(packet)
    self._serial.write(bytearray(encoded) + b'\x00')
    return True

  def _reset_read_buf(self):
    self._read_buf[0:self._read_buf_pos] = [None] * self._read_buf_pos
    self._read_buf_pos = 0

  def _recv_packet(self):
    """Reads a full line from the microcontroller
    We expect to complete a read when this is invoked, so don't invoke unless
    you expect to get data from the microcontroller. we raise a timeout if we
    cannot read a command in the alloted timeout interval."""
    # we rely on the passed-in timeout
    while True:
      c = self._serial.read(1)
      if not c:
        raise serial.SerialTimeoutException(
            "Couldn't recv command in %d seconds" % self.IO_TIMEOUT_SEC)

      # finished reading an entire COBS structure
      if c == b'\x00':
        # grab the data and reset the buffer
        data = self._read_buf[0:self._read_buf_pos]
        self._reset_read_buf()

        # return decoded data
        bdata=b''.join(data)
        return cobs.decode(bdata) #Returns byte array

      # still got reading to do
      else:
        self._read_buf[self._read_buf_pos] = c
        self._read_buf_pos += 1


        # ugh. buffer overflow. wat do?
        if self._read_buf_pos == len(self._read_buf):
          # resetting the buffer likely means the next recv will fail, too (we lost the start bits)
          self._reset_read_buf()
          raise RuntimeError("IO read buffer overflow :(")

  #The method that gets called and data goes both ways
  #Might want to make this non-blocking if the serial gets stuck
  def transferData(self,mySend):
      self._send_packet(struct.pack(PACKET_SEND_FORMAT,*mySend)) #Unpack tuple and pack into struct and serialize
      mypacket=self._recv_packet()
      print(mypacket)
      return struct.unpack(PACKET_RECV_FORMAT,mypacket) #Return tuple

