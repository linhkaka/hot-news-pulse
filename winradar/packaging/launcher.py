# PyInstaller cần 1 file script ở ngoài package để làm điểm vào.
import sys

from winradar.app import main

if __name__ == "__main__":
    sys.exit(main())
