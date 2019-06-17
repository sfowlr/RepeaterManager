#
# Copyright 2019 Spencer Fowler
#
# web_server.py - AsyncIO based Web Server class for viewing live and historical
# system and call log info from multiple DMR repeaters. 
#  
# Uses SSE and/or [soon]Websockets to stream live updates to each browser client
# after an initial GET request to retreive historical data.
#

import asyncio
import json
from aiohttp import web
from aiohttp.web import Application, Response
from aiohttp_sse import sse_response
import weakref
import datetime
import os
import functools



class WebServer:
    def __init__(self):
        path = os.path.abspath(__file__)
        self.dir_path = os.path.dirname(path)

        self.sse_clients = set()
        loop = asyncio.get_event_loop()
        self.app = Application(loop=loop)
        self.app.router.add_route('POST', '/send', self.message)
        self.app.router.add_route('GET', '/sse', self.sse_streamer)
        self.app.router.add_route('GET', '/', self.index)
        self.app.router.add_route('GET', '/devices', self.get_devices)
        self.app.router.add_static('/', self.dir_path+'/static/')
        self.devices_handler = None


    def run(self, host='127.0.0.1', port=8080):
        web.run_app(self.app, host=host, port=port)


    async def _add_to_queues(self, payload):
        for queue in self.sse_clients:
            await queue.put(payload)


    def fanout(self, message):
        # now = datetime.datetime.now()
        payload = json.dumps(dict(message))
        coro = self._add_to_queues(payload)
        asyncio.run_coroutine_threadsafe(coro, self.app.loop)


    async def get_devices(self, request):
        if not callable(self.devices_handler):
            raise web.HTTPNotImplemented
        body = json.dumps(self.devices_handler())
        return Response( body=body, content_type='application/json')


    async def sse_streamer(self, request):
        async with sse_response(request) as response:
            app = request.app
            queue = asyncio.Queue()
            print('Someone joined.')
            self.sse_clients.add(queue)
            try:
                while not response.task.done():
                    payload = await queue.get()
                    await response.send(payload)
                    queue.task_done()
            finally:
                self.sse_clients.remove(queue)
                print('Someone left.')
        return response


    async def message(self, request):
        app = request.app
        data = await request.post()
        self.fanout(data)
        return Response()


    async def index(self, request):
        return web.FileResponse(self.dir_path+'/static/index.html')


