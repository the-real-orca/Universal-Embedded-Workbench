
import sys
import os
import time

# Add current directory to path so we can import workbench_driver
sys.path.append(os.path.join(os.getcwd(), 'pytest'))

from workbench_driver import WorkbenchDriver

def verify():
    wt = WorkbenchDriver("http://localhost:8080")
    
    print("--- Phase 1: Clear existing session ---")
    wt.test_clear()
    prog = wt.test_progress()
    print(f"Active after clear: {prog.get('active')}")
    assert prog.get('active') is False

    print("\n--- Phase 2: Start new session ---")
    wt.test_start("Verify-Test", "Integration", total=2)
    prog = wt.test_progress()
    print(f"Active: {prog.get('active')}, Spec: {prog.get('spec')}, Started At: {prog.get('started_at')}")
    assert prog.get('active') is True
    assert prog.get('spec') == "Verify-Test"
    assert "started_at" in prog

    print("\n--- Phase 3: Update step ---")
    wt.test_step("T1", "Step 1", "Doing something")
    prog = wt.test_progress()
    print(f"Current Test: {prog.get('current', {}).get('name')}")
    assert prog.get('current', {}).get('id') == "T1"

    print("\n--- Phase 4: Record result ---")
    wt.test_result("T1", "Step 1", "PASS")
    prog = wt.test_progress()
    print(f"Completed count: {len(prog.get('completed', []))}")
    assert len(prog.get('completed', [])) == 1
    assert prog.get('completed')[0]['result'] == "PASS"

    print("\n--- Phase 5: End session ---")
    wt.test_end()
    prog = wt.test_progress()
    print(f"Active: {prog.get('active')}, Ended: {prog.get('ended')}, Ended At: {prog.get('ended_at')}")
    assert prog.get('active') is True  # Should stay active but marked as ended
    assert prog.get('ended') is True
    assert "ended_at" in prog

    print("\n--- Phase 6: Final Clear ---")
    wt.test_clear()
    prog = wt.test_progress()
    print(f"Active after final clear: {prog.get('active')}")
    assert prog.get('active') is False

    print("\nVerification successful!")

if __name__ == "__main__":
    try:
        verify()
    except Exception as e:
        print(f"\nVerification FAILED: {e}")
        sys.exit(1)
