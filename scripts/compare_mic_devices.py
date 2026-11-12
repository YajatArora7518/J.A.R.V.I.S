import time
import sounddevice as sd
import numpy as np

for idx in [1, 5, 9]:
    try:
        info = sd.query_devices(idx)
        print(f"\n--- Testing Device Index {idx}: {info['name']} ({sd.query_hostapis(info['hostapi'])['name']}) ---")
        samples_list = []
        def callback(indata, frames, time_info, status):
            samples_list.append(indata.copy())

        with sd.InputStream(device=idx, samplerate=16000, channels=1, dtype='int16', blocksize=1024, callback=callback):
            time.sleep(1.0)

        all_samples = np.concatenate(samples_list) if samples_list else np.array([])
        rms = np.sqrt(np.mean(all_samples.astype(np.float32) ** 2)) if len(all_samples) else 0
        peak = np.max(np.abs(all_samples)) if len(all_samples) else 0
        nz = np.count_nonzero(all_samples) if len(all_samples) else 0
        print(f"Device {idx}: frames={len(samples_list)}, total={len(all_samples)}, non_zero={nz} ({(nz/len(all_samples)*100):.1f}%), RMS={rms:.2f}, Peak={peak}")
    except Exception as e:
        print(f"Device {idx} error: {e}")
