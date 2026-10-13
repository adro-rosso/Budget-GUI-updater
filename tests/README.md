# Tests

Smoke tests drive the real Tkinter app against a temporary data file (never `budget_data.json`).

- `python tests/run_all.py` runs every `smoke_test*.py` plus the engine checks (about 15 minutes).
- `python tests/audit_overflow.py 1366 768` opens every page and overlay and reports clipped or overlapping widgets. Target: only the Bills/Funds Treeview column notes.
- `python tests/shoot.py <out_dir>` screenshots every page with sample data (needs an unlocked desktop; Pillow).
- `python tests/raster.py gerald` rasterises canvas drawings through PIL when ImageGrab is black.

Tests stub Task Scheduler, the browser and Windows toasts. The window grabs focus while they run.

Tests 9, 10 and 22 need keyboard focus and the real pointer (Enter-to-save, wheel routing). Run them on their own, not alongside the audit or another app window.
