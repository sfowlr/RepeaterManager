#! /usr/bin/env python3
#
# Copyright 2019 Spencer Fowler
#
# repeater_manager.py
#
# Entry point for multi-repeater management web server and call log aggregator.
#
#

import web_server
import localdb
import paho.mqtt.client
import json

server = web_server.WebServer() 
db = localdb.LocalDb()


def on_connect(client, userdata, flags, rc):
    print('MQTT Connected')
    client.subscribe('+/info', 1) 
    client.subscribe('+/1', 1) 
    client.subscribe('+/2', 1) 


def on_message(client, userdata, message):
    # print(message)
    topic = message.topic.split('/')
    repeater_id = topic[0]
    msg_type = topic[1]

    if msg_type == 'info':
        ...

    elif msg_type == '1':
        ...

    elif msg_type == '2':
        ...

    # payload = json.loads(message.payload)
    payload = message.payload.decode('utf-8')
    server.fanout({'sender':repeater_id, 'message':payload})


    # db.record_observation((message.topic, message.payload))

    


def main():
    mqtt_client = paho.mqtt.client.Client()
    mqtt_client.on_connect = on_connect
    mqtt_client.on_message = on_message
    mqtt_client.connect('linux.spencerfowler.com')
    mqtt_client.loop_start()

    db.open('repeater_manager.db')

    # This is blocking, starts an asyncio event loop:
    server.run(host='127.0.0.1', port=8080)

    mqtt_client.disconnect()
    mqtt_client.loop_stop()
    db.close()


if __name__ == '__main__':
    main()