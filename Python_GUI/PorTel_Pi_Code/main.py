#!/usr/bin/env python
# -*- coding: utf-8 -*-

import tornado.ioloop
import tornado.web
import tornado.websocket

import numpy as np

#import Threading

import os
import json

def error(text): print('Error: '+text)

class MainHandler(tornado.web.RequestHandler):
    def get(self):
        self.render('templates/test_cubisme.html')
        
class WebSocketHandler(tornado.websocket.WebSocketHandler):
    def initialize(self,cth):
        self.controller = cth

    def open(self):
        print("WebSocket opened")
        #self.set_nodelay(True)
        #ioloop to wait for 3 seconds before starting to send data
        #tornado.ioloop.IOLoop.instance().add_timeout(datetime.timedelta(seconds=3), self.send_data)

    def on_message(self, message):
        #self.write_message(u"You said: " + message)
        req = json.loads(message)
        
        if 'client' in req:
            print('%s: New client' % self.request.remote_ip)
            self.check_in()
            
        elif 'name' in req:
            if req['name'] in self.controller.metrics:
                try: req['data'] = tuple(self.controller.metrics[req['name']].get(int(req['start']),int(req['stop']),int(req['step'])))
                except: error('%s is an invalid metric request.'%str(req))
                else: self.write_message(json.dumps(req))
            else:error('%s is not a valid metric name.'%req['name'])
            
        elif 'btn name' in req:
            if req['btn name'] == 'bias_switch': self.controller.ToggleBias()
            if req['btn name'] == 'current_switch': self.controller.ToggleCurrent()
            if req['btn name'] == 'TEC_switch': self.controller.ToggleTEC()
            

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
        self.controller.UpdateAllStates()
        
    def set_current_button(self, text, color):
        self.send_data({'event':'set button',
                        'btn name':'current_switch',
                        'message':text,
                        'color':'color-%d'%color})
                        
    def set_bias_button(self, text, color):
        self.send_data({'event':'set button',
                        'btn name':'bias_switch',
                        'message':text,
                        'color':'color-%d'%color})
                        
    def set_TEC_button(self, text, color):
        self.send_data({'event':'set button',
                    'btn name':'TEC_switch',
                    'message':text,
                    'color':'color-%d'%color})
        
class Metric:
    def __init__(self, length=10000):
        self.length = length
        self.data = np.zeros(length, dtype='f')
        self.time = np.zeros(length, dtype='f')
        self.index = 0
        
    def push(self,time, data):
        if time < time[-1]:
            error('Data pushed to metric with decreasing time')
            return False
        self.data = np.roll(self.data,-1)
        self.time = np.roll(self.time,-1)
        self.data[-1] = data
        self.time[-1] = time
        return True

    def get(self,start,stop,step):
        if step: requested_times = np.linspace(start,stop,int((stop-start)/step+1))
        else: requested_times = start
        return np.interp(requested_times,self.time,self.data,0,0)
        
class MetricSine:
    def __init__(self,tau,phi):
        self.tau = tau
        self.phi = phi
    
    def get(self,start,stop,step):
        if step: requested_times = np.linspace(start,stop,int((stop-start)/step+1))
        else: requested_times = start
        return 10*np.sin((requested_times*self.tau)/1000+self.phi)

class Controller:
    def __init__(self):
        self.off = 1 #black
        self.on = 2 # green
        self.error = 3 #orange
        self.inop = 4 #red
        
        self.sockets = []
    
        self.metrics = {}
        self.metrics['laser_current'] = MetricSine(0.1,0)
        self.metrics['TEC_command'] = MetricSine(1,0)
        self.metrics['laser_temp'] = MetricSine(1,1)
        
        # not set, off, on, error, inop
        self.TEC_message  =    ('','TEC Disabled',           'TEC Enabled',           'SPI Error','Laser Thermal Shutdown')
        self.bias_message =    ('','Bias set to 0 V',        'Bias Enabled',          'SPI Error','')
        self.current_message = ('','Current Source Disabled','Current Source Enabled','SPI Error','Current Source Overheat')
        
        self.TEC_status = self.off
        self.bias_status = self.off
        self.current_status = self.off
        
    def AddSocket(self,ws):
        self.sockets.append(ws)
    
    def RemoveSocket(self,ws):
        self.sockets.remove(ws)
        
    def UpdateAllStates(self):
        self.UpdateButtons()
        
    def UpdateButtons(self):
        for ws in self.sockets:
            ws.set_current_button(self.current_message[self.current_status],self.current_status)
            ws.set_bias_button(self.bias_message[self.bias_status],self.bias_status)
            ws.set_TEC_button(self.TEC_message[self.TEC_status],self.TEC_status)
        
    def ToggleCurrent(self):
        if self.current_status == self.off: self.current_status = self.on
        elif self.current_status == self.on: self.current_status = self.off
        self.UpdateButtons()
        
    def ToggleBias(self):
        if self.bias_status == self.off: self.bias_status = self.on
        elif self.bias_status == self.on: self.bias_status = self.off
        self.UpdateButtons()
        
    def ToggleTEC(self):
        if self.TEC_status == self.off: self.TEC_status = self.on
        elif self.TEC_status == self.on: self.TEC_status = self.off
        self.UpdateButtons()
        
def make_app():
    control_telemetry_server = Controller()
    return tornado.web.Application(
        [
            (r"/", MainHandler),
            (r"/ws", WebSocketHandler, dict(cth = control_telemetry_server)),
        ],
        static_path=os.path.join(os.path.dirname('static'), 'static'),
        autoreload=True,
        )

if __name__ == "__main__":
    app = make_app()
    app.listen(8042)
    tornado.ioloop.IOLoop.current().start()