const http = require('http');
const { spawn } = require('child_process');

const path = require('path');

const PORT = 8090;
const TARGET_PORT = 8087;
const BASE_PATH = '/izatabi';

// 1. Next.js サーバーを子プロセスとして起動
console.log(`Starting Next.js production server on port ${TARGET_PORT}...`);
const nextBin = path.join(__dirname, 'client', 'node_modules', '.bin', 'next');
const nextProcess = spawn(nextBin, ['start', path.join(__dirname, 'client'), '-p', TARGET_PORT], {
  stdio: 'inherit',
  shell: true
});

nextProcess.on('error', (err) => {
  console.error('Failed to start Next.js process:', err);
});

nextProcess.on('exit', (code) => {
  console.log(`Next.js process exited with code ${code}`);
  process.exit(code || 0);
});

// 2. プレフィックス再付与プロキシサーバーの起動
const server = http.createServer((req, res) => {
  let targetPath = req.url;
  if (!req.url.startsWith(BASE_PATH)) {
    if (req.url === '/') {
      targetPath = BASE_PATH;
    } else {
      targetPath = BASE_PATH + req.url;
    }
  }
  
  const options = {
    hostname: '127.0.0.1',
    port: TARGET_PORT,
    path: targetPath,
    method: req.method,
    headers: req.headers
  };

  const connector = http.request(options, (targetRes) => {
    res.writeHead(targetRes.statusCode, targetRes.headers);
    targetRes.pipe(res);
  });

  // リクエストのパイプ処理
  req.pipe(connector);

  connector.on('error', (err) => {
    console.error(`Proxy request error (URL: ${req.url}):`, err.message);
    // Next.js起動直後などで一時的に繋がらない場合は502を返す
    res.writeHead(502, { 'Content-Type': 'text/plain; charset=utf-8' });
    res.end('Next.js サーバーの起動をお待ちください。 (502 Bad Gateway)');
  });
});

server.listen(PORT, '127.0.0.1', () => {
  console.log(`Izatabi Proxy listening on port ${PORT} -> forwarding to ${TARGET_PORT}${BASE_PATH}`);
});

// プロセス終了シグナル受信時に子プロセスも確実に終了させる
const cleanExit = () => {
  console.log('Stopping Next.js server...');
  nextProcess.kill('SIGTERM');
  process.exit(0);
};

process.on('SIGTERM', cleanExit);
process.on('SIGINT', cleanExit);
