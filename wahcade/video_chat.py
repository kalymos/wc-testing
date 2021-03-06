#!/usr/bin/env python
'''
Created on Jul 12, 2012

@author: dwilson
'''

import os
import pygst
pygst.require("0.10")
import gst
import commands
from constants import CONFIG_DIR
import requests
import socket
import gtk
import inspect

class video_chat():
    
    def __init__(self, WinMain):
        self.WinMain = WinMain
        self.enabled = True
        self.receiver_running = False
        
        self.streampipe = None
        self.receivepipe = None

        self.video_width, self.video_height = 320, 240
        self.localip, self.localport = str(self.get_local_ip()), str(self.get_open_port())
        #self.localip = "127.0.0.1" #manual override for testing on one machine
        #self.localip = "localhost" #manual override for testing on one machine
        self.remoteip, self.remoteport = "", "" #self.localip, self.localport #do a video loopback initially
        
        self.enabled = self.camera_available() #disables video chat if no cameras are found
    
    def setup_video_streamer(self):
        #webm video pipeline, optimized for video conferencing
        videoSrc = "autovideosrc" #auto detect the source
        command = videoSrc + " ! video/x-raw-rgb, width=" + str(self.video_width) + ", height=" + str(self.video_height) + " "
        command += "! ffmpegcolorspace ! vp8enc speed=2 max-latency=2 quality=10.0 max-keyframe-distance=3 threads=5 " 
        command += "! queue2 ! mux. autoaudiosrc ! audioconvert ! vorbisenc " 
        command += "! queue2 ! mux. webmmux name=mux streamable=true "
        command += "! tcpserversink host=" + self.localip + " port=" + self.localport
        
        self.streampipe = gst.parse_launch(command)
        #start the video stream
        self.streampipe.set_state(gst.STATE_PLAYING)
        bus = self.streampipe.get_bus()
        bus.add_signal_watch()
        bus.connect("message", self.on_stream_message)

        print "Streaming video on " + self.localip + ":" + self.localport
    
    def setup_video_receiver(self):
        #webm encoded video receiver
        command = "tcpclientsrc host=" + self.remoteip + " port=" + self.remoteport + " " 
        command += "! matroskademux name=d d. ! queue2 ! vp8dec ! ffmpegcolorspace ! xvimagesink name=sink " 
        command += "d. ! queue2 ! vorbisdec ! audioconvert ! audioresample ! alsasink"
        self.receivepipe = gst.parse_launch(command) 
        #self.receivepipe.set_state(gst.STATE_PLAYING)
        self.sink = self.receivepipe.get_by_name("sink")
        bus = self.receivepipe.get_bus()
        bus.add_signal_watch()
        bus.connect("message", self.on_message)
        bus.enable_sync_message_emission()
        bus.connect("sync-message::element", self.on_sync_message)
        self.receiver_running = True
        print 'Receiver running on', self.remoteip, self.remoteport
        
    def receiver_ready(self):
        if not self.receivepipe:
            return False
        return True
    
    def is_loopback(self):
        return (self.localip == self.remoteip and self.localport == self.remoteport)
    
    def get_local_ip(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 80)) #connect to Google's DNS server
        #self.local_IP = s.getsockname()[0] #Get local ip address
        localip = s.getsockname()[0]
        s.close()
        return localip
    
    def get_open_port(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.bind(("",0))
        s.listen(1)
        port = s.getsockname()[1]
        s.close()
        return port
    
    def camera_available(self):
        camNames = commands.getoutput("dir -format -1 /dev | grep 'video*'").strip()
        if len(camNames) == 0:
            return False
        else:
            return True
    
    def get_camera_name(self, index = 0):
        #Get the first camera's device number
        listOfCameras = commands.getoutput("dir -format -1 /dev | grep 'video*'").strip().split("\n")
        camCount = len(listOfCameras)
        device = ""
        if self.camera_available():
            if camCount == 1: 
                print "There is 1 camera: " + ", ".join(listOfCameras)
            else:
                print "There are", camCount, "cameras: " + ", ".join(listOfCameras)
            device = "/dev/" + listOfCameras[index]
        
        return device
    
    def set_remote_info(self, ip, port):
        self.remoteip = ip
        self.remoteport = port
    
    def get_remote_info(self):
        return (self.remoteip, self.remoteport)
    
    def video_is_streaming(self):
        if self.streampipe and self.streampipe.get_state()[1] == gst.STATE_PLAYING:
            return True
        return False
    
    def start_streaming_video(self):
        if self.streampipe and not self.video_is_streaming(): 
            self.streampipe.set_state(gst.STATE_PLAYING)
    
    def stop_streamer(self):
        if self.streampipe:
            self.streampipe.set_state(gst.STATE_NULL)
    
    def start_receiver(self):
        if self.receivepipe:
            self.receivepipe.set_state(gst.STATE_PLAYING)
            #self.receiver_running = True
            
    def stop_receiver(self):
        if self.receivepipe:
            self.receivepipe.set_state(gst.STATE_NULL)
            self.receiver_running = False

    def kill_pipelines(self):
        if self.streampipe:
            self.stop_streamer()
        if self.receivepipe:
            self.stop_receiver()
    
    def on_message(self, bus, message):
        t = message.type
        if t == gst.MESSAGE_EOS:
            was_running = self.receiver_running
            self.receiver_running = False
            self.stop_receiver()
            if was_running and hasattr(self.WinMain, 'start_video_chat') and hasattr(self.WinMain, 'manualVCMode'):
                self.remoteip = self.localip
                self.remoteport = self.localport
                self.WinMain.start_video_chat()
                self.WinMain.manualVCMode = False
            #self.kill_pipelines()
        elif t == gst.MESSAGE_ERROR:
            self.receiver_running = False
            err, debug = message.parse_error()
            print "Receiver Error: %s" % self.remoteip, self.remoteport, err, debug
            #self.kill_pipelines()
            self.stop_receiver()
#        elif t == gst.MESSAGE_STATE_CHANGED:
#            #print 'Message: ' + str(message)
#            old, new, pending = message.parse_state_changed()
            #print "Receiver State: " + str(new)
    
    def on_sync_message(self, bus, message):
        if message.structure is None:
            return False
        name = message.structure.get_name()
        print name
        if name == "prepare-xwindow-id":
            gtk.gdk.threads_enter()
            gtk.gdk.display_get_default().sync()
            videooutput = message.src
            videooutput.set_property("force-aspect-ratio", True)
            self.WinMain.vc_box.show()
            if self.WinMain.vc_box and self.WinMain.vc_box.window:
                videooutput.set_xwindow_id(self.WinMain.vc_box.window.xid)
            else:
                print "Video Chat Error: Unable to link the video source to the receiver sink."
            gtk.gdk.threads_leave()
    
    def on_stream_message(self, bus, message):
        t = message.type
        if t == gst.MESSAGE_ERROR:
            err, debug = message.parse_error()
            print "Stream Error: %s" % err, debug
            #self.kill_pipelines()
            self.stop_streamer()
#        elif t == gst.MESSAGE_STATE_CHANGED:
#            #print 'Stream Message: ' + str(message)
#            old, new, pending = message.parse_state_changed()
            #print "Stream State: " + str(new)

#Creates a stand alone version of video chat
class standalone_player():
    def __init__(self):
        self.vc = video_chat(self)
        
        self.vc.remoteip = self.vc.localip
        self.vc.remoteport = self.vc.localport
        
        window = gtk.Window()
        window.set_title('Video Chat Test')
        #window.set_default_size(640, 480)
        window.connect("destroy", gtk.main_quit, "WM destroy")
        
        fixed = gtk.Fixed()
        vbox = gtk.VBox()
        self.vc_box = gtk.DrawingArea()
        self.vc_box.set_size_request(self.vc.video_width,self.vc.video_height)
        startStreamButton = gtk.Button("Start Streaming")
        startStreamButton.connect("clicked", self.OnStreamStart)
        stopStreamButton = gtk.Button("Stop Streaming")
        stopStreamButton.connect("clicked", self.OnStreamStop)
        
        startReceiveButton = gtk.Button("Start Receiving")
        startReceiveButton.connect("clicked", self.OnReceiveStart)
        stopReceiveButton = gtk.Button("Stop Receiving")
        stopReceiveButton.connect("clicked", self.OnReceiveStop)
        
        self.remoteip = gtk.Entry()
        self.remoteip.set_text(self.vc.remoteip)
        self.remoteport = gtk.Entry()
        self.remoteport.set_text(self.vc.remoteport)
        
        remoteInfo = gtk.HBox()
        remoteInfo.add(self.remoteip)
        remoteInfo.add(self.remoteport)
        
        buttonBox = gtk.HButtonBox()
        buttonBox.add(startStreamButton)
        buttonBox.add(stopStreamButton)
        buttonBox.add(startReceiveButton)
        buttonBox.add(stopReceiveButton)
        
        vbox.pack_start(self.vc_box)
        vbox.pack_start(buttonBox)
        vbox.pack_start(remoteInfo)
        
        fixed.put(vbox, 0, 0)
        window.add(fixed)
        
        window.show_all()
    
    def OnStreamStart(self, widget):
        self.vc.setup_video_streamer()
        
    def OnStreamStop(self, widget):
        self.vc.stop_streamer()
    
    def OnReceiveStart(self, widget):
        if not self.remoteip.get_text() == "":
            self.vc.remoteip = self.remoteip.get_text()
        if not self.remoteport.get_text() == "":
            self.vc.remoteport = self.remoteport.get_text()
        self.vc.setup_video_receiver()
        self.vc.start_receiver()
    def OnReceiveStop(self, widget):
        self.vc.stop_receiver()
    
if __name__ == "__main__":
    standalone_player()
    gtk.gdk.threads_init()
    gtk.main()
