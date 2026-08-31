/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "standalone",
  reactStrictMode: true,
  // Avoid double-compression on BFF /api/* proxy responses.
  compress: false,
  
  // Environment variables
  env: {
    // Browser uses same-origin BFF at /api/* — do not expose backend URL publicly.
    NEXT_PUBLIC_USE_BFF: process.env.NEXT_PUBLIC_USE_BFF || "true",
  },

  // Image optimization
  images: {
    domains: ['localhost'],
    formats: ['image/webp', 'image/avif'],
    unoptimized: false, // Keep optimization enabled
  },

  // Headers
  async headers() {
    const csp = [
      "default-src 'self'",
      "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://login.microsoftonline.com",
      "style-src 'self' 'unsafe-inline'",
      "img-src 'self' data: blob:",
      "font-src 'self' data:",
      "connect-src 'self' https://login.microsoftonline.com https://*.microsoftonline.com",
      "frame-src 'self' https://login.microsoftonline.com",
      "object-src 'none'",
      "base-uri 'self'",
      "form-action 'self'",
      "frame-ancestors 'none'",
    ].join("; ");
    return [
      {
        source: '/:path*',
        headers: [
          { key: 'X-Frame-Options', value: 'DENY' },
          { key: 'X-Content-Type-Options', value: 'nosniff' },
          { key: 'X-XSS-Protection', value: '1; mode=block' },
          { key: 'Referrer-Policy', value: 'strict-origin-when-cross-origin' },
          { key: 'Permissions-Policy', value: 'geolocation=(), microphone=(), camera=()' },
          { key: 'Strict-Transport-Security', value: 'max-age=31536000; includeSubDomains' },
          { key: 'Content-Security-Policy', value: csp },
        ],
      },
    ];
  },
};

module.exports = nextConfig;

