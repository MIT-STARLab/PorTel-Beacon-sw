from cobs import cobs
import serial
import struct
import sys
import time
sys.path.append("../Python_GUI/PorTel_Pi_Code")
from constants import PACKET_RECV_FORMAT, PACKET_SEND_FORMAT, PACKET_RECV_KEYS, ALERT_MESSAGES, LASER_MESSAGES,\
    COMM_MESSAGES, POWER_MESSAGES, TEC_ENABLE_MESSAGES, LASER_ENABLE_MESSAGES, METRICS_LIST, AUDIO_PACKET_SIZE


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

        print("Got it, attempting decode")
        # return decoded data
        bdata=b''.join(data)
        print(type(bdata))
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
      return struct.unpack(PACKET_RECV_FORMAT,mypacket)#Return tuple

if __name__=="__main__":
    myMicro = Microcontroller("COM5")
    testSend = (1,0,5.0,0,0)
    res = myMicro.transferData(testSend)

    resdict = dict(zip(PACKET_RECV_KEYS, res))
    resdict["PDQueue"] = res[-AUDIO_PACKET_SIZE*2:-AUDIO_PACKET_SIZE]
    resdict["driverQueue"] = res[-AUDIO_PACKET_SIZE:]
    print(resdict)
    time.sleep(1)
