# College Mode Documentation

**Status**: `IMPLEMENTED`  
**Configuration File**: `config/college_schedule.json`  

---

## Overview
College Mode is a modular, completely configurable academic assistant integrated directly into JARVIS.
It does not hardcode personal timetables or assignments into Python code; all schedules, courses, assignments, and exams are loaded from `config/college_schedule.json`.

---

## Features

### 1. Timetable & Schedule Lookup
- **Commands**: `"JARVIS, enable college mode"`, `"What is my schedule for today?"`, `"What classes do I have on Monday?"`
- **Output**: Returns course name, time slot, and room location for specified day.

### 2. Assignment Deadline Tracker
- **Commands**: `"What assignments are due?"`, `"Check my deadlines"`, `"Add assignment Data Structures due 2026-08-20 for CS101"`
- **Output**: Lists pending assignments sorted by due date or confirms new assignment registration.

### 3. Lecture Note Summarization
- **Commands**: `"Summarize these notes: ..."`
- **Output**: Uses Gemini AI to condense raw lecture text / PDF content into key bullet points and core concepts.

### 4. Flashcard Generator
- **Commands**: `"Generate flashcards for Linear Algebra"`
- **Output**: Produces 5 study Q&A flashcards for exam preparation.

---

## Configuration Schema (`config/college_schedule.json`)

```json
{
    "college_mode_enabled": true,
    "university_name": "University",
    "semester": "Fall Semester",
    "courses": [
        {
            "code": "CS101",
            "name": "Computer Science Principles",
            "instructor": "Dr. Smith",
            "credits": 4
        }
    ],
    "timetable": {
        "Monday": [
            {"time": "09:00 - 10:30", "course": "CS101", "room": "Hall A"}
        ]
    },
    "assignments": [
        {
            "id": "ASG-1",
            "course": "CS101",
            "title": "Data Structures Assignment",
            "due_date": "2026-08-20",
            "status": "Pending"
        }
    ]
}
```
