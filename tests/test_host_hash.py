import unittest
from unittest.mock import Mock
import hashlib
import sys
import os

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.common.server import get_player_hash

class TestHostHash(unittest.TestCase):
    def test_get_player_hash_with_socket(self):
        # Create Mock socket
        mock_sock = Mock()
        mock_sock.getpeername.return_value = ("192.168.1.100", 50000)
        
        name = "Alice"
        expected_hash = hashlib.sha256(f"Alice_192.168.1.100".encode('utf-8')).hexdigest()
        
        result = get_player_hash(name, mock_sock)
        self.assertEqual(result, expected_hash)
        
    def test_get_player_hash_mock_fallback(self):
        # Test fallback when socket is None
        name = "Bob"
        expected_hash = hashlib.sha256(f"Bob_127.0.0.1".encode('utf-8')).hexdigest()
        
        result_none = get_player_hash(name, None)
        self.assertEqual(result_none, expected_hash)
        
        # Test fallback when getpeername raises an exception
        mock_sock_err = Mock()
        mock_sock_err.getpeername.side_effect = Exception("socket error")
        result_err = get_player_hash(name, mock_sock_err)
        self.assertEqual(result_err, expected_hash)

if __name__ == "__main__":
    unittest.main()
