# Rosetta Zero Dashboard - Local Deployment Guide

This guide will help you run the Rosetta Zero Dashboard locally without requiring AWS services.

## Prerequisites

- **Python 3.8+** - [Download](https://www.python.org/downloads/)
- **Node.js 18+** - [Download](https://nodejs.org/)
- **npm** (comes with Node.js)

## Quick Start

### Option 1: Automated Setup (Recommended)

#### On Linux/Mac:
```bash
chmod +x start-local.sh
./start-local.sh
```

#### On Windows (PowerShell):
```powershell
.\start-local.ps1
```

The script will:
1. Install backend dependencies (Flask)
2. Install frontend dependencies (React, etc.)
3. Start the backend server on port 5000
4. Start the frontend server on port 3000
5. Open your browser automatically

### Option 2: Manual Setup

#### Step 1: Start Backend Server

```bash
# Navigate to backend directory
cd backend-local

# Create virtual environment (first time only)
python -m venv venv

# Activate virtual environment
# On Linux/Mac:
source venv/bin/activate
# On Windows:
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Start server
python server.py
```

The backend will start on `http://localhost:5000`

#### Step 2: Start Frontend (in a new terminal)

```bash
# Navigate to frontend directory
cd frontend

# Install dependencies (first time only)
npm install

# Start development server
npm run dev
```

The frontend will start on `http://localhost:3000`

## Accessing the Dashboard

1. Open your browser and go to: **http://localhost:3000**
2. You'll see the dashboard immediately (no login required in local mode)
3. The dashboard is pre-populated with mock data

## Features Available Locally

### ✅ Fully Functional

- **Dashboard Overview**: View system statistics and metrics
- **Artifact Management**: 
  - View list of artifacts
  - Upload new artifacts (simulated)
  - View artifact details
- **Workflow Monitoring**: View workflow progress through 5 phases
- **System Health**: View mock system health metrics
- **Real-time Updates**: Dashboard refreshes automatically

### 🔄 Mock Data

The local server provides realistic mock data:
- 5 sample artifacts (COBOL, FORTRAN, BINARY)
- 5 sample workflows in various stages
- 3 sample certificates
- System health metrics
- Test results

### 📝 Simulated Operations

- **File Upload**: Accepts files but stores them in memory
- **Workflow Creation**: Creates mock workflows
- **Certificate Generation**: Returns mock certificates

## Project Structure

```
rosetta-zero/
├── backend-local/          # Local development backend
│   ├── server.py          # Flask API server
│   ├── requirements.txt   # Python dependencies
│   └── venv/              # Python virtual environment
├── frontend/              # React frontend
│   ├── src/              # Source code
│   ├── .env.local        # Local environment config
│   └── package.json      # Node dependencies
├── start-local.sh        # Linux/Mac startup script
├── start-local.ps1       # Windows startup script
└── LOCAL_DEPLOYMENT.md   # This file
```

## API Endpoints

The local backend provides these endpoints:

### Dashboard
- `GET /api/dashboard/stats` - Dashboard statistics

### Artifacts
- `GET /api/artifacts` - List artifacts
- `GET /api/artifacts/{id}` - Get artifact details
- `POST /api/artifacts/upload` - Upload artifact
- `GET /api/artifacts/{id}/download` - Download artifact

### Workflows
- `GET /api/workflows` - List workflows
- `GET /api/workflows/{id}` - Get workflow details
- `GET /api/workflows/search?q={query}` - Search workflows
- `GET /api/workflows/{id}/tests` - Get test results
- `GET /api/workflows/{id}/tests/summary` - Get test summary

### Certificates
- `GET /api/certificates` - List certificates
- `GET /api/certificates/{id}` - Get certificate details
- `POST /api/certificates/{id}/verify` - Verify signature

### System
- `GET /api/system/health` - System health metrics
- `GET /api/system/notifications` - Error notifications

### Compliance
- `GET /api/compliance/reports` - List reports
- `POST /api/compliance/reports` - Generate report

## Configuration

### Backend Configuration

Edit `backend-local/server.py` to customize:
- Port number (default: 5000)
- Mock data
- API responses

### Frontend Configuration

Edit `frontend/.env.local`:
```env
VITE_API_URL=http://localhost:5000/api
VITE_USE_MOCK_AUTH=true
```

## Troubleshooting

### Backend Issues

**Problem**: `ModuleNotFoundError: No module named 'flask'`

**Solution**:
```bash
cd backend-local
source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install -r requirements.txt
```

**Problem**: `Address already in use` (port 5000)

**Solution**: Kill the process using port 5000 or change the port in `server.py`:
```python
app.run(host='0.0.0.0', port=5001, debug=True)  # Change to 5001
```

### Frontend Issues

**Problem**: `Cannot find module` errors

**Solution**:
```bash
cd frontend
rm -rf node_modules package-lock.json
npm install
```

**Problem**: `EADDRINUSE: address already in use :::3000`

**Solution**: Kill the process using port 3000 or change the port in `vite.config.ts`:
```typescript
server: {
  port: 3001,  // Change to 3001
}
```

**Problem**: API calls fail with CORS errors

**Solution**: Make sure the backend is running and CORS is enabled (it should be by default)

### General Issues

**Problem**: Changes not reflecting

**Solution**: 
- Backend: Restart the Python server (Ctrl+C, then `python server.py`)
- Frontend: Vite should auto-reload, but you can restart with Ctrl+C and `npm run dev`

**Problem**: Blank page in browser

**Solution**:
1. Check browser console for errors (F12)
2. Verify both backend and frontend are running
3. Check that `.env.local` exists in frontend directory

## Development Tips

### Hot Reload

- **Frontend**: Vite automatically reloads when you save files
- **Backend**: Flask debug mode reloads on file changes

### Adding Mock Data

Edit `backend-local/server.py` and modify the `init_mock_data()` function:

```python
def init_mock_data():
    # Add your custom mock data here
    artifacts["my-artifact"] = {
        "artifactId": "my-artifact",
        "name": "my-program.cob",
        # ... more fields
    }
```

### Testing API Endpoints

Use curl or Postman to test endpoints:

```bash
# Get dashboard stats
curl http://localhost:5000/api/dashboard/stats

# Get artifacts
curl http://localhost:5000/api/artifacts

# Upload artifact
curl -X POST -F "file=@test.cob" http://localhost:5000/api/artifacts/upload
```

### Viewing Logs

- **Backend**: Logs appear in the terminal where you ran `python server.py`
- **Frontend**: Check browser console (F12 → Console tab)

## Stopping the Servers

### If using automated scripts:
Press `Ctrl+C` in the terminal

### If running manually:
Press `Ctrl+C` in each terminal window (backend and frontend)

## Next Steps

### Transitioning to AWS

When ready to deploy to AWS:

1. Follow `DASHBOARD_DEPLOYMENT.md` for AWS deployment
2. Update `frontend/.env` with real AWS credentials
3. Deploy using CDK: `cdk deploy DashboardStack`
4. Remove `.env.local` to use production config

### Adding Features

1. **New Pages**: Add components in `frontend/src/pages/`
2. **New API Endpoints**: Add routes in `backend-local/server.py`
3. **New Components**: Add reusable components in `frontend/src/components/`

### Testing

```bash
# Frontend type checking
cd frontend
npm run type-check

# Frontend linting
npm run lint

# Build for production
npm run build
```

## Support

For issues:
1. Check this troubleshooting section
2. Review browser console for errors
3. Check terminal output for backend errors
4. Verify all prerequisites are installed

## Summary

You now have a fully functional local development environment for the Rosetta Zero Dashboard:

- ✅ No AWS account required
- ✅ No authentication setup needed
- ✅ Mock data pre-populated
- ✅ Hot reload for development
- ✅ Full API functionality
- ✅ Realistic UI/UX

Happy developing! 🚀
