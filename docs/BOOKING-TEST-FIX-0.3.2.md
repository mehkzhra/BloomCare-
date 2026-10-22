# Booking-test setup fix v0.3.2

This patch replaces only backend/tests/test_appointments.py. It signs in both
independent clients before launching simultaneous booking requests. Password
verification and client startup no longer consume the synchronization deadline.
The actual booking race, [201, 409] response check, and exactly-one appointment
and event checks remain. The synchronization wait is still bounded (30 seconds).
No application code, model, configuration, account or migration is changed.

Stop both app servers. Extract into D:\Desktop\BloomCare, replacing the test file.
Start Docker Desktop, wait for the engine, then run in Command Prompt:

    cd /d D:\Desktop\BloomCare
    .\scripts\update-roles.cmd

The earlier installer stopped before upgrading the development database.
Let the entire installer finish; do not bypass the tests or manually skip steps.
Expected: Role and admin update passed. Restart the backend and frontend.

Verified here: all 38 appointment tests and Python lint passed on SQLite.
Live PostgreSQL and native Windows verification must run locally using the
installer. Your prior log reported 89/90 tests passed against PostgreSQL; its
only failure was BrokenBarrierError during concurrent test setup.
