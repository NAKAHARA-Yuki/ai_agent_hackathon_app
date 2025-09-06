# AI Agent Hackathon Travel App

AI-powered travel planning application with Vue.js frontend, Flask backend, Google ADK agent service, and Maps Code Assist MCP server. Deployed via Docker + Cloud Run with Google Maps and Gemini AI integration.

**Always reference these instructions first and fallback to search or bash commands only when you encounter unexpected information that does not match the info here.**

## Working Effectively

**CRITICAL - NEVER CANCEL builds or long-running commands. Always use appropriate timeouts.**

### Bootstrap, Build, and Test the Repository

**Client (Vue.js + Vite):**
```bash
cd client
npm install                    # Takes ~8 seconds
npm run build                  # Takes ~3 seconds  
npm run dev                    # Starts dev server in ~300ms
```
- TIMEOUT: Use 60+ seconds for npm install, 30+ seconds for build
- NEVER CANCEL: All npm operations complete within reasonable time

**Server (Flask + Python):**
```bash
cd server
pip install -r requirements.txt  # Takes ~25 seconds, expect SSL warnings
```
- TIMEOUT: Use 120+ seconds for pip install due to large dependency tree
- NEVER CANCEL: Dependencies include Google Cloud libraries which are large
- **Expected warnings**: SSL cert warnings and deprecation notices are normal

**Agent (Google ADK):**
```bash
cd agent  
pip install -r requirements.txt  # May fail due to firewall/network limitations
```
- **Known Issue**: Agent dependencies often fail to install due to network restrictions
- Document failures as expected in sandboxed environments
- Works in real Google Cloud environments with proper networking

**MCP (Maps Code Assist):**
```bash
npx -y @googlemaps/code-assist-mcp --port 3000  # Installs and runs MCP server
```
- TIMEOUT: Use 60+ seconds for first run (downloads packages)

### Development Mode Validation

**Start Backend Server:**
```bash
cd server
FLASK_ENV=development JWT_SECRET=dev-secret-change-me python3 app.py
```
- Server starts on http://localhost:8080
- Creates dummy user 'devuser' with password 'password'  
- Uses DevDB (in-memory) when Firestore is unavailable
- Takes ~15 seconds to initialize with DB setup

**Start Frontend:**
```bash
cd client
npm run dev  # Starts on http://localhost:5173/
```
- Proxies API calls to localhost:8080 (configured in vite.config.js)
- Starts immediately (~300ms)

**Health Check Validation:**
```bash
curl http://localhost:8080/api/health
```
Expected response: `{"status": "ok", "env": "development", "db": "devdb", ...}`

### Docker Build (Production)

**Main Application:**
```bash
docker build -t travel-app .  # Takes 5-15 minutes. NEVER CANCEL.
```
- TIMEOUT: Use 900+ seconds (15+ minutes) for complete build
- **Known Issues**: May fail in sandboxed environments due to SSL certificate restrictions
- Works in production environments with proper Docker registry access

**Individual Component Builds:**
```bash
cd agent && docker build -t agent-service .     # For ADK agent
cd mcp && docker build -t mcp-service .         # For MCP server  
```

**Docker Compose (Development):**
```bash
# Requires server/.env file with proper API keys
docker compose -f docker-compose.dev.yml up
```
- **Prerequisite**: Create `server/.env` with required environment variables
- **Known Issue**: Fails without proper .env configuration

## Validation Scenarios

**ALWAYS manually validate changes via these complete end-to-end scenarios:**

### Development Workflow Validation
1. **Build Validation**: Run client build and verify `dist/` folder is created
2. **Server Health**: Start server and verify `/api/health` returns 200 OK
3. **Frontend Connection**: Start both client dev server and backend, verify proxy works
4. **API Endpoints**: Test key endpoints like `/api/questions`, `/api/hobbies`

### Production Deployment Validation  
1. **Docker Build**: Complete multi-stage build succeeds
2. **Container Start**: Built image starts without errors
3. **Health Endpoint**: Container responds to health checks
4. **Static Assets**: SPA fallback serves frontend correctly

### User Journey Validation
1. **Registration/Login**: Create account, verify JWT token generation
2. **Travel Quiz**: Complete personality assessment  
3. **AI Planning**: Generate travel plans (requires API keys)
4. **Map Integration**: Verify Google Maps functionality (requires Maps API key)

## Environment Requirements

### Required Environment Variables (Production)
```bash
# Core API Keys
GEMINI_API_KEY=your_gemini_api_key           # Required for AI features
GOOGLE_MAPS_API_KEY=your_maps_api_key        # Required for Maps integration
JWT_SECRET=your_jwt_secret                   # Required for authentication

# Google Cloud (Production)
GCP_PROJECT_ID=your_project_id               # For Firestore
GOOGLE_CLOUD_PROJECT=your_project_id         # Alternative name

# Client Environment (Vite)
VITE_GOOGLE_MAPS_API_KEY=your_public_api_key # Public Maps API key
VITE_GOOGLE_MAPS_MAP_ID=your_map_id          # Optional for Advanced Markers
VITE_ENABLE_ADVANCED_MARKER=true             # Optional advanced features

# Agent Service
AGENT_BASE_URL=http://localhost:8080         # ADK agent endpoint
MAPS_MCP_ENDPOINT_URL=http://mcp:3000/tools/retrieve-google-maps-platform-docs
```

### Development Fallbacks
- **No API Keys**: Server uses dummy data, warns in logs
- **No Firestore**: DevDB (in-memory) is used automatically  
- **No Agent**: Falls back to direct Gemini API calls
- **Development Mode**: Bypasses auth requirements for faster iteration

## Key Components and Structure

### Frontend (`client/`)
- **Framework**: Vue.js 3.4.21 + Vite 5.2.8
- **Key Dependencies**: chart.js, vue-router, pinia
- **Build Output**: `dist/` (served by Flask in production)
- **Dev Server**: http://localhost:5173 with API proxy

### Backend (`server/`)  
- **Framework**: Flask 3.0.3 + Gunicorn
- **Database**: Google Cloud Firestore (prod) / DevDB (dev)
- **APIs**: Travel planning, user auth, Google Maps integration
- **Key Features**: JWT auth, AI analysis, travel plan generation

### Agent Service (`agent/`)
- **Framework**: Google ADK (Agent Development Kit)
- **Purpose**: Intelligent travel planning with Gemini AI
- **Dependencies**: httpx, google-adk (may fail in restricted environments)
- **Endpoint**: `/v1/plan` for travel plan generation

### MCP Server (`mcp/`)
- **Purpose**: Google Maps Platform Code Assist server
- **Runtime**: Node.js with @googlemaps/code-assist-mcp
- **Endpoint**: `/tools/retrieve-google-maps-platform-docs`

### Deployment (`Dockerfile` + Cloud Run)
- **Multi-stage**: Node.js build → Python runtime
- **Process**: Frontend build → Copy to Flask static → Run gunicorn
- **Ports**: 8080 (configurable via PORT env var)

## Common Tasks and Troubleshooting

### Build Issues
- **npm install warnings**: Normal, proceed if no errors
- **pip SSL warnings**: Expected in sandboxed environments  
- **Agent install fails**: Document as network limitation, works in cloud
- **Docker build fails**: SSL certificate issues in sandbox, works in production

### Runtime Issues
- **Server won't start**: Check JWT_SECRET in production mode
- **No AI responses**: Verify GEMINI_API_KEY is set
- **Maps not loading**: Check VITE_GOOGLE_MAPS_API_KEY
- **Auth failures**: Verify JWT_SECRET and user creation

### Testing Commands
```bash
# Quick validation of core functionality
cd server && python3 -c "
import app
with app.app.test_client() as client:
    print('Health:', client.get('/api/health').get_json())"

# Check client build artifacts
cd client && npm run build && ls -la dist/

# Verify server endpoints respond
curl -f http://localhost:8080/api/questions || echo "Server not running"
```

### Performance Notes
- **Client build**: ~10 seconds total (install + build)
- **Server startup**: ~15 seconds with database initialization  
- **Docker build**: 5-15 minutes depending on network and cache
- **MCP first run**: ~60 seconds for package download

## Additional Context

### Repository Structure
```
.
├── client/          # Vue.js frontend
├── server/          # Flask backend  
├── agent/           # Google ADK agent service
├── mcp/             # Maps Code Assist server
├── shared/          # Shared contracts/types
├── Dockerfile       # Multi-stage production build
└── docker-compose.dev.yml  # Development orchestration
```

### CI/CD Pipeline (`.github/workflows/deploy-cloud-run.yml`)
- **Triggers**: Push to main branch
- **Process**: Build agent+MCP → Deploy to Cloud Run → Build+deploy main app
- **Dependencies**: Google Cloud credentials, Artifact Registry

### Key URLs and Endpoints
- **Development Frontend**: http://localhost:5173  
- **Development Backend**: http://localhost:8080
- **Health Check**: `/api/health`
- **Authentication**: `/api/auth/login`, `/api/auth/signup`
- **Travel Planning**: `/api/agent/chat`, `/api/generate_plan`
- **Maps Integration**: `/api/maps-key`, `/api/geocode`

**Remember**: Always run builds to completion, use proper timeouts, and validate functionality through complete user scenarios. The application is designed to gracefully degrade when external services are unavailable.