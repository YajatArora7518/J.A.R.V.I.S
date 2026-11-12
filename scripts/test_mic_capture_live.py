import time
import sounddevice as sd
import numpy as np

def test_mic():
    dev_info = sd.query_devices(kind='input')
    print("Default Input Device Info:")
    print("  Name:", dev_info.get('name'))
    print("  Index:", dev_info.get('index', sd.default.device[0]))
    print("  HostAPI:", dev_info.get('hostapi'))
    print("  Default Samplerate:", dev_info.get('default_samplerate'))
    print("  Max Input Channels:", dev_info.get('max_input_channels'))

    RATE = 16000
    CHANNELS = 1
    BLOCKSIZE = 1024
    DURATION = 3.0

    frames = []
    rms_list = []
    peak_list = []
    total_samples = 0
    non_zero_samples = 0
    callback_count = 0

    def callback(indata, frame_count, time_info, status):
        nonlocal callback_count, total_samples, non_zero_samples
        callback_count += 1
        data = indata.copy()
        samples = data.flatten()
        total_samples += len(samples)
        nz = np.count_nonzero(samples)
        non_zero_samples += nz
        rms = np.sqrt(np.mean(samples.astype(np.float32) ** 2))
        peak = np.max(np.abs(samples))
        rms_list.append(rms)
        peak_list.append(peak)

    print(f"\n[MIC] Opening InputStream at {RATE}Hz, mono, int16 for {DURATION}s...")
    with sd.InputStream(samplerate=RATE, channels=CHANNELS, dtype='int16', blocksize=BLOCKSIZE, callback=callback):
        time.sleep(DURATION)

    avg_rms = np.mean(rms_list) if rms_list else 0
    max_peak = np.max(peak_list) if peak_list else 0

    print(f"\n[MIC RESULTS]")
    print(f"  Callbacks invoked: {callback_count}")
    print(f"  Total samples captured: {total_samples}")
    print(f"  Non-zero samples: {non_zero_samples}")
    print(f"  Average RMS: {avg_rms:.2f}")
    print(f"  Max Peak: {max_peak}")
    print(f"  Non-zero %: {(non_zero_samples / total_samples * 100) if total_samples > 0 else 0:.2f}%")

if __name__ == '__main__':
    test_mic()
