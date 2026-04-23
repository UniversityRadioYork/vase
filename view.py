import json
import os
import random
import re
import secrets
import shutil
import string
import subprocess
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

import flask
import requests
import werkzeug.security
from flask import Flask, redirect, render_template, request, session
from flask_apscheduler import APScheduler
from waitress import serve

from DBManager import DBManager
from forms import Forms
from RecordingManager import RecordingManager

# I'm not sure if this does anything but i'm scared to delete it
log_location = os.environ.get("LOG_LOCATION", "/logs/")

admin_password = os.environ.get("ADMIN_PASSWORD", "dev")

vase_url = os.environ.get("VASE_URL", "localhost:5040")


# creates an app and scheduler thread
class Config:
    SCHEDULER_API_ENABLED = True
    PREFERRED_URL_SCHEME = "https"


app = Flask(__name__)
app.config.from_object(Config())

scheduler = APScheduler()
scheduler.init_app(app)
scheduler.start()

unix_timestamp = (datetime.now() - datetime(1970, 1, 1)).total_seconds()
print(f"Starting at {unix_timestamp}", file=sys.stderr)

app = Flask(__name__)
app.secret_key = secrets.token_urlsafe(16)

streamfolder = os.environ.get("STREAMS_PATH", "/streams/")
tempclipfolder = os.environ.get("CLIPS_PATH", "/clipstore/")
volumefolder = os.environ.get("VOLUME_PATH", "/opt/")

recordingmanager = RecordingManager(streamfolder)
dbmanager = DBManager(volumefolder + "vase.db")
forms = Forms(dbmanager)


def randomword(length):
    letters = string.ascii_lowercase
    return "".join(random.choice(letters) for i in range(length))


def verifyKeys(keys):
    for key in keys:
        pattern = re.compile(
            "^[-ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789]+$"
        )
        if not re.search(pattern, key):
            return False
    return True


def verifySession(session):
    if myradio_key == "dev":
        return True
    if "name" in session and "uid" in session:
        api_url = (
            myradio_url
            + "/user/"
            + str(session["uid"])
            + "/permissions?"
            + myradio_apikey
        )
        response = requests.get(api_url)
        officer = json.loads(response.text)
        if 221 in officer["payload"] or 234 in officer["payload"]:
            return True
    return False


def isadmin(session):
    if "admin" in session:
        return session["admin"]
    else:
        return False


def format_datetime_readable(datetime_str):
    dt_utc = datetime.strptime(datetime_str, "%Y-%m-%d %H:%M:%S")
    dt_utc = dt_utc.replace(tzinfo=ZoneInfo("UTC"))
    dt_uk = dt_utc.astimezone(ZoneInfo("Europe/London"))

    def ordinal(n):
        if 11 <= n % 100 <= 13:
            suffix = "th"
        else:
            suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
        return f"{n}{suffix}"

    return f"{dt_uk.strftime('%H:%M')} on the {ordinal(dt_uk.day)} of {dt_uk.strftime('%B %Y')}"


@app.route("/")
def index():
    announces = dbmanager.getannoucements(5)
    formatted_announcements = [{
        "title": title,
        "content": content,
        "datetime": format_datetime_readable(date_time)
    } for title, content, date_time in announces]
    seeall = len(announces) == 5
    return render_template(
        "announcements.html", announcements=formatted_announcements, seeall=seeall
    )


@app.route("/announcements")
def announcements():
    formatted_announcements = [{
        "title": title,
        "content": content,
        "datetime": format_datetime_readable(date_time)
    } for title, content, date_time in dbmanager.getannoucements(100)]
    return render_template(
        "announcements.html", announcements=formatted_announcements, seeall=False
    )


@app.route("/clipper")
def clipper():
    return render_template("clipper.html")


@app.route("/clipper/startrecording", methods=["POST"])
def startrec():
    if request.method == "POST":
        info = request.get_json(silent=True)
        url = info["url"]
        try:
            if url[:4] != "http":
                url = "http://" + url
        except:
            return {"uid": 0}
        uid = recordingmanager.StartRecording(url)
        return {"uid": uid}


@app.route("/clipper/getstate/<uid>")
def getstate(uid):
    if not verifyKeys([uid]):
        return "error"
    return {"state": recordingmanager.GetState(int(uid))}


@app.route("/clipper/stoprecording/<uid>")
def stoprec(uid):
    if not verifyKeys([uid]):
        return "error"
    return {"info": recordingmanager.StopRecording(int(uid))}


@app.route("/clipper/makeaudio/<uid>/<size>")
def makeaudio(uid, size):
    if not verifyKeys([uid]):
        return "error"
    times = {"1": 60, "2": 120, "3": 180, "5": 300, "30": 30}
    id = randomword(32)

    audio_path = werkzeug.security.safe_join(tempclipfolder, f"{id}.flac")
    if not audio_path:
        return "error"

    recordingmanager.export(id, times.get(size, 120), audio_path)

    return {"uid": id}


@app.route("/clipper/getaudio/<uid>")
def getaudio(uid):
    if not verifyKeys([uid]):
        return "keyerror"
    return flask.send_from_directory(tempclipfolder, f"{uid}.flac")


@app.route("/clipper/getclip/<uid>")
def getclip(uid):
    if not verifyKeys([uid]):
        return "keyerror"
    return flask.send_from_directory(tempclipfolder, f"{uid}_clip.flac")


@app.route("/clipper/makeclip/<uid>/<start>/<end>")
def makeclip(uid, start, end):
    if not verifyKeys([uid, start, end]):
        return "error"

    audio_path = werkzeug.security.safe_join(tempclipfolder, f"{uid}.flac")
    clip_path = werkzeug.security.safe_join(tempclipfolder, f"{uid}_clip.flac")
    if not audio_path or not clip_path:
        return "error"

    subprocess.Popen(
        [
            "ffmpeg",
            "-loglevel",
            "error",
            "-ss",
            start,
            "-i",
            audio_path,
            "-t",
            str(int(end) - int(start)),
            clip_path,
        ]
    )

    return {"status": "complete"}


@app.route("/clipper/saveclip/<uid>/<name>/<stream>")
def saveclip(uid, name, stream):
    if not verifyKeys([uid, name, stream]):
        return "error"

    clip_id = dbmanager.addclip(name, stream)

    source = werkzeug.security.safe_join(tempclipfolder, f"{uid}_clip.flac")
    destination = werkzeug.security.safe_join(volumefolder, f"{name}{clip_id}.flac")
    if not source or not destination:
        return "error"

    shutil.copyfile(source, destination)
    return {"uid": clip_id}

def format_clips(clips) -> list[dict[str, str]]:
    formatted_clips = []
    for id, name, stream, date_time in clips:
        clip = {
            "url": f"/clips/{id}",
            "audiourl": f"/clips/audio/{id}",
            "clipname": name.replace("-", " "),
            "streamname": stream.replace("-", " "),
            "streamurl": f"/clips/filter/stream/{stream}",
            "datetime": format_datetime_readable(date_time),
        }
        if isadmin(session):
            clip["editurl"] = f"/clips/edit/{id}"
        formatted_clips.append(clip)
    return formatted_clips

@app.route("/clips")
def clips():
    clips = dbmanager.lastclips(10)
    formatted_clips = format_clips(clips)
    seeall = len(clips) == 10
    return render_template(
        "cliplist.html", clips=formatted_clips, searchterm="", seeall=seeall
    )


@app.route("/clips/<uid>")
def viewclip(uid):
    if not verifyKeys([uid]):
        return "error"
    clip = dbmanager.getclip(uid)
    _, name, stream, date_time = clip
    url = f"/clips/audio/{uid}"
    return render_template(
        "clippage.html",
        name=name.replace("-", " "),
        stream=stream.replace("-", " "),
        url=url,
        streamurl=f"/clips/filter/stream/{stream}",
        editurl=f"/clips/edit/{uid}" if isadmin(session) else "",
        linkurl=vase_url + url,
        clipped=format_datetime_readable(date_time),
    )


@app.route("/clips/audio/<uid>")
def getclipaudio(uid):
    if not verifyKeys([uid]):
        return "error"
    clipinfo = dbmanager.getclip(uid)
    name = clipinfo[1]
    return flask.send_from_directory(volumefolder, f"{name}{uid}.flac")


@app.route("/clips/filter/stream/<stream>")
def clipstreamfilter(stream):
    if not verifyKeys([stream]):
        return "error"
    clips = dbmanager.filterstream(stream)
    formatted_clips = format_clips(clips)
    return render_template(
        "cliplist.html",
        clips=formatted_clips,
        searchterm=stream.replace("-", " "),
        seeall=False,
    )


@app.route("/clips/search/<search>")
def clipsearch(search):
    if not verifyKeys([search]):
        return "error"
    clips = dbmanager.searchclip(search)
    formatted_clips = format_clips(clips)
    return render_template(
        "cliplist.html",
        clips=formatted_clips,
        searchterm=search.replace("-", " "),
        seeall=False,
    )


@app.route("/clips/all")
def clipall():
    clips = dbmanager.allclip()
    formatted_clips = format_clips(clips)
    return render_template(
        "cliplist.html", clips=formatted_clips, searchterm="", seeall=False
    )


@app.route("/clips/edit/<uid>", methods=["POST", "GET"])
def editclip(uid):
    if not verifyKeys([uid]):
        return "error"
    if not isadmin(session):
        return redirect(f"/clips/{uid}", code=302)
    form = forms.buildClipEdit(uid)
    if form.is_submitted():
        clipname = form.name.data
        streamname = form.streamname.data
        dbmanager.editclip(uid, clipname, streamname)
        return redirect(f"/clips/{uid}", code=302)
    else:
        return render_template(
            "editclip.html", form=form, deleteurl=f"/clips/delete/{uid}"
        )


@app.route("/clips/delete/<uid>")
def deleteclip(uid):
    if not verifyKeys([uid]):
        return "error"
    if not isadmin(session):
        return redirect(f"/clips/{uid}", code=302)

    clipinfo = dbmanager.getclip(uid)

    name = clipinfo[1]
    clip_path = werkzeug.security.safe_join(volumefolder, f"{name}{uid}.flac")
    if not clip_path:
        return "error"

    os.remove(clip_path)
    dbmanager.deleteclip(uid)

    return redirect("/clips", code=302)


def is_file_type(filename: str, file_type: str):
    return "." in filename and filename.rsplit(".", 1)[1].lower() == file_type


@app.route("/clips/upload", methods=["GET", "POST"])
def upload_file():
    if request.method == "POST":
        if "file" not in request.files:
            flask.flash("No file part")
            return redirect(request.url)
        file = request.files["file"]
        name = request.form["clipname"].replace(" ", "-")
        if not verifyKeys([name]):
            return "error"
        if not file.filename:
            flask.flash("No selected file")
            return redirect(request.url)
        if file and is_file_type(file.filename, "flac"):
            clipid = dbmanager.addclip(name, "Upload")
            clip_path = werkzeug.security.safe_join(volumefolder, f"{name}{clipid}.flac")
            if not clip_path:
                return "error"
            file.save(clip_path)
            return redirect(f"/clips/{clipid}", code=302)
    return render_template("uploadclip.html")


@app.route("/sounds/upload", methods=["GET", "POST"])
def uploadsound():
    if not isadmin(session):
        return redirect("/admin", code=302)
    if request.method == "POST":
        if "file" not in request.files:
            flask.flash("No file part")
            return redirect(request.url)
        file = request.files["file"]
        name = request.form["soundname"].replace(" ", "-")
        library = request.form["library"]
        if not verifyKeys([name]):
            return "error"
        if not file.filename:
            flask.flash("No selected file")
            return redirect(request.url)
        if file and is_file_type(file.filename, "mp3"):
            soundid = dbmanager.addsound(name, library)
            sound_path = werkzeug.security.safe_join(volumefolder, f"{soundid}sound.mp3")
            if not sound_path:
                return "error"
            file.save(sound_path)
            return redirect(f"/sounds/audio/{soundid}", code=302)
    return render_template("uploadsound.html")


@app.route("/sounds/audio/<uid>")
def getsoundaudio(uid):
    if not verifyKeys([uid]):
        return "error"
    return flask.send_from_directory(volumefolder, f"{uid}sound.mp3")

def format_sounds(sounds) -> list[dict[str, str]]:
    return [{
        "id": id,
        "name": name.replace("-", " "),
        "link": f"/sounds/audio/{id}",
        "library": library,
    } for id, name, library in sounds]

@app.route("/sounds")
def sounds():
    sounds = dbmanager.getsounds("All")
    formatted_sounds = format_sounds(sounds)
    return render_template("soundplayer.html", tracklist=formatted_sounds)


@app.route("/sounds/list")
def soundlist():
    if not isadmin(session):
        return redirect("/sounds", code=302)
    sounds = dbmanager.getsounds("All")
    formatted_sounds = format_sounds(sounds)
    return render_template("soundslist.html", sounds=formatted_sounds)


@app.route("/sounds/delete/<uid>")
def deletesound(uid):
    if not verifyKeys([uid]):
        return "error"
    if not isadmin(session):
        return redirect("/sounds", code=302)
    sound_path = werkzeug.security.safe_join(volumefolder, f"{uid}sound.mp3")
    if not sound_path:
        return "error"
    os.remove(sound_path)
    dbmanager.deletesound(uid)
    return redirect("/sounds/list", code=302)


@app.route("/admin", methods=["POST", "GET"])
def auth():
    if isadmin(session):
        return render_template("admin.html")
    form = forms.buildLoginForm()
    if not form.is_submitted():
        return render_template("login.html", form=form)

    inputpass = form.password.data
    session["admin"] = inputpass == admin_password
    return redirect("/admin", code=302)


@app.route("/admin/announce", methods=["POST", "GET"])
def announce():
    if not isadmin(session):
        return redirect("/admin", code=302)
    form = forms.buildAnnouncementForm("", "")

    if not form.is_submitted():
        return render_template("announcementform.html", form=form)

    title = form.title.data
    content = form.content.data
    dbmanager.addannouncement(title, content)
    return redirect("/announcements", code=302)


@app.route("/admin/announce/list")
def announcelist():
    if not isadmin(session):
        return redirect("/admin", code=302)
    formatted_announcements = [{
        "id": id,
        "title": title,
        "content": content,
        "time": date_time,
        "edit": f"/admin/announce/edit/{id}",
        "delete": f"/admin/announce/delete/{id}",
    } for id, title, content, date_time in dbmanager.getannoucements(100)]
    return render_template("announcementlist.html", announcements=formatted_announcements)


@app.route("/admin/announce/delete/<uid>")
def announcementdelete(uid):
    if not verifyKeys([uid]):
        return "error"
    if not isadmin(session):
        return redirect("/", code=302)
    dbmanager.deleteannouncement(uid)
    return redirect("/admin/announce/list", code=302)


@app.route("/admin/announce/edit/<uid>", methods=["POST", "GET"])
def announcementedit(uid):
    if not isadmin(session):
        return redirect("/admin", code=302)
    _, title, content = dbmanager.getannouncement(uid)
    form = forms.buildAnnouncementForm(title, content)

    if not form.is_submitted():
        return render_template("announcementform.html", form=form)

    title = form.title.data
    content = form.content.data
    dbmanager.editannouncement(uid, title, content)
    return redirect("/announcements", code=302)


@app.route("/admin/threads")
def recthreads():
    if not isadmin(session):
        return redirect("/admin", code=302)
    threads = recordingmanager.GetAllStates()
    return render_template("threads.html", threads=threads)


@app.route("/admin/threads/close/<uid>")
def closethread(uid):
    if not isadmin(session):
        return redirect("/admin", code=302)
    recordingmanager.StopRecording(int(uid))
    return redirect("/admin/threads", code=302)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5040))
    threads = int(os.environ.get("THREADS", 20))
    print(
        f"Starting server on port {port} with {threads} threads",
        file=sys.stderr,
    )
    # app.run(debug=False, host='0.0.0.0', port=port)
    serve(app, host="0.0.0.0", port=port, threads=threads)
