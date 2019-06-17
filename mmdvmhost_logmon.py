#!/usr/bin/env python
#
# I know this should've been in python3, but it's not. I'm ashamed of myself.
#
# Copyright 2019 Spencer Fowler
#
# MMDVMHost DMR Log Monitoring/Reporting Service
#
# This program reports log data from an MMDVM-based repeater controller to
# a central MQTT broker, where it can be aggregated, logged, and displayed
# on a log viewing website.
#
# Requirements:
# paho-mqtt
#
# Optional:
# pyinotify
# systemd
#
# There may be more requirements, these are all I can recall at the moment. Eventually I'll
# make a real requirements.txt file if this code gets further developed.
#

import glob
import sys, os
from optparse import OptionParser
from Queue import Queue
from threading import Thread
import subprocess
import paho.mqtt.client as mqtt
import json
mqttc = mqtt.Client()

try:
    import pyinotify
    systemd_mode = False
except:
    from systemd import journal
    import select
    systemd_mode = True


repeater_id = 0

global dmrStatus
dmrStatus=[{},{}]

global oldDmrStatus
oldDmrStatus=[{},{}]

global dmrInfo
dmrInfo={}

def get_repeater_id():
    global repeater_id
    repeater_id = int(subprocess.check_output(['awk', '-F', '=', '/^Id=/ {print $2}', '/etc/mmdvmhost']))
    print("Repeater ID: "+str(repeater_id))

if not systemd_mode:
    def killListener():
        global killListenerLoop
        global listener_t
        global listenerProcess

        killListenerLoop = True
        listenerProcess.kill()
        print("waiting for listener to die")
        listener_t.join()

    # the event handlers:
    class PTmp(pyinotify.ProcessEvent):
        def process_IN_MODIFY(self, event):
            global fh
            #read_mmdvm_line(fh.readline().rstrip())
            #q.put(fh.readline().rstrip())
            pass

        def process_IN_CREATE(self, event):
            print("new file: " + os.path.join(event.path, event.name))
            if(event.name[0:6] == "MMDVM-"):
                print("Switching to new file")
                global wm
                global fh
                #old_wd = wm.get_wd(os.path.realpath(fh.name))
                #print("removing WD " + str(old_wd))
                #wm.rm_watch(old_wd)
                fh.close
                fh = open(os.path.join(event.path, event.name), 'r')



                latest_file = os.path.join(event.path, event.name)
                global listener_t
                killListener()
                listener_t = Thread(target = reader_thread, args=[latest_file, True])
                listener_t.daemon = True
                listener_t.start()
                return


                # catch up, in case lines were written during the time we were re-opening:
                if options.debug:
                    print("My file was created! I'm now catching up with lines in the newly created file.")
                for line in fh.readlines():
                    #print(line.rstrip())
                    #read_mmdvm_line(line.rstrip())
                    q.put(line.rstrip())
                # then skip to the end, and wait for more IN_MODIFY events
                wm.add_watch(fh.name, pyinotify.IN_MODIFY)
                fh.seek(0,2)
            return


    def reader_thread(filename, readHistory=False):
        print("Starting log listener")
        global killListenerLoop
        global listenerProcess
        if readHistory:
            opts = '-Fn100'
        else:
            opts = '-Fn0'

        listenerProcess = subprocess.Popen(['tail',opts,filename], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        while True:
            line = listenerProcess.stdout.readline()
            q.put(line)
            if killListenerLoop:
                print("Killing listener")
                try:
                    listenerProcess.kill()
                except:
                    pass
                killListenerLoop = False
                break
else:

    def systemd_reader_thread():
        dmrlog = journal.Reader()
        dmrlog.this_boot()
        dmrlog.log_level(journal.LOG_INFO)
        dmrlog.add_match(_SYSTEMD_UNIT="mmdvmhost.service")
        dmrlog.seek_tail()
        dmrlog.get_previous()
        p = select.poll()
        p.register(dmrlog, dmrlog.get_events())
        while True:
            if p.poll(250):
                if dmrlog.process() == journal.APPEND:
                    for entry in dmrlog:
                        try:
                            line = entry['MESSAGE']
                            #print(line)
                            q.put(line)
                        except:
                            pass


def log_worker():
    print("Starting log worker")
    while True:
        item = q.get()
        try:
            read_mmdvm_line(item)
        except KeyError:
            pass

q = Queue()
t = Thread(target = log_worker)
t.daemon = True


def read_mmdvm_line(line):
    global dmrStatus
    global dmrInfo
    #print(line)
    line = line.rstrip('\n').split(' ')
    if (line[0] == 'I:'):
        if (line[3] == ''):
            # Indented line, probably configuration parameters
            if (line[8] == 'Frequency:'):
                if (line[7] == 'RX'):
                    dmrInfo['RxFreq'] = line[9]
                elif (line[7] == 'TX'):
                    dmrInfo['TxFreq'] = line[9]
            elif (line[7] == 'Power:'):
                dmrInfo['Power'] = line[8]
            elif (line[7] == 'Latitude:'):
                dmrInfo['Latitude'] = line[8][0:-3]
            elif (line[7] == 'Longitude:'):
                dmrInfo['Longitude'] = line[8][0:-3]
            elif (line[7] == 'Height:'):
                dmrInfo['Height'] = line[8]
            elif (line[7] == 'Location:'):
                dmrInfo['Location'] = ' '.join(line[8:]).strip('\"')
            elif (line[7] == 'Callsign:'):
                dmrInfo['Callsign'] = line[8]
            elif (line[7] == 'Color' and line[8] == 'Code:'):
                dmrInfo['ColorCode'] = line[9]

    elif (line[0] == 'M:'):
        if (line[4] == 'is' and line[5] == 'running'):
            # MMDVMHost Startup complete
            dmrInfo['Version'] = line[3]
            print(dmrInfo)
            mqttc.publish(str(repeater_id) + "/info", json.dumps(dmrInfo), 0, True)


        elif (line[3] == 'DMR' and line[4] == 'Slot'):
            slot = int(line[5].rstrip(','))-1

            if (line[6] == 'ended'):
                # Data endings
                dmrStatus[slot]['Status'] = "Idle"
            elif (line[8] == 'end'):
                # Voice endings
                dmrStatus[slot]['Status'] = "Idle"
                dmrStatus[slot]['Length'] = line[12]+"s"
                if (line[7] == 'RF'):
                    dmrStatus[slot]['BER'] = line[15]
                    dmrStatus[slot]['Loss'] = ""
                elif (line[7] == 'network'):
                    dmrStatus[slot]['BER'] = line[18]
                    dmrStatus[slot]['Loss'] = line[14]

            else:
                # All starts/continuations
    #            dmrStatus[slot]['BER'] = None
    #            dmrStatus[slot]['Loss'] = None
    #            dmrStatus[slot]['Length'] = None
                try:
                    del dmrStatus[slot]['BER']
                except:
                    pass
                try:
                    del dmrStatus[slot]['Loss']
                except:
                    pass
                try:
                    del dmrStatus[slot]['Length']
                except:
                    pass

                if (line[6] == 'RF' or line[7] == 'RF'):
                    dmrStatus[slot]['Status'] = "RX"
                    dmrStatus[slot]['Origin'] = 'RF'
                elif (line[7] == 'network'):
                    dmrStatus[slot]['Status'] = "TX"
                    dmrStatus[slot]['Origin'] = 'Net'


                if ((line[8] == 'voice' and line[9] == 'header') or (line[8] == 'late' and line[9] == 'entry')):
                    # Voice Start
                    dmrStatus[slot]['Mode'] = "Voice"
                    dmrStatus[slot]['Source'] = line[11]
                    if (line[13] == 'TG'):
                        dmrStatus[slot]['Destination'] = line[14]
                        dmrStatus[slot]['CallType'] = 'Group'
                    else:
                        dmrStatus[slot]['Destination'] = line[13]
                        dmrStatus[slot]['CallType'] = 'Private'
                    try:
                        del dmrStatus[slot]['Length']
                    except:
                        pass

                elif (line[8] == 'SMS' or line[8] == 'data' or line[8] == "Data"):
                    # Data Start
                    dmrStatus[slot]['Mode'] = "Data"
                    if (line[9] == 'Preamble'):
                        dmrStatus[slot]['Source'] = line[15]
                        if (line[17] == 'TG'):
                            dmrStatus[slot]['Destination'] = line[18]
                            dmrStatus[slot]['CallType'] = 'Group'
                        else:
                            dmrStatus[slot]['Destination'] = line[17]
                            dmrStatus[slot]['CallType'] = 'Private'
                    elif (line[9] == 'header'):
                        dmrStatus[slot]['Source'] = line[11]
                        if (line[13] == 'TG'):
                            dmrStatus[slot]['Destination'] = line[14]
                            dmrStatus[slot]['CallType'] = 'Group'
                            dmrStatus[slot]['Length'] = line[15]+"bl"
                        else:
                            dmrStatus[slot]['Destination'] = line[13]
                            dmrStatus[slot]['CallType'] = 'Private'
                            dmrStatus[slot]['Length'] = line[14]+"bl"

    #        if dmrStatus[slot]['Status'] == "Idle" or True :
            global oldDmrStatus
            if cmp(dmrStatus[slot], oldDmrStatus[slot]):
                # Dictionary has changed
                # print(dmrStatus[slot])
                sys.stdout.flush()
                oldDmrStatus[slot] = dmrStatus[slot].copy()
                global repeater_id
                mqttc.publish(str(repeater_id) + "/"+ str(slot+1), json.dumps(dmrStatus[slot]), 0, True)

def on_message(client, userdata, msg):
    return


def main():
    get_repeater_id()

    parser = OptionParser()
    parser.add_option("--debug", help="print debug messages", action="store_true", dest="debug")
    (options, args) = parser.parse_args()

    mqttc.on_message = on_message
    mqttc.connect("linux.spencerfowler.com")
    mqttc.loop_start()

    t.start()

    if systemd_mode:

       # listener_t = Thread(target = systemd_reader_thread)
       systemd_reader_thread()

    else:
        myfile = args[0]
        if options.debug:
            print("Input path argument: " + myfile)

        global wm
        wm = pyinotify.WatchManager()

        # Find the newest file
        list_of_files = glob.glob(myfile)
        latest_file = max(list_of_files, key=os.path.getctime)
        print("Opening log file " + latest_file)

        global fh
        # open file, skip to end..
        fh = open(latest_file, 'r')
        fh.seek(0,2)
        notifier = pyinotify.Notifier(wm, PTmp())

        print("Watching file: " + latest_file)
    #    wm.add_watch(latest_file, pyinotify.IN_MODIFY)
        index = myfile.rfind('/')
        print("Watching directory " + myfile[:index])
        wm.add_watch(myfile[:index], pyinotify.IN_CREATE)


        print(wm.watches)

        global killListenerLoop
        killListenerLoop = False
        global listener_t
        listener_t = Thread(target = reader_thread, args=[latest_file, False])
        listener_t.daemon = True
        listener_t.start()


        while True:
            try:
                notifier.process_events()
                if notifier.check_events():
                    notifier.read_events()
            except KeyboardInterrupt:
                break

        # cleanup: stop the inotify, and close the file handle:
        notifier.stop()
        fh.close()

    sys.exit(0)

if __name__ == "__main__":
    main()
