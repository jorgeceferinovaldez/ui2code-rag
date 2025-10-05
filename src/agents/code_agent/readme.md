# Code Agent

## Docker commands
```bash
docker build -t code-agent .
docker run --env-file .env -p 10001:10001 code-agent
```