create-db:
	@echo "Creating database..."
	@docker pull postgres
	@docker run --name warnet-api-server-db -e POSTGRES_PASSWORD=postgres -p 5432:5432 -d postgres

start:
	@echo "Starting API..."
	@chmod +x ./start_api.sh
	@./start_api.sh