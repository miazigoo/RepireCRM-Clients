const target = process.env.API_TARGET || 'http://127.0.0.1:8040';

module.exports = {
  '/api': {
    target,
    secure: false,
    changeOrigin: true,
    logLevel: 'debug'
  }
};
