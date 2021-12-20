# coding=utf-8
import json
import time
import math
import random
import urllib.request
import sqlite3
from datetime import datetime, timedelta
from playlist_item import PlaylistItem
from playlist import Playlist
from colorama import Back, Style
import os
import ssl
import shutil

config = json.loads(open("config.json", "r", encoding='utf-8').read())

print("DATABASE v.1.0")


class Database:
    history = None
    conn = None
    c = None
    weather_forecast = {}

    def __init__(self, pHistory):
        self.history = pHistory

    if (not os.environ.get('PYTHONHTTPSVERIFY', '') and getattr(ssl, '_create_unverified_context', None)):
        ssl._create_default_https_context = ssl._create_unverified_context

    def reset(self):
        self.weather_forecast = {}

    @staticmethod
    def _division(x, y, r=False):
        if y == 0 or x == 0:
            return 0
        if not r:
            return x / y
        else:
            return math.ceil(x / y)

    @staticmethod
    def _get(url):
        with urllib.request.urlopen(url) as url:
            return json.loads(url.read().decode())

    def _openConnection(self):
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
        self._openConnection()
        self.c.execute(command)
        res = self.c.fetchall()
        self._closeDatabase()
        return res

    def _getOne(self, command):
        self._openConnection()
        self.c.execute(command)
        res = self.c.fetchone()
        self._closeDatabase()
        return res

    def _executeAndSave(self, command):
        self._openConnection()
        self.c.execute(command)
        res = self.c.fetchone()
        self._saveChanges()
        self._closeDatabase()
        return res

    @staticmethod
    def createJingle(jingle):
        jingle_info = {
            "Title": jingle["name"],
            "Artist": "Radio JFM",
            "Duration": jingle["duration"],
            "Filename": config["paths"]["jingles"] + "/" + jingle["filename"],
            "Type": "Jingle",
            "Class": "File",
            "Customized": True
        }
        jingleItem = PlaylistItem()
        jingleItem.importJson(jingle_info)
        return jingleItem

    @staticmethod
    def createPromotionHook(file, duration_sec, track):
        promotion_info = {
            "Title": 'Promotion',
            "Artist": track.getTitle(),
            "Duration": duration_sec,
            "Filename": file,
            "Type": "Promo",
            "Class": "File",
            "Customized": True
        }
        promotionItem = PlaylistItem()
        promotionItem.importJson(promotion_info)
        return promotionItem

    def createPlaylistItem(self, databaseID):
        databaseID = str(databaseID)

        playlist_item = PlaylistItem()
        playlist_item.importJson({
            "DatabaseID": databaseID,
            "Type": "Music",
            "State": "Normal",
            "Class": "File"
        })

        fetch = self._getOne(
            "SELECT * FROM 'items' WHERE idx='" + databaseID + "'")

        playlist_item.setValue("Title", fetch[2])
        playlist_item.setValue("Artist", fetch[3])
        playlist_item.setValue("Duration", fetch[6])
        playlist_item.setValue("Amplification", fetch[8])
        playlist_item.setValue(
            "Filename", config["paths"]["music"] + "/" + fetch[15])

        playlist_item.setValue(
            "Levels", {"Loudness": fetch[22], "TruePeak": fetch[21], "Peak": fetch[20]})

        # attributes
        attributes = self._getAll(
            "SELECT * FROM 'item_attributes' WHERE item='" + databaseID + "'")

        for attribute in attributes:
            playlist_item.setAttribute(attribute[1], attribute[2])

        playlist_item.setAttribute('Lyrics', 'nein')

        if not playlist_item.getAttribute("Spotify Artist IDs"):
            playlist_item.setAttribute("Spotify Artist IDs", "Null")

        # markers
        cue_markers = self._getAll(
            "SELECT * FROM 'item_cuemarkers' WHERE item='" + databaseID + "'")

        for cue_marker in cue_markers:
            cue_marker = list(cue_marker)
            if cue_marker[1] == 'CueIn' and ((cue_marker[2] < 0 and cue_marker[2] != -1) or self._division(cue_marker[2], playlist_item.getValue('Duration')) > 0.5):
                cue_marker[2] = 0

            if cue_marker[2] >= 0 or cue_marker[2] == -1:
                playlist_item.setMarker(cue_marker[1], cue_marker[2])

        return playlist_item

    def getPlaylistRestrictions(self, date):
        for plan in config['special_playlists']:
            if date.weekday() in plan['days']:
                if date.hour in plan['hours']:
                    return plan

    def getAvailablePlaylistItems(self, date):
        # songs with zero points per tag
        unusable_tracks = {}
        unusable_tracks_count = 0

        # plan from 'special_playlists' in config.json
        plan = self.getPlaylistRestrictions(date)

        if not plan:
            # every song that is playable at this hour
            all_tracks = self._getSongsByHour(date)
        else:
            print('SPECIAL PLAYLIST FOUND')
            # get all songs that fit in plan
            all_tracks = self._getSongsByPlan(plan)

        # remove already played songs
        filtered_playlist = Playlist(date)
        for track in all_tracks:
            track_used = False
            if not self._isItemPlaned(track.getDatabaseID(), date) and not track.isGerman():
                if track.fileExists():
                    # give points depending on playlist date
                    result = self._calculatePoints(track, date)
                    if result["Points"] > 0:
                        track.setPoints(result["Points"])
                        track.setValue("PointsSubdivision",
                                       result["PointsSubdivision"])
                        filtered_playlist.append(track)
                        track_used = True
                    else:
                        if track.getAttribute("Bewertung") not in unusable_tracks:
                            unusable_tracks[track.getAttribute(
                                "Bewertung")] = 0
                        unusable_tracks[track.getAttribute("Bewertung")] = unusable_tracks[
                            track.getAttribute("Bewertung")] + 1

            if not track_used:
                unusable_tracks_count = unusable_tracks_count + 1
        print(unusable_tracks)
        filtered_playlist.setValue(
            "StartLength", filtered_playlist.getLength())
        filtered_playlist.setValue("UnavailableSongs", unusable_tracks_count)
        return filtered_playlist

    def getYouTubeStats(self, youtube_id, day=0):
        date = (datetime.strptime(datetime.now().strftime("%d/%m/%Y"),
                "%d/%m/%Y") + timedelta(days=day)).timestamp()
        return self._getOne(
            'SELECT * FROM youtube_statistics WHERE youtube_id = "' + str(youtube_id) + '" and date = ' + str(date))

    def deleteOldYouTubeStats(self):
        max_age_timestamp = round((datetime.now() - timedelta(days=14)).timestamp())
        self._executeAndSave('DELETE FROM youtube_statistics WHERE date < ' + str(max_age_timestamp))

    def deleteOldMixdowns(self):
        # delete mixdowns from yesterday
        y = datetime.now() - timedelta(days=1)
        mixdown_folder = config['paths']['mixdowns'] + '/' + y.strftime('%Y') + '/' + y.strftime('%m') + '/' + y.strftime('d')
        if os.path.exists(mixdown_folder):
            shutil.rmtree(mixdown_folder, ignore_errors=True)
            print('[DATABASE] Mixdowns von gestern gelöscht')

    def deleteDuplicates(self):
        duplicates = self._getAll('SELECT item, Count(*) FROM item_attributes as First JOIN items AS Second on First.item = Second.idx WHERE First.name == "Spotify ID" GROUP BY value HAVING COUNT(*) > 1')
        i = 0
        if duplicates:
            if len(duplicates) > 0:
                for track in duplicates:
                    # check if track is active
                    track_id = str(track[0])
                    active = self._getOne('SELECT value FROM item_attributes WHERE item == "'+track_id+'" and name == "active"')
                    if active and len(active) > 0 and active[0] == 'ja':
                        i = i+1
                        self._executeAndSave('UPDATE item_attributes SET value="nein" WHERE item="' + track_id + '" AND name="active"')
            if i > 0:
                print('REMOVED '+str(i)+' DUPLICATES FROM DATABASE')

    def _isSummerWeather(self, date):
        return self.getWeather(date)["has_summer_weather"]

    def getWeather(self, date):
        timestamp = str(round(time.mktime(date.timetuple())))
        if timestamp not in self.weather_forecast:
            weather = self._get('URL_TO_WEATHER_API?t=' + timestamp)
            if weather:
                self.weather_forecast[timestamp] = weather
                self.weather_forecast[timestamp]["has_summer_weather"] = False
                if weather["temp"] > 20:
                    if weather["weather"] == "clear sky" or weather["weather"] == "scattered clouds" or weather[
                            "weather"] == "broken clouds":
                        self.weather_forecast[timestamp]["has_summer_weather"] = True
                if self.weather_forecast[timestamp]["has_summer_weather"]:
                    print(Back.BLUE + "HAS SUMMER WEATHER WITH " + str(weather["temp"]) + "°C and " + str(
                        weather["weather"]) + Style.RESET_ALL)
                else:
                    print(Back.RED + "HAS NO SUMMER WEATHER WITH " + str(weather["temp"]) + "°C and " + str(
                        weather["weather"]) + Style.RESET_ALL)
            else:
                self.weather_forecast[timestamp] = {'has_summer_weather': False}
                print(Back.RED + 'ERROR WHILE FETCHING WEATHER' + Style.RESET_ALL)
        return self.weather_forecast[timestamp]

    def _calculatePoints(self, track, date):
        subdivision = []

        log_command = "SELECT * FROM 'playlistlog' WHERE item=" + track.getDatabaseID() + " AND (studio == '...' OR item=" + \
            track.getDatabaseID() + " AND starttime > '" + \
            date.strftime('%Y-%m-%d')+"')"
        found_in_log = self._getOne("SELECT EXISTS("+log_command+")")[0]

        logs = []
        plays_last_seven_days = 0
        seven_days_ago = (date - timedelta(days=7)).timestamp()

        latest_start_time = 0
        if found_in_log == 1:
            logs = self._getAll(log_command)

            for log in logs:
                played_dur = log[6]
                if played_dur is None:
                    played_dur = 0
                played_percentage = (played_dur / track.getValue("Duration"))

                if played_percentage > 0.5:
                    if len(log[0]) == 23:
                        log_start_timestamp = time.mktime(
                            datetime.strptime(log[0][:-4], "%Y-%m-%d %H:%M:%S").timetuple())
                    else:
                        log_start_timestamp = time.mktime(
                            datetime.strptime(log[0], "%Y-%m-%d").timetuple())

                    if log_start_timestamp < time.mktime(date.timetuple()):
                        if log_start_timestamp > seven_days_ago:
                            plays_last_seven_days = plays_last_seven_days + 1

                        if log_start_timestamp > latest_start_time:
                            latest_start_time = log_start_timestamp

        days_ago = (time.mktime(date.timetuple()) - latest_start_time) / 86400

        # created and released
        released_at = int(track.getAttribute('Release Date')) + 1000
        created_at = self._getAll(
            "SELECT created FROM 'items' WHERE idx='" + track.getDatabaseID() + "'")[0]
        created_at = time.mktime(datetime.strptime(
            created_at[0][:-4], "%Y-%m-%d %H:%M:%S").timetuple())

        days_since_import = round(
            (time.mktime(date.timetuple()) - created_at) / 86400)
        if released_at > 0:
            days_since_release = round(
                (time.mktime(date.timetuple()) - released_at) / 86400)
        else:
            days_since_release = -1

        track.setValue("DaysSinceImport", days_since_import)
        track.setValue("DaysSinceRelease", days_since_release)
        av_plays_per_day = self._division(len(logs), days_since_import)
        av_plays_last_week = self._division(plays_last_seven_days, 7)

        # add points
        # give created points not each new item, to avoid playing every [min_song_distance] hour
        track.setValue("Plays", len(logs))
        track.setValue("PlaysPerDay", av_plays_per_day)
        track.setValue("AvPlaysLastWeek", av_plays_last_week)
        track.setValue("PlaysLastWeek", plays_last_seven_days)
        track.setAttribute("IsNew", "nein")
        track.setAttribute("HasPoints", "ja")

        # points for high valence at summer day
        if self._isSummerWeather(date):
            valence = track.getValence()
            if valence > config["categorizations"]["low_valence"]:
                add_points = (100 * valence)
                subdivision.append({"title": "Hohe Valence im Sommer", "value": add_points,
                                    "calc_value": str(valence)})

        if days_since_import <= config["categorizations"]["track_new"]:
            add_points = (-3.3 * days_since_import + 100) / 2
            subdivision.append({"title": "Tage seit Import", "value": add_points,
                                "calc_value": str(round(days_since_import, 2)) + " Tage"})

        if days_since_release <= config["categorizations"]["track_new"]:
            track.setAttribute("IsNew", "ja")

        if days_since_release <= config["categorizations"]["track_age_middle"]:
            add_points = (-1.11 * days_since_release + 100) / 2
            subdivision.append({"title": "Alter", "value": add_points,
                                "calc_value": str(round(days_since_release, 2)) + " Tage"})

        if days_since_release <= config["categorizations"]["track_age_old"]:
            add_points = (14.286 * days_ago) / 3
            subdivision.append({"title": "Zuletzt gespielt", "value": add_points,
                                "calc_value": "Vor " + str(round(days_ago, 2)) + " Tagen"})

            """
            add_points = (-50 * av_plays_last_week + 100) / 3
            subdivision.append({"title": "Ø Gespielt pro Tag in letzter Woche", "value": add_points,
                                "calc_value": round(av_plays_last_week, 2)})
            """

            add_points = (-200 * av_plays_per_day + 100) / 2
            subdivision.append({"title": "Ø Gespielt pro Tag", "value": add_points,
                                "calc_value": round(av_plays_per_day, 2)})

        # points for youtube-stats
        youtube_id = track.getAttribute('YouTube ID')
        if youtube_id:
            cur_stats = None
            cur_stats_days_ago = -1
            while not cur_stats and cur_stats_days_ago > -7:
                cur_stats_days_ago = cur_stats_days_ago - 1
                cur_stats = self.getYouTubeStats(
                    youtube_id, cur_stats_days_ago)

            last_stats = None
            last_stats_days_ago = -8
            while not last_stats and last_stats_days_ago < -1:
                last_stats_days_ago = last_stats_days_ago + 1
                last_stats = self.getYouTubeStats(
                    youtube_id, last_stats_days_ago)
            last_stats_days_ago = last_stats_days_ago * (-1)

            if cur_stats and last_stats:
                stats_multiplicator = 7 / last_stats_days_ago

                views_last_week = last_stats[1]
                likes_last_week = last_stats[2]
                dislikes_last_week = last_stats[3]

                views_this_week = cur_stats[1]
                likes_this_week = cur_stats[2]
                dislikes_this_week = cur_stats[3]

                added_views = (views_this_week -
                               views_last_week) * stats_multiplicator
                added_likes = (likes_this_week -
                               likes_last_week) * stats_multiplicator
                added_dislikes = (dislikes_this_week -
                                  dislikes_last_week) * stats_multiplicator

                views_this_week = cur_stats[1] + \
                    (added_views - (views_this_week - views_last_week))
                likes_this_week = cur_stats[2] + \
                    (added_likes - (likes_this_week - likes_last_week))
                dislikes_this_week = cur_stats[3] + (
                    added_dislikes - (dislikes_this_week - dislikes_last_week))

                if added_likes < 0:
                    # added_dislikes = added_dislikes + (added_likes * (-1))
                    added_likes = 0

                if added_dislikes < 0:
                    # added_likes = added_likes + (added_dislikes * (-1))
                    added_dislikes = 0

                added_views_perc = self._division(
                    added_views, views_this_week) * 100
                added_likes_perc = self._division(
                    added_likes, likes_this_week) * 100
                added_dislikes_perc = self._division(
                    added_dislikes, dislikes_this_week) * 100
                added_votes_perc = self._division(
                    added_likes + added_dislikes, likes_this_week + dislikes_this_week)*100

                total_votes_last_week = likes_last_week + dislikes_last_week
                total_votes_this_week = total_votes_last_week + added_likes + added_dislikes

                total_added_votes = added_likes + added_dislikes

                voters_perc = self._division(
                    total_added_votes, total_votes_last_week) * 100

                positive_votes_this_week_perc_from_all_votes = self._division(
                    added_likes, total_added_votes) * 100
                negative_votes_this_week_perc_from_views = self._division(
                    added_dislikes, total_added_votes) * 100

                if added_dislikes < 1:
                    positive_votes_this_week_perc_from_views = -1

                if added_likes < 1:
                    positive_votes_this_week_perc_from_views = -1

                add_points = (1.5 * added_views_perc) / 2
                subdivision.append({
                    "title": "Views diese Woche in %",
                    "value": add_points,
                    "calc_value": str(round(added_views_perc, 2)) + "%"
                })

                if positive_votes_this_week_perc_from_all_votes != 100.0 and positive_votes_this_week_perc_from_all_votes > -1:
                    calc_value = (
                        positive_votes_this_week_perc_from_all_votes*added_votes_perc)/100
                    add_points = (5*calc_value)/2
                    subdivision.append({
                        "title": "(likes_w/votes_w)*(votes_w/all_votes) in %",
                        "value": add_points,
                        "calc_value": str(round(calc_value, 2)) + "%"
                    })

        # add points together
        points = 0
        for sub in subdivision:
            points = points + sub["value"]
            sub["value"] = round(sub["value"])

        track.setValue("HasLessPoints", points <
                       config["categorizations"]["less_points"])

        if track.getAttribute("IsNew") == "ja":
            if not (random.randrange(1, 100) < config["percentage_chances"]["give_new_songs_points"]):
                track.setAttribute("HasPoints", "nein")
                return {"Points": 0, "PointsSubdivision": []}

        if config['max_points'] > 0 and points > config["max_points"]:
            points = config['max_points']
        track.setAttribute("Points", round(points))
        return {"Points": round(points), "PointsSubdivision": subdivision}

    def _getSongsByHour(self, date, plan=None):
        active_tracks = self._getAll(
            "SELECT * FROM 'item_attributes' WHERE name='active' AND value='ja'")

        tracks = []
        pos = (date.weekday() * 24) + date.hour
        for t in active_tracks:
            if not plan:
                playable, restriction = self._isPlayableAtHour(t[0], date)
                if playable:
                    track = self.createPlaylistItem(t[0])
                    if not track.isOnBlacklist():
                        track.setAttribute('used_res', str(restriction))
                        track.setAttribute('res_weekday', str(date.weekday()))
                        track.setAttribute('res_hour', str(date.hour))
                        track.setAttribute('res_pos', str(pos))
                        tracks.append(track)
            else:
                track = self.createPlaylistItem(t[0])
                if not track.isOnBlacklist():
                    if track.hasOneSourcePlaylist(plan['source_playlists']):
                        if track.getEnergy() >= plan['min_energy']:
                            if track.getDanceability() >= plan['min_danceability']:
                                tracks.append(track)
        return tracks

    def _getSongsByPlan(self, plan):
        active_tracks = self._getAll(
            "SELECT * FROM 'item_attributes' WHERE name='active' AND value='ja'")

        tracks = []
        for track in active_tracks:
            track = self.createPlaylistItem(track[0])
            if track.hasOneSourcePlaylist(plan['source_playlists']):
                if track.getEnergy() >= plan['min_energy']:
                    if track.getDanceability() >= plan['min_danceability']:
                        tracks.append(track)
        return tracks

    def getAllSongs(self, active=True):
        if active:
            active = 'ja'
        else:
            active = 'nein'
        active_tracks = self._getAll(
            "SELECT * FROM 'item_attributes' WHERE name='active' AND value='" + active + "'")

        tracks = []
        for track in active_tracks:
            track = self.createPlaylistItem(track[0])
            if track not in tracks:
                tracks.append(track)
        return tracks

    def _isPlayableAtHour(self, databaseId, date):
        databaseId = str(databaseId)

        has_restriction = self._getOne(
            "SELECT EXISTS(SELECT hours FROM 'item_restrictions' WHERE item='" + databaseId + "' AND station='1')")[0]

        if has_restriction == 1:
            item_restriction = \
                self._getOne("SELECT hours FROM 'item_restrictions' WHERE item='" +
                             databaseId + "' AND station='1'")[0]
            pos = (date.weekday() * 24) + date.hour
            if len(item_restriction) > pos:
                char = item_restriction[pos]
                return [char == "1", item_restriction]
            else:
                print('[DATABASE] Error: restriction pos for '+str(databaseId)+' is to long. len(res): '+str(len(item_restriction))+', pos: '+str(pos))
        else:
            print('[DATABASE] Error: '+databaseId+' has no restriction')

        return [False, ""]

    def _isItemPlaned(self, databaseId, date):
        if config["use_song_distance"]:
            return self.history.isLocked(databaseId, time.mktime(date.timetuple()))
        return False

    def removeTrack(self, track):
        self._openConnection()
        self.c.execute('UPDATE item_attributes SET value = "nein" WHERE item = ' + str(
            track.getDatabaseID()) + ' and name = "active"')
        res = self.c.fetchall()
        self._saveChanges()
        self._closeDatabase()
        return res

    @staticmethod
    def _RepresentsInt(s):
        try:
            int(s)
            return True
        except ValueError:
            return False
