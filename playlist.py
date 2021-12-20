import random
import json
import os
import random
import urllib.request
import requests
from pydub import AudioSegment

config = json.loads(open("config.json", "r", encoding='utf-8').read())

print("PLAYLIST v.1.0")


class Playlist:
    def __init__(self, date, accepted_dur=3600, is_emergency=False):
        self.date = date
        self.hasPlan = False
        self.duration = 0
        self.items = []
        self.plan = {}
        self.attributes = {"BaseTime": date.strftime("%Y-%m-%dT%H:%M:%S"), "AveragePoints": 0}
        self.accepted_dur = accepted_dur
        self.is_emergency = is_emergency

    def checkForPlan(self):
        with urllib.request.urlopen(
                "FIREBASE_URL/" + str(self.date.year) + "/" + str(
                    self.date.month) + "/" + str(self.date.day) + "/" + str(self.date.hour) + ".json") as url:
            jfo = json.loads(url.read().decode())
            if jfo:
                print("PLAN FOUND")
                self.hasPlan = True
                self.plan = jfo
            else:
                print("NO PLAN FOUND")

    def setValue(self, name, value):
        self.attributes[name] = value

    def getValue(self, name):
        return self.attributes[name]

    def getLength(self):
        return len(self.items)

    def getDate(self):
        return self.date

    def generatePathAndFile(self, first_folder, file_extension, create_dir=True, filename=False):
        folder = first_folder + "/" + self.date.strftime("%Y") + "/" + self.date.strftime(
            "%m") + "/" + self.date.strftime("%d")

        if filename:
            folder = folder + '/' + self.date.strftime("%H")
        if create_dir:
            os.makedirs(folder, exist_ok=True)

        if not filename:
            return folder + "/" + self.date.strftime("%H") + file_extension
        else:
            return folder + "/" + filename + file_extension

    def getHour(self):
        return self.date.hour

    def getAveragePoints(self):
        total_items = 0
        total_points = 0
        for item in self.items:
            if item.getPoints() > -1:
                total_items = total_items + 1
                total_points = total_points + item.getPoints()
        return round(total_points / total_items)

    def append(self, item):
        self.items.append(item)
        self.duration = self.duration + item.getDuration()

    def remove(self, item):
        self.items.remove(item)
        self.duration = self.duration - item.getDuration()

    def insert(self, index, item, countDur=True):
        self.items.insert(index, item)
        if countDur:
            self.duration = self.duration + item.getDuration()

    def index(self, item):
        return self.items.index(item)

    def sort(self):
        if config["sort_songs_by_points"]:
            self.items = sorted(self.items, key=lambda x: x.getPoints(), reverse=True)
        return self.items

    def sortAsDuration(self, longestFirst=True, outputPlaylist=False):
        new_items = sorted(self.items, key=lambda x: x.getDurationSec(), reverse=longestFirst)
        return self._newPlaylist(new_items, outputPlaylist)

    def getItems(self):
        return self.items

    def getItemsWithValue(self, valueName, value, outputPlaylist=False):
        new_items = []
        for item in self.items:
            if item.getValue(valueName) == value:
                new_items.append(item)
        return self._newPlaylist(new_items, outputPlaylist)

    def importItems(self, items):
        self.duration = 0
        self.items = items
        for item in items:
            self.duration = self.duration + item.getDuration()

    def setDuration(self, pDuration):
        self.duration = pDuration

    def getDuration(self):
        dur = 0
        for i in self.items:
            dur = dur + i.getDuration()
        return dur
        # return round(self.duration)

    def isDurationOk(self):
        dur = self.getDuration()

        r = range(self.accepted_dur - config["max_playlist_len_diff"] * 60, self.accepted_dur + config[
            "max_playlist_len_diff"] * 60)
        return (dur in r) or (dur > self.accepted_dur + config["max_playlist_len_diff"] * 60)

    def getReamingSec(self):
        return round(self.accepted_dur - self.duration)

    def getItem(self, index):
        if index > -1:
            return self.items[index]
        else:
            return None

    def getItemCount(self):
        return len(self.items)

    def getRandomItem(self):
        if len(self.items) > 0:
            return random.choice(self.items)

    def shuffle(self, rounds=1):
        for i in range(0, rounds):
            random.shuffle(self.items)

    def sortItemsAs(self, sortValue, outputPlaylist=False):
        items = sorted(self.items, key=lambda x: x.getAttribute(sortValue), reverse=True)
        return self._newPlaylist(items, outputPlaylist)

    def compareAndRemoveItems(self,  valueName, comperator, value, outputPlaylist=False, source_list=False):
        if not source_list:
            source_list = self.items
        new_list = []
        for item in source_list:
            if comperator == '>':
                if item.getValue(valueName) < value:
                    new_list.append(item)
            elif comperator == '<':
                if item.getValue(valueName) > value:
                    new_list.append(item)
            elif comperator == '==':
                if item.getValue(valueName) != value:
                    new_list.append(item)
        return self._newPlaylist(new_list, outputPlaylist)

    def removeShorterItems(self, durationSec, outputPlaylist=False):
        new_list = []
        for item in self.items:
            if item.getDurationSec() >= durationSec:
                new_list.append(item)
        return self._newPlaylist(new_list, outputPlaylist)

    def filterItems(self, filterValueName, filterValue, outputPlaylist=True):
        items = [d for d in self.items if d.getAttribute(filterValueName) == filterValue]
        return self._newPlaylist(items, outputPlaylist)

    def filterItemsByVotes(self, votes, outputPlaylist=True):
        items = [d for d in self.items if config["votes_tags"].index(d.getAttribute("Bewertung")) in votes]
        return self._newPlaylist(items, outputPlaylist)

    def filterItemsByConditions(self, cond=False, second=False):
        # block playlists
        print(cond)
        cond['source_playlist_blacklist'] = []
        if 'used_tracks' in cond:
            if len(cond['used_tracks']) > 1:
                print('count is '+str(len(cond['used_tracks'])))
                last_tracks = reversed(cond['used_tracks'])

                for playlist_id in last_tracks[0].getSourcedPlaylists():
                    if playlist_id in last_tracks[1].getSourcedPlaylists():
                        cond['source_playlist_blacklist'].append(playlist_id)
        print(cond['source_playlist_blacklist'])

        filtered_items = []
        for item in self.items:
            r = item.isMeetingConditions(cond)
            if r[0]:
                filtered_items.append(item)
            # else:
            # print(r[1])

        if len(filtered_items) == 0 and not second and config['use_vote_condition']:
            # change vote because no results
            cond["votes"] = [a for a in [0, 1, 2] if a not in set(cond["votes"])]
            return self.filterItemsByConditions(cond, True)

        return self._newPlaylist(filtered_items)

    def _newPlaylist(self, items, outputPlaylist=True):
        if outputPlaylist:
            new_playlist = Playlist(self.date)
            new_playlist.importItems(items)
            return new_playlist
        else:
            return items

    def _exportToJson(self):
        if not self.is_emergency:
            self.setValue("AveragePoints", self.getAveragePoints())

        items = []
        for item in self.items:
            items.append(item.exportJson())
        self.setValue("Items", items)
        return self.attributes

    def exportToFile(self, output_file="date"):
        output_folder = False
        if not self.is_emergency:
            if output_file == "date":
                output_file = self.generatePathAndFile(config["paths"]["output"], ".json")
                extra_output_file = self.generatePathAndFile(config["paths"]["output"]+'/original', ".json")
            else:
                output_folder = os.path.dirname(os.path.abspath(output_file))
                os.makedirs(output_folder, exist_ok=True)
        else:
            output_file = config["paths"]["emergency_playlist"]

        # write .json file
        f = open(output_file, "w")
        f.write(json.dumps(self._exportToJson()))
        f.close()

        # extra save original .json file
        if not output_folder and not self.is_emergency:
            f = open(extra_output_file, "w")
            f.write(json.dumps(self._exportToJson()))
            f.close()

    def exportToFirebase(self):
        path = self.generatePathAndFile("playlists", ".json", False)
        requests.put("FIREBASE_URL/" + path + "?auth=...",
                     data=json.dumps(self._exportToJson()))

    def removeOverlappingTracks(self):
        while True:
            dur = self.getDuration()
            max_removeable = dur - self.accepted_dur
            if max_removeable > 0:
                canidates = []
                linkedWith = {}
                for item in self.getItems():
                    if item.getValue('Type') in ('Jingle', 'Music', 'Promo'):
                        if item.getValue('LinkedTo'):
                            linkedWith[item.getValue('LinkedTo')] = item
                        elif item.getValue('UseInTeaser') != 'ja':
                            if item.getDuration() < max_removeable:
                                canidates.append(item)

                if len(canidates) > 0:
                    canidates = sorted(canidates, key=lambda x: x.getDuration() + (linkedWith[x.getID()].getDuration() if x.getID() in linkedWith else 0), reverse=True)
                    for c in canidates:
                        total_d = c.getDuration() + (linkedWith[c.getID()].getDuration() if c.getID() in linkedWith else 0)
                        # print(total_d)
                        if total_d >= max_removeable:
                            canidates.remove(c)

                    if len(canidates) > 0:
                        # remove the first canidate
                        self.remove(canidates[0])
                        print('[PLAYLIST] Removed: '+canidates[0].getTitle())

                        if canidates[0].getID() in linkedWith:
                            self.remove(linkedWith[canidates[0].getID()])
                            print('[PLAYLIST] Removed linked item: '+linkedWith[canidates[0].getID()].getTitle())
                    else:
                        return True
                else:
                    return True
            else:
                return True

    def createPromotionHook(self, track, station_id_jingle_path):
        promotion_hooks = []

        hook_folder = config['paths']['hooks'] + '/' + track.getID()
        if not os.path.exists(hook_folder):
            os.makedirs(hook_folder)

        # open jingle
        jingle_file = config['paths']['jingles'] + '/x.wav'
        if os.path.exists(jingle_file) and os.path.exists(station_id_jingle_path):
            promotion = AudioSegment.from_wav(jingle_file)
            station_id = AudioSegment.from_wav(station_id_jingle_path)

            for hook_type in ['short', 'medium', 'long']:
                output_file = self.generatePathAndFile(config['paths']['mixdowns'], '.mp3', create_dir=True, filename='promotion_'+track.getID()+'_'+hook_type)

                # open hook with fx
                fx_hook = hook_folder + '/fx_' + hook_type + '.mp3'
                if os.path.exists(fx_hook):
                    hook = AudioSegment.from_mp3(fx_hook)

                    overlap_promotion = 600
                    overlap_station_id = 370

                    wrapper = AudioSegment.silent()
                    wrapper = AudioSegment.silent(duration=(len(promotion) - overlap_promotion) + (len(station_id) - overlap_station_id) + len(hook))
                    promotion_hook = wrapper.overlay(promotion, position=0)
                    promotion_hook = promotion_hook.overlay(hook, position=len(promotion) - overlap_promotion)
                    promotion_hook = promotion_hook.overlay(station_id, position=((len(promotion) - overlap_promotion) + len(hook)) - overlap_station_id)
                    promotion_hook.export(output_file, format='mp3')
                    promotion_hooks.append([output_file, len(promotion_hook)/1000])
        else:
            print('[PLAYLIST] Error: jingle_file or station_id_jingle_path does not exist')
        return promotion_hooks

    def filterPlayableTracks(self, last_tracks, without_playlist_block=False):
        items = []
        if len(last_tracks) == 0:
            return self._newPlaylist(self.items)

        last_tracks = last_tracks[::-1]
        cond = last_tracks[0].getNextConditions()

        # block playlists
        if len(last_tracks) > 1 and not without_playlist_block:
            first_category = last_tracks[0].getSourcePlaylistCategory(return_ids=True)
            second_category = last_tracks[1].getSourcePlaylistCategory(return_ids=True)
            if first_category == second_category:
                cond['source_playlist_blacklist'] = first_category[1]

        has_results = False
        for item in self.items:
            r = item.isMeetingConditions(cond)
            if r[0]:
                has_results = True
                items.append(item)

        if not has_results and not without_playlist_block:
            print('[PLAYLIST] Fehler: Keine Ergebnisse. Filterumfang wird reduziert')
            return self.filterPlayableTracks(last_tracks[::-1], without_playlist_block=True)

        return self._newPlaylist(items)
