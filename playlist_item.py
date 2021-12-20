import os
import json
from colorama import init
from history import History
from colorama import Back, Style

config = json.loads(open("config.json", "r", encoding='utf-8').read())

init()

print("PLAYLIST ITEM v.1.0")


class PlaylistItem:
    def __init__(self):
        self.exists = False
        self.json = {
            "Type": "Music",
            "State": "Normal",
            "Class": "File",
            "Attributes": {},
            "Markers": {},
            "Points": 0
        }

    def importJsonFromFile(self, json_file_path):
        self.json = json.loads(open(json_file_path, "r").read())
        self.exists = True
        self._convertVoteAttribute()

    def importJson(self, pJson):
        self.json = pJson
        self.exists = True
        self._convertVoteAttribute()

    def exportJson(self):
        # clear false VolumeEnvelope
        if "VolumeEnvelope" in self.json:
            has_error = False
            if type(self.json["VolumeEnvelope"]) is not bool:
                if "Items" in self.json["VolumeEnvelope"]:
                    for item in self.json["VolumeEnvelope"]["Items"]:
                        if "Position" not in item:
                            has_error = True
                        elif item["Position"] < 0:
                            has_error = True
            else:
                has_error = True
            if has_error:
                print(Back.RED + "REMOVED WRONG VolumeEnvelope FROM ITEM" + Style.RESET_ALL)
                del self.json["VolumeEnvelope"]
        return self.json

    def setValue(self, valueName, value):
        self.json[valueName] = value
        self.exists = True

    def getValue(self, valueName):
        if valueName == "valence":
            return self.getValence()
        elif valueName == 'age':
            return self.getAge()
        elif valueName in self.json:
            return self.json[valueName]
        else:
            if valueName == "energy":
                return 0.5

    def getID(self):
        return self.getAttribute("Spotify ID")

    def getSourcePlaylists(self):
        p = self.getAttribute('Quell-Playlists')
        if p:
            return p.split(', ')
        return []

    def hasOneSourcePlaylist(self, source_playlists):
        for playlist in source_playlists:
            if playlist in self.getSourcePlaylists():
                return True
        return False

    def getSourcePlaylistCategory(self, return_ids=False):
        for c in config['playlist_categorys']:
            for p_id in c['ids']:
                if p_id in self.getSourcePlaylists():
                    if return_ids:
                        return [c['name'], c['ids']]
                    return c['name']
        return [False, None]

    def getValence(self):
        if "valence" in self.json["Attributes"]:
            if self.json["Attributes"]["valence"]:
                if self.json["Attributes"]["valence"] != '':
                    return float(self.json["Attributes"]["valence"])
        return config["categorizations"]["low_valence"]

    def getEnergy(self):
        if "energy" in self.json["Attributes"]:
            if self.json["Attributes"]["energy"]:
                if self.json["Attributes"]["energy"] != '':
                    return float(self.json["Attributes"]["energy"])
        return config["categorizations"]["low_energy"]

    def getDanceability(self):
        if "danceability" in self.json["Attributes"]:
            if self.json["Attributes"]["danceability"]:
                if self.json["Attributes"]["danceability"] != '':
                    return float(self.json["Attributes"]["danceability"])
        return -1

    def setAttribute(self, attributeName, attributeValue):
        self.exists = True
        if "Attributes" not in self.json:
            self.json["Attributes"] = {}
        self.json["Attributes"][attributeName] = str(attributeValue)
        self._convertVoteAttribute()

    def getAttribute(self, attributeName):
        if "Attributes" not in self.json:
            self.json["Attributes"] = {}

        if attributeName in self.json["Attributes"]:
            if attributeName == "Release Date" and not self.json["Attributes"][attributeName]:
                return -1
            return self.json["Attributes"][attributeName]
        else:
            if attributeName == "Release Date":
                return -1
            return ""

    def isMusic(self):
        return self.getValue("Type") == "Music"

    def hasAttribute(self, attributeName):
        if "Attributes" not in self.json:
            self.json["Attributes"] = {}
        return attributeName in self.json["Attributes"]

    def hasValue(self, valueName):
        return valueName in self.json

    def _convertVoteAttribute(self):
        if self.getAttribute("Bewertung") == "Passt zum Sender":
            self.setAttribute("Bewertung", "+")
        elif self.getAttribute("Bewertung") == "Kann auch mal laufen":
            self.setAttribute("Bewertung", "-")
        elif self.getAttribute("Bewertung") == "Ausprobieren (Sender abheben)":
            self.setAttribute("Bewertung", "Test")
        elif self.getAttribute("Bewertung") == "":
            self.setAttribute("Bewertung", "-")

    def getDurationSec(self):
        return self.getDuration()

    def setMarker(self, markerName, markerValue):
        self.exists = True
        if "Markers" not in self.json:
            self.json["Markers"] = {}
        self.json["Markers"][markerName] = markerValue

    def getMarker(self, markerName):
        if "Markers" in self.json:
            if markerName in self.json["Markers"]:
                return self.json["Markers"][markerName]
        return -1

    def hasMarker(self, markerName):
        if "Markers" in self.json:
            return markerName in self.json["Markers"]

    def removeMarker(self, markerName):
        if self.hasMarker(markerName):
            del self.json["Markers"][markerName]
            return True
        return False

    def getDatabaseID(self):
        return str(self.json["DatabaseID"])

    def getPoints(self):
        if "Points" in self.json:
            return self.json["Points"]
        else:
            return -1

    def getAge(self):
        if self.hasValue('DaysSinceRelease'):
            return self.getValue('DaysSinceRelease')
        return -1

    def setPoints(self, pPoints):
        self.exists = True
        self.json["Points"] = pPoints
        self.setAttribute('Points', pPoints)

    def getTitle(self):
        return str(self.getValue("Title"))

    def getArtist(self):
        return str(self.getValue("Artist"))

    def getArtists(self):
        retList = []
        artistIDs = self.json["Attributes"]["Spotify Artist IDs"].split(", ")
        for artistID in artistIDs:
            if artistID:
                if artistID != "" and artistID != "Null":
                    retList.append(artistID)
        return retList

    def getDuration(self):
        if "Duration" in self.json:
            if self.json["Duration"] > 0:
                start_pos = 0
                if self.hasMarker('CueIn'):
                    start_pos = self.getMarker('CueIn')
                end_pos = self.json["Duration"]

                if self.hasMarker('StartNext') and self.getMarker('StartNext') > 0:
                    end_pos = self.getMarker('StartNext')
                elif self.hasMarker('FadeOut'):
                    end_pos = self.getMarker('FadeOut')
                elif self.hasMarker('CueOut'):
                    end_pos = self.getMarker('CueOut')

                if end_pos > self.json["Duration"]:
                    end_pos = self.json["Duration"]

                return end_pos - start_pos
        return -1

    def getNextConditions(self):
        cond = {
            "votes": [-1],
            "min": {
                "energy": -1,
                "age": -1
            },
            "max": {
                "energy": -1,
                "age": -1
            },
            "source_playlist_blacklist": []
        }

        # next vote
        cur_vote = config["votes_tags"].index(self.getAttribute("Bewertung"))
        if cur_vote == 0:
            cond["votes"] = [1, 2]
        elif cur_vote == 1:
            cond["votes"] = [0, 2]
        elif cur_vote == 2:
            cond["votes"] = [0]

        # next energy
        if float(self.getValence()) <= config["categorizations"]["low_valence"]:
            cond["min"]["valence"] = config["categorizations"]["high_valence"]

        # next age
        if self.getAge() > config["categorizations"]["track_age_old"]:
            cond["max"]["age"] = config["categorizations"]["track_age_middle"]

        # next age
        if self.getAge() < config["categorizations"]["track_new"]:
            cond["min"]["age"] = config["categorizations"]["track_age_middle"]

        return cond

    def isMeetingConditions(self, cond=False, last_track=False):
        if not cond:
            cond = {
                "votes": [-1],
                "min": {
                    "energy": -1,
                    "age": -1
                },
                "max": {
                    "energy": -1,
                    "age": -1
                },
                'source_playlist_blacklist': []
            }

        for playlist_id in self.getSourcePlaylists():
            if playlist_id in cond['source_playlist_blacklist']:
                return [False, 'source_playlist_blacklist']

        if config['use_vote_condition']:
            if "votes" in cond:
                if cond["votes"][0] > -1:
                    if not config["votes_tags"].index(self.getAttribute("Bewertung")) in cond["votes"]:
                        return [False, 'vote']

        for comp in ['min', 'max']:
            if comp in cond:
                for param in ['valence', 'energy', 'age']:
                    if param in cond[comp]:
                        if cond[comp][param] > -1:
                            comperator = '>' if comp == 'max' else '<'
                            if comperator == '>':
                                if self.getValue(param) > cond[comp][param]:
                                    return [False, 'COND: '+param+' '+comp+' '+str(cond[comp][param])+', OWN: '+str(self.getValue(param))]
                            elif comperator == '<':
                                if self.getValue(param) < cond[comp][param]:
                                    return [False, 'COND: '+param+' '+comp+' '+str(cond[comp][param])+', OWN: '+str(self.getValue(param))]
                            elif comperator == '==':
                                if self.getValue(param) == cond[comp][param]:
                                    return [False, 'COND: '+param+' '+comp+' '+str(cond[comp][param])+', OWN: '+str(self.getValue(param))]

        return [True, None]

    def fileExists(self):
        if self.getAttribute("Spotify ID") is None:
            print("Item not in mAirList Database")
            return False
        else:
            return os.path.isfile(config["paths"]["music"] + '/' + self.getAttribute("Spotify ID") + ".mp3")

    def isNew(self):
        return self.getAge() <= config["categorizations"]["track_new"]

    # deprecated
    def _isInLastArtists(self):
        history = History()
        if config["use_artist_distance"]:
            return history.isInLastArtists(self.getArtists())
        return False

    def toString(self, time="", hasError=False):
        color = Back.GREEN

        self.setValue("HasError", hasError)

        if hasError:
            color = Back.RED
        else:
            if self.getAttribute("HasLessPoints"):
                color = Back.LIGHTRED_EX
            elif self.getValue("IsRandom") == "ja":
                color = Back.MAGENTA
            elif self.getValue("DaysSinceRelease") < 30:
                color = Back.CYAN
        return str(time) + color + "[" + str(self.getValue("Points")) + "][" + str(self.getSourcePlaylistCategory()) + "][" + str(self.getAttribute("energy")) + "] " + str(self.getValue("Title")) + " - " + str(
            self.getValue("Artist")) + Style.RESET_ALL

    def isGerman(self):
        return self.getAttribute('Sprache') == 'DE'

    def isOnBlacklist(self):
        if self.getID() in config['blacklist']['track_ids']:
            return True

        for artist_name in config['blacklist']['artists']:
            if artist_name in self.getArtist():
                return True

        return 'Spotify' in self.getTitle()

    def getLockedEnergy(self):
        # lock an energy tag to prevent e.g. using low energy jingles in high energy tracks
        locked_energy = "NULL"
        if self.getValue('energy') >= config["jingles"]["moods"][0]["min_song_energy"]:
            # can use high energy jingle
            locked_energy = "low_energy"
        elif self.getValue('energy') <= config["jingles"]["moods"][1]["max_song_energy"]:
            # can use low energy jingle
            locked_energy = "high_energy"
        return locked_energy

    def setComment(self, comment):
        self.setValue('Comment', comment)
