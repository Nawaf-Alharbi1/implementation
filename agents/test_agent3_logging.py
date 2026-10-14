"""
Test script to verify Agent 3 database logging works.
"""
import json
import os
import sqlite3
from agent3_explainer import ExplainerAgent

def test_agent3_logging():
    """Test that Agent 3 logs explanation to database when rec_id is provided."""
    # Ensure we're using a test database to avoid interfering with existing data
    test_db_path = "../database/test_thiqa.db"

    # Remove test database if it exists
    if os.path.exists(test_db_path):
        os.remove(test_db_path)

    # Create agent with test database
    agent = ExplainerAgent(db_path=test_db_path)

    # Test data
    selected = {
        "provider_name": "Test Company",
        "premium": 1000.0,
        "suitability_score": 0.85,
        "score_breakdown": {
            "premium_score": 0.8,
            "coverage_scope_score": 0.7,
            "coverage_value_score": 0.75,
            "deductible_score": 0.9,
            "addons_score": 0.6,
            "profile_fit_score": 0.7,
            "reliability_score": 0.85,
            "workshop_score": 0.8,
            "digital_score": 0.6
        },
        "weighted_contributions": {
            "premium": 0.24,
            "coverage_scope": 0.14,
            "coverage_value": 0.15,
            "deductible": 0.135,
            "add_ons": 0.06,
            "profile_fit": 0.07,
            "reliability": 0.1275,
            "workshop_network": 0.08,
            "digital": 0.0
        },
        "add_ons": ["roadside_assistance"]
    }

    ranked = [
        selected,
        {
            "provider_name": "Second Company",
            "premium": 1100.0,
            "suitability_score": 0.75,
            "score_breakdown": {
                "premium_score": 0.7,
                "coverage_scope_score": 0.6,
                "coverage_value_score": 0.65,
                "deductible_score": 0.8,
                "addons_score": 0.5,
                "profile_fit_score": 0.6,
                "reliability_score": 0.75,
                "workshop_score": 0.7,
                "digital_score": 0.5
            },
            "weighted_contributions": {
                "premium": 0.21,
                "coverage_scope": 0.12,
                "coverage_value": 0.13,
                "deductible": 0.12,
                "add_ons": 0.05,
                "profile_fit": 0.07,
                "reliability": 0.1125,
                "workshop_network": 0.08,
                "digital": 0.0
            },
            "add_ons": ["roadside_assistance"]
        }
    ]

    # Test with rec_id = 1 (we'll create this in the test database)
    test_rec_id = 1

    # Make sure test database exists and has the tables
    conn = sqlite3.connect(test_db_path)
    cursor = conn.cursor()

    # Create tables if they don't exist (using the same schema as the main database)
    cursor.executescript("""
    CREATE TABLE IF NOT EXISTS Users (
        UserId       INTEGER PRIMARY KEY AUTOINCREMENT,
        UserName     VARCHAR(50)  NOT NULL UNIQUE COLLATE NOCASE,
        Email        VARCHAR(100) NOT NULL UNIQUE COLLATE NOCASE,
        PasswordHash VARCHAR(255) NOT NULL,
        IsAdmin      BOOLEAN      NOT NULL DEFAULT 0,
        CreatedAt    DATETIME     NOT NULL DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS Customer_Profiles (
        ProfileId       INTEGER PRIMARY KEY AUTOINCREMENT,
        UserId          INTEGER NOT NULL,
        FullName        VARCHAR(100),
        NationalId      VARCHAR(20),
        DateOfBirth     DATE,
        DriverLicenseNo VARCHAR(30),
        FOREIGN KEY (UserId) REFERENCES Users(UserId)
    );

    CREATE TABLE IF NOT EXISTS Vehicles (
        VehicleId      INTEGER PRIMARY KEY AUTOINCREMENT,
        ProfileId      INTEGER NOT NULL,
        SerialNumber   VARCHAR(40),
        MakeModelYear  VARCHAR(80),
        EstimatedValue DECIMAL(10,2),
        PurposeOfUse   VARCHAR(40),
        FOREIGN KEY (ProfileId) REFERENCES Customer_Profiles(ProfileId)
    );

    CREATE TABLE IF NOT EXISTS Insurance_Providers (
        ProviderId   INTEGER PRIMARY KEY AUTOINCREMENT,
        ProviderName VARCHAR(100),
        LogoUrl      VARCHAR(255),
        Website      VARCHAR(255)
    );

    CREATE TABLE IF NOT EXISTS API_Settings (
        SettingId  INTEGER PRIMARY KEY AUTOINCREMENT,
        ProviderId INTEGER NOT NULL,
        Endpoint   VARCHAR(255),
        AuthKey    VARCHAR(255),
        Protocol   VARCHAR(40),
        Timeout    INTEGER,
        FOREIGN KEY (ProviderId) REFERENCES Insurance_Providers(ProviderId)
    );

    CREATE TABLE IF NOT EXISTS Quote_Requests (
        RequestId       INTEGER PRIMARY KEY AUTOINCREMENT,
        ProfileId       INTEGER NOT NULL,
        VehicleId       INTEGER NOT NULL,
        CoverageType    VARCHAR(30),
        RequestedAddOns TEXT,
        Timestamp       DATETIME,
        FOREIGN KEY (ProfileId) REFERENCES Customer_Profiles(ProfileId),
        FOREIGN KEY (VehicleId) REFERENCES Vehicles(VehicleId)
    );

    CREATE TABLE IF NOT EXISTS Retrieved_Quotes (
        QuoteId      INTEGER PRIMARY KEY AUTOINCREMENT,
        RequestId    INTEGER NOT NULL,
        ProviderId   INTEGER NOT NULL,
        Premium      DECIMAL(10,2),
        CoverageType VARCHAR(30),
        Deductible   DECIMAL(10,2),
        AddOns       TEXT,
        FOREIGN KEY (RequestId)  REFERENCES Quote_Requests(RequestId),
        FOREIGN KEY (ProviderId) REFERENCES Insurance_Providers(ProviderId)
    );

    CREATE TABLE IF NOT EXISTS Recommendations (
        RecId            INTEGER PRIMARY KEY AUTOINCREMENT,
        RequestId        INTEGER NOT NULL UNIQUE,
        SelectedQuoteId  INTEGER NOT NULL,
        SuitabilityScore DECIMAL(5,4),
        CreatedAt        DATETIME,
        FOREIGN KEY (RequestId)       REFERENCES Quote_Requests(RequestId),
        FOREIGN KEY (SelectedQuoteId) REFERENCES Retrieved_Quotes(QuoteId)
    );

    CREATE TABLE IF NOT EXISTS Explanations (
        ExplId            INTEGER PRIMARY KEY AUTOINCREMENT,
        RecId             INTEGER NOT NULL UNIQUE,
        MainReasons       TEXT,
        CriteriaBreakdown TEXT,
        ComparisonText    TEXT,
        FOREIGN KEY (RecId) REFERENCES Recommendations(RecId)
    );
    """)

    # Insert a test user
    cursor.execute(
        "INSERT OR IGNORE INTO Users (UserName, Email, PasswordHash) VALUES (?, ?, ?)",
        ("testuser", "test@example.com", "hashedpassword")
    )
    user_id = cursor.lastrowid
    if user_id == 0:  # If it already existed, get the existing id
        cursor.execute("SELECT UserId FROM Users WHERE UserName = ?", ("testuser",))
        user_id = cursor.fetchone()[0]

    # Insert a test customer profile
    cursor.execute(
        "INSERT OR IGNORE INTO Customer_Profiles (UserId, FullName, NationalId, DateOfBirth, DriverLicenseNo) VALUES (?, ?, ?, ?, ?)",
        (user_id, "test customer", "1234567890", "1990-01-01", "1234567890")
    )
    profile_id = cursor.lastrowid
    if profile_id == 0:
        cursor.execute("SELECT ProfileId FROM Customer_Profiles WHERE UserId = ?", (user_id,))
        profile_id = cursor.fetchone()[0]

    # Insert a test vehicle
    cursor.execute(
        "INSERT OR IGNORE INTO Vehicles (ProfileId, SerialNumber, MakeModelYear, EstimatedValue, PurposeOfUse) VALUES (?, ?, ?, ?, ?)",
        (profile_id, "ABC123", "2020", 100000, "personal")
    )
    vehicle_id = cursor.lastrowid
    if vehicle_id == 0:
        cursor.execute("SELECT VehicleId FROM Vehicles WHERE ProfileId = ?", (profile_id,))
        vehicle_id = cursor.fetchone()[0]

    # Insert a test insurance provider
    cursor.execute(
        "INSERT OR IGNORE INTO Insurance_Providers (ProviderId, ProviderName) VALUES (?, ?)",
        (1, "Test Insurance Company")
    )

    # Insert a test quote request
    cursor.execute(
        "INSERT OR IGNORE INTO Quote_Requests (ProfileId, VehicleId, CoverageType, RequestedAddOns, Timestamp) VALUES (?, ?, ?, ?, ?)",
        (profile_id, vehicle_id, "TPL", '["roadside_assistance"]', "2023-01-01T10:00:00")
    )
    request_id = cursor.lastrowid
    if request_id == 0:
        cursor.execute("SELECT RequestId FROM Quote_Requests WHERE ProfileId = ? AND VehicleId = ?", (profile_id, vehicle_id))
        request_id = cursor.fetchone()[0]

    # Insert a test retrieved quote
    cursor.execute(
        "INSERT OR IGNORE INTO Retrieved_Quotes (RequestId, ProviderId, Premium, CoverageType, Deductible, AddOns) VALUES (?, ?, ?, ?, ?, ?)",
        (request_id, 1, 1000.0, "TPL", 500.0, '["roadside_assistance"]')
    )
    quote_id = cursor.lastrowid
    if quote_id == 0:
        cursor.execute("SELECT QuoteId FROM Retrieved_Quotes WHERE RequestId = ? AND ProviderId = ?", (request_id, 1))
        quote_id = cursor.fetchone()[0]

    # Insert a test recommendation to get a valid RecId
    cursor.execute(
        "INSERT OR IGNORE INTO Recommendations (RequestId, SelectedQuoteId, SuitabilityScore, CreatedAt) VALUES (?, ?, ?, ?)",
        (request_id, quote_id, 0.85, "2023-01-01T10:00:00")
    )
    test_rec_id = cursor.lastrowid
    if test_rec_id == 0:
        cursor.execute("SELECT RecId FROM Recommendations WHERE RequestId = ? AND SelectedQuoteId = ?", (request_id, quote_id))
        test_rec_id = cursor.fetchone()[0]

    conn.commit()
    conn.close()

    # Now test the agent logging
    result = agent.run(selected, ranked, rec_id=test_rec_id)

    # Verify the result
    assert "main_reasons" in result
    assert "strengths" in result
    assert "criteria_explanations" in result
    assert "comparison" in result
    assert "comparison_array" in result

    # Check that an explanation was logged to the database
    conn = sqlite3.connect(test_db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM Explanations WHERE RecId = ?", (test_rec_id,))
    explanation_record = cursor.fetchone()
    conn.close()

    assert explanation_record is not None, "No explanation record found in database"
    assert explanation_record[0] is not None, "ExplId should not be null"
    assert explanation_record[1] == test_rec_id, "RecId should match"
    assert explanation_record[2] is not None, "MainReasons should not be null"
    assert explanation_record[3] is not None, "CriteriaBreakdown should not be null"
    assert explanation_record[4] is not None, "ComparisonText should not be null"

    print("Agent 3 database logging test PASSED")
    print("Logged explanation for RecId: {}".format(test_rec_id))
    print("Main reasons: {}".format(result['main_reasons'][:50]))
    print("Number of criteria explanations: {}".format(len(result['criteria_explanations'])))

if __name__ == "__main__":
    test_agent3_logging()