/** Modo institucional — oculta rótulos de uso interno (demo MCID / homologação). */
export function isInstitutionalMode(): boolean {
  return process.env.NEXT_PUBLIC_INSTITUTIONAL_MODE === 'true';
}

export const PRESENTATION_DISCLAIMER = {
  internal:
    'Este diagnóstico é para uso interno. Não substitui estudos técnicos oficiais.',
  institutional:
    'Diagnóstico territorial Sinidu+Clima — MCID/CGMUR. Não substitui estudos técnicos oficiais nem pareceres de mérito.',
} as const;

export function presentationDisclaimer(): string {
  return isInstitutionalMode()
    ? PRESENTATION_DISCLAIMER.institutional
    : PRESENTATION_DISCLAIMER.internal;
}
