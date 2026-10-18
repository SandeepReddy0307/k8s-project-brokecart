import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    strictPort: true,
    proxy: {
      '/api/identity': { target: process.env.IDENTITY_URL || 'http://127.0.0.1:8083' },
      '/api/cart': { target: process.env.CART_URL || 'http://127.0.0.1:8084' },
      '/api/checkout': { target: process.env.CHECKOUT_URL || 'http://127.0.0.1:8085' },
      '/api/orders': { target: process.env.ORDERS_URL || 'http://127.0.0.1:8086' },
      '/api/shipping': { target: process.env.SHIPPING_URL || 'http://127.0.0.1:8090' },
      '/api/returns': { target: process.env.RETURNS_URL || 'http://127.0.0.1:8091' },
      '/api/notifications': { target: process.env.NOTIFICATIONS_URL || 'http://127.0.0.1:8092' },
      '/api/search': { target: process.env.SEARCH_URL || 'http://127.0.0.1:8093' },
      '/api/operations/orders': { target: process.env.ORDERS_URL || 'http://127.0.0.1:8086' },
      '/api/operations/inventory': { target: process.env.INVENTORY_URL || 'http://127.0.0.1:8087' },
      '/api/operations/payments': { target: process.env.PAYMENTS_URL || 'http://127.0.0.1:8088' },
      '/api/operations/shipping': { target: process.env.SHIPPING_URL || 'http://127.0.0.1:8090' },
      '/api/operations/returns': { target: process.env.RETURNS_URL || 'http://127.0.0.1:8091' },
      '/api/operations/reports': { target: process.env.REPORTING_URL || 'http://127.0.0.1:8094' },
      '/api/catalog': { target: process.env.CATALOG_URL || 'http://127.0.0.1:8081' },
      '/api/pricing': { target: process.env.PRICING_URL || 'http://127.0.0.1:8082' }
    }
  }
});
