/** @type {import('next').NextConfig} */
const config={transpilePackages:['@golden-motion/isi','@golden-motion/rf','@golden-motion/relay'], poweredByHeader:false, experimental:{cpus:2}, webpack:(config)=>{config.resolve.alias['@mediapipe/tasks-vision']=new URL('../../node_modules/@mediapipe/tasks-vision/vision_bundle.mjs',import.meta.url).pathname;return config;}};
export default config;
