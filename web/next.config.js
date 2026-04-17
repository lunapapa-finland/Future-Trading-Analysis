/** @type {import('next').NextConfig} */
const backendPort = process.env.API_PORT || (process.env.NODE_ENV === "production" ? "5000" : "8050");
const backendOrigin = (process.env.BACKEND_ORIGIN || `http://localhost:${backendPort}`).replace(/\/+$/, "");

const nextConfig = {
  reactStrictMode: true,
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${backendOrigin}/api/:path*`
      }
    ];
  }
};

module.exports = nextConfig;
