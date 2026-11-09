/// <reference types="vitest/config" />
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: { port: 5173, strictPort: true },
  test: {
    env: { VITE_USE_MOCKS: 'true' },
    globals: true,
    environment: 'jsdom',
    setupFiles: ['./src/setupTests.ts'], // @testing-library/jest-dom
  },
})
