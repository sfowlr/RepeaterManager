--
-- File generated with SQLiteStudio v3.1.1 on Sun Jun 9 17:14:27 2019
--
-- Text encoding used: UTF-8
--
PRAGMA foreign_keys = off;
BEGIN TRANSACTION;

-- Table: Devices
CREATE TABLE Devices (
    DeviceId     INTEGER  PRIMARY KEY
                          NOT NULL
                          UNIQUE,
    Description  STRING,
    CreatedDT    DATETIME NOT NULL
                          DEFAULT (CURRENT_TIMESTAMP),
    LastHeardDT  DATETIME,
    ShouldRecord BOOLEAN  NOT NULL
                          DEFAULT (1)
);


-- Table: Observations
CREATE TABLE Observations (
    DataPointId      INTEGER  PRIMARY KEY AUTOINCREMENT
                              UNIQUE
                              NOT NULL,
    TopicName        STRING,
    ObservationValue STRING,
    StoreDT          DATETIME NOT NULL
                              DEFAULT (CURRENT_TIMESTAMP),
    StoreDTMillis    INTEGER  DEFAULT (0),
    ObservationDT    DATETIME,
    Device           INTEGER  REFERENCES Devices (DeviceId)
                              NOT NULL,
    RecordingSession INTEGER  REFERENCES RecordingSessions (SessionId)
                              NOT NULL,
    ObservationType  INTEGER  REFERENCES ObservationTypes (TypeId)
                              NOT NULL
);


-- Table: ObservationTypes
CREATE TABLE ObservationTypes (
    TypeId           INTEGER PRIMARY KEY AUTOINCREMENT
                             UNIQUE
                             NOT NULL,
    TypeName         STRING  UNIQUE,
    TypeTopicPattern STRING  UNIQUE,
    ShouldRecord     BOOLEAN DEFAULT (1)
                             NOT NULL
);

INSERT INTO ObservationTypes (
    TypeName,
    TypeTopicPattern,
    ShouldRecord
) VALUES
('Other','*', 1),
('Position','cdas/dev/+/GPS', 1),
('HeartRate','ch/snsr/+/HeartRateSim', 1),
('OxygenTank','ch/snsr/+/OxygenTankLevelSim', 0);


-- Table: RecordingSessions
CREATE TABLE RecordingSessions (
    SessionId   INTEGER   PRIMARY KEY AUTOINCREMENT
                          UNIQUE
                          NOT NULL,
    SessionUuid UUID (16) UNIQUE,
    StartDT     DATETIME  NOT NULL
                          DEFAULT (CURRENT_TIMESTAMP),
    EndDT       DATETIME,
    IsRecording BOOLEAN   DEFAULT (1)
                          NOT NULL,
    IsArchived  BOOLEAN   DEFAULT (0)
                          NOT NULL
);
-- Start a recording session
-- INSERT INTO RecordingSessions DEFAULT VALUES;

COMMIT TRANSACTION;
PRAGMA foreign_keys = on;
