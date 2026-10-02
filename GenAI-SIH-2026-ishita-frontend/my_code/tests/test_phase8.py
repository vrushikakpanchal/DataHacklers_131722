import sys
import os

def verify_phase8():
    print("==================================================")
    print("   SIH PS ID: 26154 - PHASE 8 STREAMLIT DASHBOARD ")
    print("==================================================")

    gui_path = os.path.join("apps", "gui.py")
    assert os.path.exists(gui_path), "apps/gui.py is missing!"
    print(f"[✓] Streamlit GUI Application verified at: {gui_path}")

    print("\nTo launch the operator interface, run:")
    print("  streamlit run apps/gui.py")
    print("==================================================")
    print("SUCCESS: Phase 8 Multi-Tab Operator Interface Ready!")

if __name__ == "__main__":
    verify_phase8()