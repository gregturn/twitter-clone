"""
   Copyright 2010 Greg L. Turnquist, All Rights Reserved

   Licensed under the Apache License, Version 2.0 (the "License");
   you may not use this file except in compliance with the License.
   You may obtain a copy of the License at

       http://www.apache.org/licenses/LICENSE-2.0

   Unless required by applicable law or agreed to in writing, software
   distributed under the License is distributed on an "AS IS" BASIS,
   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
   See the License for the specific language governing permissions and
   limitations under the License.       
"""

import logging
import os.path
import pickle
import pika
import threading
import time

from springpython.context import DisposableObject, InitializingObject

class Receiver(threading.Thread, DisposableObject, InitializingObject):
    def __init__(self, message_store=None):
        threading.Thread.__init__(self)
        self.logger = logging.getLogger("twitter_clone.controller.Receiver")
        self.message_store = message_store

    def after_properties_set(self):
        self.logger.debug("Starting up separate thread for this object.")
        self.start()

    def destroy(self):
        # Try to nicely shutdown the connection, but swallow any errors that occur
        try:
            self.conn.close()
        except Exception, e:
            self.logger.error(e)
        self.conn = None

    def run(self):
        self.receive_message()

    def receive_message(self):
        self.logger.debug("Connecting to RabbitMQ broker...")
        self.conn = pika.AsyncoreConnection(pika.ConnectionParameters(
                '127.0.0.1',
                credentials = pika.PlainCredentials('guest', 'guest'),
                heartbeat = 10))

        self.logger.debug('Connected to %r' % (self.conn.server_properties,))

        self.logger.debug("Creating channel...")
        ch = self.conn.channel()
        self.logger.debug("Declaring queue...")
        ch.queue_declare(queue="twitter", durable=True, exclusive=False, auto_delete=False)

        def handle_delivery(ch, method, header, body):
            self.logger.debug("Received a message. Parsing...")
            self.logger.debug("method=%r" % method)
            self.logger.debug("header=%r" % header)
            self.logger.debug("  body=%r" % body)
            ch.basic_ack(delivery_tag = method.delivery_tag)
            self.logger.debug("self.message_store = %s" % self.message_store)
            self.message_store.append(pickle.loads(body))

        self.logger.debug("Consuming a message...")
        ch.basic_consume(handle_delivery, queue = "twitter")
        self.logger.debug("Looping...")
        pika.asyncore_loop() 
        self.conn.close()
        self.logger.debug('Close reason: %s' % str(conn.connection_close))

    def send_message(self, pickled_message):
        conn = pika.AsyncoreConnection(pika.ConnectionParameters(
                '127.0.0.1',
                credentials=pika.PlainCredentials('guest', 'guest')))

        ch = conn.channel()
        ch.queue_declare(queue="twitter", durable=True, exclusive=False, auto_delete=False)

        ch.basic_publish(exchange='',
                         routing_key="twitter",
                         body=pickled_message,
                         properties=pika.BasicProperties(
                                content_type = "text/plain",
                                delivery_mode = 2, # persistent
                                ),
                         block_on_flow_control = True)

        conn.close()

class MessageStore(object):
    filename = ".tweets"

    def __init__(self):
        #self._data = [("Hello, world!", "gregturn", "1:32pm"), ("This is really cool", "gregturn", "2:43pm"), ("These tweets are neat.", "gregturn", "4:52pm")]
        if os.path.exists(self.filename):
            f = open(self.filename)
            self._data = pickle.load(f)
            f.close()
        else:
            self._data = []

    def append(self, item):
        self._data.append(item)
        f = open(self.filename, "w")
        pickle.dump(self._data, f)
        f.close()

    def popleft(self):
        return self._data.popleft()

    def get_data(self):
        return [x for x in self._data]

