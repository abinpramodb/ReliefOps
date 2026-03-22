-- ═══════════════════════════════════════════
-- ReliefOps — SQLite Schema
-- ═══════════════════════════════════════════

PRAGMA foreign_keys = ON;

-- USERS (admin, donor, volunteer)
CREATE TABLE IF NOT EXISTS users (
    user_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    full_name     TEXT    NOT NULL,
    email         TEXT    NOT NULL UNIQUE,
    password_hash TEXT    NOT NULL,
    role          TEXT    NOT NULL CHECK(role IN ('admin','donor','volunteer')),
    phone         TEXT,
    organization  TEXT,
    joined_date   TEXT    DEFAULT (date('now'))
);

-- DISASTERS
CREATE TABLE IF NOT EXISTS disaster (
    disaster_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    disaster_name  TEXT NOT NULL,
    disaster_type  TEXT NOT NULL,
    location       TEXT NOT NULL,
    severity_level TEXT NOT NULL CHECK(severity_level IN ('Low','Medium','High','Severe')),
    start_date     TEXT NOT NULL,
    end_date       TEXT,
    status         TEXT NOT NULL DEFAULT 'Active' CHECK(status IN ('Active','Closed','Monitoring')),
    lat            REAL,
    lng            REAL
);

-- RELIEF CAMPS
CREATE TABLE IF NOT EXISTS relief_camp (
    camp_id           INTEGER PRIMARY KEY AUTOINCREMENT,
    camp_name         TEXT    NOT NULL,
    location          TEXT    NOT NULL,
    total_capacity    INTEGER NOT NULL DEFAULT 0,
    current_occupancy INTEGER NOT NULL DEFAULT 0,
    status            TEXT    NOT NULL DEFAULT 'Active' CHECK(status IN ('Active','Full','Closed')),
    opened_date       TEXT    DEFAULT NULL,
    disaster_id       INTEGER REFERENCES disaster(disaster_id) ON DELETE CASCADE
);

-- RESOURCES
CREATE TABLE IF NOT EXISTS resource (
    resource_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    resource_name      TEXT    NOT NULL,
    category           TEXT    NOT NULL,
    unit               TEXT    NOT NULL,
    quantity_available INTEGER NOT NULL DEFAULT 0,
    min_threshold      INTEGER NOT NULL DEFAULT 0
);

-- RESOURCE SHORTAGES (reported by volunteers per camp)
CREATE TABLE IF NOT EXISTS resource_shortage (
    shortage_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    camp_id         INTEGER NOT NULL REFERENCES relief_camp(camp_id) ON DELETE CASCADE,
    resource_id     INTEGER NOT NULL REFERENCES resource(resource_id) ON DELETE CASCADE,
    quantity_needed INTEGER NOT NULL,
    remarks         TEXT,
    status          TEXT NOT NULL DEFAULT 'Pending' CHECK(status IN ('Pending','Allocated','Received')),
    reported_at     TEXT DEFAULT (datetime('now'))
);

-- RESOURCE ALLOCATIONS (admin allocates to camp)
CREATE TABLE IF NOT EXISTS resource_allocation (
    allocation_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    resource_id        INTEGER NOT NULL REFERENCES resource(resource_id) ON DELETE CASCADE,
    camp_id            INTEGER NOT NULL REFERENCES relief_camp(camp_id) ON DELETE CASCADE,
    quantity_dispatched INTEGER NOT NULL,
    allocation_date    TEXT    NOT NULL,
    status             TEXT    NOT NULL DEFAULT 'Dispatched' CHECK(status IN ('Dispatched','Received'))
);

-- DONATIONS (donor donates to resource pool)
CREATE TABLE IF NOT EXISTS donation (
    donation_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    donor_id      INTEGER NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    resource_id   INTEGER NOT NULL REFERENCES resource(resource_id) ON DELETE CASCADE,
    quantity      INTEGER NOT NULL,
    donation_date TEXT    NOT NULL,
    status        TEXT    NOT NULL DEFAULT 'Completed',
    remarks       TEXT
);