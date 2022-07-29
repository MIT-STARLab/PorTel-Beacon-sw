import tornado.ioloop
import tornado.web
import tornado.websocket

import numpy as np

#import Threading

import os
import json

import time
import logging

from Controller import Controller


#These functions allow a python program to operate the laser
#The GUI will still be generated, but at this point the input setpoints will not visibly change in response to the API
#All telemetry read from the board should still be displayed correctly
class Controller_API():
    def __init__(self, mycontroller):
        self.controller=mycontroller

    self.laserOn = False
    self.TECOn = False
    self.tempSet = 20
    self.tempSetSend = 20
    self.driveAmplitude = 0  # 0 to 1
    self.driveOffset = 0  # 0 to 1

    self.requestAmplitude = 0  # Watts 0-5
    self.requestAVG = 0  # Watts 0-5

    def turn_laser_off(self): #Disables power to the laser
        self.controller.laserOn = False

    def turn_laser_on(self, driveAmplitude, driveAVG): #Enables power to the laser and sets operating parameters
    #Drive amplitude and drive average requests are in Watts, notionally 0 to 5
        self.controller.laserOn = True
        self.controller.requestAmplitude = driveAmplitude
        self.controller.requestAVG = driveAVG

    def turn_TEC_off(self): #Disables the thermo-electric cooler
        self.controller.TECOn = False

    def turn_TEC_on(self,tempset=25): #Enables the TEC and sets the temperature set point
        self.controller.TECOn = True
        self.controller.tempSetSend = tempset

    def get_waveform(self): #Gets the laser waveform from the most recent interaction
        return self.controller.PDQueue

    def get_status_dictionary(self): #Gets the full telemetry from the microcontroller
        return self.controller.resdict

    #Here is an example of using the API, see the bottom of this file for the call
    def example_script(self):
        self.turn_TEC_on(25)
        print("TEC turned on")
        time.sleep(10)
        self.turn_laser_on(1,1)
        print("Laser turned on, acquiring waveform")
        self.sleep(1)
        np.savetxt('example_script_file.csv', self.get_waveform(), delimiter=',')


if __name__=="__main__":
    myapi = Controller_API(Controller())    #Get our instance of the API class
    myapi.example_script()                  #Run the function we are interested in
