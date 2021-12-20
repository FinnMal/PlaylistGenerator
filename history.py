import json
import time
import sqlite3
from datetime import datetime, timedelta
import uuid

config = json.loads(open("config.json", "r", encoding='utf-8').read())

print("HISTORY v.1.0")


class History:
    conn = None
    c = None
    try:
        last_artists = json.loads(open("...", "r").read())
    except Exception as e:
        last_artists = []

    def _save_last_artists(self):
        with open("...", 'w') as outfile:
            json.dump(self.last_artists, outfile)

    def _openDatabase(self):
        if self.conn is None and self.c is None:
            self.conn = sqlite3.connect(config["paths"]["database"])
            self.c = self.conn.cursor()

    def _saveChanges(self):
        self.conn.commit()

    def _closeDatabase(self):
        self.conn.close()
        self.conn = None
        self.c = None

    def _getAll(self, command):
        self._openDatabase()
        self.c.execute(command)
        res = self.c.fetchall()
        self._closeDatabase()
        return res

    @staticmethod
    def _isList(var):
        return isinstance(var, list)

    def delete(self):
        self._openDatabase()
        self.c.execute('DELETE FROM item_locks')
        # self.c.execute('DELETE FROM playlistlog WHERE studio="PLAYLIST-GENERATOR"')
        self.resetLastArtists()
        self._saveChanges()
        self._closeDatabase()

    def deleteOldLocks(self, at_date):
        at_time = time.mktime(at_date.timetuple())
        self._openDatabase()
        self.c.execute(
            'DELETE FROM item_locks WHERE end_time < ' + str(at_time))
        self._saveChanges()
        self._closeDatabase()

    def deleteOldLogs(self, at_time):
        range_end = datetime.strptime(at_time.strftime("%d/%m/%Y"), "%d/%m/%Y")
        range_start = range_end - timedelta(hours=2)
        self._openDatabase()
        self.c.execute('DELETE FROM playlistlog WHERE (starttime < "'+range_start.strftime('%Y-%m-%d %H:%M:%S.000') +
                       '" OR starttime > "'+range_end.strftime('%Y-%m-%d %H:%M:%S.000')+'") AND  studio = "PLAYLIST-GENERATOR"')
        self._saveChanges()
        self._closeDatabase()

    def resetLastArtists(self):
        self.last_artists = []
        for i in range(0, config["min_artist_distance"]):
            self.last_artists.append([""])
        self._save_last_artists()

    def addLock(self, track):
        if track.getValue("Type") == "Music":
            duration = round(pow(0.9, 0.21 * track.getPoints()) * 18, 2)
            min_song_distance_used = False
            if track.getPoints() > 100:
                min_song_distance_used = True
                duration = config["min_song_distance_hour"]

            start_time = track.getValue("PlannedTime") - 7200

            lock = {
                "start": start_time,
                "end": start_time + duration * 3600,
                "duration": round(duration * 3600),
                "min_song_distance_used": min_song_distance_used
            }

            track.setValue("Lock", lock)

            # save into logs
            self._openDatabase()
            self.c.execute('INSERT INTO playlistlog VALUES ("' + datetime.fromtimestamp(lock["start"]).strftime(
                '%Y-%m-%d %H:%M:%S.000') + '", 1, "PLAYLIST-GENERATOR", ' + str(
                track.getDatabaseID()) + ', "{' + str(uuid.uuid4()) + '}", NULL, "' + str(
                track.getDurationSec()) + '", 0, 0, NULL)')
            self.c.execute('INSERT INTO item_locks VALUES (' + str(track.getDatabaseID()) + ', ' +
                           str(lock["start"]) + ', ' + str(lock["end"]) + ', ' + str(lock["duration"]) + ')')
            self._saveChanges()
            self._closeDatabase()

    def addToLastArtists(self, artist_s):
        if not self._isList(artist_s):
            artist_s = [artist_s]
        self.last_artists.append(artist_s)
        if len(self.last_artists) > 3:
            del self.last_artists[0]
        self._save_last_artists()

    def getLastArtists(self):
        return self.last_artists

    def setLastArtists(self, last_artists):
        self.last_artists = last_artists
        self._save_last_artists()

    def isLocked(self, databaseID, at_time):
        locks = self._getAll('SELECT * FROM item_locks WHERE item = ' + str(databaseID) +
                             ' AND start_time <= ' + str(at_time) + ' AND end_time >= ' + str(at_time))
        return len(locks) > 0

    def isInLastArtists(self, pPlaylistItem):
        if config["use_artist_distance"]:
            artist_s = pPlaylistItem.getArtists()
            if not self._isList(artist_s):
                artists = [artist_s]
            else:
                artists = artist_s

            artist_found = False
            for source_artist in artists:
                for last_artist in self.last_artists:
                    if source_artist in last_artist:
                        artist_found = True
            return artist_found
        return False
