import math
import os
from pydub import AudioSegment
import time
from builtins import int
from datetime import datetime, timedelta
import json
import random
import urllib.request
from colorama import init
from colorama import Back, Style
import time
from mutagen.mp3 import MP3
import copy
from playlist_item import PlaylistItem
from database import Database
from playlist import Playlist
from history import History
import os.path
import librosa
import schedule

init()
print_space = "                                                                       "
history = History()
history.delete()
db = Database(history)
db.deleteOldMixdowns()
db.deleteOldYouTubeStats()
db.deleteDuplicates()

config = json.loads(open("config.json", "r", encoding='utf-8').read())
default_items = json.loads(open("default_items.json", "r", encoding='utf-8').read())

news_item = PlaylistItem()
news_item.importJson(default_items["news"])

news_jingle = PlaylistItem()
news_jingle.importJson(default_items["news_jingle"])

jingles = []
announcement_moderations = [
    config["paths"]["jingles"] + "x.mp3"
]


def division(x, y, r=False):
    if y == 0 or x == 0:
        return 0
    if not r:
        return x / y
    else:
        return math.ceil(x / y)


def get(url):
    with urllib.request.urlopen(url) as url:
        return json.loads(url.read().decode())


def normalize(sound):
    change_in_dBFS = config["teaser_dBFS"] - sound.dBFS
    return sound.apply_gain(change_in_dBFS)


def generate_teaser(pPlaylist):
    moderation_path = random.choice(announcement_moderations)
    moderation = normalize(AudioSegment.from_file(moderation_path))
    hooks = []
    for item in pPlaylist.filterItems("UseInTeaser", "ja", False):
        spotify_id = item.getAttribute("Spotify ID")
        hook_path = config["paths"]["hooks"] + \
            "/" + spotify_id + "/fx_medium.mp3"
        hooks.append(normalize(AudioSegment.from_file(hook_path)))

    if len(hooks) == 3:
        output_file = pPlaylist.generatePathAndFile(config["paths"]["mixdowns"], ".mp3", create_dir=True, filename='teaser')
        silence = AudioSegment.silent(duration=len(
            moderation) + len(hooks[0]) + len(hooks[1]) + len(hooks[2]) - 2200)
        silence = silence.overlay(moderation)
        silence = silence.overlay(hooks[0], position=len(moderation) - 400)
        silence = silence.overlay(hooks[1], position=len(
            moderation) + len(hooks[0]) - 1200)
        silence = silence.overlay(hooks[2], position=len(
            moderation) + len(hooks[0]) + len(hooks[1]) - 2000)
        silence.export(output_file, format="mp3")

        item = PlaylistItem()
        item.setValue("Type", "Voice")
        item.setValue("Title", "Das läuft ab " +
                      str(pPlaylist.getHour()) + " Uhr")
        item.setValue("Artist", "Radio JFM")
        item.setValue("Duration", len(silence) / 1000)
        item.setValue("Filename", output_file)
        item.setValue("Customized", True)
        item.setValue('LinkedTo', 'Playlist')
        return item


def generate_emergency_playlist(timestamp):
    date = datetime.fromtimestamp(timestamp)
    history.deleteOldLocks(date)
    db.reset()

    sourcePlaylist = db.getAvailablePlaylistItems(date)
    sourcePlaylist.sort()

    playlist = Playlist(date, 3600*3, is_emergency=True)

    first_round_started_at = time.time()
    while sourcePlaylist.getItemCount() > 0 and not playlist.isDurationOk():
        if time.time() - first_round_started_at > config["first_round_timeout"]:
            print("generate_emergency_playlist: Timeout in first round")
            return

        highest_points = sourcePlaylist.getItem(0).getPoints()
        track = sourcePlaylist.getItemsWithValue("Points", highest_points, True).getRandomItem()

        playlist.append(track)
        sourcePlaylist.remove(track)

    # no results
    if playlist.getItemCount() == 0:
        print("generate_emergency_playlist: No tracks for hour")
        return False

    playlist.shuffle(3)
    playlist.exportToFile()


def generate_hour(timestamp, dur=60):
    global last_vote, cur_vote

    date = datetime.fromtimestamp(timestamp)
    history.deleteOldLocks(date)
    history.deleteOldLogs(date)
    db.reset()

    locked_seasons = []
    cur_date = (date.month * 2628000) + (date.day * 86400)
    for season in config["jingles"]["seasons"]:
        if not (season["start_day"] < cur_date < season["end_day"]):
            locked_seasons.append(season["name"])

    locked_daytimes = []
    for daytime in config["jingles"]["daytimes"]:
        if not (daytime["start_hour"] < date.hour < daytime["end_hour"]):
            locked_daytimes.append(daytime["name"])

    locked_weektimes = []
    for weektime in config["jingles"]["weektimes"]:
        if date.weekday() not in weektime["days"]:
            locked_daytimes.append(weektime["name"])

    available_jingles = []
    locked_tags = locked_seasons + locked_daytimes + locked_weektimes
    for jingle in config["jingles"]["files"]:
        if not jingle["is_special"]:
            can_use = True
            if "tags" in jingle:
                for tag in jingle["tags"]:
                    if tag in locked_tags:
                        can_use = False

            if can_use:
                if "tags" not in jingle:
                    jingle["tags"] = []
                jingle["duration"] = librosa.get_duration(
                    filename=config["paths"]["jingles"] + "/" + jingle["filename"])
                available_jingles.append(jingle)

    # Alle songs, die in stunde spielbar sind herraussuchen
    sourcePlaylist = db.getAvailablePlaylistItems(date)

    # Sort by points
    # sourcePlaylist.sort()

    plus_songs = sourcePlaylist.filterItems("Bewertung", "+").getItemCount()
    minus_songs = sourcePlaylist.filterItems("Bewertung", "-").getItemCount()
    test_songs = sourcePlaylist.filterItems("Bewertung", "Test").getItemCount()

    # finale playlist
    playlist = Playlist(date, 3600 - 80)

    generating_started_at = time.time()
    while not playlist.isDurationOk() and sourcePlaylist.getItemCount() > 0:
        if time.time() - generating_started_at > config['first_round_timeout']:
            print('[MAIN] Timeout while generating playlist')
            return

        # get all playable tracks based on last tracks
        playable = sourcePlaylist.filterPlayableTracks(playlist.getItems())
        if playable.getItemCount() > 0:
            # choose best item
            if random.randrange(0, 100) < config['percentage_chances']['choose_random_item']:
                # get random item and not with highest points
                track = playable.getRandomItem()
                track.setValue('IsRandom', 'ja')
                track.setAttribute('FirstReason', 'Zufall')
            else:
                # sort by points
                playable.sort()

                # get any item, that has the same points as the highes item
                highest_points = playable.getItem(0).getPoints()
                track = playable.getItemsWithValue('Points', highest_points, True).getRandomItem()
                track.setValue('IsRandom', 'nein')
                track.setAttribute('FirstReason', 'Die meisten Punkte: '+str(highest_points))

            # check if track is in last artists
            if history.isInLastArtists(track):
                print('Track is not useable -> is in last artists')
            else:
                playlist.append(track)
                sourcePlaylist.remove(track)
        else:
            print('[MAIN] Keine Songs gefunden')
            break

    # TODO: Blöcke mit doppelten Tags aus LIST5 auflösen
    # for doubling in doubling_positions:

    # mark announcement items
    marked = 0
    teaser = None
    new_items = playlist.filterItems("IsNew", "ja")
    new_items = new_items.sortItemsAs("energy", False)
    for item in new_items:
        if marked < 3:
            spotify_id = item.getAttribute("Spotify ID")
            hook_path = config["paths"]["hooks"] + \
                "/" + spotify_id + "/fx_medium.mp3"
            if os.path.isfile(hook_path):
                marked = marked + 1
                posInPlaylist = playlist.index(item)
                playlist.getItem(posInPlaylist).setAttribute(
                    "UseInTeaser", "ja")

    if marked < 3:
        plus_items = playlist.filterItems("Bewertung", "+")
        plus_items = plus_items.sortItemsAs("energy", False)

        for item in plus_items:
            if marked < 3:
                spotify_id = item.getAttribute("Spotify ID")
                hook_path = config["paths"]["hooks"] + \
                    "/" + spotify_id + "/fx_medium.mp3"
                if os.path.isfile(hook_path):
                    marked = marked + 1
                    posInPlaylist = playlist.index(item)
                    playlist.getItem(posInPlaylist).setAttribute(
                        "UseInTeaser", "ja")

    if marked == 3:
        teaser = generate_teaser(playlist)
        if teaser is None:
            marked = 0

    # add promotions
    playlistWithPromotions = Playlist(date)
    for track in playlist.getItems():
        if track.getAge() < config["categorizations"]["track_age_middle"]:
            # choose a jingle
            filtered_jingles = [j for j in available_jingles if track.getLockedEnergy() not in j["tags"]]
            rand_jingle = random.choice(filtered_jingles)

            # create promotion hook
            promotions = playlist.createPromotionHook(track, config["paths"]["jingles"] + "/" + rand_jingle["filename"])

            if len(promotions) > 0:
                # use medium promotion
                promotion = promotions[1] if len(promotions) > 2 else promotions[0]
                promotion = db.createPromotionHook(promotion[0], promotion[1], track)
                promotion.setValue('LinkedTo', track.getID())

                promotion_placed = False

                # place promotion on ramp, if track has one
                if track.hasMarker('Ramp1') and 2 < track.getMarker('Ramp1') < 20:
                    padding = track.getMarker('Ramp1') - config["jingle_offset"] - config["music_fade_out_duration"] - rand_jingle['duration']

                    # can the jingle of the promotion be placed on ramp
                    if padding - config["music_fade_in_duration"] > 0:
                        track.setValue("Customized", True)
                        volume_envelope = {"Items": []}

                        # fade out start
                        fade_out_start = padding - config["music_fade_in_duration"]
                        volume_envelope["Items"].append({
                            "Position": fade_out_start
                        })

                        # fade out end
                        fade_out_end = padding
                        volume_envelope["Items"].append({
                            "Position": fade_out_end,
                            "Value": config["music_volume_while_jingle"]
                        })

                        # fade in start
                        fade_in_start = track.getMarker('Ramp1') - config["music_fade_out_duration"] - config["jingle_offset"]
                        volume_envelope["Items"].append({
                            "Position": fade_in_start,
                            "Value": config["music_volume_while_jingle"]
                        })

                        # fade in end
                        fade_in_end = track.getMarker('Ramp1') - config["jingle_offset"]
                        volume_envelope["Items"].append({
                            "Position": fade_in_end
                        })

                        track.setValue("VolumeEnvelope", volume_envelope)

                        # remove intro of track before jingle
                        track.setMarker('CueIn', fade_out_start)
                        track.setMarker('FadeIn', fade_out_end)

                        # move Ramp to new start of track
                        promotion.setMarker('StartNext', -1)
                        promotion.setMarker("StartNext", promotion.getDuration() - (fade_in_start - fade_out_start))

                        promotion.setValue('PlacedOnRamp', True)

                        promotion_placed = True
                        playlistWithPromotions.append(promotion)

                if not promotion_placed:
                    playlistWithPromotions.append(promotion)

        playlistWithPromotions.append(track)

    # jingles hinzufügen
    playlistWithJingles = Playlist(date)
    playlistWithJingles.importItems(playlistWithPromotions.getItems().copy())
    for pos in range(1, playlistWithPromotions.getItemCount() - 1, config["min_jingle_distance"]):
        track = playlistWithPromotions.getItem(pos)

        # check if track has promotion before
        track_pos = playlistWithPromotions.index(track)
        if track_pos > 0:
            before_track = playlistWithPromotions.getItem(track_pos-1)
            if before_track.getValue('Type') == 'Promo':
                # stop adding a jingle
                continue

        if track.hasMarker("Ramp1"):
            ramp = track.getMarker("Ramp1")
            if 2 < ramp < 20:

                filtered_jingles = [j for j in available_jingles if ramp > j['duration'] and track.getLockedEnergy() not in j["tags"]]
                if len(filtered_jingles) > 0:
                    rand_jingle = random.choice(filtered_jingles)
                    jingle = db.createJingle(rand_jingle)
                    jingle.setValue('LinkedTo', track.getID())
                    jingle.setValue("Padding", ramp - config["jingle_offset"] - config["music_fade_out_duration"] - jingle.getValue("Duration"))

                    # can the jingle be placed on ramp
                    # is the fade out start point on the track (>0)
                    if jingle.getValue("Padding") - config["music_fade_in_duration"] > 0:
                        track.setValue("Customized", True)
                        volume_envelope = {"Items": []}

                        # fade out start
                        fade_out_start = jingle.getValue("Padding") - config["music_fade_in_duration"]
                        volume_envelope["Items"].append({
                            "Position": fade_out_start
                        })

                        # fade out end
                        fade_out_end = jingle.getValue("Padding")
                        volume_envelope["Items"].append({
                            "Position": fade_out_end,
                            "Value": config["music_volume_while_jingle"]
                        })

                        # fade in start
                        volume_envelope["Items"].append({
                            "Position": ramp - config["music_fade_out_duration"] - config["jingle_offset"],
                            "Value": config["music_volume_while_jingle"]
                        })

                        # fade in end
                        volume_envelope["Items"].append({
                            "Position": ramp - config["jingle_offset"]
                        })

                        track.setValue("VolumeEnvelope", volume_envelope)

                        # Set CueIn and FadeIn
                        if random.randrange(0, 100) < config["percentage_chances"]["remove_intro_before_ramp_with_jingle"]:
                            # remove intro of track before jingle
                            track.setMarker('CueIn', fade_out_start)
                            track.setMarker('FadeIn', fade_out_end)

                            # move Ramp to new start of track
                            jingle.setValue("Padding", fade_out_end-fade_out_start)
                        else:
                            # check if CueIn or FadeIn is in VolumeEnvelope
                            if track.getMarker('CueIn') > fade_out_start:
                                track.setMarker('CueIn', 0)

                            if track.getMarker('FadeIn') > fade_out_start:
                                track.setMarker('FadeIn', 0)

                        jingle.setValue('PlacedOnRamp', True)
                        track_pos = playlistWithJingles.index(playlistWithPromotions.getItem(pos))
                        playlistWithJingles.insert(track_pos, jingle, False)

    playlist = playlistWithJingles

    # add news and one jingle
    playlist.insert(0, copy.deepcopy(news_item))
    playlist.getItem(0).setValue(
        "Filename", config["paths"]["news"] + "/" + date.strftime("/%Y/%m/%d/%H.mp3"))
    playlist.getItem(0).setValue("Title", 'News ' + str(date.hour) + ' Uhr')
    playlist.getItem(0).setValue("FixTime", str(date.hour).zfill(2) + ":00:00")

    firstMusicItem = playlist.getItem(1)
    if firstMusicItem.hasMarker("Ramp1"):
        newsItem = playlist.getItem(0)
        ramp = firstMusicItem.getMarker("Ramp1")
        if ramp < config["durations"]["min_ramp_after_news"]:
            print(Back.BLUE + "RAMP AFTER NEWS USED" + Style.RESET_ALL)
            newsItem.setMarker('StartNext', ramp - config["news_offset"] - config["music_fade_out_duration"])
            if newsItem.getMarker('StartNext')/newsItem.getDuration() > 0.6:
                firstMusicItem.setValue('Customized', True)
                firstMusicItem.setValue('LinkedTo', 'Playlist')

                VolumeEnvelope = {"Items": []}

                # fade out end
                VolumeEnvelope["Items"].append({
                    "Position": 0,
                    "Value": config["music_volume_while_news"]
                })

                # fade in start
                VolumeEnvelope["Items"].append({
                    "Position": ramp - config["music_fade_out_duration"],
                    "Value": config["music_volume_while_news"]
                })

                # fade in end
                VolumeEnvelope["Items"].append({
                    "Position": ramp
                })

                firstMusicItem.setValue("VolumeEnvelope", VolumeEnvelope)
            else:
                print('Removed wrong StartNext marker from news')
                newsItem.removeMarker('StartNext')

    playlist.insert(0, news_jingle, False)

    # add generated teaser
    # if marked == 3:
    # playlist.append(teaser)

    playlist.removeOverlappingTracks()

    # calculate planed times
    last = -1
    date_timestamp = time.mktime(date.replace(
        hour=0, minute=0, second=0, microsecond=0).timetuple())
    start_timestamp = date_timestamp + (((date.hour + 2) * 60) * 60)
    seconds_to_add = -2
    for track in playlist.getItems():
        track.setValue("PlannedTime", round(start_timestamp + seconds_to_add))
        if last == 0 and track.getValue("Type") != "Jingle":
            seconds_to_add = seconds_to_add + track.getDuration()
            history.addLock(track)
        elif last == -1:
            seconds_to_add = 0
            last = 0

    # show playlist
    last = -1
    for track in playlist.getItems():
        pos = (datetime.utcfromtimestamp(track.getValue("PlannedTime")) - timedelta(hours=1)).strftime(
            '%H:%M:%S') + " "
        if track.getValue("Type") == 'Music':
            has_error = False
            if config['use_vote_condition']:
                cur = config["votes_tags"].index(track.getAttribute("Bewertung"))

                if last == cur and not (cur == 0 == last):
                    has_error = True

                last = cur

            # set track comment
            comment = 'Punkte: '+str(track.getPoints())+'\r\n'+'Quell-Playlist Gruppe: '+str(track.getSourcePlaylistCategory())
            track.setComment(comment)

            if db._isPlayableAtHour(track.getDatabaseID(), date) and track.hasAttribute('res_pos'):
                print(track.toString(pos, has_error))
            elif track.hasAttribute('res_pos'):
                print(Back.RED + track.getValue("Title")+' IST NICHT SPIELBAR' + Style.RESET_ALL)
            else:
                print(Back.RED + track.getValue("Title")+' HAT KEIN RICHTIGES RES_POS ATTRIBUT' + Style.RESET_ALL)
        else:
            print(pos + Back.YELLOW + track.getValue("Title") + Style.RESET_ALL)
    print("END -> " + datetime.utcfromtimestamp(start_timestamp +
          seconds_to_add).strftime('%H:%M:%S'))
    print("AVERAGE POINTS: " + str(playlist.getAveragePoints()))

    playlist.setValue("AvailableSongs", sourcePlaylist.getValue("StartLength"))
    playlist.setValue("UnavailableSongs",
                      sourcePlaylist.getValue("UnavailableSongs"))
    playlist.setValue("Weather", db.getWeather(playlist.getDate()))

    playlist.exportToFile()
    playlist.exportToFirebase()

    diff = playlist.getDuration() - 120

    if diff < 0:
        diff_minutes = round((diff / 60) * (-1))
        print("Playlist is " + str(diff_minutes) + " Min. to short!")


def generate_playlist_for_next_day(first_start=False):
    global jingles
    date_0_today = datetime.strptime(
        datetime.now().strftime("%d/%m/%Y"), "%d/%m/%Y")
    date_0_tomorrow = date_0_today + timedelta(days=1)

    if not os.path.isdir(config["paths"]["output"] + date_0_today.strftime("/%Y/%m/%d")) or first_start:
        # today playlist not generated
        print('GENERATING PLAYLIST FOR TODAY ...')
        start_timestamp = round(time.mktime(date_0_today.timetuple()))
        next_check_date = date_0_today + timedelta(hours=22)
    else:
        print('GENERATING PLAYLIST FOR TOMORROW ...')
        # today playlist generated -> generate for tomorrow
        start_timestamp = round(time.mktime(date_0_tomorrow.timetuple()))
        next_check_date = date_0_tomorrow + timedelta(hours=22)

    # jingles laden
    for filename in os.listdir("Jingles"):
        jingle = {
            "filename": os.path.splitext(filename)[0],
            "path": "Jingles/" + filename,
            "duration": MP3("Jingles/" + filename).info.length
        }
        jingles.append(jingle)

    if not first_start:
        generate_emergency_playlist(start_timestamp + (15 * 3600))

    hours = 24
    for h in range(0, hours):
        print("\nHour: " + str(h))
        generate_hour(start_timestamp)
        start_timestamp = start_timestamp + 3600


generate_playlist_for_next_day(first_start=True)
if datetime.now().hour >= 22 and datetime.now().minute > 0:
    print('Playlist für morgen wird generiert, da es nach 22 Uhr ist')
    generate_playlist_for_next_day()

schedule.every().day.at("22:00").do(generate_playlist_for_next_day)
while True:
    schedule.run_pending()
    time.sleep(1)
