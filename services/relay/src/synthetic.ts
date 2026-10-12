import { runSyntheticPublisher } from './synthetic-publisher';

async function main() {
  const token = process.env.GM_RELAY_TOKEN;
  if (!token) throw new Error('Set GM_RELAY_TOKEN to the current local pairing token');
  const port = Number(process.env.GM_RELAY_PORT ?? 8787);
  const count = Number(process.env.GM_DEMO_COUNT ?? 60);
  const modality = process.env.GM_DEMO_MODALITY === 'wifi-csi' ? 'wifi-csi' : 'native';
  const result = await runSyntheticPublisher({ url: `ws://127.0.0.1:${port}`, token, count, modality });
  console.log(`Published ${result.published} synthetic ${modality}-shaped ISI events. Physical acquisition: false.`);
}

main().catch((error: unknown) => {
  console.error(error instanceof Error ? error.message : 'Synthetic publisher failed');
  process.exitCode = 1;
});
