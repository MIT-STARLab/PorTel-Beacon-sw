#!/usr/bin/env python
# -*- coding: utf-8 -*-

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

def error(text): 
    print('Error: '+text)
    logging.warning(text)


class MainHandler(tornado.web.RequestHandler):
    def get(self):
        self.render('templates/test_cubisme.html')
        
class WebSocketHandler(tornado.websocket.WebSocketHandler):
    def initialize(self,cth):
        self.controller = cth

    def open(self):
        print("WebSocket opened")
        logging.info("WebSocket opened")

    def on_message(self, message):
        #print(message)
        req = json.loads(message)
        
        if 'client' in req:
            print('%s: New client' % self.request.remote_ip)
            self.check_in()
            
        elif 'name' in req:
            if req['name'] in self.controller.metrics:
                try:
                    req['data'] = tuple(self.controller.metrics[req['name']].get(int(req['start']),int(req['stop']),int(req['step'])))
                except KeyError: error('%s is an invalid metric request.'%str(req))
                else: self.write_message(json.dumps(req))
            else:error('%s is not a valid metric name.'%req['name'])
            
        elif 'btn name' in req:
            if req['btn name'] == 'laser_switch': self.controller.ToggleLaser()
            if req['btn name'] == 'TEC_switch': self.controller.ToggleTEC()

        elif 'slider name' in req:
            if req['slider name'] == 'temp_slider':
                self.controller.tempSet = float(req['value'])
                self.set_slider(req['slider name'],float(req['value']))
            if req['slider name'] == 'avg_slider': self.controller.requestAVG = float(req['value'])
            if req['slider name'] == 'mod_slider': self.controller.requestAmplitude = float(req['value'])

            #Make sure the slider gets updated in multiple tabs, use the button as template
            #Be careful reading API, if you programatically update slider, ignore event if already at value

        else:
            print("Warning: Unprocessed message", message)
            logging.warning("Unprocessed message", message)

        self.controller.GeneralUpdate()
            

    def on_close(self):
        print("WebSocket closed")
        self.controller.RemoveSocket(self)
        
    def send_data(self, pck):
        #write the json object to the socket
        #self.write_message(json.dumps(data_pack))
        self.write_message(json.dumps(pck))
        
    def check_in(self):
        self.send_data({'event':'connected',
                        'message':'Connected to %s'%self.request.host})
        self.controller.AddSocket(self)
        #self.controller.GeneralUpdate()

    def set_indicator(self, ind_name,text,color):
        # print("button pressed", ind_name, color)
        self.send_data({'event':'set indicator',
                        'btn name':ind_name,
                        'message':text,
                        'color':'color-%d'%color})
    
    def set_control(self, ind_name,text,color):
        # print("button pressed", ind_name, color)
        self.send_data({'event':'set control',
                        'btn name':ind_name,
                        'message':text,
                        'color':'color-%d'%color})

    def set_slider(self, slider_name,value):
        print("Slider set called")
        self.send_data({'event':'set slider',
                        'slider name':slider_name,
                        'value':value})


def make_app():
    print("making app...")
    control_telemetry_server = Controller()

    filename = './data/update_' + (time.strftime("%Y%m%d_%H%M%S")) + ".log"    
    logging.basicConfig(filename=filename, encoding='utf-8', format='%(asctime)s: %(levelname)s - %(message)s', 
            datefmt='%m/%d/%Y %I:%M:%S %p', level=logging.DEBUG)
    logging.info('Made app')

    myapp = tornado.web.Application(
        [
            (r"/", MainHandler),
            (r"/ws", WebSocketHandler, dict(cth = control_telemetry_server)),
        ],
        static_path=os.path.join(os.path.dirname('static'), 'static'), #TODO: auto direct
        autoreload=True,
        )

    return myapp

if __name__ == "__main__":
    app = make_app()
    app.listen(8042)
    tornado.ioloop.IOLoop.current().start()

