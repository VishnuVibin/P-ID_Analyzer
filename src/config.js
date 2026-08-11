// Detect if we are in development mode
const isDev = import.meta.env.DEV;

// Use the environment variable VITE_API_BASE_URL if set,
// otherwise default to localhost:5000 in dev and the current origin in production.
export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 
  (isDev ? 'http://localhost:5000' : window.location.origin);
