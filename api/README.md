# Warnet API

To start the server run:

1. Run the docker daemon

```bash
docker-compose -f api-compose.yml up -d
```

2. We use Postgresql as a data store. You can access it locally by using this connection string.

```bash
postgresql://warnet:password@db:5432/warnet
```

The server should be running on `localhost:8080`.
To see all rest endpoints, check the API documentation at `localhost:8080/docs`
