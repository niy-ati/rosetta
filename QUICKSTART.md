# 🚀 Rosetta Zero Dashboard - Quick Start

Get the dashboard running locally in 2 minutes!

## Prerequisites

✅ Python 3.8+ installed  
✅ Node.js 18+ installed

## Start the Dashboard

### Windows (PowerShell):
```powershell
.\start-local.ps1
```

### Linux/Mac:
```bash
chmod +x start-local.sh
./start-local.sh
```

## Access the Dashboard

Open your browser to: **http://localhost:3000**

That's it! The dashboard is now running with mock data.

## What You'll See

- 📊 Dashboard with system statistics
- 📁 5 sample artifacts (COBOL, FORTRAN, BINARY)
- 🔄 5 workflows in various stages
- 🏆 3 sample certificates
- 📈 System health metrics

## Features to Try

1. **Upload an Artifact**: Click "Upload Artifact" button
2. **View Workflows**: Navigate to "Workflows" in sidebar
3. **Check System Health**: Go to "System Health"
4. **View Certificates**: Browse "Certificates" section

## Stop the Servers

Press `Ctrl+C` in the terminal

## Need Help?

See `LOCAL_DEPLOYMENT.md` for detailed instructions and troubleshooting.

## What's Running?

- **Backend API**: http://localhost:5000 (Flask server with mock data)
- **Frontend**: http://localhost:3000 (React app)

No AWS account or authentication required for local development!

---

**Next Steps**: When ready for production, see `DASHBOARD_DEPLOYMENT.md` for AWS deployment.
