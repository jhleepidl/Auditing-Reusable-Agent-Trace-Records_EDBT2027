"""Read-only portable R21B confirmation verifier entrypoint."""
import sys
sys.dont_write_bytecode=True
from verify_measurement_v2 import main
if __name__=='__main__':main(force_confirmation=True)
