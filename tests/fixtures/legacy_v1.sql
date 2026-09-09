-- Schema extracted from the actual earlier conversation ZIP, no personal data.
BEGIN TRANSACTION;
CREATE TABLE system_state (
            id INTEGER PRIMARY KEY CHECK(id = 1),
            version INTEGER NOT NULL DEFAULT 1
        );
INSERT INTO "system_state" VALUES(1,1);
CREATE TABLE task_templates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            difficulty INTEGER NOT NULL DEFAULT 3,
            recurrence TEXT NOT NULL DEFAULT 'once',
            weekday INTEGER,
            month_day INTEGER,
            start_date TEXT NOT NULL,
            assignment_mode TEXT NOT NULL DEFAULT 'auto',
            fixed_user_id INTEGER,
            active INTEGER NOT NULL DEFAULT 1,
            notes TEXT,
            FOREIGN KEY (fixed_user_id) REFERENCES users(id) ON DELETE SET NULL
        );
CREATE TABLE tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            template_id INTEGER,
            user_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            difficulty INTEGER NOT NULL DEFAULT 3,
            due_date TEXT NOT NULL,
            notes TEXT,
            completed INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            completed_at TEXT,
            FOREIGN KEY (template_id) REFERENCES task_templates(id) ON DELETE SET NULL,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            UNIQUE(template_id, due_date)
        );
CREATE TABLE users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            active INTEGER NOT NULL DEFAULT 1
        );
DELETE FROM "sqlite_sequence";
COMMIT;
