// Default runtime environment config — overwritten at container startup by
// docker-entrypoint.sh. In developer mode (npm run dev), AnnouncementBanner
// falls back to import.meta.env.VITE_BANNER_* so this file is a no-op.
window.__ENV__ = {};
