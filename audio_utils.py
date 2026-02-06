"""Utility per registrazione e gestione file audio."""

import os
import tempfile
import threading

AUDIO_EXTENSIONS = {".mp3", ".wav", ".ogg", ".m4a", ".flac", ".aac", ".wma"}

# Lazy import - sounddevice necessario solo per registrazione
_sd = None
_recording_stream = None
_recording_frames = []
_recording_lock = threading.Lock()


def is_audio_file(filename):
    """Controlla se il file ha un'estensione audio supportata."""
    _, ext = os.path.splitext(filename.lower())
    return ext in AUDIO_EXTENSIONS


def is_available():
    """True se sounddevice e' installato (necessario per registrazione)."""
    try:
        import sounddevice
        return True
    except ImportError:
        return False


def _get_sd():
    """Lazy import di sounddevice."""
    global _sd
    if _sd is None:
        import sounddevice
        _sd = sounddevice
    return _sd


def get_temp_wav_path():
    """Crea un path temporaneo per la registrazione WAV."""
    fd, path = tempfile.mkstemp(suffix=".wav")
    os.close(fd)
    return path


def record_audio(on_chunk=None):
    """Avvia registrazione in background. Ritorna True se avviata."""
    global _recording_stream, _recording_frames
    sd = _get_sd()

    with _recording_lock:
        if _recording_stream is not None:
            return False
        _recording_frames = []

    samplerate = 44100
    channels = 1

    def callback(indata, frames, time_info, status):
        with _recording_lock:
            _recording_frames.append(indata.copy())
        if on_chunk:
            on_chunk(len(_recording_frames))

    _recording_stream = sd.InputStream(
        samplerate=samplerate, channels=channels,
        dtype="int16", callback=callback
    )
    _recording_stream.start()
    return True


def stop_recording(save_path):
    """Ferma registrazione e salva come WAV. Ritorna True se salvato."""
    import wave
    global _recording_stream, _recording_frames

    with _recording_lock:
        if _recording_stream is None:
            return False
        stream = _recording_stream
        frames = _recording_frames[:]
        _recording_stream = None
        _recording_frames = []

    stream.stop()
    stream.close()

    if not frames:
        return False

    import numpy as np
    audio_data = np.concatenate(frames, axis=0)

    with wave.open(save_path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)  # 16-bit
        wf.setframerate(44100)
        wf.writeframes(audio_data.tobytes())

    return True


def is_recording():
    """True se una registrazione e' in corso."""
    return _recording_stream is not None
