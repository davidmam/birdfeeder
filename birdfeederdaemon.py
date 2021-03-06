# -*- coding: utf-8 -*-
"""
Created on Tue Jan  3 19:44:16 2017

Data logging for weighing birdfeeder

@author: David
"""


# To kick off the script, run the following from the python directory:
#   PYTHONPATH=`pwd` python testdaemon.py start

#standard python libs
import sys
import logging
import time
import statistics
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

MONGODBCLIENT='bird-db.local'

class App():
    
    def __init__(self, maxring=5, average=5, smoothingbuffersize=1024,sensitivity=1.5):
        self.initialising = True
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
        self.smoothingbuffersize = smoothingbuffersize
        self.avecount=average
        client = MongoClient(MONGODBCLIENT)
        self.db=client.test.birdfeeder
        time.sleep(2)
        self.feeder.tare()
        self.initialising = False
        print('Tare complete')
            
    def run(self):
        while self.initialising:
            print('Waiting for initialising')
            time.sleep(2)
        ringbuffer = []
        maxringsize = self.maxringsize
        smoothingbuffer = []
        pos = 0
        sbpos = 0
        lastweight = 0 
        sensitivity = 2 # minimum change to record
        while True:
            try:
                weight = self.feeder.get_weight(self.avecount)                
                assert weight
                timestamp = datetime.now()
                if len(ringbuffer) <maxringsize:
                    ringbuffer.append((weight,timestamp))
                else:
                    ringbuffer[pos] = (weight, timestamp)
                thisweight = median([x[0] for x in ringbuffer])
                if len(smoothingbuffer) <self.smoothingbuffersize:
                    smoothingbuffer.append((timestamp, thisweight))
                else:
                    smoothingbuffer[sbpos] = (timestamp,thisweight)
                if len(smoothingbuffer) >50:
                    stdev = statistics.stdev([x[1] for x in smoothingbuffer])
                    threshold = stdev * sensitivity
                else:
                    threshold=8
                if abs(thisweight - lastweight) >threshold:
                    # trigger photo here
                    tag = datetime.now().strftime('%Y%m%d%H%M%S')
                    try:
                        url = 'http://'+watcher_ip+'/take-image?tag='+tag
                        print(url)
                        response=urlopen(url)
                    except:
                        print('No response from', watcher_ip)
                    for n in ringbuffer:
                
                # save median value
                
                        self.db.insert({'Sensor': 'birdfeeder', 
                                        'timestamp': n[1],
                                        'weight': n[0], 
                                        'change': thisweight-lastweight,
                                        'sd': stdev,
                                        'tag': tag} )
                #self.feeder.power_down()
                #self.feeder.power_up()
                pos = (pos+1)%maxringsize
                sbpos = (sbpos+1)%self.smoothingbuffersize
                lastweight = thisweight
                if sbpos ==0:
                    ofh = open('weightdata/{}.txt'.format(timestamp),'w')
                    data = sorted([x for x in smoothingbuffer if x[1]], key=lambda x:x[0])
                    mw = statistics.mean([x[1] for x in data])
                    print('Current weight: {: .2f} Mean weight: {: .2f} SD: {: .2f} Threshold: {: .2f}'.format(lastweight, statistics.mean([x[1] for x in data]), stdev, threshold))
                    print('Current weight: {: .2f} Mean weight: {: .2f} SD: {: .2f} Threshold: {: .2f}'.format(lastweight, statistics.mean([x[1] for x in data]), stdev, threshold), file=ofh)
                    for w in data:
                        if w[1]:
                            print(w[0], w[1], w[1] - mw, sep='\t' ,file=ofh)

                    #logging.info('Current weight: {} Mean weight: {} SD: {} Threshold: {}'.format(lastweight, statistics.mean(smoothingbuffer), stdev, threshold))
                    ofh.close()

                time.sleep(0.01)

                
            except (KeyboardInterrupt, SystemExit):
                self.cleanAndExit()
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
    
def runprog(sensitivity=1.5):
    app = App(maxring=5, average=3, sensitivity=sensitivity)
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
    watcher_ip = open('watcher_ip').read().strip()
    if len(sys.argv) >1:
        sens =float(sys.argv[1])
    else:
        sens = 1.5

    runprog(sensitivity=sens)
