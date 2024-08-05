import librosa
import numpy as np
import soundfile as sf

SAMPLE_RATE = 44100


def mix_audio(
    samples: list[np.ndarray],
    events: list[list[int]],
    fps: int = 30,
) -> np.ndarray:
    """Play multiple audio samples at different times.

    All samples are of type np.ndarray and have the same sample rate, and should be float32."""
    total_num_frames = len(events)
    total_num_seconds = total_num_frames / fps
    total_num_samples = int(
        total_num_seconds * SAMPLE_RATE + max(len(s) for s in samples)
    )
    mixed = np.zeros(total_num_samples, dtype=np.float32)
    num_mixed = np.zeros(total_num_samples, dtype=np.uint8)
    for current_frame, events in enumerate(events):
        for event in events:
            sample = samples[event]
            start = int(current_frame / fps * SAMPLE_RATE)
            end = start + len(sample)
            mixed[start:end] += sample
            num_mixed[start:end] += 1
    mixed /= np.maximum(num_mixed, 1)
    return mixed


def load_audio_sample(filepath: str) -> np.ndarray:
    data, samplerate = librosa.load(filepath, sr=SAMPLE_RATE)
    return data


if __name__ == "__main__":
    audio_samples = [
        load_audio_sample(
            "/Users/lbq/Downloads/Steampunk Vol 2/Mechanisms/Steam UI Click.wav"
        )
    ]

    events = [[0]] + [[]] * 5 + [[0]]

    mixed = mix_audio(audio_samples, events)
    sf.write("mixed.wav", mixed, SAMPLE_RATE)
