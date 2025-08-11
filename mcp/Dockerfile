# syntax=docker/dockerfile:1
FROM node:20-slim

ENV PORT=3000
WORKDIR /app

# Install the MCP server globally (alpha toolkit)
RUN npm install -g @googlemaps/code-assist-mcp@latest

EXPOSE 3000
CMD ["npx", "-y", "@googlemaps/code-assist-mcp", "--port", "3000"]
