import random
import time

from recorder import Recorder


class RecordingManager:
    def __init__(self, folder):
        self.threads = {}
        self.folder = folder

    def StartRecording(self, url):
        for key in self.threads:
            if self.threads[key]["url"] == url:
                return key

        id = random.randint(1, 65536)
        while id in self.threads:
            id = random.randint(1, 65536)

        recorder = Recorder(url)

        self.threads[id] = {"recorder": recorder, "url": url}
        recorder.start()

        return id

    def GetState(self, id):
        try:
            if id in self.threads:
                recorder = self.threads[id]["recorder"]
                return "recording" if recorder.is_healthy() else "conerror"
            else:
                return "closed"
        except:
            return "closed"

    def GetAllStates(self):
        toret = []
        for id in self.threads:
            thread = self.threads[id]
            recorder = thread["recorder"]
            state = "recording" if recorder.is_healthy() else "conerror"
            info = {
                "id": id,
                "url": thread["url"],
                "lastread": time.monotonic() - recorder.get_last_read(),
                "state": state,
                "delete": f"/admin/threads/close/{id}",
            }
            toret.append(info)
        return toret

    def StopRecording(self, id):
        try:
            self.threads[id]["recorder"].stop()
            del self.threads[id]
            return "shutdown"
        except:
            return "error"

    def export(self, id: int, length: int, path: str):
        thread = self.threads.get(id)
        if not thread:
            print(f"invalid recorder id {id} was passed to export")
            return
        recorder = thread["recorder"]
        recorder.export_flac(length, path)
