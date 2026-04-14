# TrackCrack - Local Complaint Tracking System

TrackCrack is a localhost web app for train track crack complaint tracking.
It supports login, image upload, YOLO-based severity detection, complaint status management, and completion history.

## Features

- Username/password login (default account included)
- Role-based access (`admin`, `supervisor`, `inspector`)
- Upload crack image and auto-run YOLO model
- Bounding-box output image saved with timestamp filename
- Automatic severity classification (`LOW`, `MEDIUM`, `HIGH`)
- Complaint lifecycle tracking (`OPEN` -> `COMPLETED`)
- Completion audit details (completed date/time and completed by user)
- Location and description fields per complaint
- Search, status/severity/date filters on dashboard
- Severity chart widget
- High-severity alert log entries (email + WhatsApp placeholders)
- Completed-history page with CSV/PDF export
- Admin user-management page for role assignment

## Default Login

- Username: `admin`
- Password: `admin123`
- Username: `supervisor` / Password: `super123`
- Username: `inspector` / Password: `inspect123`

## Project Structure

```text
crack_system/
|-- app.py
|-- database.db
|-- requirements.txt
|-- README.md
|-- model/
|   `-- best.pt
|-- static/
|   |-- styles.css
|   |-- uploads/
|   `-- outputs/
|-- templates/
|   |-- login.html
|   `-- dashboard.html
`-- utils/
    |-- db.py
    |-- detector.py
    `-- notifier.py
```

## How to Run (Windows / PowerShell)

1. Create and activate virtual environment:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

2. Install dependencies:

```powershell
pip install -r requirements.txt
```

3. Run app:

```powershell
python app.py
```

4. Open browser:

- [http://127.0.0.1:5000](http://127.0.0.1:5000)

## Raspberry Pi Auto-Capture Flow (IR + Webcam + GPS)

The app now supports direct ingestion from Raspberry Pi via:

- `POST /api/pi-capture`
- Header: `X-API-Token: <your token>`
- Form-data fields:
  - `image` (required)
  - `ir_triggered` (`true/false`)
  - `latitude` (optional)
  - `longitude` (optional)
  - `location` (optional fallback text)
  - `description` (optional)

If location is saved as `lat,lon`, dashboard/history show it as a clickable Google Maps link.

### Server env vars

Set these before running `app.py`:

```powershell
$env:PI_API_TOKEN="set-a-strong-token"
$env:FRONTEND_ORIGIN="https://<your-github-username>.github.io"
python app.py
```

### Raspberry Pi script

Use `pi_sensor_uploader.py` on the Pi. It:

1. Watches IR sensor GPIO pin
2. Captures webcam frame only when IR is true
3. Reads NEO-6M coordinates from serial
4. Uploads image + GPS to `/api/pi-capture`

Example on Raspberry Pi:

```bash
export TRACKCRACK_API_URL="http://<server-ip>:5000/api/pi-capture"
export TRACKCRACK_API_TOKEN="set-a-strong-token"
export IR_GPIO_PIN="17"
export GPS_SERIAL_PORT="/dev/ttyAMA0"
python3 pi_sensor_uploader.py
```

## Workflow

1. Login.
2. Upload train track crack image.
3. System stores timestamped image and analyzed output.
4. Severity appears on the complaint card and image.
5. Open complaint in modal and click **Mark Completed** after repair.
6. Completion history is stored and displayed.

## Extra Pages

- `GET /history`: completed complaints history
- `GET /history/export/csv`: export history as CSV
- `GET /history/export/pdf`: export history as PDF
- `GET/POST /users`: admin user management

## Roles

- `admin`: full access (upload + close complaints)
- `supervisor`: upload + close complaints
- `inspector`: upload only

## Notes

- Ensure YOLO model exists at `model/best.pt`.
- Uploaded raw images are saved in `static/uploads/`.
- Processed images are saved in `static/outputs/`.
- GitHub Pages can host static frontend only, not Flask/YOLO runtime.

## Hosting UI on GitHub Pages

Your current Flask app cannot run directly on GitHub Pages. Use this architecture:

- GitHub Pages: static UI/landing page
- Flask app (this project): API + YOLO running on Raspberry Pi/server

### Quick deploy steps

1. Push this project to GitHub.
2. In repo **Settings -> Pages**:
   - Source: `Deploy from a branch`
   - Branch: `main`
   - Folder: `/docs` (recommended) or `/root`
3. Create `docs/index.html` as your public frontend page.
4. In that page, call your backend API URL (e.g. `http://<server-ip>:5000/api/pi-capture` or your domain).
5. Keep CORS aligned:
   - `FRONTEND_ORIGIN=https://<username>.github.io`

If you want, I can also generate a ready-to-use `docs/index.html` in this project next.
