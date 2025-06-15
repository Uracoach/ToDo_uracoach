-- src/flask_todo_app/schema.sql

DROP TABLE IF EXISTS todos;
DROP TABLE IF EXISTS students;

CREATE TABLE students (
    name TEXT PRIMARY KEY,
    password TEXT NOT NULL
);

CREATE TABLE todos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student TEXT NOT NULL,
    date TEXT NOT NULL,
    subject TEXT NOT NULL,
    material TEXT,
    start_page INTEGER,
    end_page INTEGER,
    target_hour INTEGER DEFAULT 0,
    target_min INTEGER DEFAULT 0,
    actual_hour INTEGER DEFAULT 0,
    actual_min INTEGER DEFAULT 0,
    completed INTEGER DEFAULT 0,
    FOREIGN KEY (student) REFERENCES students (name)
);