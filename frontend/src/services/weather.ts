import { http } from './http';

export interface Weather {
  city: string;
  available: boolean; // false = service météo injoignable
  temperatureC?: number;
  feelsLikeC?: number;
  windKmh?: number;
  rainPct?: number;
}

/** Météo du jour de la ville (même source que l'objectif 6). */
export const getWeather = (city: string) => http<Weather>(`/weather?city=${encodeURIComponent(city)}`);

// Ville choisie dans « Tenue du jour », partagée avec le bandeau du haut
const KEY = 'dressme_city';
export const loadCity = () => {
  try { return localStorage.getItem(KEY) || 'Tunis'; } catch { return 'Tunis'; }
};
export const saveCity = (city: string) => {
  try { localStorage.setItem(KEY, city); } catch { /* stockage indisponible */ }
  window.dispatchEvent(new CustomEvent('dressme-city', { detail: city }));
};
export const weatherLabel = (w?: Weather) =>
  !w ? '…' : !w.available ? 'météo indisponible' : `${w.temperatureC}°C · pluie ${w.rainPct} %`;
