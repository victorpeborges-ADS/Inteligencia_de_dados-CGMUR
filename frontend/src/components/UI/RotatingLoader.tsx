'use client';

import { useEffect, useState } from 'react';
import { Loader2 } from 'lucide-react';

type RotatingLoaderProps = {
  messages: string[];
  intervalMs?: number;
  className?: string;
  showSpinner?: boolean;
};

export function useRotatingMessage(messages: string[], intervalMs = 3000): string {
  const [index, setIndex] = useState(0);
  useEffect(() => {
    if (messages.length <= 1) return;
    const timer = setInterval(() => {
      setIndex((i) => (i + 1) % messages.length);
    }, intervalMs);
    return () => clearInterval(timer);
  }, [messages, intervalMs]);
  return messages[index] ?? messages[0] ?? '';
}

export default function RotatingLoader({
  messages,
  intervalMs = 3000,
  className = '',
  showSpinner = true,
}: RotatingLoaderProps) {
  const message = useRotatingMessage(messages, intervalMs);
  return (
    <div className={`flex items-center gap-2 text-xs ${className}`}>
      {showSpinner && <Loader2 className="h-3.5 w-3.5 shrink-0 animate-spin" />}
      <span>{message}</span>
    </div>
  );
}

export const PDF_DIAGNOSTIC_MESSAGES = [
  '🔄 Gerando diagnóstico… Coletando dados CEMADEN…',
  '🔄 Calculando Score Sinidu+Clima…',
  '🔄 Consolidando ranking territorial…',
  '🔄 Montando narrativa executiva…',
  '🔄 Renderizando PDF…',
];

export const SIMULATION_MESSAGES = (mm: number) => [
  `🌧 Simulando ${mm}mm… Calculando manchas…`,
  '🌧 Modelando escoamento superficial…',
  '🌧 Cruzando DEM e malha de bairros…',
  '🌧 Preparando camadas no mapa…',
];

export const INTERPRETATION_MESSAGES = [
  '🤖 Analisando resultado da simulação…',
  '🤖 Identificando áreas críticas…',
  '🤖 Gerando recomendações operacionais…',
];

export const PRESENTATION_MESSAGES = [
  'Preparando apresentação…',
  'Carregando mapa e score territorial…',
  'Montando slides executivos…',
];

export const MUNICIPIO_LOAD_STEPS = [
  'Verificando cadastro IBGE…',
  'Integrando malha territorial…',
  'Sincronizando dados oficiais…',
  'Finalizando configuração…',
];
