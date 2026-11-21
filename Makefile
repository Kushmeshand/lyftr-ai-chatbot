.PHONY: up down build test logs clean

# Starts both backend (8000) and frontend (3000) with docker-compose
up:
	docker compose up --build -d

# Stops running containers
down:
	docker compose down

# Rebuilds Docker containers
build:
	docker compose build

# Runs backend tests
test:
	cd backend && pytest -v

# Tails container logs
logs:
	docker compose logs -f

# Cleans up volumes and temporary files
clean:
	docker compose down -v
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
