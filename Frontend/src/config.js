// Detect if we are in development mode
const isDev = import.meta.env.DEV;

// Use the environment variable VITE_API_BASE_URL if set,
// otherwise default to localhost:5000 in dev and the current origin in production.
const base = import.meta.env.VITE_API_BASE_URL || 
  (isDev ? 'https://p-id-analyzer.onrender.com/' : window.location.origin);

export const API_BASE_URL = base.endsWith('/') ? base.slice(0, -1) : base;
