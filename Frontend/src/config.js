// Detect if we are in development mode
const isDev = import.meta.env.DEV;

// Use the environment variable VITE_API_BASE_URL if set,
// otherwise use the deployed Flask backend.
const base =
  import.meta.env.VITE_API_BASE_URL ||
  'https://p-id-analyzer.onrender.com';

export const API_BASE_URL = base.endsWith('/')
  ? base.slice(0, -1)
  : base;