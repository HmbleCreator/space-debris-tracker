"""
Entry point to launch the AETHERIS-ADR Platform & Mission Operations Center.
"""

import uvicorn
import os
import sys

# Ensure current working directory is on sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def main():
    print("==========================================================================")
    print("              AETHERIS-ADR MISSION OPERATIONS PLATFORM                    ")
    print("      Autonomous Space Debris Tracking, Fleet VRP & Deorbit Engine        ")
    print("==========================================================================")
    print("Starting FastAPI REST server & Web Console at http://127.0.0.1:8000 ...")
    uvicorn.run("aetheris.api.server:app", host="127.0.0.1", port=8000, reload=False, log_level="info")

if __name__ == "__main__":
    main()
