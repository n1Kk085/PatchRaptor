import hashlib
import subprocess
import uuid
import sys

class LicenseManager:
    """Handles license validation"""
    @staticmethod
    def generate_hardware_fingerprint() -> str:
        """Generate hardware fingerprint for license validation"""
        try:
            # Windows-specific wmic; fallback to MAC addr
            cmd_args = ['wmic', 'baseboard', 'get', 'serialnumber']
            result = subprocess.check_output(
                cmd_args, shell=False  # Critical: Don't use shell to prevent injection
            ).decode(errors='ignore').split('\n')
            serial = result[1].strip() if len(result) > 1 else ''
            if not serial or serial.lower() in ['to be filled by o.e.m.', 'default string', 'none']:
                return str(uuid.getnode())
            return hashlib.sha256(serial.encode()).hexdigest()
        except Exception:
            return str(uuid.getnode())

