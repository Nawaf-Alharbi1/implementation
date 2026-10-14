-- نسخة SQLite من مخطط thiqa_database.sql (نفس الجداول والأعمدة، بصيغة SQLite).
-- تُنفَّذ تلقائياً عند تشغيل السيرفر (server/db.js). ملف MySQL الأصلي لم يُمسّ.
-- الفرق الوحيد عن الأصلي: UNIQUE على UserName و Email (ضروري لمنع تكرار الحسابات).

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS Users (
    UserId            INTEGER PRIMARY KEY AUTOINCREMENT,
    UserName          VARCHAR(50)  NOT NULL UNIQUE COLLATE NOCASE,
    Email             VARCHAR(100) NOT NULL UNIQUE COLLATE NOCASE,
    PasswordHash      VARCHAR(255) NOT NULL,
    IsAdmin           BOOLEAN      NOT NULL DEFAULT 0,
    IsCompanyEmployee BOOLEAN      NOT NULL DEFAULT 0,
    ProviderId        TEXT         NULL REFERENCES Insurance_Providers(ProviderId),
    NationalId        VARCHAR(20)  NULL,
    CreatedAt         DATETIME     NOT NULL DEFAULT (datetime('now'))
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

CREATE TABLE IF NOT EXISTS Company_Offers (
    OfferId           INTEGER PRIMARY KEY AUTOINCREMENT,
    ProviderId        INTEGER NOT NULL,
    OfferName         VARCHAR(100) NOT NULL,
    CoverageType      VARCHAR(30) NOT NULL, -- 'TPL' or 'Comprehensive'
    BasePremiumRate   DECIMAL(5,4) NOT NULL, -- Rate as percentage of vehicle value
    MinPremium        DECIMAL(10,2) NOT NULL,
    Description       TEXT,
    IsActive          BOOLEAN NOT NULL DEFAULT 1,
    CreatedAt         DATETIME NOT NULL DEFAULT (datetime('now')),
    UpdatedAt         DATETIME NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (ProviderId) REFERENCES Insurance_Providers(ProviderId)
);

-- Trigger to update UpdatedAt timestamp
CREATE TRIGGER IF NOT EXISTS update_company_offers_updated_at
AFTER UPDATE ON Company_Offers
FOR EACH ROW
BEGIN
    UPDATE Company_Offers SET UpdatedAt = datetime('now') WHERE OfferId = NEW.OfferId;
END;
