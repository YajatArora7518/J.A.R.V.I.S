"""
JARVIS Cold-Start Test: 3 boot cycles
Launches python main.py, waits for [BOOT] 9/9, verifies stability, then kills.
"""
import subprocess
import time
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

JARVIS_DIR = r"C:\Users\yajat\OneDrive\Desktop\JARVIS M\JARVIS MAIN"
RESULTS = []

for cycle in range(1, 4):
    print(f"\n{'='*60}")
    print(f"  COLD START CYCLE {cycle}/3")
    print(f"{'='*60}")
    
    # Kill any existing JARVIS/python instances from previous cycle
    try:
        subprocess.run(["taskkill", "/F", "/FI", "WINDOWTITLE eq JARVIS*"], 
                       capture_output=True, timeout=5)
    except Exception:
        pass
    time.sleep(2)
    
    # Start JARVIS
    print(f"  [CYCLE {cycle}] Starting python main.py ...")
    proc = subprocess.Popen(
        [sys.executable, "main.py"],
        cwd=JARVIS_DIR,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding='utf-8',
        errors='replace'
    )
    
    boot_complete = False
    start_time = time.time()
    timeout = 120  # 2 minute max for boot
    output_lines = []
    
    while time.time() - start_time < timeout:
        try:
            line = proc.stdout.readline()
            if not line:
                if proc.poll() is not None:
                    print(f"  [CYCLE {cycle}] PROCESS EXITED with code {proc.returncode}")
                    break
                time.sleep(0.1)
                continue
            
            line = line.strip()
            output_lines.append(line)
            
            if "[BOOT] 9/9" in line:
                boot_time = round(time.time() - start_time, 1)
                print(f"  [CYCLE {cycle}] BOOT COMPLETE in {boot_time}s")
                boot_complete = True
                
                # Wait additional time to verify stability
                print(f"  [CYCLE {cycle}] Verifying stability for 30 seconds...")
                stable_start = time.time()
                crashed = False
                
                while time.time() - stable_start < 30:
                    if proc.poll() is not None:
                        print(f"  [CYCLE {cycle}] CRASHED during stability check! Exit code: {proc.returncode}")
                        crashed = True
                        break
                    time.sleep(1)
                
                if not crashed:
                    print(f"  [CYCLE {cycle}] STABLE for 30 seconds after boot")
                    RESULTS.append("PASS")
                else:
                    RESULTS.append("FAIL: Crashed during stability check")
                break
                
        except Exception as e:
            print(f"  [CYCLE {cycle}] Read error: {e}")
            break
    
    if not boot_complete:
        elapsed = round(time.time() - start_time, 1)
        if proc.poll() is not None:
            RESULTS.append(f"FAIL: Process exited before 9/9 (code={proc.returncode}, elapsed={elapsed}s)")
        else:
            RESULTS.append(f"FAIL: Boot timeout after {elapsed}s")
    
    # Kill the process
    try:
        proc.kill()
        proc.wait(timeout=5)
    except Exception:
        pass
    
    print(f"  [CYCLE {cycle}] Result: {RESULTS[-1]}")
    time.sleep(3)  # Brief pause between cycles


# Final Report
print(f"\n{'='*60}")
print(f"  COLD START TEST RESULTS")
print(f"{'='*60}")
for i, r in enumerate(RESULTS, 1):
    icon = "PASS" if r == "PASS" else "FAIL"
    print(f"  Cycle {i}: [{icon}] {r}")
print(f"{'='*60}")
