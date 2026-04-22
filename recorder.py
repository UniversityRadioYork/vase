import collections
import subprocess
import threading
import time

BUFFER_SECONDS = 600
CHUNK_SIZE = 4096


class Recorder:
    def __init__(self, url: str):
        self.__url = url
        self.__buffer = collections.deque()
        self.__lock = threading.Lock()
        self.__process = None
        self.__last_data = -1

    def start(self):
        cmd = [
            "ffmpeg",
            "-loglevel",
            "error",
            "-reconnect",
            "1",
            "-reconnect_streamed",
            "1",
            "-reconnect_delay_max",
            "5",
            "-timeout",
            "900000000", # 15 minutes
            "-i",
            self.__url,
            "-f",
            "s16le",
            "-c:a",
            "pcm_s16le",
            "-ar",
            "48000",
            "-ac",
            "2",
            "pipe:1",
        ]

        self.__process = subprocess.Popen(cmd, stdout=subprocess.PIPE)

        threading.Thread(target=self._reader, daemon=True).start()

    def stop(self):
        if self.__process:
            self.__process.kill()

    def _reader(self):
        self.__last_data = time.monotonic()
        while True:
            if not self.__process:
                time.sleep(1)
                continue
            stdout = self.__process.stdout
            if not stdout:
                break
            chunk = stdout.read(CHUNK_SIZE)
            if not chunk:
                break

            now = time.monotonic()
            if now - self.__last_data > 15 * 60:
                self.stop()
                break
            self.__last_data = now

            with self.__lock:
                self.__buffer.append((now, chunk))
                self._trim(now)

    def _trim(self, now: float):
        cutoff = now - BUFFER_SECONDS

        while self.__buffer and self.__buffer[0][0] < cutoff:
            self.__buffer.popleft()

    def _get_last(self, seconds: int):
        cutoff = time.monotonic() - seconds
        out = bytearray()

        with self.__lock:
            for t, chunk in self.__buffer:
                if t >= cutoff:
                    out.extend(chunk)

        return bytes(out)

    def get_last_read(self) -> float:
        return self.__last_data

    def is_healthy(self) -> bool:
        return time.monotonic() - self.__last_data <= 10

    def export_flac(self, seconds: int, filename: str):
        audio = self._get_last(seconds)

        cmd = [
            "ffmpeg",
            "-loglevel",
            "error",
            "-f",
            "s16le",
            "-ar",
            "48000",
            "-ac",
            "2",
            "-channel_layout",
            "stereo",
            "-i",
            "pipe:0",
            "-c:a",
            "flac",
            "-y",
            filename,
        ]

        p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
        stdin = p.stdin
        if not stdin:
            return
        stdin.write(audio)
        stdin.close()
        p.wait()


if __name__ == "__main__":
    recorder = Recorder("https://audio.ury.org.uk/jukebox")
    recorder.start()

    time.sleep(40)

    recorder.export_flac(30, "last30s.flac")
