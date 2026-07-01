/** @type {import('next').Config} */
const nextConfig = {
  output: 'standalone',
  // Allow connecting to any backend endpoint
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/:path*`,
      },
    ];
  },
};

module.exports = nextConfig;
