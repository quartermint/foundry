.PHONY: dev dev-backend dev-frontend build deploy logs setup clean deploy-blender blender-logs blender-status

# Development
dev:
	@echo "Starting Foundry development servers..."
	@make dev-backend & make dev-frontend & wait

dev-backend:
	cd backend && .venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8787 --reload

dev-frontend:
	cd frontend && npm run dev -- --port 5175 --host 0.0.0.0

# Setup
setup: setup-backend setup-frontend
	@echo "Foundry setup complete."

setup-backend:
	cd backend && python3.12 -m venv .venv && .venv/bin/pip install -r requirements.txt
	@echo "Backend ready. Copy .env.example to .env and configure."

setup-frontend:
	cd frontend && npm install

# Build
build:
	cd frontend && npm run build
	@echo "Frontend built to frontend/dist/"
	@echo "FastAPI will serve it as static files on :8787"

# Deploy (macOS launchd)
deploy: build
	@mkdir -p ~/Library/LaunchAgents
	cp com.foundry.plist ~/Library/LaunchAgents/com.foundry.plist
	launchctl unload ~/Library/LaunchAgents/com.foundry.plist 2>/dev/null || true
	launchctl load ~/Library/LaunchAgents/com.foundry.plist
	@echo "Foundry deployed and running on :8787"

# BlenderMCP (headless Blender with poly-mcp addon)
deploy-blender:
	@mkdir -p ~/Library/LaunchAgents logs
	cp com.blender-mcp.plist ~/Library/LaunchAgents/com.blender-mcp.plist
	launchctl unload ~/Library/LaunchAgents/com.blender-mcp.plist 2>/dev/null || true
	launchctl load ~/Library/LaunchAgents/com.blender-mcp.plist
	@echo "BlenderMCP deployed — check with: make blender-status"

blender-logs:
	tail -f logs/blender-mcp.stdout.log logs/blender-mcp.stderr.log

blender-status:
	@curl -s http://localhost:8000/mcp/list_tools | python3 -m json.tool 2>/dev/null && echo "BlenderMCP: UP" || echo "BlenderMCP: DOWN"

# Logs
logs:
	tail -f logs/stdout.log logs/stderr.log

# Clean
clean:
	rm -rf backend/.venv frontend/node_modules frontend/dist
