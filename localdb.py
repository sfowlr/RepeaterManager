#
# Copyright 2019 Spencer Fowler
#
# localdb.py
#
# Generic database wrapper class for efficiently aggregating sensor data into a
# SQLite database (will be adapted for additional database types in the future).
#
#

import os
import datetime
import sqlite3
import queue
import threading
import time

MAX_RECORD_QUEUE_SIZE = 500
SCHEMA_FILENAME = os.path.join(os.path.dirname(__file__), 'default_schema.sql')

class LocalDb(object):

    def __init__(self, db_path='', this_device_id=None, auto_start=True):
        self.auto_start = auto_start
        self.recorder_enabled = False
        self._record_thread = None
        self.this_device_id = this_device_id
        self.db_path = db_path
        self._record_queue = queue.Queue(MAX_RECORD_QUEUE_SIZE)


    def __del__(self):
        self.close()


    def open(self, db_name=None):
        self.start_new_db(db_name)
        if self.auto_start:
            self.start_recording()


    def close(self):
        self.stop_worker()
        try:
            self.stop_recording()
            self._db.commit()
            self._db.close()
            print('Saved database at {fullpath}'.format(fullpath=self.db_fullpath))
        except (sqlite3.ProgrammingError, AttributeError):
            pass # If an existing connection exists, close it. Otherwise ignore

    def start_worker(self):
        try:
            self._record_thread = threading.Thread(target=self.record_worker)
            self.recorder_enabled = True
            self._record_thread.start()
        except RuntimeError:
            raise
            # Ignore attempts to start a thread that is already running
            pass

    def stop_worker(self):
        if self._record_thread is None:
            return
        try:
            self.recorder_enabled = False
            print("Joining worker thread")
            self._record_thread.join()
            print("Worker stopped")
            self._record_thread = None
        except RuntimeError:
            # Ignore attempts to stop a thread that is already stopped
            pass


    def start_new_db(self, db_name=None):
        self.stop_worker()
        self.close()

        if db_name == None:
            self.db_name = (
                'localdb-' +
                datetime.datetime.now().strftime('%Y%m%d-%H%M%S') +
                '.db' )
        else:
            self.db_name = db_name

        self.db_fullpath = os.path.abspath(os.path.join(self.db_path, self.db_name))
        existing_db = True if os.path.isfile(self.db_fullpath) else False
        self._db = sqlite3.connect(self.db_fullpath)
        self._db.execute('pragma journal_mode=wal')
        if not existing_db:
            self.initialize_db()
            print('New Database created at {fullpath}'.format(fullpath=self.db_fullpath))
        else:
            print('Opened existing database at {fullpath}'.format(fullpath=self.db_fullpath))
        self.load_obs_types()
        self.load_devices()
        self.load_sessions()
        self._db.commit()
        self.start_worker()

    def load_obs_types(self):
        # Get Observation Types
        curs = self._db.cursor()
        curs.row_factory = sqlite3.Row
        curs.execute('SELECT * from ObservationTypes')
        self._obs_types = curs.fetchall()
        curs.close()

    def load_devices(self):
        # Get Devices
        curs = self._db.cursor()
        curs.row_factory = sqlite3.Row
        curs.execute('SELECT * from Devices')
        self._devices = curs.fetchall()
        curs.close()

    def load_sessions(self):
        # Get Recording Sessions
        curs = self._db.cursor()
        curs.row_factory = sqlite3.Row
        curs.execute('SELECT * from RecordingSessions')
        self._sessions = curs.fetchall()
        curs.close()


    def initialize_db(self):
        with open(SCHEMA_FILENAME, 'r') as f:
            cursor = self._db.cursor()
            cursor.executescript(f.read())
            cursor.close()

    def find_observation_type(self, topic):
        # Search Observation Types list for a topic pattern match
        obs_type_idx = None
        wildcard_idx = None
        for idx, obs_type in enumerate(self._obs_types):
            if obs_type['TypeTopicPattern'] == '*':
                wildcard_idx = idx
                continue
            topic_pattern = obs_type['TypeTopicPattern'].split('+')
            match = False
            if len(topic_pattern) == 1:
                # print('Topic has no + symbol. Start: {} '.format(topic_pattern[0]))
                if topic.startswith(topic_pattern[0]):
                    match = True
            else:
                # print('Topic has a + symbol. Start: {}  End: {}'.format(topic_pattern[0], topic_pattern[1]))
                if (topic.startswith(topic_pattern[0]) and
                    topic.endswith(topic_pattern[1]) ):
                    match = True
            if match:
                obs_type_idx = idx
                break
        if obs_type_idx is not None:
            return self._obs_types[obs_type_idx]
        elif wildcard_idx is not None:
            return self._obs_types[wildcard_idx]
        else:
            return None

    def find_recording_session(self):
        curs = self._db.cursor()
        # curs.row_factory = sqlite3.Row
        curs.execute('SELECT SessionId from RecordingSessions WHERE IsRecording = 1 AND EndDT IS NULL LIMIT 1')
        result = curs.fetchall()
        curs.close()
        if len(result):
            return result[0][0]
        else:
            return None

    def find_or_create_device(self, topic):
        # TODO: This currently only handles local device ID! Add support for remote devices
        # topic_split = topic.split('/')
        # for part in topic_split:
        #     try:
        #         incoming_id = int(part)
        #         break
        #     except ValueError:
        #         continue
        if self.this_device_id is not None:
            device_id = self.this_device_id
        # curs = self._db.cursor()
        # curs.execute('INSERT OR IGNORE INTO Devices (DeviceId, Description) VALUES (?, ?)', (device_id, 'Local Device'))
        # curs.close()
        return device_id

    def start_recording(self):
        curs = self._db.cursor()
        # curs.row_factory = sqlite3.Row
        curs.execute('SELECT SessionId from RecordingSessions WHERE IsRecording = 1 AND EndDT IS NULL LIMIT 1')
        result = curs.fetchall()
        if len(result):
            existing_session=result[0][0]
        else:
            curs.execute('INSERT INTO RecordingSessions DEFAULT VALUES')
            self._db.commit()
        curs.close()

    def stop_recording(self):
        curs = self._db.cursor()
        # curs.row_factory = sqlite3.Row
        curs.execute('SELECT SessionId from RecordingSessions WHERE IsRecording = 1 AND EndDT IS NULL LIMIT 1')
        result = curs.fetchall()
        if len(result):
            existing_session=result[0][0]
            curs.execute('UPDATE RecordingSessions SET EndDT = CURRENT_TIMESTAMP, IsRecording = 0 WHERE SessionId = ?' , ( existing_session,) )
            self._db.commit()
        curs.close()

    def record_observation(self, obs):
        rx_timestamp = datetime.datetime.now()

        recording_session_id = self.find_recording_session()
        if recording_session_id is None:
            print('No active recording session.')
            return -1

        if type(obs) == tuple:
            topic = obs[0]
            payload = obs[1]
            if len(obs) > 2:
                rx_timestamp = obs(3)
        elif type(obs) == dict:
            topic = obs['Topic']
            payload = obs['Payload']
            try:
                rx_timestamp = obs['Time']
            except:
                pass
        obs_type = self.find_observation_type(topic)
        if obs_type is not None:
            # print("Observation Type match found: {}".format(obs_type['TypeName']))
            if not obs_type['ShouldRecord']:
                # print('Recording disabled for this type.')
                return 0
        else:
            # print("No Observation Type match found.")
            return -1

        device_id = self.find_or_create_device(topic)

        # print('QUEUE RECORD')
        self._record_queue.put(
            (rx_timestamp,
            topic,
            payload,
            device_id,
            recording_session_id,
            obs_type['TypeId']
            ), timeout=0.01)
        return 1

    def record_generator(self):
        try:
            return self._record_queue.get(timeout=0.001)
        except queue.Empty:
            return None

    # def record_generator(self):
    #     try:
    #         for item in iter(self._record_queue.get_nowait, None):
    #             yield(item)
    #     except queue.Empty or TypeError:
    #         return


    def record_worker(self):
        # self.start_new_db()

        worker_conn = sqlite3.connect(self.db_fullpath)
        worker_conn.execute('pragma journal_mode=wal')

        print("Started Worker Thread")

        while self.recorder_enabled == True:
            qsize = self._record_queue.qsize()
            if qsize:
                curs = worker_conn.cursor()
                curs.executemany(
                    '''INSERT INTO Observations(
                        StoreDT,
                        TopicName,
                        ObservationValue,
                        Device,
                        RecordingSession,
                        ObservationType
                        ) VALUES (?,?,?,?,?,?)''',
                    # self.record_generator())
                    iter(self.record_generator, None))
                # print('exec done')
                curs.close()
                worker_conn.commit()
                # print('committed {qsize} items'.format(qsize=qsize))

            time.sleep(.1)

        try:
            worker_conn.commit()
            print("Committed all changes from worker connection")
            worker_conn.close()
            print("Closed worker connection")

        except AttributeError:
            pass # If an existing connection exists, close it. Otherwise ignore

