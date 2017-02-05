# -*- coding: utf-8 -*-
"""
Created on Wed Jan 25 20:35:03 2017

@author: David
"""
import datetime
import glob
import logging
import os
import sys
import time
import subprocess
import picamera
import picamera.array
import numpy as np
import pyexiv2
from PIL import Image
from PIL import ImageFont
from PIL import ImageDraw
from fractions import Fraction
from subprocess import call
from flask import Flask, send_file,request, render_template,send_from_directory
from pymongo import MongoClient
from bson.json_util import dumps

app=Flask(__name__)

mypath = os.path.abspath(__file__)  # Find the full path of this python script
baseDir = os.path.dirname(mypath)  # get the path location only (excluding script name)
baseFileName = os.path.splitext(os.path.basename(mypath))[0]
progName = os.path.basename(__file__)
logFilePath = os.path.join(baseDir, baseFileName + ".log")
print("----------------------------------------------------------------------------------------------")
# print("%s %s" %( progName, progVer ))

configFilePath = os.path.join(baseDir, "config.py")
if not os.path.exists(configFilePath):
    print("ERROR - Cannot Import Configuration Variables. Missing Configuration File %s" % ( configFilePath ))
    quit()
else:
    # Read Configuration variables from config.py file
    print("Importing Configuration Variables from File %s" % ( configFilePath ))    
    from config import *

def writeTextToImage(imagename, datetoprint):
    # function to write date/time stamp directly on top or bottom of images.
    FOREGROUND = ( 255, 255, 255 )  # rgb settings for white text foreground
    textColour = "White"

    # centre text and compensate for graphics text being wider
    x = int((imageWidth/2) - (len(imagename)*2))
    if showTextBottom:
        y = (imageHeight - 50)  # show text at bottom of image 
    else:
        y = 10  # show text at top of image
    TEXT = imageNamePrefix + datetoprint
    font_path = '/usr/share/fonts/truetype/freefont/FreeSansBold.ttf'
    font = ImageFont.truetype(font_path, showTextFontSize, encoding='unic')
    text = TEXT.decode('utf-8')

    # Read exif data since ImageDraw does not save this metadata
    img = Image.open(imagename)
    metadata = pyexiv2.ImageMetadata(imagename) 
    metadata.read()
    
    draw = ImageDraw.Draw(img)
    # draw.text((x, y),"Sample Text",(r,g,b))
    draw.text(( x, y ), text, FOREGROUND, font=font)
    img.save(imagename)
    metadata.write()    # Write previously saved exif data to image file
    logging.info("Added %s Text[%s] on %s", textColour, datetoprint, imagename)
    return

def getImageName(path, prefix):
    # build image file names by number sequence or date/time

    rightNow = datetime.datetime.now()
    filename = "%s/%s%04d%02d%02d-%02d%02d%02d.jpg" % ( path, prefix ,rightNow.year, rightNow.month, rightNow.day, rightNow.hour, rightNow.minute, rightNow.second)     
    return filename

def getVideoName(path, prefix):
    # build image file names by number sequence or date/time

    rightNow = datetime.datetime.now()
    filename = "%s/%s%04d%02d%02d-%02d%02d%02d.h264" % ( path, prefix ,rightNow.year, rightNow.month, rightNow.day, rightNow.hour, rightNow.minute, rightNow.second)
    return filename

def takeDayImage(filename):
    # Take a Day image using exp=auto and awb=auto
    with picamera.PiCamera() as camera:
            camera.resolution = (imageWidth, imageHeight)
            camera.vflip = imageVFlip
            camera.hflip = imageHFlip
            camera.rotation = imageRotation #Note use imageVFlip and imageHFlip variables
            sleep(0.2)
            camera.capture(filename, use_video_port=useVideoPort)
    logging.info("Size=%ix%i exp=auto awb=auto %s" % (imageWidth, imageHeight, filename))
    return

def takeWebcamImage(filename):
    call(["fswebcam", "-d","/dev/video0", "-r", "640x480", "--no-banner", filename])


def takeVideo(filename):
    # Take a short motion video if required
    logging.info("Size %ix%i for %i sec %s" % (imageWidth, imageHeight, motionVideoTimer, filename))
    if motionVideoOn:
        with picamera.PiCamera() as camera:
            camera.resolution = (imageWidth, imageHeight)
            camera.vflip = imageVFlip
            camera.hflip = imageHFlip
            camera.rotation = imageRotation #Note use imageVFlip and imageHFlip variables
            if showDateOnImage:
                rightNow = datetime.datetime.now()            
                dateTimeText = " Started at %04d-%02d-%02d %02d:%02d:%02d " % (rightNow.year, rightNow.month, rightNow.day, rightNow.hour, rightNow.minute, rightNow.second)
                camera.annotate_text_size = showTextFontSize
                camera.annotate_foreground = picamera.Color('black')
                camera.annotate_background = picamera.Color('white')               
                camera.annotate_text = dateTimeText              
            camera.start_recording(filename)
            camera.wait_recording(motionVideoTimer)
            camera.stop_recording()
        # This creates a subprocess that runs convid.sh with the filename as a parameter
        try:
            convid = "%s/convid.sh %s" % ( baseDir, filename )        
            proc = subprocess.Popen(convid, shell=True,
                             stdin=None, stdout=None, stderr=None, close_fds=True) 
        except IOError:
            print("subprocess %s failed" %s ( convid ))
        else:        
            print("unidentified error")
        createSyncLockFile(filename)            
    return
    
@app.route('/')
def hello():
    return "Hello World!"

@app.route('/take-image')
def take_image():
    filename = getImageName(motionDir, imageNamePrefix)
    daystamp = datetime.datetime.now().strftime('%Y%m%d')
    tag = request.args.get('tag')
    takeDayImage(filename)
    revfn = getImageName(motionDir, 'reverse')
    writeTextToImage(filename, str(datetime.datetime.now()))
    if tag:
        db = MongoClient('192.168.0.4')
        db.test.birdwatcher.insert({'tag':tag, 'filename':filename,
                                     'day': daystamp})
        db.test.birdwatcher.insert({'tag':tag, 'filename':revfn,
                                     'day': daystamp})
    return send_file(open(filename, 'rb'), mimetype='image/jpeg')

@app.route('/take-video')
def take_video():
    filename = getVideoName(motionDir, imageNamePrefix)
    takeVideo(filename)
    return take_image()

@app.route('/show-image')
def show_image():
    '''return a specific image'''
    filename=request.args.get('filename','Notfound.png')
    return send_file(open('motion/'+filename, 'rb'), mimetype='image/jpeg')
    
@app.route('/list-images')
def list_images():
    '''list images for a specific day'''
    daystamp = datetime.datetime.now().strftime('%Y%m%d')
    daystamp = request.args.get('day', daystamp)
    files = sorted([ x for x in os.listdir('motion') if daystamp in x ])
    day = datetime.datetime.strptime(daystamp, '%Y%m%d')
    db = MongoClient('192.168.0.4').test.birdwatcher
    cursor = db.find({'day': daystamp})
    filelist = [ x for x in cursor if x['filename'][7:] in files]
    nextday = day + datetime.timedelta(days=1)
    previousday =day - datetime.timedelta(days=1)
    return render_template('filelist.html', heading = 'images for '+daystamp,
                           images=filelist, nextday=nextday.strftime('%Y%m%d'), 
                           previousday=previousday.strftime('%Y%m%d'))
    
@app.route('/image-details')
def image_details():
    filename=request.args.get('filename')
    if filename is None:
        return render_template('Notfound.html')
    imgtime = datetime.datetime.strptime(filename, imageNamePrefix+'%Y%m%d-%H%M%S.jpg')
    td = datetime.timedelta(seconds=5.5)
    db = MongoClient('192.168.0.4')
    
    fileinfo = db.test.birdwatcher.find_one({'filename': 'motion/'+filename})
    if fileinfo and 'tag' in fileinfo:
        cursor = db.test.birdfeeder.find({'tag': fileinfo['tag']})
    else:
         cursor = db.test.birdfeeder.find({'timestamp': {'$gte': imgtime - td, '$lte': imgtime }})
    entries = sorted([y for y in cursor],key=lambda x:x['timestamp'])    
    weights = [x['weight'] for x in entries] 
    change = max(weights)-min(weights)
    changesign = 'arrived'
    if weights[0] > weights[-1]:
        changesign = 'departed'
    files=sorted(os.listdir('motion'))
    fileindex = files.index(filename)
    nextfile = files[-1]
    if fileindex < len(files) -1:
        nextfile = files[fileindex + 1]
    previousfile = files[fileindex - 1]
    return render_template('imageinfo.html', filename=filename, 
                           changesign=changesign, change=change, weights=entries,
                           nextfile=nextfile, previousfile=previousfile, 
                           fileinfo=fileinfo, timestamp=imgtime)
 
@app.route('/bird-details', methods=['POST'])
def bird_details():
    '''setter for bird details'''
    picid = request.form.get('picid')
    bird = request.form.get('species')
    db = MongoClient('192.168.0.4')
    db.test.birdwatcher.update({'filename': 'motion/'+picid},
                              {'$set': {'species': bird}},
                              upsert=True)

    return dumps({'species':bird,
		'id': picid} )


@app.route('/static/js/<path:path>')
def send_js(path):
    return send_from_directory('static/js', path)
                            
    
if __name__=='__main__':
    #with picamera.PiCamera() as camera:
     #   camera.resolution = (imageWidth, imageHeight)
    app.run(port=8000, host='0.0.0.0', debug=True)
