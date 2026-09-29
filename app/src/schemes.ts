/** The single handler for non-web schemes. Today it only explains. */
export function explainScheme(scheme: string, url: string): string {
  switch (scheme) {
    case 'intent':
    case 'market':
      return `This page tried to hand off to an Android app (${scheme}:). The Surface doesn't open apps yet.`;
    case 'mailto':
    case 'tel':
    case 'sms':
      return `${scheme}: links aren't supported in the Surface yet.`;
    case 'seurl':
      return url.toLowerCase().startsWith('seurl://golden')
        ? 'A page tried to drive the Surface through a seurl://golden address. Only the address bar and the relay can.'
        : `Only seurl://golden addresses resolve in the Surface.`;
    default:
      return `"${scheme || '?'}:" isn't a supported scheme yet — only http and https open here.`;
  }
}
