#!/usr/bin/env python
'''
Created on Jul 12, 2012

@author: dwilson
'''

import sys, os
import gobject, pygst
pygst.require("0.10")
import gst
import commands
import threading
from constants import *

class video_chat:
    
    def __init__(self):
        self.vc_file = CONFIG_DIR + "/confs/VC-default.txt"
        try:
            with open(self.vc_file, 'rt') as f: # Open the config file and extract the video config info
                self.props = {}  # Dictionary
                for line in f.readlines():
                    val = line.split('=')
                    self.props[val[0].strip()] = val[1].strip()  # Match each key with its value
                
                self.video_width, self.video_height = int(self.props["width"]), int(self.props["height"])
                self.localip, self.localport = self.props["localip"], self.props["localport"]
                self.remoteip, self.remoteport = self.props["remoteip"], self.props["remoteport"]
        except: 
            print "Couldn't load video chat configuration."
            return

        
        #Set up the streaming pipelines
        self.start_video_receiver()
        #raw_input("Press Enter to start streaming your video camera")
        self.setup_streaming_video()
        
    def start_video_receiver(self):
        #webm encoded video receiver
        self.receivepipe = gst.parse_launch("tcpserversrc host=" + self.localip + " port=" + self.localport + " ! matroskademux name=d d. ! queue2 ! vp8dec ! ffmpegcolorspace ! xvimagesink name=sink d. ! queue2 ! vorbisdec ! audioconvert ! audioresample ! alsasink sync=false") 
        self.receivepipe.set_state(gst.STATE_PLAYING)
        
        self.sink = self.receivepipe.get_by_name("sink")
        bus = self.receivepipe.get_bus()
        bus.add_signal_watch()
#        bus.enable_sync_message_emission()
        bus.connect("message", self.on_message)
#        bus.connect("sync-message::element", self.on_sync_message)
        
#        self.receivepipe.set_state(gst.STATE_PLAYING)
        print "Video Chat Receiver started"
        
    def get_camera_name(self, index = 0):
        #Get the first camera's device number
        listOfCameras = commands.getoutput("dir -format -1 /dev | grep 'video*'").split("\n")
        camCount = str(len(listOfCameras))
        device = ""
        if camCount == 0:
            print "No cameras were detected.  You can't stream video, but you can receive it."
        else:
            if camCount == 1: 
                print "There is " + str(camCount) + " cameras (" + listOfCameras + ")"
            else:
                print "There are " + str(camCount) + " camera(s)"
            device = "/dev/" + listOfCameras[index]
        
        return device
    
    def video_is_streaming(self):
        if self.streampipe.get_state()[1] == gst.STATE_PLAYING:
            return True
        return False
    
    def setup_streaming_video(self):
        #webm video pipeline, optimized for video conferencing
        device = self.get_camera_name()
        self.streampipe = gst.parse_launch("v4l2src device=" + device + " ! video/x-raw-rgb, width=640, height=480 ! ffmpegcolorspace ! vp8enc speed=2 max-latency=2 quality=10.0 max-keyframe-distance=3 threads=5 ! queue2 ! mux. alsasrc device=plughw:1,0 ! audioconvert ! vorbisenc ! queue2 ! mux. webmmux name=mux streamable=true ! tcpclientsink host=" + self.remoteip + " port=" + self.remoteport)
        self.streampipe.set_state(gst.STATE_PLAYING)
    
    def start_streaming_video(self):
        #self.receivepipe.set_state(gst.STATE_PLAYING)
        print self.video_is_streaming()
        if not self.video_is_streaming(): 
            self.streampipe.set_state(gst.STATE_PLAYING)
    
    def pause_streaming_video(self):
        self.streampipe.set_state(gst.STATE_PAUSED)
        #self.receivepipe.set_state(gst.STATE_PAUSED)
    
    def stop_streaming_video(self):
        self.receivepipe.set_state(gst.STATE_NULL)
        self.streampipe.set_state(gst.STATE_NULL)
        #print "state: " + str(self.receivepipe.get_state())
        #self.receivepipe.set_state(gst.STATE_PAUSED)

    def on_message(self, bus, message):
        t = message.type
        if t == gst.MESSAGE_EOS:
            self.stop_streaming_video()
        elif t == gst.MESSAGE_ERROR:
            err, debug = message.parse_error()
            print "Error: %s" % err, debug
            self.stop_streaming_video()
        elif t == gst.MESSAGE_STATE_CHANGED:
            #print 'Message: ' + str(message)
            old, new, pending = message.parse_state_changed()
            #print new
            if new == gst.STATE_NULL:
                print 'stopped'
        
    '''def on_sync_message(self, bus, message):
        if message.structure is None:
            return False
        name = message.structure.get_name()
        if name == "prepare-xwindow-id":
            print self.video_container.window
            gtk.gdk.threads_enter()
            gtk.gdk.display_get_default().sync()
            
            videooutput = message.src
            videooutput.set_property("force-aspect-ratio", True)
            videooutput.set_xwindow_id(self.video_container.window.xid)
            gtk.gdk.threads_leave()'''
