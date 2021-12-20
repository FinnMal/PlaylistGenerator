import urllib.request as urllib2
from mutagen.mp3 import MP3
import time
import os
from datetime import datetime, timedelta
from shutil import copyfile
from pydub import AudioSegment
import threading
import eyed3
import json
import itertools
import json
import os
import random
import pyrebase
import requests
import urllib.request
import schedule
import ssl
from colorama import Back, Style
from cue_splitter import CueSplitter
import soundfile as sf
import sys
import librosa
from scipy import signal
import numpy as np

import firebase_admin
from firebase_admin import credentials
from firebase_admin import db

# 6.757
last_jingle_len = 6740
first_jingle_len = 6030
weather_len = 21376
weather_plus_jingle_len = 24600

news_username = '...'
news_password = '...'

teaser_output_folder = '...'
mixdown_output_folder = '...'
news_output_folder = '...'
planed_items_output_folder = '...'
playlist_output_folder = "..."
print_space = "                                                                       "


do_test = False
if len(sys.argv) > 1 and (sys.argv[1] == True or sys.argv[1] == 'true' or sys.argv[1] == 'True'):
    do_test = True
news_url = '...'

firebase_config = {
    "apiKey": "...",
    "authDomain": "...",
    "projectId": "...",
    "storageBucket": "...",
    "messagingSenderId": "...",
    "appId": "...",
    "serviceAccount": '...',
    'databaseURL': '...'
}


if (not os.environ.get('PYTHONHTTPSVERIFY', '') and getattr(ssl, '_create_unverified_context', None)):
    ssl._create_default_https_context = ssl._create_unverified_context


firebase = pyrebase.initialize_app(firebase_config)
storage = firebase.storage()

cred = credentials.Certificate('...')
obj = firebase_admin.initialize_app(cred, firebase_config, name='...')


def get(url):
    with urllib.request.urlopen(url) as url:
        return json.loads(url.read().decode())


def get_wav_duration(filename):
    f = sf.SoundFile(filename)
    return f.frames / f.samplerate


def match_target_amplitude(sound, target_dBFS):
    change_in_dBFS = target_dBFS - sound.dBFS
    return sound.apply_gain(change_in_dBFS)


def get_playlist_file(p_date, s_date=None, r=0):
    output_folder = playlist_output_folder
    if s_date is not None:
        p_date = p_date - timedelta(days=1)
        output_folder = playlist_output_folder + '/original'

    playlist_file = output_folder + p_date.strftime("/%Y/%m/%d/%H.json")
    if not os.path.exists(playlist_file) and r < 10:
        if not s_date:
            s_date = p_date

        print(Back.RED + 'PLAYLIST DATEI NICHT GEFUNDEN' + Style.RESET_ALL)
        return get_playlist_file(p_date, s_date, r+1)

    if r == 10:
        return None

    if s_date:
        # copy original playlist file to current hour
        output_folder = playlist_output_folder + s_date.strftime("/%Y/%m/%d")
        if not os.path.exists(output_folder):
            os.makedirs(output_folder)

        new_playlist_file = output_folder + '/' + s_date.strftime("%H.json")
        copyfile(playlist_file, new_playlist_file)
        playlist_file = new_playlist_file

    return playlist_file


def add_teaser(cur_date, next_date):
    default_items = json.loads(open("default_items.json", "r", encoding='utf-8').read())
    teaser_file = mixdown_output_folder + '/' + next_date.strftime("%Y/%m/%d/%H") + '/teaser.mp3'
    if os.path.exists(teaser_file):
        playlist_file = get_playlist_file(cur_date)
        with open(playlist_file) as jf:
            current_playlist = json.load(jf)
            if current_playlist and 'Items' in current_playlist:

                # find best position to insert teaser
                pos = -1
                items = current_playlist['Items'][::-1]
                for track in items:
                    if pos > -1:
                        break

                    if track['Type'] == 'Music':
                        pos = current_playlist['Items'].index(track)

                        # get spotify id
                        if 'Attributes' in track and 'Spotify ID' in track['Attributes']:
                            spotify_id = track['Attributes']['Spotify ID']

                            # get item before this item
                            if pos > 0:
                                before = current_playlist['Items'][pos]
                                if 'LinkedTo' in before and before['LinkedTo'] == spotify_id:
                                    pos = -1
                        else:
                            pos = -1

                teaser = default_items['teaser']
                teaser['Filename'] = teaser_file
                teaser['Duration'] = MP3(teaser['Filename']).info.length
                teaser['Title'] = "Das läuft ab " + str(next_date.hour) + " Uhr"

                if pos > 0:
                    current_playlist["Items"].insert(pos, teaser)
                else:
                    print('Keine Position für den Teaser gefunden!')
                    current_playlist["Items"].insert(len(current_playlist["Items"]) - 1, teaser)

                if not do_test:
                    with open(playlist_file, 'w') as file:
                        json.dump(current_playlist, file)
                else:
                    with open(playlist_file+'_test.json', 'w') as file:
                        json.dump(current_playlist, file)
    else:
        print('ERROR: Teaser file existiert nicht')


def add_ads(cur_date):
    default_items = json.loads(open("default_items.json", "r", encoding='utf-8').read())
    # add ad item to current playlist

    playlist_file = get_playlist_file(cur_date)
    with open(playlist_file) as jf:
        current_playlist = json.load(jf)
        if current_playlist:
            if current_playlist["Items"]:
                # add one to middle
                l = current_playlist["Items"]
                l = l[:len(l)//2] + [default_items['advertisement']] + l[len(l)//2:]
                current_playlist["Items"] = l

                # add one before news
                i = len(current_playlist["Items"])
                for item in current_playlist["Items"]:
                    i = i-1
                    before = current_playlist["Items"][i]
                    print('AD ++++++++++++++++')
                    print(item['Type'])
                    print(before['Type'])
                    if i+1 < len(current_playlist["Items"]):
                        if item['Type'] == 'Music' and ('LinkedTo' not in before or before['LinkedTo'] == 'Playlist'):
                            break

                if i > 0:
                    current_playlist["Items"].insert(i + 1, default_items['advertisement'])
                else:
                    current_playlist["Items"].insert(len(current_playlist["Items"]) - 1, default_items['advertisement'])

                if not do_test:
                    with open(playlist_file, 'w') as file:
                        json.dump(current_playlist, file)
                else:
                    with open(playlist_file+'_test.json', 'w') as file:
                        json.dump(current_playlist, file)

            else:
                print("Cannot add ad to current playlist: Cur playlist has no items")
        else:
            print("Cannot add ad to current playlist: Cur playlist is null")


def remove_next_teaser(next_date):
    # remove teaser item from next playlist and save
    next_playlist_file = get_playlist_file(next_date)
    with open(next_playlist_file) as json_file:
        next_playlist = json.load(json_file)
        if next_playlist:
            if next_playlist["Items"]:
                if next_playlist["Items"][-1]:
                    if next_playlist["Items"][-1]["Type"] == "Voice":
                        del next_playlist["Items"][-1]
                        with open(next_playlist_file, 'w') as f:
                            json.dump(next_playlist, f)
                    else:
                        print("Teaser not found in next playlist: Type is not Voice")
                else:
                    print("Teaser not found in next playlist: Last item does not exist")
            else:
                print("Teaser not found in next playlist: Playlist has no items")
        else:
            print("Teaser not found in next playlist: Playlist does not exist")


def get_track_duration(pTrack):
    start_pos = 0
    end_pos = pTrack["Duration"]
    if 'PlacedOnRamp' in pTrack and pTrack['PlacedOnRamp'] and pTrack['Type'] == 'Jingle':
        return 0

    if 'Markers' in pTrack:
        if 'CueIn' in pTrack['Markers']:
            start_pos = pTrack['Markers']['CueIn']

        if 'StartNext' in pTrack['Markers']:
            end_pos = pTrack['Markers']['StartNext']
        elif 'FadeOut' in pTrack['Markers']:
            end_pos = pTrack['Markers']['FadeOut']
        elif 'CueOut' in pTrack['Markers']:
            end_pos = pTrack['Markers']['CueOut']

        if end_pos > pTrack['Duration']:
            end_pos = pTrack['Duration']
    return end_pos - start_pos


def get_removeable_sec(pTrack):
    end_pos = pTrack["Duration"]
    cut_pos = -1

    if 'Markers' in pTrack:
        if 'StartNext' in pTrack['Markers']:
            end_pos = pTrack['Markers']['StartNext']
        elif 'FadeOut' in pTrack['Markers']:
            end_pos = pTrack['Markers']['FadeOut']
        elif 'CueOut' in pTrack['Markers']:
            end_pos = pTrack['Markers']['CueOut']

    if 'Attributes' in pTrack:
        if 'last_section_start' in pTrack["Attributes"]:
            cut_pos = float(pTrack["Attributes"]["last_section_start"])
    if cut_pos > 0:
        return end_pos - cut_pos
    else:
        return -1


def get_news_duration(pTracks):
    for track in pTracks:
        if track["Type"] == "News":
            return MP3(track['Filename']).info.length
    return -1


def generate_silence_item(dur):
    item = {
        "Artist": "Radio JFM",
        "Duration": dur,
        "Title": "PRE NEWS: SILENCE",
        "Type": "Silence",
        "State": "Normal",
        "Class": "Silence",
        "Customized": True
    }
    return item


def generate_instrumental_item(dur):
    item = {
        "Artist": "Radio JFM",
        "Duration": dur,
        "Amplification": -0.853227376937866,
        "Levels": {
            "Loudness": -11.073522567749,
            "TruePeak": 0.986725032329559,
            "Peak": 0.853227376937866
        },
        "Markers": {
            "FadeOut": dur - 1,
            "CueOut": dur
        },
        "Title": "PRE NEWS: INSTRUMENTAL",
        "Type": "Instrumental",
        "State": "Normal",
        "Filename": "...",
        "Class": "File",
        "Customized": True
    }
    return item


def cue_file_to_cue_data(cue_file):
    cue_data = {'Items': []}
    splitter = CueSplitter(cue_file)
    cue_file_json = splitter.get_json()

    if 'tracks' in cue_file_json:
        for track in cue_file_json['tracks']:
            if 'performer' not in track:
                track['performer'] = 'Radio JFM'

            if 'title' not in track:
                track['title'] = 'DJ Session'

            if 'starts_at' not in track:
                track['starts_at'] = 0

            cue = {
                'Title': track['title'],
                'Artist': track['performer'],
                'Position': track['starts_at'],
                'Class': 'Track',
            }

            if cue['Position'] <= 0:
                del cue['Position']
            cue_data['Items'].append(cue)
    return cue_data


def download_planed_files(p_time):
    plan_path = str(p_time.year) + "/" + str(p_time.month) + "/" + str(p_time.day) + "/" + str(p_time.hour)
    plan = db.reference('planed_files/'+plan_path, app=obj).get()

    if plan and 'first_hour' in plan and plan['first_hour'] == True:
        audio_filename = get_planed_item_filename(plan['audio_file_extension'], 2)
        cue_filename = audio_filename + '_cue.cue'

        # download planed item
        storage.child(plan['audio_storage_path']).download(audio_filename)

        # download cue item
        if 'cue_storage_path' in plan:
            storage.child(plan['cue_storage_path']).download(cue_filename)

        print('DOWNLOADED PLANED FILES FOR NEXT HOUR')

        return True
    return False


def adjust_playlist(playlist_time):
    global do_test
    a = []

    i = 0
    if not do_test:
        add_teaser(playlist_time, playlist_time + timedelta(hours=1))
        # remove_next_teaser(playlist_time + timedelta(hours=1))
        add_ads(playlist_time)
    else:
        add_teaser(playlist_time, playlist_time + timedelta(hours=1))
        add_ads(playlist_time)

    playlist_file = get_playlist_file(playlist_time)
    if do_test:
        playlist_file = playlist_file + '_test.json'

    with open(playlist_file) as json_file:
        secs = (playlist_time.strftime("%H") * 60) * 60
        total_dur = 0
        jfo = json.load(json_file)

        # set news fixtime
        for track in jfo["Items"]:
            if track["Type"] == "News":
                track["Timing"] = "Hard"
                track["FixTime"] = str(playlist_time.hour).zfill(2) + ":00:00"

        # do plan
        plan_path = str(playlist_time.year) + "/" + str(playlist_time.month) + "/" + str(playlist_time.day) + "/" + str(playlist_time.hour)
        with urllib.request.urlopen("FIREBASE_URL/" + plan_path + ".json") as url:
            plan = json.loads(url.read().decode())

            if plan:
                print("PLAN FOUND")

                new_playlist = {
                    "Duration": 0
                }
                new_playlist_items = []

                planedItem = {
                    "ReamingAfterHour": plan["reaming_duration"] - plan["duration"],
                    "Filename": get_planed_item_filename(plan['audio_file_extension'])
                }

                if plan["first_hour"]:
                    # download planed item
                    if not os.path.exists(planedItem["Filename"]):
                        print('PLANED FILES NOT DOWNLOADED')
                        storage.child(plan['audio_storage_path']).download(planedItem["Filename"])

                        try:
                            storage.delete(plan['audio_storage_path'])
                        except Exception as e:
                            print(e)

                    # download cue file
                    if 'cue_storage_path' in plan:
                        planedItem["CueFilename"] = planedItem["Filename"]+'_cue.cue'
                        if not os.path.exists(planedItem["CueFilename"]):
                            storage.child(plan['cue_storage_path']).download(planedItem["CueFilename"])

                        try:
                            storage.delete(plan['cue_storage_path'])
                        except Exception as e:
                            print(e)

                        planedItem["CueData"] = cue_file_to_cue_data(planedItem["CueFilename"])

                    # create playlist item
                    if plan["fixed"]:
                        planedItem["Timing"] = "Hard"
                        planedItem["FixTime"] = str(plan["hour"]).zfill(2) + ":" + str(plan["minute"]).zfill(
                            2) + ":" + str(plan["second"]).zfill(2)

                    planedItem["Artist"] = plan["artist"]
                    planedItem["Title"] = plan["title"]
                    planedItem["Type"] = "Music"
                    planedItem["Class"] = "File"
                    planedItem["Amplification"] = -0.0409790351986885
                    planedItem["Levels"] = {
                        "Loudness": -8.87694454193115,
                        "TruePeak": 0.0650772899389267,
                        "Peak": 0.0409790351986885
                    }
                    planedItem['Customized'] = True
                    if plan['audio_file_extension'] == 'mp3':
                        planedItem["Duration"] = MP3(planedItem['Filename']).info.length
                    else:
                        planedItem["Duration"] = get_wav_duration(planedItem['Filename'])

                    seconds_with_music_before_plan = plan["minute"] * 60 + plan["second"]
                    if plan["news_in_hour"]:
                        news_dur = get_news_duration(jfo["Items"])
                        if seconds_with_music_before_plan < news_dur:
                            seconds_with_music_before_plan = news_dur - 2

                    # add enough songs before planed item
                    for track in jfo["Items"]:
                        if new_playlist["Duration"] < seconds_with_music_before_plan:
                            if track["Type"] == "Music":
                                track["AddedToNewPlaylist"] = True
                                new_playlist_items.append(track)
                                new_playlist["Duration"] = new_playlist["Duration"] + get_track_duration(track)
                            elif plan["news_in_hour"] and (track["Type"] == "News" or track["Type"] == "Voice"):
                                track["AddedToNewPlaylist"] = True
                                mp3_dur = MP3(track['Filename']).info.length
                                track['Duration'] = mp3_dur

                                new_playlist_items.append(track)
                                new_playlist["Duration"] = new_playlist["Duration"] + mp3_dur
                        else:
                            break

                    # add planed item to playlist
                    # planedItem["ReamingAfterHour"] = planedItem["Duration"] - (3600 - new_playlist["Duration"])
                    new_playlist_items.append(planedItem)
                    new_playlist["Duration"] = new_playlist["Duration"] + planedItem["Duration"]

                if plan["last_hour"]:

                    if new_playlist["Duration"] == 0:
                        new_playlist["Duration"] = plan["reaming_duration"]

                    # add enough songs after planed item
                    for track in jfo["Items"]:
                        if new_playlist["Duration"] < 3600:
                            if "AddedToNewPlaylist" not in track:
                                if track["Type"] == "Music":
                                    new_playlist_items.append(track)
                                    new_playlist["Duration"] = new_playlist["Duration"] + get_track_duration(track)
                                elif plan["news_in_hour"] and (track["Type"] == "News" or track["Type"] == "Voice"):
                                    mp3_dur = MP3(track['Filename']).info.length
                                    track['Duration'] = mp3_dur
                                    new_playlist_items.append(track)
                                    new_playlist["Duration"] = new_playlist["Duration"] + mp3_dur
                else:
                    # planed item ends in other hour
                    # -> plan item for next hour
                    next_plan = plan
                    next_plan["last_hour"] = False
                    next_plan["first_hour"] = False
                    next_plan["reaming_duration"] = planedItem["ReamingAfterHour"]

                    if planedItem["ReamingAfterHour"] <= 3600:
                        next_plan["last_hour"] = True
                        if planedItem["ReamingAfterHour"] < 200:
                            next_plan["news_in_hour"] = True
                    else:
                        next_plan["duration"] = 3600
                        next_plan["news_in_hour"] = False

                    next_plan["fixed"] = False
                    next_plan["minute"] = 0
                    next_plan["second"] = 0

                    # save plan for next hour
                    if not do_test:
                        next_playlist_time = playlist_time + timedelta(hours=1)
                        requests.post('...', json={
                            'path': str(next_playlist_time.year) + "/" + str(next_playlist_time.month) + "/" + str(
                                next_playlist_time.day) + "/" + str(next_playlist_time.hour), 'plan_data': next_plan})

                jfo["Items"] = new_playlist_items

                # TODO: delete plan from firebase
                # db.reference('planed_files/' + plan_path, app=obj).remove()

            else:
                # adjust playlist to fit in hour
                for track in jfo["Items"]:
                    if 'Duration' in track and track['Type'] != 'News':
                        total_dur = total_dur + get_track_duration(track)
                        if track['Type'] == 'Music':
                            a.append(i)
                    elif track['Type'] == 'News':
                        total_dur = 0
                        track['Filename'] = get_news_filename(playlist_time)

                        # ceck if file is older than current hour
                        news_date = get_news_filename(playlist_time, True)
                        if news_date != playlist_time:
                            track['Title'] = 'News ' + str(playlist_time.hour) + ' Uhr - Stand: '
                            if news_date.date == playlist_time.date:
                                track['Title'] = track['Title'] + str(news_date.hour) + ' Uhr'
                            elif news_date.year == playlist_time.year:
                                track['Title'] = track['Title'] + news_date.strftime('%d.%m.') + ', '+str(news_date.hour)+' Uhr'
                            else:
                                track['Title'] = track['Title'] + news_date.strftime('%d.%m.%Y') + ', '+str(news_date.hour)+' Uhr'

                        print('USED NEWS: '+track['Filename'])
                        dur = MP3(track['Filename']).info.length
                        if do_test:
                            dur = 120

                        track['Duration'] = dur

                        if "Markers" in track:
                            if "StartNext" in track["Markers"]:
                                if track["Markers"]["StartNext"] > 0:
                                    dur = dur - track["Markers"]["StartNext"]
                                    track["Markers"]["StartNext"] = dur
                                else:
                                    del track["Markers"]["StartNext"]

                        total_dur = total_dur + dur
                    else:
                        print(track['Title']+' has no duration value')
                    i = i + 1

                # diff_sec = total_dur - 3593
                diff_sec = total_dur - 3600
                print('TOTAL DUR: '+str(total_dur))
                print('DIFF SEC: '+str(diff_sec))
                print("DIFF: " + str(time.strftime('%M:%S', time.gmtime(diff_sec))))

                if round(diff_sec) > 0 or do_test:
                    # remove tracks, with get_removeable_sec > diff_sec
                    for pos in a:
                        track = jfo["Items"][pos]
                        r = get_removeable_sec(track)
                        if r > diff_sec and r > 0:
                            a.remove(pos)

                    diffs = {}
                    combinations = []
                    possible_combinations = 0
                    for i in range(1, len(a) + 1):
                        if possible_combinations < 300000:
                            comb = list(itertools.combinations(a, i))
                        else:
                            break
                        for l in comb:
                            if possible_combinations < 300000:
                                possible_combinations = possible_combinations + 1
                                print('Mögliche Kombinationen: '+"{:,}".format(possible_combinations).replace(',', '.')+print_space, end="\r")
                                combinations.append(l)
                            else:
                                break

                    i = 0
                    for c in combinations:
                        t = 0
                        removeable = 0
                        for pos in c:
                            track = jfo["Items"][pos]
                            removeable = removeable + get_removeable_sec(track)
                        diffs[i] = abs(diff_sec - removeable)
                        i = i + 1

                    top_list = sorted(diffs, key=lambda x: diffs[x], reverse=False)
                    best_combination = combinations[top_list[0]]
                    for t in range(0, 1):
                        names_array = []
                        comb_list = list(combinations[top_list[t]])
                        for comb in comb_list:
                            names_array.append('[' + str(comb) + '] ' + jfo["Items"][comb]["Title"])
                        names = ', '.join(map(str, names_array))

                        print(names)
                        print(round(diffs[top_list[t]], 3))

                        if 1 < diffs[top_list[t]] < 5:
                            # add silence
                            silence = generate_silence_item(diffs[top_list[t]])
                            jfo["Items"].append(silence)
                        elif 1 < diffs[top_list[t]] < 130:
                            # add instrumental
                            instrumental = generate_instrumental_item(diffs[top_list[t]])
                            jfo["Items"].append(instrumental)

                    for track_id in best_combination:
                        if 'Markers' not in jfo["Items"][track_id]:
                            jfo["Items"][track_id]["Markers"] = {}
                        jfo["Items"][track_id]['Markers']['StartNext'] = float(
                            jfo["Items"][track_id]["Attributes"]["last_section_start"])
                        jfo["Items"][track_id]['Markers']['FadeOut'] = jfo["Items"][track_id]['Markers'][
                            'StartNext'] - 0.8
                        jfo["Items"][track_id]['Markers']['CueOut'] = jfo["Items"][track_id]['Markers'][
                            'StartNext'] + 0.7
                        jfo["Items"][track_id]['Customized'] = True

                else:
                    if 1 < diff_sec < 5:
                        # add silence
                        silence = generate_silence_item(diff_sec)
                        jfo["Items"].append(silence)
                    elif diff_sec < 130:
                        # add instrumental
                        instrumental = generate_instrumental_item(diff_sec)
                        jfo["Items"].append(instrumental)

            # print playlist
            total_dur = 0
            for item in jfo["Items"]:
                color = Back.GREEN
                if item['Type'] == 'News':
                    total_dur = 0
                    color = Back.MAGENTA
                elif item['Type'] == 'Jingle':
                    color = Back.YELLOW
                elif item['Type'] == 'Promo':
                    color = Back.CYAN
                elif item['Type'] == 'Advertising':
                    color = Back.BLUE
                print(str(time.strftime('%H:%M:%S', time.gmtime(total_dur + datetime.now().hour*3600))) + ' ' + color + str(item["Title"]) + Style.RESET_ALL)
                total_dur = total_dur + get_track_duration(item)
            print('-> '+str(time.strftime('%H:%M:%S', time.gmtime(total_dur + datetime.now().hour*3600))))

    print('SAVING TO '+playlist_file)
    with open(playlist_file, 'w') as f:
        json.dump(jfo, f)


def get_playlist_restrictions(playlist_date):
    config = json.loads(open("config.json", "r", encoding='utf-8').read())
    for plan in config['special_playlists']:
        if playlist_date.weekday() in plan['days']:
            if playlist_date.hour in plan['hours']:
                return plan


def get_moderation_file(plan, playlist_date):
    for pattern in plan['start_moderation']['day_patterns']:
        if playlist_date.weekday() in pattern['days'] and playlist_date.hour in pattern['hours']:
            file_var = random.choice(pattern['files'])
            return plan['start_moderation']['file_pattern'].replace('[NR]', file_var)

    if 'end_moderation' in plan:
        for pattern in plan['end_moderation']['day_patterns']:
            if playlist_date.weekday() in pattern['days'] and playlist_date.hour in pattern['hours']:
                file_var = random.choice(pattern['files'])
                return plan['end_moderation']['file_pattern'].replace('[NR]', file_var)

    return False


def get_news_intro(playlist_date):
    file = AudioSegment.from_wav('News-Jingles/' + str(playlist_date.hour) + ' Uhr.wav')
    return match_target_amplitude(file, -18.0)


def get_weather_jingle(playlist_date):
    if playlist_date.hour < 5:
        file = '...'
    else:
        file = '...'
    file = AudioSegment.from_wav(file)
    return match_target_amplitude(file, -18.0)


def remove_mp3_from_mp3(source_file, find_file, output_file, add_between=False):
    y_within, sr_within = librosa.load(source_file, sr=None)
    y_find, _ = librosa.load(find_file, sr=sr_within)

    c = signal.correlate(y_within, y_find, mode='valid', method='fft')
    peak = np.argmax(c)
    offset = round(peak / sr_within, 2)*1000

    audio = MP3(find_file)
    find_file_length = audio.info.length*1000

    song = AudioSegment.from_mp3(source_file)
    if add_between:
        between = AudioSegment.from_wav(add_between)
        extract = song[:offset] + between + song[offset+find_file_length:]
    else:
        extract = song[:offset] + song[offset+find_file_length:]
    extract.export(output_file, format="mp3")


def get_planed_item_filename(extension, add_hours=1):
    date = datetime.today() + timedelta(hours=add_hours)
    cur_output_folder = planed_items_output_folder + "/" + date.strftime("%Y") + "/" + date.strftime(
        "%m") + "/" + date.strftime("%d")
    os.makedirs(cur_output_folder, exist_ok=True)
    return cur_output_folder + "/" + date.strftime("%H") + "." + extension


def get_news_filename(pDate, return_date=False, ignore_exists=False):
    started_at = time.time()
    while time.time() - started_at < 5:
        output_folder = news_output_folder + "/" + pDate.strftime("%Y") + "/" + pDate.strftime(
            "%m") + "/" + pDate.strftime("%d")
        file_path = output_folder + '/' + pDate.strftime('%H') + '.mp3'

        os.makedirs(output_folder, exist_ok=True)

        if ignore_exists:
            return file_path

        if os.path.exists(file_path):
            if return_date:
                return pDate
            return file_path
        else:
            print('News file does not exist: '+file_path)

        time.sleep(0.1)
        pDate = pDate - timedelta(hours=1)

    print('Error: NO OLD NEWS FILE FOUND')
    return False


def save_temp_file(playlist_date):
    filename = get_news_filename(playlist_date, False, ignore_exists=True)
    copyfile(news_output_folder + '/temp.mp3', filename)
    print('COPIED '+news_output_folder + '/temp.mp3'+' TO '+filename)


def is_new_file_on_server(use_old=False):
    old_length = -1
    try:
        if eyed3.load(news_output_folder + '/temp.mp3'):
            old_length = eyed3.load(news_output_folder + '/temp.mp3').info.time_secs
            print('OLD LENGTH: '+str(old_length))

        manager = urllib2.HTTPPasswordMgrWithDefaultRealm()
        manager.add_password(None, news_url, news_username, news_password)
        auth = urllib2.HTTPBasicAuthHandler(manager)
        opener = urllib2.build_opener(auth)
        urllib2.install_opener(opener)
        read = urllib2.urlopen(news_url).read()

        with open(news_output_folder + '/temp.mp3', 'wb') as f:
            f.write(read)
            print('Downloaded News file from laut.fm')

            new_length = old_length
            if eyed3.load(news_output_folder + '/temp.mp3'):
                new_length = eyed3.load(news_output_folder + '/temp.mp3').info.time_secs
                print('NEW LENGTH: '+str(new_length))
            return (new_length != old_length) or use_old
    except Exception as e:
        print(e)
        return False


def start_waiting():
    date = datetime.today() + timedelta(hours=1)
    print("Waiting for news file at " + str(date.hour) + " Uhr ...")

    # wait until new file is online
    waited_seconds = 0
    started_at = time.time()
    while (not is_new_file_on_server() and waited_seconds < 2*50) and not do_test:
        time.sleep(5)
        print('[' + datetime.now().strftime('%d.%m.%Y %H:%M:%S') + "] No new file")
        waited_seconds = time.time() - started_at
    if waited_seconds > 3*60:
        print('Timeout while waiting for new news file')

    save_temp_file(date)
    adjust_playlist(date)
    threading.Thread(target=download_planed_files, args=[date + timedelta(hours=1)]).start()


if do_test:
    start_waiting()

schedule.every().hour.at(":56").do(start_waiting)
while True:
    schedule.run_pending()
    time.sleep(1)
