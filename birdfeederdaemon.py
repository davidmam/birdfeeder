# -*- coding: utf-8 -*-
"""
Created on Tue Jan  3 19:44:16 2017

Data logging for weighing birdfeeder

@author: David
"""


# To kick off the script, run the following from the python directory:
#   PYTHONPATH=`pwd` python testdaemon.py start

#standard python libs
import logging
import time
import requests
from urllib.request import urlopen

#third party libs
#from daemon import runner
from hx711 import HX711
import RPi.GPIO as GPIO
import sys
import numpy as np  # sudo apt-get python-numpy
from datetime import datetime
from pymongo import MongoClient
from statistics import median

MONGODBCLIENT='192.168.0.3'

class App():
    
    def __init__(self, maxring=5, average=5):
        self.stdin_path = '/dev/null'
        self.stdout_path = '/dev/tty'
        self.stderr_path = '/dev/tty'
        self.pidfile_path =  '/var/run/testdaemon/testdaemon.pid'
        self.pidfile_timeout = 5
        self.feeder = HX711(5, 6)
        self.feeder.set_scale(7.99)
        self.feeder.set_reference_unit(92)
        self.feeder.power_down()
        self.feeder.power_up()
        self.maxringsize=maxring
        self.avecount=average
        client = MongoClient(MONGODBCLIENT)
        self.db=client.test.birdfeeder
        time.sleep(2)
        self.feeder.tare()
            
    def run(self):
        ringbuffer = []
        maxringsize = self.maxringsize
        pos = 0
        lastweight = 0 
        threshold = 3.0 # minimum change to record
        while True:
            try:
                weight = self.feeder.get_weight(self.avecount)                
                timestamp = datetime.now()
                if len(ringbuffer) <maxringsize:
                    ringbuffer.append((weight,timestamp))
                else:
                    ringbuffer[pos] = (weight, timestamp)
                thisweight = median([x[0] for x in ringbuffer])
                if abs(thisweight - lastweight) >threshold:
                    # trigger photo here
                    tag = datetime.now().strftime('%Y%m%d%H%M%S')
                    try:
                        response=urlopen('http://'+watcher_ip+'/take-image?tag='+tag)
                    except:
                        print('No response from', watcher_ip)
                    for n in ringbuffer:
                
                # save median value
                
                        self.db.insert({'Sensor': 'birdfeeder', 
                                        'timestamp': n[1],
                                        'weight': n[0], 
                                        'change': thisweight-lastweight,
                                        'tag': tag} )
                #self.feeder.power_down()
                #self.feeder.power_up()
                pos = (pos+1)%maxringsize
                lastweight = thisweight
                time.sleep(0.1)
                
            except (KeyboardInterrupt, SystemExit):
                self.cleanAndExit()#Main code goes here ...
            #Note that logger level needs to be set to logging.DEBUG before this shows up in the logs
            '''logger.debug("Debug message")
            logger.info("Info message")
            logger.warn("Warning message")
            logger.error("Error message")'''
            


    def cleanAndExit(self):
        print( "Cleaning...")
        GPIO.cleanup()
        print ("Bye!")
        sys.exit()
    
def runprog():
    app = App(maxring=5, average=3)
    '''
    logger = logging.getLogger("DaemonLog")
    logger.setLevel(logging.INFO)
    formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    handler = logging.FileHandler("/var/log/birdfeederdaemon/birdfeederdaemon.log")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    
    daemon_runner = runner.DaemonRunner(app)
    #This ensures that the logger file handle does not get closed during daemonization
    daemon_runner.daemon_context.files_preserve=[handler.stream]
    daemon_runner.do_action()
    '''
    app.run()

if __name__ == '__main__':
    watcher_ip = open('watcher_ip').read()
    runprog()
