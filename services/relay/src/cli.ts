import { randomBytes } from 'node:crypto';
import { startRelay } from './server';

async function main() {
  const supplied = process.env.GM_RELAY_TOKEN;
  const token = supplied || randomBytes(32).toString('base64url');
  const port = Number(process.env.GM_RELAY_PORT ?? 8787);
  if (!Number.isSafeInteger(port) || port < 1 || port > 65535) throw new Error('GM_RELAY_PORT must be 1–65535');
  const relay = await startRelay({ token, port });
  console.log(`GOLDEN MOTION relay listening at ${relay.address}; protocol v1; local pairing required.`);
  if (!supplied) console.log(`Ephemeral local pairing token (this session only): ${token}`);
  let stopping = false;
  const stop = async () => {
    if (stopping) return;
    stopping = true;
    await relay.close();
  };
  process.once('SIGINT', stop);
  process.once('SIGTERM', stop);
}

main().catch(() => {
  console.error('Relay startup failed. Check the local port and pairing-token configuration.');
  process.exitCode = 1;
});
