# Use official Node image
FROM node:20-slim

# Set work directory
WORKDIR /app

# Install dependencies first (to leverage Docker build cache)
COPY package.json package-lock.json /app/
RUN npm ci

# Copy the rest of the application files
COPY . /app/

# Expose Vite dev server port
EXPOSE 5173

# Run Vite dev server bound to all interfaces
CMD ["npm", "run", "dev", "--", "--host"]
