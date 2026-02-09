"""
Test suite for License Manager.
"""
import pytest
import subprocess
from unittest.mock import patch, MagicMock
from patchraptor.license_manager import LicenseManager


class TestLicenseManager:
    """Test LicenseManager functionality."""

    def test_generate_hardware_fingerprint_wmic_success(self):
        """Test fingerprint generation with successful wmic call."""
        mock_output = b"SerialNumber\n1234567890\n"
        
        with patch('subprocess.check_output', return_value=mock_output) as mock_check_output:
            fingerprint = LicenseManager.generate_hardware_fingerprint()
            
            assert fingerprint  # Should return a hash
            # Expected hash of "1234567890" using sha256
            # hashlib.sha256("1234567890".encode()).hexdigest()
            # We just verify it returns a string and called subprocess
            assert isinstance(fingerprint, str)
            mock_check_output.assert_called_with(['wmic', 'baseboard', 'get', 'serialnumber'], shell=False)

    def test_generate_hardware_fingerprint_wmic_empty(self):
        """Test fingerprint generation when wmic returns empty/invalid serial."""
        mock_output = b"SerialNumber\nTo be filled by O.E.M.\n"
        
        with patch('subprocess.check_output', return_value=mock_output), \
             patch('uuid.getnode', return_value=9876543210):
            
            fingerprint = LicenseManager.generate_hardware_fingerprint()
            
            assert fingerprint == "9876543210"

    def test_generate_hardware_fingerprint_wmic_failure(self):
        """Test fingerprint generation when wmic fails."""
        with patch('subprocess.check_output', side_effect=subprocess.CalledProcessError(1, 'cmd')), \
             patch('uuid.getnode', return_value=9876543210):
            
            fingerprint = LicenseManager.generate_hardware_fingerprint()
            
            assert fingerprint == "9876543210"
