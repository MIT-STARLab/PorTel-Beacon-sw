import struct
AUDIO_PACKET_SIZE = 128

USE_PID = False

PACKET_SEND_FORMAT = "??ccfff"
PACKET_RECV_FORMAT = "???cc?cc" + "ffffff" + "h"*(AUDIO_PACKET_SIZE*2)

PACKET_RECV_KEYS = ("Alert","LaserOn","TECOn","laserStatus","powerStatus","commLoss","d1","d2",\
                    "temp","TECI","TECV","LaserIAVG","LaserIModulation","PDPeak",\
                    "PDQueue","driverQueue")

ALERT_MESSAGES = {0:'System Good', 1:'SYSTEM ERROR'}
LASER_MESSAGES = {0:'Laser Good', 1:'Laser Over Power', 2:'Laser Over Current', 3:'Laser Over Power and Current',\
                  4:'Laser Over Temp', 5:'Laser Over Power and Temp', 6:'Laser Over Current and Temp', \
                  7:'Laser Over Current and Temp and Power'}
POWER_MESSAGES = {0:'Power Good', 1:'TEC Power ERROR', 2:'2V2 Power ERROR', 3:'2V2 and TEC Power Errors'}
COMM_MESSAGES = {0:'Comm Good', 1:'Comm Lost'}

LASER_ENABLE_MESSAGES = {0: "Laser is Off", 1:"Laser is On"}
TEC_ENABLE_MESSAGES = {0: "TEC is Off", 1:"TEC is On"}

METRICS_LIST = ['LaserIAVG', 'LaserIPeak', 'LaserPDAVG', 'LaserPDModulation', 'temp', 'TECV', 'TECI']

OUTPUT_LIMIT = 0.2 #output limit

MAX_OPTICAL_POWER = 5 #Max optical power