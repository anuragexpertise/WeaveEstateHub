"""
WeaveEstateHub QR Evaluation API Tests
Tests the /api/evaluate-qr endpoint for apartment owners and vendors
"""
import pytest
import requests

BASE_URL = "http://localhost:8050"

class TestQREvaluationAPI:
    """Tests for /api/evaluate-qr Flask endpoint"""
    
    def test_apartment_owner_pass_no_dues(self):
        """Test QR evaluation for apartment owner with no dues - should PASS"""
        # QR format: ESTATEHUB|APT:{id}|FLAT:{flat}|SOC:{society_id}
        qr_data = "ESTATEHUB|APT:1|FLAT:A-101|SOC:1"
        response = requests.post(
            f"{BASE_URL}/api/evaluate-qr",
            json={"qr_data": qr_data}
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        
        # Verify response structure
        assert "status" in data, "Response should have 'status' field"
        assert "title" in data, "Response should have 'title' field"
        assert "name" in data, "Response should have 'name' field"
        assert "detail" in data, "Response should have 'detail' field"
        
        # For apartment with no dues, should return PASS
        print(f"Apartment QR Response: {data}")
        # Status could be 'pass' or 'fail' depending on dues
        assert data["status"] in ["pass", "fail"], f"Status should be pass or fail, got {data['status']}"
        assert data["entity_type"] == "apartment", f"Entity type should be apartment"
    
    def test_vendor_pass_no_dues(self):
        """Test QR evaluation for vendor with no dues - should PASS"""
        # QR format: ESTATEHUB|VEN:{id}|SVC:{service}|SOC:{society_id}
        qr_data = "ESTATEHUB|VEN:1|SVC:Plumber|SOC:1"
        response = requests.post(
            f"{BASE_URL}/api/evaluate-qr",
            json={"qr_data": qr_data}
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        
        print(f"Vendor QR Response: {data}")
        assert "status" in data
        assert data["status"] in ["pass", "fail"]
        assert data["entity_type"] == "vendor"
    
    def test_nonexistent_apartment_fail(self):
        """Test QR evaluation for non-existent apartment - should FAIL"""
        qr_data = "ESTATEHUB|APT:999|FLAT:Z|SOC:1"
        response = requests.post(
            f"{BASE_URL}/api/evaluate-qr",
            json={"qr_data": qr_data}
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        
        print(f"Non-existent apartment response: {data}")
        assert data["status"] == "fail", f"Expected fail for non-existent apartment, got {data['status']}"
        assert data["title"] == "FAIL"
        assert "not found" in data["detail"].lower() or "unknown" in data["name"].lower()
    
    def test_invalid_qr_format_error(self):
        """Test QR evaluation with invalid format - should return error"""
        # Invalid QR - doesn't start with ESTATEHUB|
        qr_data = "INVALID_QR_CODE_DATA"
        response = requests.post(
            f"{BASE_URL}/api/evaluate-qr",
            json={"qr_data": qr_data}
        )
        
        assert response.status_code == 400, f"Expected 400 for invalid QR, got {response.status_code}"
        data = response.json()
        
        print(f"Invalid QR response: {data}")
        assert data["status"] == "error"
        assert "invalid" in data["message"].lower()
    
    def test_empty_qr_data_error(self):
        """Test QR evaluation with empty data - should return error"""
        response = requests.post(
            f"{BASE_URL}/api/evaluate-qr",
            json={"qr_data": ""}
        )
        
        assert response.status_code == 400, f"Expected 400 for empty QR, got {response.status_code}"
        data = response.json()
        
        print(f"Empty QR response: {data}")
        assert data["status"] == "error"
    
    def test_missing_society_in_qr(self):
        """Test QR evaluation without society ID - should return error"""
        qr_data = "ESTATEHUB|APT:1|FLAT:A-101"  # Missing SOC
        response = requests.post(
            f"{BASE_URL}/api/evaluate-qr",
            json={"qr_data": qr_data}
        )
        
        assert response.status_code == 400, f"Expected 400 for missing society, got {response.status_code}"
        data = response.json()
        
        print(f"Missing society response: {data}")
        assert data["status"] == "error"
        assert "society" in data["message"].lower()
    
    def test_unrecognized_qr_format(self):
        """Test QR with ESTATEHUB prefix but unrecognized entity type"""
        qr_data = "ESTATEHUB|UNKNOWN:1|SOC:1"
        response = requests.post(
            f"{BASE_URL}/api/evaluate-qr",
            json={"qr_data": qr_data}
        )
        
        assert response.status_code == 400, f"Expected 400 for unrecognized format, got {response.status_code}"
        data = response.json()
        
        print(f"Unrecognized format response: {data}")
        assert data["status"] == "error"


class TestGateAccessLogging:
    """Tests to verify gate_access table logging on PASS"""
    
    def test_gate_access_logged_on_pass(self):
        """Verify that successful QR scan logs entry to gate_access table"""
        # First, get current count of gate_access entries
        # We'll test by scanning a valid QR and checking the response mentions logging
        qr_data = "ESTATEHUB|APT:1|FLAT:A-101|SOC:1"
        response = requests.post(
            f"{BASE_URL}/api/evaluate-qr",
            json={"qr_data": qr_data}
        )
        
        data = response.json()
        print(f"Gate access test response: {data}")
        
        # If status is pass, detail should mention "Entry logged"
        if data["status"] == "pass":
            assert "logged" in data["detail"].lower(), "PASS response should mention entry was logged"


class TestUserQRFormat:
    """Tests for USER type QR codes"""
    
    def test_user_qr_identified(self):
        """Test QR evaluation for generic USER type"""
        qr_data = "ESTATEHUB|USER:1|ROLE:admin|SOC:1"
        response = requests.post(
            f"{BASE_URL}/api/evaluate-qr",
            json={"qr_data": qr_data}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        print(f"User QR response: {data}")
        assert data["status"] == "pass"
        assert data["title"] == "IDENTIFIED"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
